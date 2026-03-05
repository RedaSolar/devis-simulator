import re as _re
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from routers.auth_router import get_current_user
from catalog import load_catalog, get_prices
import pandas as pd
import sys

router = APIRouter()

# ---- Compatibility shim ----
# autofill.py tries to import select_inverter_for_power from catalog,
# but that function lives in autofill.py itself.
# Patch catalog module in sys.modules so the import succeeds.
def _patch_catalog_for_autofill():
    import catalog as _cat_module
    if not hasattr(_cat_module, 'select_inverter_for_power'):
        # Import the real function from autofill (deferred to avoid circular)
        # We provide a safe stub — autofill.py defines the real one itself
        def _stub_select_inverter(catalog, onduleur_type, puissance_kwp):
            return None
        _cat_module.select_inverter_for_power = _stub_select_inverter

# Patch streamlit so autofill.py can import it (uses st.session_state inside function body)
if "streamlit" not in sys.modules:
    from unittest.mock import MagicMock
    mock_st = MagicMock()
    mock_st.session_state = {}
    sys.modules["streamlit"] = mock_st

# Apply catalog patch before any autofill import
_patch_catalog_for_autofill()


class AutofillRequest(BaseModel):
    puissance_kwp: float
    puissance_panneau_w: int = 710
    structure_type: str = "acier"  # "acier" or "aluminium"


def _get_base_df() -> pd.DataFrame:
    base_rows = [
        {"Désignation": "Onduleur réseau",  "Marque": "", "Quantité": 1, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
        {"Désignation": "Onduleur hybride", "Marque": "", "Quantité": 1, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
        {"Désignation": "Smart Meter",      "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
        {"Désignation": "Wifi Dongle",      "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
        {"Désignation": "Panneaux",         "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
        {"Désignation": "Batterie",         "Marque": "", "Quantité": 1, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
        {"Désignation": "Batterie",         "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
        {"Désignation": "Structures acier", "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
        {"Désignation": "Structures aluminium", "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
        {"Désignation": "Socles",           "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
        {"Désignation": "Accessoires",      "Marque": "", "Quantité": 1, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
        {"Désignation": "Tableau De Protection AC/DC", "Marque": "", "Quantité": 1, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
        {"Désignation": "Installation",     "Marque": "", "Quantité": 1, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
        {"Désignation": "Transport",        "Marque": "", "Quantité": 1, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
        {"Désignation": "Suivi journalier, maintenance chaque 12 mois pendent 2 ans",
         "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
    ]
    return pd.DataFrame(base_rows)


@router.post("")
async def autofill(body: AutofillRequest, current_user: dict = Depends(get_current_user)):
    # Apply patches before importing autofill module
    _patch_catalog_for_autofill()

    from autofill import auto_fill_from_power, select_inverter_for_power

    catalog = load_catalog()
    df = _get_base_df()

    try:
        result_df = auto_fill_from_power(df, catalog, body.puissance_kwp, body.puissance_panneau_w)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Autofill error: {str(e)}")

    # Override structure selection based on user's radio button choice
    use_acier = body.structure_type != "aluminium"
    chosen_des = "Structures acier" if use_acier else "Structures aluminium"
    other_des  = "Structures aluminium" if use_acier else "Structures acier"
    # Calculate nb_panneaux from kwp and panel wattage
    nb_pan_auto = round(body.puissance_kwp * 1000 / body.puissance_panneau_w) if body.puissance_panneau_w > 0 else 0
    mask_chosen = result_df["Désignation"] == chosen_des
    mask_other  = result_df["Désignation"] == other_des
    if mask_chosen.any():
        idx_c = mask_chosen.idxmax()
        if result_df.at[idx_c, "Quantité"] == 0 and nb_pan_auto > 0:
            result_df.at[idx_c, "Quantité"] = nb_pan_auto
        # Fill price from catalog if missing
        sell_s, buy_s = get_prices(catalog, chosen_des, "")
        if result_df.at[idx_c, "Prix Unit. TTC"] == 0 and sell_s:
            result_df.at[idx_c, "Prix Unit. TTC"] = sell_s
        if result_df.at[idx_c, "Prix Achat TTC"] == 0 and buy_s:
            result_df.at[idx_c, "Prix Achat TTC"] = buy_s
    if mask_other.any():
        idx_o = mask_other.idxmax()
        result_df.at[idx_o, "Quantité"] = 0  # zero out the non-chosen structure

    # Convert to list of dicts, handle NaN
    records = result_df.where(result_df.notna(), other=None).to_dict(orient="records")
    cleaned = []
    for r in records:
        cleaned.append({
            "designation": str(r.get("Désignation") or ""),
            "marque": str(r.get("Marque") or ""),
            "quantite": float(r.get("Quantité") or 0),
            "prix_achat_ttc": float(r.get("Prix Achat TTC") or 0),
            "prix_unit_ttc": float(r.get("Prix Unit. TTC") or 0),
            "tva": float(r.get("TVA (%)") or 20),
            "photo": str(r.get("PhotoKey") or ""),
        })

    # Get selected onduleur info for each type
    info_res = select_inverter_for_power(catalog, "Onduleur Injection", body.puissance_kwp)
    info_hyb = select_inverter_for_power(catalog, "Onduleur Hybride", body.puissance_kwp)

    onduleur_options = {}
    if info_res:
        onduleur_options["reseau"] = {
            "brand": info_res["marque"],
            "power": info_res["power"],
            "phase": info_res["phase"],
        }
    if info_hyb:
        onduleur_options["hybride"] = {
            "brand": info_hyb["marque"],
            "power": info_hyb["power"],
            "phase": info_hyb["phase"],
        }

    return {"rows": cleaned, "onduleur_options": onduleur_options}


@router.get("/onduleur-options")
async def get_onduleur_catalog_options(
    type: str = "reseau",
    brand: str = "",
    current_user: dict = Depends(get_current_user),
):
    """Return all available power/phase options for an onduleur brand from the catalog."""
    _patch_catalog_for_autofill()
    catalog = load_catalog()
    onduleur_type = "Onduleur Injection" if type == "reseau" else "Onduleur Hybride"

    if onduleur_type not in catalog or brand not in catalog[onduleur_type]:
        return []

    brand_dict = catalog[onduleur_type][brand]
    options = []

    for power_str, power_info in brand_dict.items():
        if not isinstance(power_info, dict):
            continue
        power_kw = None
        m = _re.search(r'(\d+(?:[.,]\d+)?)', str(power_str))
        if m:
            try:
                power_kw = float(m.group(1).replace(",", "."))
            except Exception:
                pass

        if "variants" in power_info and isinstance(power_info["variants"], dict):
            for phase, vinfo in power_info["variants"].items():
                options.append({
                    "power_str": power_str,
                    "power": power_kw,
                    "phase": phase,
                    "sell_ttc": vinfo.get("sell_ttc"),
                    "buy_ttc": vinfo.get("buy_ttc"),
                })
        else:
            options.append({
                "power_str": power_str,
                "power": power_kw,
                "phase": power_info.get("phase", "Monophasé"),
                "sell_ttc": power_info.get("sell_ttc"),
                "buy_ttc": power_info.get("buy_ttc"),
            })

    options.sort(key=lambda x: (x["power"] or 0, x["phase"]))
    return options
