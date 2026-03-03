import json
import re
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
import pandas as pd

from routers.auth_router import get_current_user
from models.devis_models import DevisRequest
from constants import GHI, MOIS, DAYS_IN_MONTH, EFFICIENCY, KWH_PRICE
from roi import roi_figure_buffer, roi_cumulative_buffer
from pdf_generator import generate_double_devis_pdf
import pdf_generator
from generate_devis_premium import generate_premium_pdf

router = APIRouter()

# Use absolute path from this file's location (routers/ → parent = project root)
BASE_DIR = Path(__file__).parent.parent
DEVIS_HISTORY_FILE = BASE_DIR / "devis_history.json"
CONFIG_FILE = BASE_DIR / "config.json"
DEVIS_DIR = BASE_DIR / "devis_client"
DEVIS_DIR.mkdir(exist_ok=True)

# Set pdf_generator paths (all absolute)
pdf_generator.DEVIS_DIR = DEVIS_DIR
pdf_generator.FACTURES_DIR = BASE_DIR / "factures_client"
pdf_generator.LOGO_PATH = BASE_DIR / "logo.png"
pdf_generator.PICTURES_DIR = BASE_DIR / "pictures"


def _load_history() -> dict:
    if DEVIS_HISTORY_FILE.exists():
        with open(DEVIS_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_history(history: dict):
    with open(DEVIS_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def _load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"devis_counter": 1, "facture_counter": 1}


def _save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def _build_df(lines) -> pd.DataFrame:
    rows = []
    for line in lines:
        rows.append({
            "Désignation": line.designation,
            "Marque": line.marque,
            "Quantité": line.quantite,
            "Prix Achat TTC": line.prix_achat_ttc,
            "Prix Unit. TTC": line.prix_unit_ttc,
            "TVA (%)": line.tva,
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["Désignation", "Marque", "Quantité", "Prix Achat TTC", "Prix Unit. TTC", "TVA (%)"]
    )


def _calc_roi(factures, kwp, day_pct, battery_kwh):
    eco_sans = []
    eco_avec = []
    for i in range(12):
        prod = GHI[i] * kwp * EFFICIENCY
        self_consumed = prod * day_pct
        sans = self_consumed * KWH_PRICE
        remaining = prod - self_consumed
        battery_stored = min(battery_kwh * DAYS_IN_MONTH[i], remaining)
        avec = (self_consumed + battery_stored) * KWH_PRICE
        eco_sans.append(sans)
        eco_avec.append(avec)
    return eco_sans, eco_avec


@router.get("")
async def list_devis(current_user: dict = Depends(get_current_user)):
    history = _load_history()
    result = []
    for devis_id, entry in history.items():
        result.append({
            "devis_id": devis_id,
            "client_name": entry.get("client_name", ""),
            "doc_number": entry.get("doc_number", devis_id),
            "total_ttc": entry.get("total_ttc", 0),
            "created_at": entry.get("created_at", ""),
            "scenario_choice": entry.get("scenario_choice", ""),
        })
    result.sort(key=lambda x: str(x.get("devis_id", "")), reverse=True)
    return result


@router.get("/{devis_id}")
async def get_devis(devis_id: str, current_user: dict = Depends(get_current_user)):
    history = _load_history()
    entry = history.get(devis_id) or history.get(str(devis_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Devis not found")
    return {"devis_id": devis_id, **entry}


@router.post("/generate")
async def generate_devis(request: DevisRequest, current_user: dict = Depends(get_current_user)):
    # Build product DataFrame
    df_all = _build_df(request.product_lines)

    # Split SANS and AVEC based on scenario
    scenario = request.scenario_choice

    def _filter_sans(df):
        """SANS scenario: remove Batterie and Onduleur hybride"""
        if df.empty:
            return df
        mask = ~df["Désignation"].isin(["Batterie", "Onduleur hybride"])
        return df[mask].reset_index(drop=True)

    def _filter_avec(df):
        """AVEC scenario: remove Onduleur réseau, Smart Meter, Wifi Dongle (Huawei-only items)"""
        if df.empty:
            return df
        mask = ~df["Désignation"].isin(["Onduleur réseau", "Smart Meter", "Wifi Dongle"])
        return df[mask].reset_index(drop=True)

    df_sans = _filter_sans(df_all.copy())
    df_avec = _filter_avec(df_all.copy())

    # Add custom lines
    if request.custom_lines_sans:
        extra_sans = _build_df(request.custom_lines_sans)
        df_sans = pd.concat([df_sans, extra_sans], ignore_index=True)
    if request.custom_lines_avec:
        extra_avec = _build_df(request.custom_lines_avec)
        df_avec = pd.concat([df_avec, extra_avec], ignore_index=True)

    # Compute totals
    def _total_ttc(df):
        if df.empty or "Prix Unit. TTC" not in df.columns or "Quantité" not in df.columns:
            return 0.0
        return float((df["Prix Unit. TTC"] * df["Quantité"]).sum())

    total_sans = _total_ttc(df_sans)
    total_avec = _total_ttc(df_avec)

    # Apply discount
    if request.discount_percent and request.discount_percent > 0:
        _factor = 1 - request.discount_percent / 100
        total_sans = round(total_sans * _factor, 2)
        total_avec = round(total_avec * _factor, 2)

    # ROI calculations
    factures = request.roi_data.factures_mensuelles
    if len(factures) < 12:
        last = factures[-1] if factures else 500.0
        factures = factures + [last] * (12 - len(factures))
    factures = factures[:12]

    day_pct = request.roi_data.day_usage_percent / 100.0
    kwp = request.puissance_kwp

    # eco_sans: solar self-consumption savings only
    eco_sans_monthly, _ = _calc_roi(factures, kwp, day_pct, 0)

    # eco_avec: eco_sans + flat battery bonus (236.25 MAD/month per 5 kWh = 47.25 MAD/kWh/month)
    # Search designation AND marque for the kWh value — autofill keeps designation as
    # plain "Batterie" and puts the capacity (e.g. "Deyness 5kWh") in Marque.
    _bat_total_kwh = 0.0
    if not df_avec.empty and "Désignation" in df_avec.columns:
        for _, _row in df_avec.iterrows():
            _des = str(_row.get("Désignation", "")).lower()
            if "batterie" not in _des:
                continue
            _qty = float(_row.get("Quantité", 0) or 0)
            _search_str = _des + " " + str(_row.get("Marque", "")).lower()
            _m = re.search(r'(\d+(?:\.\d+)?)\s*kwh', _search_str)
            _bat_total_kwh += _qty * (float(_m.group(1)) if _m else 5.0)
    _bat_monthly_bonus = round(_bat_total_kwh * 47.25)  # 236.25 / 5 kWh = 47.25 MAD/kWh/month

    eco_avec_monthly = [s + _bat_monthly_bonus for s in eco_sans_monthly]
    eco_sans_annual = sum(eco_sans_monthly)
    eco_avec_annual = sum(eco_avec_monthly)

    payback_sans = (total_sans / eco_sans_annual) if eco_sans_annual > 0 and total_sans > 0 else 0
    payback_avec = (total_avec / eco_avec_annual) if eco_avec_annual > 0 and total_avec > 0 else 0

    prod_annuelle = sum(GHI[i] * kwp * EFFICIENCY for i in range(12))

    roi_summary_sans = {
        "prod_annuelle": prod_annuelle,
        "eco_annuelle": eco_sans_annual,
        "cout_systeme": total_sans,
        "payback": payback_sans if payback_sans else None,
    }

    roi_summary_avec = {
        "prod_annuelle": prod_annuelle,
        "eco_annuelle": eco_avec_annual,
        "cout_systeme": total_avec,
        "payback": payback_avec if payback_avec else None,
    }

    # ROI chart buffers
    years = list(range(0, 26))
    cumul_sans = []
    cumul_avec = []
    v_sans = -total_sans
    v_avec = -total_avec
    cumul_sans.append(v_sans)
    cumul_avec.append(v_avec)
    for _ in range(1, 26):
        v_sans += eco_sans_annual
        v_avec += eco_avec_annual
        cumul_sans.append(v_sans)
        cumul_avec.append(v_avec)

    roi_fig_buf = roi_figure_buffer(MOIS, factures, eco_sans_monthly, eco_avec_monthly)
    roi_cumul_buf = roi_cumulative_buffer(years, cumul_sans, cumul_avec)

    # Determine labels from installation type
    install_type = request.installation_type
    type_label_map = {
        "Résidentielle": "résidentielle",
        "Commerciale": "commerciale",
        "Industrielle": "industrielle",
        "Agricole": "agricole",
    }
    type_phrase_map = {
        "Résidentielle": "Installation photovoltaïque résidentielle",
        "Commerciale": "Installation photovoltaïque commerciale",
        "Industrielle": "Installation photovoltaïque industrielle",
        "Agricole": "Installation photovoltaïque agricole",
    }
    type_label = type_label_map.get(install_type, "résidentielle")
    type_phrase = type_phrase_map.get(install_type, "Installation photovoltaïque")

    # Generate PDF
    doc_number = request.doc_number
    doc_type = "Devis"
    safe_client = re.sub(r"[^A-Za-z0-9]", "_", request.client_name or "Client")
    pdf_filename = f"{doc_type}_{safe_client}_{int(doc_number)}.pdf"

    _onduleur_kw    = request.onduleur_kw
    _onduleur_phase = request.onduleur_phase or "Monophasé"

    def _df_to_items(df):
        items = []
        for _, row in df.iterrows():
            if float(row.get("Quantité", 0) or 0) == 0:
                continue
            des = row.get("Désignation", "")
            # Append kW and phase to any onduleur row when the user filled them in
            if _onduleur_kw and "onduleur" in des.lower():
                des = f"{des} {_onduleur_kw:g}kW {_onduleur_phase}"
            items.append({
                "designation":   des,
                "marque":        row.get("Marque", ""),
                "quantite":      row.get("Quantité", 1),
                "prix_unit_ttc": float(row.get("Prix Unit. TTC", 0)),
            })
        return items

    nb_pan = round(kwp * 1000 / request.puissance_panneau_w) if request.puissance_panneau_w > 0 else 0

    # Raw unfiltered items for one-page mode (no scenario filtering, no qty==0 skip)
    all_items = [
        {
            "designation": ln.designation,
            "marque": ln.marque or "",
            "quantite": ln.quantite,
            "prix_unit_ttc": ln.prix_unit_ttc,
        }
        for ln in request.product_lines
        if ln.quantite and ln.quantite > 0
    ]

    premium_data = {
        "ref":              str(doc_number),
        "date":             datetime.utcnow().strftime("%d/%m/%Y"),
        "client_name":      request.client_name,
        "client_addr":      request.client_address,
        "client_phone":     request.client_phone,
        "inst_type":        install_type,
        "puissance_kwc":    kwp,
        "nb_panneaux":      nb_pan,
        "watt_par_panneau": request.puissance_panneau_w,
        "prod_kwh":         round(prod_annuelle),
        "total_sans":       total_sans,
        "total_avec":       total_avec,
        "eco_s_ann":        round(eco_sans_annual),
        "eco_a_ann":        round(eco_avec_annual),
        "eco_a_cumul":      round(eco_avec_annual),
        "roi_s":            round(payback_sans, 1) if payback_sans else 0,
        "roi_a":            round(payback_avec, 1) if payback_avec else 0,
        "eco_s_monthly":    [round(v) for v in eco_sans_monthly],
        "eco_a_monthly":    [round(v) for v in eco_avec_monthly],
        "factures_mensuelles": [round(v) for v in factures],
        "sans_items":       _df_to_items(df_sans),
        "avec_items":       _df_to_items(df_avec),
        "scenario":         scenario,
        "recommended":      request.recommended_option,
        "pdf_mode":         request.pdf_mode,
        "all_items":        all_items,
    }

    out_path = DEVIS_DIR / pdf_filename
    try:
        generate_premium_pdf(premium_data, out_path)
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"PDF ERROR:\n{error_detail}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}\n{error_detail}")
    


    # Save to history
    devis_id = str(doc_number)
    history = _load_history()
    history[devis_id] = {
        "client_name": request.client_name,
        "client_address": request.client_address,
        "client_phone": request.client_phone,
        "doc_number": doc_number,
        "df": df_all.to_dict(orient="records"),
        "df_sans": df_sans.to_dict(orient="records"),
        "df_avec": df_avec.to_dict(orient="records"),
        "total_ttc": total_avec if "Avec" in scenario else total_sans,
        "total_sans": total_sans,
        "total_avec": total_avec,
        "notes_sans": request.notes_sans,
        "notes_avec": request.notes_avec,
        "scenario_choice": scenario,
        "installation_type": install_type,
        "recommended_option": request.recommended_option,
        "puissance_kwp": kwp,
        "pdf_filename": pdf_filename,
        "created_at": datetime.utcnow().strftime("%Y-%m-%d"),
    }
    _save_history(history)

    # Increment devis counter
    cfg = _load_config()
    cfg["devis_counter"] = max(cfg.get("devis_counter", 1), doc_number)
    _save_config(cfg)

    return {
        "devis_id": devis_id,
        "pdf_filename": pdf_filename,
        "download_url": f"/api/devis/{devis_id}/pdf",
        "total_sans": round(total_sans, 2),
        "total_avec": round(total_avec, 2),
    }


@router.get("/{devis_id}/pdf")
async def download_devis_pdf(devis_id: str, current_user: dict = Depends(get_current_user)):
    history = _load_history()
    entry = history.get(devis_id) or history.get(str(devis_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Devis not found")
    pdf_filename = entry.get("pdf_filename")
    if not pdf_filename:
        # Try to reconstruct filename
        doc_number = entry.get("doc_number", devis_id)
        safe_client = re.sub(r"[^A-Za-z0-9]", "_", entry.get("client_name", "Client") or "Client")
        pdf_filename = f"Devis_{safe_client}_{int(doc_number)}.pdf"
    pdf_path = DEVIS_DIR / pdf_filename
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"PDF file not found: {pdf_filename}")
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=pdf_filename,
    )


@router.delete("/{devis_id}", status_code=204)
async def delete_devis(devis_id: str, current_user: dict = Depends(get_current_user)):
    history = _load_history()
    if devis_id not in history and str(devis_id) not in history:
        raise HTTPException(status_code=404, detail="Devis not found")
    history.pop(devis_id, None)
    history.pop(str(devis_id), None)
    _save_history(history)
