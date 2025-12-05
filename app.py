import streamlit as st
import pandas as pd
import json, re
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Image,
    Paragraph,
    Spacer,
    PageBreak,
    Preformatted,
    HRFlowable,
    ListFlowable,
    ListItem,
)
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib.colors import HexColor
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
import matplotlib.pyplot as plt
from io import BytesIO

# ---------- CONSTANTES VISUELLES ----------
BLUE_MAIN = "#0A5275"        # Bleu TAQINOR
BLUE_LIGHT = "#E6F1F7"
TEXT_DARK = "#222222"
ORANGE_ACCENT = "#F28E2B"
GREY_NEUTRAL = "#555555"

# ---------- CONSTANTES ROI / PRODUCTION ----------
GHI = [83.99, 96.79, 133.43, 155.30, 175.28, 179.62, 179.56, 161.17, 137.03, 111.59, 81.91, 74.61]
MOIS = ["Jan","Fév","Mar","Avr","Mai","Juin","Juil","Août","Sep","Oct","Nov","Déc"]
EFFICIENCY = 0.8  # rendement global
KWH_PRICE = 2.0   # MAD/kWh FIXE (utilisé en interne — ne pas afficher dans les PDF/UI)

# ---------- DOSSIERS ----------
BASE_DIR = Path(".")
CONFIG_FILE = BASE_DIR / "config.json"
DEVIS_HISTORY_FILE = BASE_DIR / "devis_history.json"
LOGO_PATH = BASE_DIR / "logo.png"
CATALOG_FILE = BASE_DIR / "brand_catalog.json"
CUSTOM_LINES_FILE = BASE_DIR / "custom_line_templates.json"

DEVIS_DIR = BASE_DIR / "devis_client"
FACTURES_DIR = BASE_DIR / "factures_client"
PICTURES_DIR = BASE_DIR / "pictures"

for d in [DEVIS_DIR, FACTURES_DIR, PICTURES_DIR]:
    d.mkdir(exist_ok=True)

def img_candidates(name_base: str):
    return [
        PICTURES_DIR / f"{name_base}.png",
        PICTURES_DIR / f"{name_base}.jpg",
        PICTURES_DIR / f"{name_base}.jpeg",
    ]

IMAGE_FILES = {
    "Onduleur réseau": img_candidates("onduler") + img_candidates("onduleur"),
    "Onduleur hybride": img_candidates("onduler") + img_candidates("onduleur"),
    "Smart Meter": img_candidates("smart_meter"),
    "Wifi Dongle": img_candidates("wifi_dongle"),
    "Panneaux": img_candidates("panneaux"),
    "Batterie": img_candidates("batterie"),
    "Structures": img_candidates("structures"),
    "Socles": img_candidates("socles"),
    "Accessoires": img_candidates("accessoires"),
    "Tableau De Protection AC/DC": img_candidates("tableau_protection"),
    "Installation": img_candidates("installation"),
    "Transport": img_candidates("transport"),
    "Suivi journalier, maintenance chaque 12 mois pendent 2 ans": img_candidates("suivi_maintenance"),
}

# ---------- INIT CONFIG / HISTORY ----------
if CONFIG_FILE.exists():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
else:
    config = {"devis_counter": 1, "facture_counter": 1}

if DEVIS_HISTORY_FILE.exists():
    with open(DEVIS_HISTORY_FILE, "r", encoding="utf-8") as f:
        devis_history = json.load(f)
else:
    devis_history = {}

# ---------- SESSION STATE ----------
if "custom_lines_sans" not in st.session_state:
    st.session_state.custom_lines_sans = []

if "custom_lines_avec" not in st.session_state:
    st.session_state.custom_lines_avec = []

if "notes_sans" not in st.session_state:
    st.session_state.notes_sans = []

if "notes_avec" not in st.session_state:
    st.session_state.notes_avec = []

if "roi_fact_init" not in st.session_state:
    st.session_state.roi_fact_init = {m: 2000.0 for m in MOIS}

if "df_common_overrides" not in st.session_state:
    st.session_state.df_common_overrides = None

# ---------- FONCTIONS AIDE ROI ----------
def interpoler_factures(hiver, ete):
    if ete == 0:
        return [hiver] * 12
    premiere = [hiver + (ete - hiver) / 6 * i for i in range(7)]
    seconde = [ete - (ete - hiver) / 4 * i for i in range(5)]
    return [*premiere, *seconde]

def build_roi_figure(mois, factures, eco_sans, eco_avec):
    taqinor_graph_style()
    fig, ax = plt.subplots(figsize=(6.2, 3.2))
    x = list(range(len(mois)))
    bar_width = 0.35

    bars_sans = ax.bar(
        [i - bar_width / 2 for i in x],
        eco_sans,
        width=bar_width,
        color=BLUE_MAIN,
        label="Économie SANS batterie",
        alpha=0.9,
    )
    bars_avec = ax.bar(
        [i + bar_width / 2 for i in x],
        eco_avec,
        width=bar_width,
        color=ORANGE_ACCENT,
        label="Économie AVEC batterie",
        alpha=0.9,
    )

    ax.plot(
        x,
        factures,
        marker="o",
        linestyle="-",
        linewidth=1.0,
        color=GREY_NEUTRAL,
        label="Facture sans PV",
    )

    ax.set_title("Estimation des économies mensuelles", pad=8, fontsize=11)
    ax.set_xlabel("Mois")
    ax.set_ylabel("Montant (MAD)")
    ax.set_xticks(x)
    ax.set_xticklabels(mois)
    ax.set_axisbelow(True)
    ax.set_ylim(bottom=0)
    ax.margins(y=0.08)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.grid(axis="y", alpha=0.2, linestyle="--", linewidth=0.8)
    ax.legend(loc="upper left", frameon=False)

    # Optionally add value labels on bars for a premium touch (small and subtle)
    for bars in (bars_sans, bars_avec):
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + (max(factures) * 0.01),
                f"{height:,.0f}".replace(",", " "),
                ha="center",
                va="bottom",
                fontsize=7,
                color=TEXT_DARK,
            )

    plt.tight_layout()
    return fig

def roi_figure_buffer(mois, factures, eco_sans, eco_avec):
    fig = build_roi_figure(mois, factures, eco_sans, eco_avec)
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf

# ---------- GRAPHIQUES TAQINOR ----------
def taqinor_graph_style():
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
        }
    )


def _taqinor_graph_style():
    # Backward-compat wrapper to keep any legacy calls working
    return taqinor_graph_style()

# ---------- CANONICALS ----------
CANONICALS = [
    "Onduleur réseau",
    "Onduleur hybride",
    "Smart Meter",
    "Wifi Dongle",
    "Panneaux",
    "Batterie",
    "Structures",
    "Socles",
    "Accessoires",
    "Tableau De Protection AC/DC",
    "Installation",
    "Transport",
    "Suivi journalier, maintenance chaque 12 mois pendent 2 ans",
]
CANON_MAP = {c.lower(): c for c in CANONICALS}
CANON_MAP.update(
    {
        "installation": "Installation",
        "installation + transport": "Installation",
        "structures en acier galvanisé": "Structures",
        "transport": "Transport",
    }
)

# ---------- CATALOG ----------
def normalize_onduleur_entries(catalog: dict) -> bool:
    """
    Convert keys like '10_Monophase' or '10Triphase' into a numeric key '10'
    with nested variants: {"10": {"variants": {"Monophase": {...}, "Triphase": {...}}}}
    Returns True if catalog was changed (so caller can persist it).
    """
    changed = False
    for on_key in ("Onduleur Injection", "Onduleur Hybride"):
        if on_key not in catalog:
            continue
        brands = catalog.get(on_key, {})
        for brand, brand_dict in list(brands.items()):
            if brand == "__default__" or not isinstance(brand_dict, dict):
                continue
            new_brand_dict = {}
            temp = {}
            for power_key, info in brand_dict.items():
                if not isinstance(power_key, str):
                    power_key = str(power_key)
                # Try to detect suffix like '_Monophase' or '_Triphase' or ' 10 Monophase'
                m = re.match(r"^(\d+(?:[.,]\d+)?)(?:[_\s-]?(Monophase|Triphase))?$", power_key, re.IGNORECASE)
                if m and m.group(2):
                    num = m.group(1).replace(",", ".")
                    phase = m.group(2).capitalize()
                    temp.setdefault(num, {}).setdefault("variants", {})[phase] = info
                else:
                    # If info itself contains 'phase' key, move it under variants
                    if isinstance(info, dict) and "phase" in info:
                        # extract numeric from key if possible
                        m2 = re.search(r"(\d+(?:[.,]\d+)?)", power_key)
                        num = m2.group(1).replace(",", ".") if m2 else power_key
                        phase = info.get("phase", "Monophase")
                        temp.setdefault(str(num), {}).setdefault("variants", {})[phase] = info
                    else:
                        # keep as-is (either already numeric key or custom)
                        temp.setdefault(power_key, info)

            # Build new_brand_dict from temp
            for k, v in temp.items():
                new_brand_dict[k] = v

            if new_brand_dict != brand_dict:
                catalog[on_key][brand] = new_brand_dict
                changed = True
    return changed

def load_catalog():
    if CATALOG_FILE.exists():
        with open(CATALOG_FILE, "r", encoding="utf-8") as f:
            catalog = json.load(f)
            # Normalize onduleur entries to nested variant format if needed
            try:
                changed = normalize_onduleur_entries(catalog)
                if changed:
                    save_catalog(catalog)
            except Exception:
                # If normalization fails, silently continue with original catalog
                pass
            return catalog
    return {
        "Onduleur Injection": {},
        "Onduleur Hybride": {},
        "Panneaux": {},
        "Batterie": {},
        "Structures": {"__default__": {"sell_ttc": 0.0, "buy_ttc": 0.0}},
        "Socles": {"__default__": {"sell_ttc": 0.0, "buy_ttc": 0.0}},
        "Accessoires": {"__default__": {"sell_ttc": 0.0, "buy_ttc": 0.0}},
        "Smart Meter": {"__default__": {"sell_ttc": 0.0, "buy_ttc": 0.0}},
        "Wifi Dongle": {"__default__": {"sell_ttc": 0.0, "buy_ttc": 0.0}},
        "Tableau De Protection AC/DC": {"__default__": {"sell_ttc": 0.0, "buy_ttc": 0.0}},
        "Installation": {"__default__": {"sell_ttc": 0.0, "buy_ttc": 0.0}},
        "Transport": {"__default__": {"sell_ttc": 0.0, "buy_ttc": 0.0}},
        "Suivi journalier, maintenance chaque 12 mois pendent 2 ans": {
            "__default__": {"sell_ttc": 0.0, "buy_ttc": 0.0}
        },
    }

    def normalize_onduleur_entries(catalog: dict) -> bool:
        """
        Convert keys like '10_Monophase' or '10Triphase' into a numeric key '10'
        with nested variants: {"10": {"variants": {"Monophase": {...}, "Triphase": {...}}}}
        Returns True if catalog was changed (so caller can persist it).
        """
        changed = False
        for on_key in ("Onduleur Injection", "Onduleur Hybride"):
            if on_key not in catalog:
                continue
            brands = catalog.get(on_key, {})
            for brand, brand_dict in list(brands.items()):
                if brand == "__default__" or not isinstance(brand_dict, dict):
                    continue
                new_brand_dict = {}
                temp = {}
                for power_key, info in brand_dict.items():
                    if not isinstance(power_key, str):
                        power_key = str(power_key)
                    # Try to detect suffix like '_Monophase' or '_Triphase' or ' 10 Monophase'
                    m = re.match(r"^(\d+(?:[.,]\d+)?)(?:[_\s-]?(Monophase|Triphase))?$", power_key, re.IGNORECASE)
                    if m and m.group(2):
                        num = m.group(1).replace(",", ".")
                        phase = m.group(2).capitalize()
                        temp.setdefault(num, {}).setdefault("variants", {})[phase] = info
                    else:
                        # If info itself contains 'phase' key, move it under variants
                        if isinstance(info, dict) and "phase" in info:
                            # extract numeric from key if possible
                            m2 = re.search(r"(\d+(?:[.,]\d+)?)", power_key)
                            num = m2.group(1).replace(",", ".") if m2 else power_key
                            phase = info.get("phase", "Monophase")
                            temp.setdefault(str(num), {}).setdefault("variants", {})[phase] = info
                        else:
                            # keep as-is (either already numeric key or custom)
                            temp.setdefault(power_key, info)

                # Build new_brand_dict from temp
                for k, v in temp.items():
                    new_brand_dict[k] = v

                if new_brand_dict != brand_dict:
                    catalog[on_key][brand] = new_brand_dict
                    changed = True
        return changed

def save_catalog(catalog):
    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

def _catalog_key_for_designation(designation: str) -> str:
    # Normalize keys so that variant designations map to their catalog base keys
    if designation in ("Onduleur réseau", "Onduleur hybride"):
        return "Onduleur Injection" if designation == "Onduleur réseau" else "Onduleur Hybride"
    if designation in ("Panneaux", "Batterie"):
        return designation
    if isinstance(designation, str) and designation.startswith("Structures"):
        return "Structures"
    return designation

def set_prices(catalog, designation, marque, sell_ttc=None, buy_ttc=None, power_key=None, phase=None):
    """Set sell/buy prices in catalog. If power_key and phase are provided for inverters,
    update the nested variant price when present.
    """
    base_key = _catalog_key_for_designation(designation)
    key = marque if base_key in ("Onduleur Injection", "Onduleur Hybride", "Panneaux", "Batterie") else "__default__"
    if base_key in ("Onduleur Injection", "Onduleur Hybride") and power_key:
        # Ensure nested structure exists
        base = catalog.setdefault(base_key, {})
        brand_entry = base.setdefault(key, {})
        power_entry = brand_entry.setdefault(str(power_key), {})
        # If variants structure is present, update variant
        if "variants" in power_entry and isinstance(power_entry["variants"], dict) and phase:
            variant = power_entry["variants"].setdefault(phase, {})
            if sell_ttc not in (None, "", 0):
                variant["sell_ttc"] = float(sell_ttc)
            if buy_ttc not in (None, "", 0):
                variant["buy_ttc"] = float(buy_ttc)
        else:
            # update at power level
            if sell_ttc not in (None, "", 0):
                power_entry["sell_ttc"] = float(sell_ttc)
            if buy_ttc not in (None, "", 0):
                power_entry["buy_ttc"] = float(buy_ttc)
    else:
        item = catalog.setdefault(base_key, {}).setdefault(key, {})
        if sell_ttc not in (None, "", 0):
            item["sell_ttc"] = float(sell_ttc)
        if buy_ttc not in (None, "", 0):
            item["buy_ttc"] = float(buy_ttc)
    save_catalog(catalog)

def get_prices(catalog, designation, marque):
    base_key = _catalog_key_for_designation(designation)
    key = marque if base_key in ("Onduleur Injection", "Onduleur Hybride", "Panneaux", "Batterie") else "__default__"
    if base_key in catalog and key in catalog[base_key]:
        return (
            catalog[base_key][key].get("sell_ttc"),
            catalog[base_key][key].get("buy_ttc"),
        )
    return (None, None)

def known_brands(catalog, designation):
    base_key = _catalog_key_for_designation(designation)
    if base_key not in ("Onduleur Injection", "Onduleur Hybride", "Panneaux", "Batterie"):
        return [""]
    return [""] + sorted([b for b in catalog.get(base_key, {}).keys() if b != "__default__"])

# ---------- CUSTOM TEMPLATES ----------
def load_custom_templates():
    if CUSTOM_LINES_FILE.exists():
        with open(CUSTOM_LINES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_custom_templates(templates):
    with open(CUSTOM_LINES_FILE, "w", encoding="utf-8") as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)


def _num(s):
    try:
        s = str(s).replace(",", ".")
        s = re.sub(r"[^0-9.\-]", "", s)
        return float(s) if s not in ("", "-", ".", "-.") else 0.0
    except Exception:
        return 0.0


def sanitize_df(df):
    df = df.copy()
    orig = df["Désignation"].astype(str).str.strip()
    canon = orig.str.lower().map(CANON_MAP)
    df["Désignation"] = canon.fillna(orig)
    df["Marque"] = df["Marque"].astype(str).apply(lambda x: x.title().strip() if x else "")
    for c in ["Quantité", "Prix Achat TTC", "Prix Unit. TTC", "TVA (%)"]:
        df[c] = df[c].apply(_num).clip(lower=0)
    return df

def learn_from_df(df, catalog):
    for _, r in df.iterrows():
        des = r["Désignation"]
        base_key = _catalog_key_for_designation(des)
        brand = r.get("Marque", "")
        sell, buy = _num(r.get("Prix Unit. TTC", 0)), _num(r.get("Prix Achat TTC", 0))
        if base_key in ("Onduleur", "Panneaux", "Batterie"):
            if brand and (sell > 0 or buy > 0):
                set_prices(catalog, des, brand, sell, buy)
        elif des in CANONICALS and (sell > 0 or buy > 0):
            set_prices(catalog, des, "__default__", sell, buy)

def get_first_existing_image(designation: str):
    # Try exact designation first, then fall back to catalog base key (e.g., 'Structures')
    paths = []
    if designation in IMAGE_FILES:
        paths.extend(IMAGE_FILES.get(designation, []))
    base_key = _catalog_key_for_designation(designation)
    if base_key and base_key in IMAGE_FILES and base_key != designation:
        paths.extend(IMAGE_FILES.get(base_key, []))
    for p in paths:
        if p.exists():
            return str(p)
    return None

def get_dynamic_image(photo_key: str):
    if not photo_key:
        return None
    for p in img_candidates(photo_key):
        if p.exists():
            return str(p)
    return None


def create_monthly_savings_chart(months, monthly_sans, monthly_avec):
    """
    months: liste de labels ["Jan", "Fév", ...]
    monthly_sans: liste de 12 valeurs (économies mensuelles scénario SANS batterie)
    monthly_avec: liste de 12 valeurs (économies mensuelles scénario AVEC batterie)
    Retourne un buffer PNG (BytesIO) utilisable par ReportLab.Image.
    """
    taqinor_graph_style()
    fig, ax = plt.subplots(figsize=(6, 2.6))

    x = range(len(months))
    width = 0.35

    bars_sans = ax.bar(
        [i - width / 2 for i in x],
        monthly_sans,
        width=width,
        label="Sans batterie",
        color=BLUE_MAIN,
    )
    bars_avec = ax.bar(
        [i + width / 2 for i in x],
        monthly_avec,
        width=width,
        label="Avec batterie",
        color=ORANGE_ACCENT,
    )

    ax.set_title("Économies mensuelles estimées")
    ax.set_ylabel("Économies mensuelles (MAD)")
    ax.set_xticks(list(x))
    ax.set_xticklabels(months)
    ax.set_axisbelow(True)
    ax.set_ylim(bottom=0)
    ax.margins(y=0.05)

    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.grid(axis="y", alpha=0.25, linestyle="--")

    for bar in list(bars_sans) + list(bars_avec):
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            height + 10,
            f"{int(round(height))}",
            ha="center",
            va="bottom",
            fontsize=7,
        )

    ax.legend(frameon=False, loc="upper left")

    plt.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf


def create_monthly_production_chart(months, production_kwh):
    """
    months: liste de labels de mois, ex: ['Jan', 'Fév', ...]
    production_kwh: liste de valeurs mensuelles en kWh
    Retourne un buffer d'image PNG (BytesIO) prêt à être utilisé par ReportLab.
    """
    fig, ax = plt.subplots(figsize=(6, 3))

    ax.bar(months, production_kwh)
    ax.set_ylabel("Production (kWh)")
    ax.set_title("Production annuelle estimée par mois")
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf


def create_cumulative_savings_chart(years, yearly_savings):
    """
    years: liste des années, ex: [1, 2, ..., 20]
    yearly_savings: liste des économies annuelles (MAD/an)
    Affiche la courbe des économies cumulées sur la durée.
    """
    cumulative = []
    total = 0
    for val in yearly_savings:
        total += val
        cumulative.append(total)

    fig, ax = plt.subplots(figsize=(6, 3))

    ax.plot(years, cumulative, marker="o")
    ax.set_xlabel("Années")
    ax.set_ylabel("Économies cumulées (MAD)")
    ax.set_title("Projection des économies cumulées sur 20 ans")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf

# ---------- AUTO-CHOIX ONDULEUR & STRUCTURES & PANNEAUX ----------
def get_onduleur_powers_and_phases(catalog, onduleur_type: str, brand: str):
    """
    Récupère les puissances et phases disponibles pour une marque d'onduleur.
    Retourne : dict {power_str: phase_str, ...} ex: {"5": "Monophase", "10": "Monophase", "15": "Triphase"}
    """
    result = {}
    if onduleur_type in catalog and brand in catalog[onduleur_type]:
        brand_dict = catalog[onduleur_type][brand]
        for power_str, power_info in brand_dict.items():
            phases = []
            if isinstance(power_info, dict):
                # New format: variants per power
                if "variants" in power_info and isinstance(power_info["variants"], dict):
                    phases = list(power_info["variants"].keys())
                elif "phase" in power_info:
                    phases = [power_info.get("phase", "Monophase")]
            if not phases:
                phases = ["Monophase"]
            result[power_str] = phases
    return result

def get_onduleur_brands(catalog, onduleur_type: str):
    """Retourne liste des marques disponibles pour un type d'onduleur."""
    result = []
    if onduleur_type in catalog:
        for brand in catalog[onduleur_type].keys():
            if brand != "__default__":
                result.append(brand)
    return sorted(result)

def parse_kw_from_brand(name: str):
    if not name:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(k[wW]|kva|KVA)?", name)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except Exception:
        return None

def select_inverter_for_power(catalog, onduleur_type: str, puissance_kwp: float):
    """
    Sélectionne un onduleur basé sur le type (Injection ou Hybride) et la puissance.
    Retourne le plus petit onduleur avec puissance >= puissance_kwp.
    onduleur_type: "Onduleur Injection" ou "Onduleur Hybride"
    Retourne: {marque, power, phase, sell, buy} ou None
    """
    ond_dict = catalog.get(onduleur_type, {})
    candidates = []
    
    for marque, powers_dict in ond_dict.items():
        if marque == "__default__" or not isinstance(powers_dict, dict):
            continue
        
        # Itérer sur les puissances disponibles pour cette marque
        for power_str, power_info in powers_dict.items():
            if isinstance(power_info, dict):
                # Parse numeric kW from power_str like '10', '10_Monophase' or '10 kW'
                power_kw = parse_kw_from_brand(power_str)
                phase = power_info.get("phase", "Monophase")
                sell = power_info.get("sell_ttc")
                buy = power_info.get("buy_ttc")
                if power_kw is None:
                    # try to fallback to numeric conversion of keys directly
                    m = re.search(r"(\d+(?:[.,]\d+)?)", str(power_str))
                    if m:
                        try:
                            power_kw = float(m.group(1).replace(",", "."))
                        except Exception:
                            power_kw = None

                # If this power key contains multiple variants, iterate them
                if isinstance(power_info, dict) and "variants" in power_info and isinstance(power_info["variants"], dict):
                    for vphase, vinfo in power_info["variants"].items():
                        vsell = vinfo.get("sell_ttc")
                        vbuy = vinfo.get("buy_ttc")
                        if power_kw is None:
                            # try to extract numeric from power_str
                            m = re.search(r"(\d+(?:[.,]\d+)?)", str(power_str))
                            if m:
                                try:
                                    power_kw = float(m.group(1).replace(",", "."))
                                except Exception:
                                    power_kw = None
                        if power_kw is not None and vsell is not None:
                            candidates.append((power_kw, marque, power_str, vphase, vsell, vbuy))
                else:
                    if power_kw is not None and sell is not None:
                        candidates.append((power_kw, marque, power_str, phase, sell, buy))
    
    if not candidates:
        return None
    
    # Chercher le plus petit onduleur avec kw >= puissance_kwp
    above = [c for c in candidates if c[0] >= puissance_kwp]
    if above:
        best = min(above, key=lambda x: x[0])
    else:
        # Fallback: le plus grand disponible
        best = max(candidates, key=lambda x: x[0])
    
    power_kw, marque, power_str, phase, sell, buy = best
    return {
        "marque": marque,
        "power": power_kw,
        "power_str": power_str,
        "phase": phase,
        "sell": sell,
        "buy": buy,
    }


def get_panel_brands(catalog):
    """Retourne liste des marques disponibles pour panneaux."""
    result = []
    if "Panneaux" in catalog:
        for brand in catalog["Panneaux"].keys():
            if brand != "__default__":
                result.append(brand)
    return sorted(result)

def get_panel_powers(catalog, brand: str):
    """Retourne dict {power_str: {sell_ttc, buy_ttc}} pour une marque de panneau."""
    result = {}
    if "Panneaux" in catalog and brand in catalog["Panneaux"]:
        brand_dict = catalog["Panneaux"][brand]
        for power_str, power_info in brand_dict.items():
            if isinstance(power_info, dict):
                result[power_str] = power_info
    return result

def get_battery_brands(catalog):
    """Retourne liste des marques disponibles pour batteries."""
    result = []
    if "Batterie" in catalog:
        for brand in catalog["Batterie"].keys():
            if brand != "__default__":
                result.append(brand)
    return sorted(result)

def get_battery_capacities(catalog, brand: str):
    """Retourne dict {capacity_str: {sell_ttc, buy_ttc}} pour une marque de batterie."""
    result = {}
    if "Batterie" in catalog and brand in catalog["Batterie"]:
        brand_dict = catalog["Batterie"][brand]
        for capacity_str, capacity_info in brand_dict.items():
            if isinstance(capacity_info, dict):
                result[capacity_str] = capacity_info
    return result
def select_jinko_710(catalog):
    """Cherche un panneau Jinko 710 dans le catalog['Panneaux']."""
    pan_dict = catalog.get("Panneaux", {})
    candidates = []
    for marque, vals in pan_dict.items():
        if marque == "__default__":
            continue
        if "jinko" in marque.lower() and "710" in marque:
            candidates.append((marque, vals.get("sell_ttc"), vals.get("buy_ttc")))
    if not candidates:
        # fallback : premier Jinko tout court
        for marque, vals in pan_dict.items():
            if marque == "__default__":
                continue
            if "jinko" in marque.lower():
                candidates.append((marque, vals.get("sell_ttc"), vals.get("buy_ttc")))
    if not candidates:
        return None
    return {
        "marque": candidates[0][0],
        "sell": candidates[0][1],
        "buy": candidates[0][2],
    }

def auto_fill_from_power(df_common: pd.DataFrame, catalog, puissance_kwp: float, puissance_panneau_w: int):
    df = df_common.copy()

    # Nb panneaux (toujours Jinko 710)
    import math
    if puissance_kwp > 0 and puissance_panneau_w > 0:
        nb_panneaux = math.ceil(puissance_kwp * 1000.0 / puissance_panneau_w)
    else:
        nb_panneaux = 0

    # Panneaux
    mask_pan = df["Désignation"] == "Panneaux"
    if mask_pan.any():
        idx = mask_pan.idxmax()
        if nb_panneaux > 0:
            df.at[idx, "Quantité"] = nb_panneaux
        # Prefer 'Canadian Solar' 710W if available, otherwise pick first brand/power
        pan_dict = catalog.get("Panneaux", {})
        sel_brand = None
        sel_power = None
        sell_price = None
        buy_price = None
        if pan_dict:
            if "Canadian Solar" in pan_dict and "710" in pan_dict["Canadian Solar"]:
                sel_brand = "Canadian Solar"
                sel_power = "710"
                sell_price = pan_dict[sel_brand][sel_power].get("sell_ttc")
                buy_price = pan_dict[sel_brand][sel_power].get("buy_ttc")
            else:
                # fallback: first brand and its first power
                for b, powers in pan_dict.items():
                    if b == "__default__":
                        continue
                    sel_brand = b
                    # pick first numeric power key
                    for p in powers.keys():
                        if p == "__default__":
                            continue
                        sel_power = p
                        sell_price = powers[p].get("sell_ttc")
                        buy_price = powers[p].get("buy_ttc")
                        break
                    break

        if sel_brand:
            # store brand and power separately so widgets can preselect them
            df.at[idx, "Marque"] = sel_brand
            df.at[idx, "Power"] = sel_power
            if df.at[idx, "Prix Unit. TTC"] == 0 and sell_price is not None:
                df.at[idx, "Prix Unit. TTC"] = sell_price
            if df.at[idx, "Prix Achat TTC"] == 0 and buy_price is not None:
                df.at[idx, "Prix Achat TTC"] = buy_price
            # also keep in session_state for immediate widget defaults
            st.session_state["pan_brand"] = sel_brand
            st.session_state["pan_power"] = float(sel_power) if sel_power is not None else None

        # Socles en béton : 2 par panneau
        mask_socles = df["Désignation"] == "Socles"
        if mask_socles.any():
            idx_soc = mask_socles.idxmax()
            if nb_panneaux > 0:
                df.at[idx_soc, "Quantité"] = int(nb_panneaux * 2)

    # Structures : acier <30kW, alu >=30kW (1 structure par panneau)
    mask_struct_acier = df["Désignation"] == "Structures acier"
    mask_struct_aluminium = df["Désignation"] == "Structures aluminium"
    if nb_panneaux > 0:
        if puissance_kwp < 30:
            # utiliser acier
            if mask_struct_acier.any():
                idx = mask_struct_acier.idxmax()
                df.at[idx, "Quantité"] = nb_panneaux
                df.at[idx, "CustomLabel"] = "Structures en acier galvanisé"
            if mask_struct_aluminium.any():
                idx2 = mask_struct_aluminium.idxmax()
                df.at[idx2, "Quantité"] = 0
        else:
            # utiliser aluminium
            if mask_struct_aluminium.any():
                idx = mask_struct_aluminium.idxmax()
                df.at[idx, "Quantité"] = nb_panneaux
                df.at[idx, "CustomLabel"] = "Structures en aluminium"
            if mask_struct_acier.any():
                idx2 = mask_struct_acier.idxmax()
                df.at[idx2, "Quantité"] = 0

    # Onduleur réseau (Injection) → Sélectionner par puissance
    mask_ondu_res = df["Désignation"] == "Onduleur réseau"
    info_hw = None
    if mask_ondu_res.any():
        idx = mask_ondu_res.idxmax()
        info_hw = select_inverter_for_power(catalog, "Onduleur Injection", puissance_kwp)
        if info_hw:
            # Store brand, power, and phase in session state for widget to retrieve
            st.session_state["ondu_res_brand"] = info_hw["marque"]
            st.session_state["ondu_res_power"] = info_hw["power"]
            st.session_state["ondu_res_phase"] = info_hw["phase"]

            df.at[idx, "Marque"] = info_hw["marque"]
            # Compute number of inverters needed
            import math as _math
            if info_hw.get("power") and info_hw["power"] > 0:
                nb_ondu = int(_math.ceil(puissance_kwp / float(info_hw["power"]))) if puissance_kwp > 0 else 0
            else:
                nb_ondu = 1
            df.at[idx, "Quantité"] = max(0, nb_ondu)
            if df.at[idx, "Prix Unit. TTC"] == 0 and info_hw["sell"] is not None:
                df.at[idx, "Prix Unit. TTC"] = info_hw["sell"]
            if df.at[idx, "Prix Achat TTC"] == 0 and info_hw["buy"] is not None:
                df.at[idx, "Prix Achat TTC"] = info_hw["buy"]

    # Onduleur hybride → Sélectionner par puissance
    mask_ondu_hyb = df["Désignation"] == "Onduleur hybride"
    if mask_ondu_hyb.any():
        idx = mask_ondu_hyb.idxmax()
        info_deye = select_inverter_for_power(catalog, "Onduleur Hybride", puissance_kwp)
        if info_deye:
            # Store brand, power, and phase in session state for widget to retrieve
            st.session_state["ondu_hyb_brand"] = info_deye["marque"]
            st.session_state["ondu_hyb_power"] = info_deye["power"]
            st.session_state["ondu_hyb_phase"] = info_deye["phase"]

            df.at[idx, "Marque"] = info_deye["marque"]
            # Compute number of hybrid inverters needed
            import math as _math
            if info_deye.get("power") and info_deye["power"] > 0:
                nb_ondu_h = int(_math.ceil(puissance_kwp / float(info_deye["power"]))) if puissance_kwp > 0 else 0
            else:
                nb_ondu_h = 1
            df.at[idx, "Quantité"] = max(0, nb_ondu_h)
            if df.at[idx, "Prix Unit. TTC"] == 0 and info_deye["sell"] is not None:
                df.at[idx, "Prix Unit. TTC"] = info_deye["sell"]
            if df.at[idx, "Prix Achat TTC"] == 0 and info_deye["buy"] is not None:
                df.at[idx, "Prix Achat TTC"] = info_deye["buy"]

    # Pour TOUS les items, chercher les prix dans le catalogue si pas déjà remplis
    for idx, row in df.iterrows():
        des = row.get("Désignation")
        if not isinstance(des, str):
            continue
        # Si Prix Unit. TTC est à 0 ou vide, chercher dans le catalogue
        if row.get("Prix Unit. TTC") == 0 or pd.isna(row.get("Prix Unit. TTC")):
            sell_price, buy_price = get_prices(catalog, des, row.get("Marque", ""))
            if sell_price is not None:
                df.at[idx, "Prix Unit. TTC"] = sell_price
            if buy_price is not None and (row.get("Prix Achat TTC") == 0 or pd.isna(row.get("Prix Achat TTC"))):
                df.at[idx, "Prix Achat TTC"] = buy_price

    # Si Huawei utilisé → Smart Meter + Wifi Dongle auto (quantité 1 + prix du catalog si dispo)
    if info_hw is not None:
        for des in ["Smart Meter", "Wifi Dongle"]:
            mask = df["Désignation"] == des
            if mask.any():
                idx = mask.idxmax()
                if df.at[idx, "Quantité"] == 0:
                    df.at[idx, "Quantité"] = 1
                sell, buy = get_prices(catalog, des, "")
                if df.at[idx, "Prix Unit. TTC"] == 0 and sell is not None:
                    df.at[idx, "Prix Unit. TTC"] = sell
                if df.at[idx, "Prix Achat TTC"] == 0 and buy is not None:
                    df.at[idx, "Prix Achat TTC"] = buy

    # Batterie pour scénario AVEC : Deyness, taille = puissance du système (en kWh)
    # Algo : 2×5kWh → 1×10kWh (consolidation), puis rajouter des 5kWh ou 10kWh si besoin
    import math
    
    mask_bat = df["Désignation"] == "Batterie"
    if mask_bat.any() and puissance_kwp > 0:
        # Find all Battery rows (first and potentially second)
        bat_indices = df[mask_bat].index.tolist()
        idx_bat_primary = bat_indices[0] if bat_indices else None
        idx_bat_secondary = bat_indices[1] if len(bat_indices) > 1 else None
        
        # Calculer le nombre de batteries 5kWh nécessaires
        nb_bat_5kwh = math.ceil(puissance_kwp / 5.0)
        # Consolidation : convertir 2×5kWh en 1×10kWh
        nb_bat_10kwh = nb_bat_5kwh // 2
        remaining_5kwh = nb_bat_5kwh % 2
        
        # Chercher Deyness 10kWh et 5kWh en priorité
        bat_dict = catalog.get("Batterie", {})
        dey_10_info = None
        dey_5_info = None
        
        for marque, vals in bat_dict.items():
            if marque == "__default__":
                continue
            if "deyness" in marque.lower():
                if "10" in marque and not dey_10_info:
                    dey_10_info = (marque, vals.get("sell_ttc"), vals.get("buy_ttc"))
                elif "5" in marque and not dey_5_info:
                    dey_5_info = (marque, vals.get("sell_ttc"), vals.get("buy_ttc"))
        
        # Fill primary battery row (10kWh)
        if idx_bat_primary is not None:
            if nb_bat_10kwh > 0 and dey_10_info:
                df.at[idx_bat_primary, "Marque"] = dey_10_info[0]
                df.at[idx_bat_primary, "Quantité"] = nb_bat_10kwh
                if df.at[idx_bat_primary, "Prix Unit. TTC"] == 0 and dey_10_info[1] is not None:
                    df.at[idx_bat_primary, "Prix Unit. TTC"] = dey_10_info[1]
                if df.at[idx_bat_primary, "Prix Achat TTC"] == 0 and dey_10_info[2] is not None:
                    df.at[idx_bat_primary, "Prix Achat TTC"] = dey_10_info[2]
            elif dey_5_info:
                # Fallback: use 5kWh if 10kWh not available
                df.at[idx_bat_primary, "Marque"] = dey_5_info[0]
                df.at[idx_bat_primary, "Quantité"] = nb_bat_5kwh
                if df.at[idx_bat_primary, "Prix Unit. TTC"] == 0 and dey_5_info[1] is not None:
                    df.at[idx_bat_primary, "Prix Unit. TTC"] = dey_5_info[1]
                if df.at[idx_bat_primary, "Prix Achat TTC"] == 0 and dey_5_info[2] is not None:
                    df.at[idx_bat_primary, "Prix Achat TTC"] = dey_5_info[2]
            else:
                # Last resort: fill with catalog default
                df.at[idx_bat_primary, "Quantité"] = max(1, nb_bat_10kwh or nb_bat_5kwh)
                sell, buy = get_prices(catalog, "Batterie", "")
                if df.at[idx_bat_primary, "Prix Unit. TTC"] == 0 and sell is not None:
                    df.at[idx_bat_primary, "Prix Unit. TTC"] = sell
                if df.at[idx_bat_primary, "Prix Achat TTC"] == 0 and buy is not None:
                    df.at[idx_bat_primary, "Prix Achat TTC"] = buy
        
        # Fill secondary battery row with remaining 5kWh (if exists and needed)
        if idx_bat_secondary is not None and remaining_5kwh > 0 and dey_5_info:
            df.at[idx_bat_secondary, "Marque"] = dey_5_info[0]
            df.at[idx_bat_secondary, "Quantité"] = remaining_5kwh
            if df.at[idx_bat_secondary, "Prix Unit. TTC"] == 0 and dey_5_info[1] is not None:
                df.at[idx_bat_secondary, "Prix Unit. TTC"] = dey_5_info[1]
            if df.at[idx_bat_secondary, "Prix Achat TTC"] == 0 and dey_5_info[2] is not None:
                df.at[idx_bat_secondary, "Prix Achat TTC"] = dey_5_info[2]

    return df

# ---------- PDF DOUBLE DEVIS ----------
def build_devis_section_elements(df, notes, styles, scenario_title):
    elements = []
    style_normal = styles["Normal"]
    style_normal.fontName = "Helvetica"
    style_normal.fontSize = 10
    style_normal.leading = 13
    style_normal.textColor = colors.HexColor(TEXT_DARK)
    style_normal.spaceAfter = 6

    style_header = ParagraphStyle(
        "header",
        parent=style_normal,
        fontSize=11,
        leading=13,
    )
    style_header_white = ParagraphStyle(
        "header_white",
        parent=style_header,
        textColor=colors.white,
        fontSize=9,
    )

    df = sanitize_df(df.copy())
    # Inclure toutes les lignes avec Quantité > 0, même si le prix est à 0.0
    # (L'utilisateur peut vouloir renseigner la quantité puis renseigner le prix manuellement;
    #  on doit afficher ces lignes et les compter dans le récapitulatif.)
    df = df[(df["Quantité"] > 0)].reset_index(drop=True)
    
    # Clean CustomLabel: Remove dict artifacts (from deserialization issues)
    if "CustomLabel" in df.columns:
        for idx, row in df.iterrows():
            custom_label = row.get("CustomLabel", "")
            # If CustomLabel is a dict, convert to empty string
            if isinstance(custom_label, dict):
                df.at[idx, "CustomLabel"] = ""
            # If it's a string containing only "nan", convert to empty string
            elif isinstance(custom_label, str) and custom_label.strip().lower() == "nan":
                df.at[idx, "CustomLabel"] = ""
    df["Prix Unit. HT"] = df["Prix Unit. TTC"] / (1 + df["TVA (%)"] / 100)
    df["Total HT"] = df["Prix Unit. HT"] * df["Quantité"]
    df["Total TTC"] = df["Prix Unit. TTC"] * df["Quantité"]
    total_ht, total_ttc = float(df["Total HT"].sum()), float(df["Total TTC"].sum())
    def fmt_money(val):
        try:
            v = float(val)
        except Exception:
            return str(val)
        return f"{v:,.2f}".replace(",", " ") + "\u00a0MAD"

    # Titre scénario (grand, encadré et coloré)
    title_style = ParagraphStyle("scenario_title", parent=style_normal, fontSize=14, leading=16, alignment=1)
    title_para = Paragraph(f"<b>{scenario_title}</b>", title_style)
    title_tbl = Table([[title_para]], colWidths=[480])
    title_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(BLUE_MAIN)),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor(BLUE_MAIN)),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(title_tbl)
    elements.append(Spacer(1, 6))

    header_row = [
        Paragraph("<b>Photo</b>", style_header_white),
        Paragraph("<b>Désignation</b>", style_header_white),
        Paragraph("<b>Spécifications techniques</b>", style_header_white),
        Paragraph("<b>Garantie</b>", style_header_white),
        Paragraph("<b>Qté</b>", style_header_white),
        Paragraph("<b>PU TTC (MAD)</b>", style_header_white),
        Paragraph("<b>Total TTC (MAD)</b>", style_header_white),
    ]
    data = [header_row]

    spec_map = {
        "smart meter": (
            "Compteur intelligent pour suivi et limitation de puissance",
            "2 ans",
        ),
        "wifi dongle": (
            "Communication et supervision à distance via application",
            "2 ans",
        ),
        "panneaux – canadian solar 710w": (
            "Modules 710 Wc, haute performance, technologie mono",
            "12 ans produit",
        ),
        "panneaux - canadian solar 710w": (
            "Modules 710 Wc, haute performance, technologie mono",
            "12 ans produit",
        ),
        "structures acier": (
            "Structure acier galvanisé adaptée à la toiture",
            "20 ans",
        ),
        "socles": (
            "Socles de support et lestage pour structure",
            "—",
        ),
        "accessoires": (
            "Câblage, connecteurs, protections AC/DC",
            "—",
        ),
        "tableau de protection ac/dc": (
            "Tableau de protection AC/DC complet",
            "—",
        ),
        "installation": (
            "Main d’œuvre, mise en service et tests",
            "Garantie de bonne exécution",
        ),
        "instalation": (
            "Main d’œuvre, mise en service et tests",
            "Garantie de bonne exécution",
        ),
        "transport": (
            "Acheminement du matériel jusqu’au site",
            "—",
        ),
        "batterie – deyness 5kwh": (
            "Batterie lithium 5 kWh pour stockage et secours",
            "10 ans",
        ),
        "batterie - deyness 5kwh": (
            "Batterie lithium 5 kWh pour stockage et secours",
            "10 ans",
        ),
        "onduleur réseau": (
            "Onduleur 5 kW monophasé haute efficacité",
            "10 ans",
        ),
        "onduleur rŽseau": (
            "Onduleur 5 kW monophasé haute efficacité",
            "10 ans",
        ),
        "onduleur rÇ¸seau": (
            "Onduleur 5 kW monophasé haute efficacité",
            "10 ans",
        ),
        "onduleur hybride": (
            "Onduleur 5 kW monophasé haute efficacité",
            "10 ans",
        ),
    }

    for _, r in df.iterrows():
        des = r["Désignation"]
        custom_label = r.get("CustomLabel", "")
        
        # Clean custom_label: remove dict, empty, or "nan" values
        if isinstance(custom_label, dict) or (isinstance(custom_label, str) and custom_label.strip().lower() in ("nan", "")):
            custom_label = ""
        
        # Determine designation text
        if isinstance(des, str) and des.startswith("Structures"):
            # For structures, prefer CustomLabel if it's valid, else use designation
            if custom_label and isinstance(custom_label, str) and custom_label.strip():
                des_txt = custom_label.strip()
            else:
                des_txt = des
        elif des == "Suivi journalier, maintenance chaque 12 mois pendent 2 ans":
            des_txt = "Suivi journalier<br/>Maintenance chaque 12 mois pendent 2 ans"
        else:
            des_txt = des

        # Add brand name for relevant items
        if r.get("Marque") and des in ("Onduleur réseau", "Onduleur hybride", "Panneaux", "Batterie"):
            des_txt = f"{des_txt} – {r['Marque']}"

        # Ensure we always pass a string to Paragraph (ReportLab fails on non-strings)
        if des_txt is None:
            des_txt = ""
        des_txt = str(des_txt).strip()
        des_cell = Paragraph(des_txt, style_normal)

        spec_txt = "—"
        garantie_txt = "—"
        des_key = des_txt.lower()
        if des_key in spec_map:
            spec_txt, garantie_txt = spec_map[des_key]
        elif "panneaux" in des_key:
            spec_txt = "Modules solaires haute performance"
            garantie_txt = "12 ans produit"
        elif "batterie" in des_key:
            spec_txt = "Batterie lithium pour stockage et secours"
            garantie_txt = "10 ans"
        elif "onduleur" in des_key:
            spec_txt = "Onduleur haute efficacité"
            garantie_txt = "10 ans"
        spec_cell = Paragraph(spec_txt, style_normal)
        garantie_cell = Paragraph(garantie_txt, style_normal)

        photo_key = ""
        if "PhotoKey" in r and isinstance(r["PhotoKey"], str):
            photo_key = r["PhotoKey"].strip()

        img_path = None
        if photo_key:
            img_path = get_dynamic_image(photo_key)
        if not img_path:
            img_path = get_first_existing_image(des)

        if img_path:
            img_cell = Image(img_path, width=45, height=45)
            img_cell.hAlign = "CENTER"
        else:
            img_cell = Table(
                [[Paragraph("Photo", style_small)]],
                colWidths=[45],
                rowHeights=[45],
                style=TableStyle(
                    [
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#777777")),
                    ]
                ),
            )

        data.append(
            [
                img_cell,
                des_cell,
                spec_cell,
                garantie_cell,
                int(r["Quantité"]),
                fmt_money(r["Prix Unit. TTC"]),
                fmt_money(r["Total TTC"]),
            ]
        )

    total_ht_lbl = Paragraph("<b>TOTAL HT</b>", style_normal)
    total_ttc_lbl = Paragraph("<b>TOTAL TTC</b>", style_normal)
    data.append(["", "", "", "", "", total_ht_lbl, fmt_money(total_ht)])
    data.append(["", "", "", "", "", total_ttc_lbl, fmt_money(total_ttc)])

    elements.append(Spacer(1, 12))

    def make_premium_table(data_table):
        table = Table(
            data_table,
            repeatRows=1,
        )

        last_row = len(data_table) - 1
        before_last_row = len(data_table) - 2
        body_end = before_last_row - 1

        style = TableStyle(
            [
                # Header styling
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BLUE_MAIN)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
                ("FONTSIZE", (0, 0), (-1, 0), 8.5),
                ("TOPPADDING", (0, 0), (-1, 0), 7),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
                ("LINEBELOW", (0, 0), (-1, 0), 1.0, colors.white),
                # Body styling
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#222222")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CCCCCC")),
                ("INNERGRID", (0, 1), (-1, -3), 0.3, colors.HexColor("#DDDDDD")),
                ("LEFTPADDING", (0, 1), (-1, -1), 6),
                ("RIGHTPADDING", (0, 1), (-1, -1), 6),
                ("TOPPADDING", (0, 1), (-1, -3), 5),
                ("BOTTOMPADDING", (0, 1), (-1, -3), 5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 1), (0, -1), "CENTER"),
                ("ALIGN", (1, 1), (2, -1), "LEFT"),
                ("ALIGN", (3, 1), (3, -3), "CENTER"),
                ("ALIGN", (4, 1), (4, -1), "RIGHT"),
                ("ALIGN", (5, 1), (5, -1), "RIGHT"),
                ("ALIGN", (6, 1), (6, -1), "RIGHT"),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("WORDWRAP", (1, 1), (2, -1), None),
            ]
        )

        if body_end >= 1:
            style.add(
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, body_end),
                (colors.white, colors.HexColor(BLUE_LIGHT)),
            )

        style.add("SPAN", (0, before_last_row), (5, before_last_row))
        style.add("SPAN", (0, last_row), (5, last_row))
        style.add("BACKGROUND", (0, before_last_row), (-1, last_row), colors.whitesmoke)
        style.add("FONTNAME", (0, before_last_row), (-1, last_row), "Helvetica-Bold")
        style.add("LINEABOVE", (0, before_last_row), (-1, before_last_row), 1, colors.HexColor(TEXT_DARK))
        style.add("TOPPADDING", (0, before_last_row), (-1, last_row), 6)
        style.add("BOTTOMPADDING", (0, before_last_row), (-1, last_row), 6)

        table.setStyle(style)
        table._argW = [
            1.6 * cm,  # Photo
            4.6 * cm,  # Désignation
            4.6 * cm,  # Spécifications techniques
            2.4 * cm,  # Garantie
            1.1 * cm,  # Quantité
            2.7 * cm,  # Prix Unit
            2.7 * cm,  # Total TTC
        ]
        return table

    table = make_premium_table(data)
    elements += [table, Spacer(1, 12)]

    # Notes
    if notes:
        clean_notes = [n.strip() for n in notes if isinstance(n, str) and n.strip()]
        if clean_notes:
            elements.append(Paragraph("<b>Notes :</b>", style_normal))
            elements.append(Spacer(1, 4))
            for n in clean_notes:
                safe_n = n.replace("<", "&lt;").replace(">", "&gt;")
                elements.append(Paragraph(f"- {safe_n}", style_normal))
                elements.append(Spacer(1, 2))
            elements.append(Spacer(1, 8))

    return elements, total_ttc

def generate_double_devis_pdf(
    df_sans,
    df_avec,
    notes_sans,
    notes_avec,
    client_name,
    client_address,
    client_phone,
    doc_type,
    doc_number,
    roi_summary_sans,
    roi_summary_avec,
    roi_fig_all_buf,
    scenario_choice,
    recommended_option=None,
):
    safe_client = re.sub(r"[^A-Za-z0-9]", "_", client_name or "Client")
    file_name = f"{doc_type}_{safe_client}_{int(doc_number)}.pdf"
    pdf_path = DEVIS_DIR / file_name

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=56,  # ~2 cm
        leftMargin=56,   # ~2 cm
        topMargin=50,
        bottomMargin=45,
    )
    elements = []
    styles = getSampleStyleSheet()
    style_normal = ParagraphStyle(
        "body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor(TEXT_DARK),
        spaceAfter=6,
    )
    style_body = style_normal
    style_small = ParagraphStyle(
        "small",
        parent=style_body,
        fontSize=9,
        leading=11,
    )
    style_bullet = ParagraphStyle(
        "bullet",
        parent=style_body,
        leftIndent=14,
        bulletIndent=0,
        spaceAfter=4,
    )
    style_h1 = ParagraphStyle(
        "style_h1",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=21,
        textColor=colors.HexColor(BLUE_MAIN),
        spaceBefore=18,
        spaceAfter=8,
        alignment=0,
    )
    style_h2 = ParagraphStyle(
        "style_h2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13.5,
        leading=17,
        textColor=colors.HexColor(TEXT_DARK),
        spaceBefore=12,
        spaceAfter=6,
        alignment=0,
    )
    style_company = ParagraphStyle(
        "company",
        parent=style_body,
        fontSize=9,
        leading=14,
    )
    style_header_top = ParagraphStyle(
        "header_top",
        parent=style_normal,
        fontSize=11,
        leading=13,
    )
    cover_title_style = ParagraphStyle(
        "cover_title_style",
        parent=styles["Heading1"],
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#0A5275"),
        alignment=0,
    )

    cover_subtitle_style = ParagraphStyle(
        "cover_subtitle_style",
        parent=styles["Normal"],
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#555555"),
        alignment=0,
    )

    cover_label_style = ParagraphStyle(
        "cover_label_style",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#777777"),
        uppercase=True,
    )

    cover_value_style = ParagraphStyle(
        "cover_value_style",
        parent=styles["Normal"],
        fontSize=11,
        leading=13,
        textColor=colors.HexColor("#222222"),
        spaceAfter=2,
    )

    today = datetime.now().strftime("%d/%m/%Y")
    # Panel metrics for hero chips and summaries
    def _extract_panel_power(value):
        try:
            s = str(value)
        except Exception:
            return 0
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*[wW]", s)
        if m:
            try:
                return int(float(m.group(1).replace(",", ".")))
            except Exception:
                return 0
        try:
            return int(float(re.sub(r"[^0-9.,]", "", s).replace(",", ".")))
        except Exception:
            return 0

    def _panels_info(df_obj):
        total_qty = 0
        watt = 0
        if isinstance(df_obj, pd.DataFrame):
            try:
                mask = df_obj["Désignation"] == "Panneaux"
                if mask.any():
                    panneaux_rows = df_obj[mask]
                    total_qty = int(panneaux_rows["Quantité"].sum())
                    first_row = panneaux_rows.iloc[0]
                    power_candidate = first_row.get("Power", None)
                    if power_candidate in (None, ""):
                        power_candidate = first_row.get("Marque", "")
                    watt = _extract_panel_power(power_candidate)
            except Exception:
                pass
        elif isinstance(df_obj, list):
            for row_data in df_obj:
                if isinstance(row_data, dict) and row_data.get("Désignation") == "Panneaux":
                    total_qty += int(row_data.get("Quantité", 0) or 0)
                    if watt == 0:
                        power_candidate = row_data.get("Power", row_data.get("Marque", ""))
                        watt = _extract_panel_power(power_candidate)
        return total_qty, watt

    nombre_panneaux, puissance_panneau = _panels_info(df_sans)
    if nombre_panneaux == 0 and isinstance(df_avec, (pd.DataFrame, list)):
        nb_alt, power_alt = _panels_info(df_avec)
        if nb_alt:
            nombre_panneaux = nb_alt
        if puissance_panneau == 0:
            puissance_panneau = power_alt
    puissance_totale_kwc = round(nombre_panneaux * puissance_panneau / 1000, 2) if puissance_panneau else 0.0
    
    # ========== PAGE 1 : PRÉSENTATION DU PROJET ==========
    heading_style = style_h1
    heading2_for_intro = style_h1

    # --- PREMIUM HEADER BAR (PAGE 1 ONLY) ---
    if "LOGO_PATH" in globals() and LOGO_PATH.exists():
        logo = Image(str(LOGO_PATH), width=120)
    else:
        logo = Image("taqinor_logo.png", width=120)
    # Preserve aspect ratio
    try:
        logo.drawHeight = logo.drawWidth * logo.imageHeight / logo.imageWidth
    except Exception:
        pass

    contact_para = Paragraph(
        "TAQINOR Solutions — contact@taqinor.com — +212 6 61 85 04 10",
        ParagraphStyle(
            "contact_line",
            parent=style_small,
            fontSize=8,
            leading=10,
            textColor=colors.HexColor(TEXT_DARK),
        ),
    )
    logo_row = Table([[logo, contact_para]], colWidths=[140, 340])
    logo_row.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BLUE_LIGHT)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "LEFT"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(logo_row)
    elements.append(Spacer(1, 12))

    title_para = Paragraph("Devis Installation Photovoltaïque", cover_title_style)
    subtitle_para = Paragraph(
        "<i>Solution premium et sur-mesure pour votre autonomie énergétique</i>",
        cover_subtitle_style,
    )

    right_block = Table(
        [[title_para], [subtitle_para]],
        colWidths=[380],
    )
    right_block.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    hero_table = Table([[right_block]], colWidths=[480], hAlign="CENTER")
    hero_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#E6F1F7")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#0A5275")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )

    elements.append(hero_table)
    elements.append(Spacer(1, 12))

    # --- SUMMARY BOX (CLIENT & PROJET) ---
    summary_label_style = ParagraphStyle(
        "summary_label",
        parent=style_normal,
        fontSize=9,
        leading=11,
        textColor=colors.HexColor(TEXT_DARK),
        fontName="Helvetica-Bold",
    )
    summary_value_style = ParagraphStyle(
        "summary_value",
        parent=style_normal,
        fontSize=9,
        leading=11,
        textColor=colors.HexColor(TEXT_DARK),
    )

    config_text = f"{nombre_panneaux} x {puissance_panneau} W"
    summary_rows = [
        [Paragraph("Client", summary_label_style), Paragraph(client_name or "-", summary_value_style)],
        [Paragraph("Adresse", summary_label_style), Paragraph(client_address or "-", summary_value_style)],
        [Paragraph("Téléphone", summary_label_style), Paragraph(client_phone or "-", summary_value_style)],
        [Paragraph("Numéro du devis", summary_label_style), Paragraph(f"{int(doc_number)}", summary_value_style)],
        [Paragraph("Date d’émission", summary_label_style), Paragraph(today, summary_value_style)],
        [Paragraph("Puissance totale installée", summary_label_style), Paragraph(f"{puissance_totale_kwc:.2f} kWc", summary_value_style)],
        [Paragraph("Configuration proposée", summary_label_style), Paragraph(config_text, summary_value_style)],
    ]

    summary_table = Table(summary_rows, colWidths=[180, 300], hAlign="CENTER")
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(BLUE_LIGHT)),
                ("BOX", (0, 0), (-1, -1), 1.0, colors.HexColor(BLUE_MAIN)),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D5E6F2")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    elements.append(Spacer(1, 12))
    elements.append(summary_table)
    elements.append(Spacer(1, 12))

    # RÉSUMÉ DU PROJET
    heading1_style = style_h1
    heading2_style = style_h2
    heading3_style = style_h2
    def ensure_page_break():
        if not elements or not isinstance(elements[-1], PageBreak):
            elements.append(PageBreak())
    def add_divider():
        line = Drawing(480, 1)
        line.add(Line(0, 0, 480, 0, strokeColor=colors.HexColor("#E0E0E0"), strokeWidth=0.7))
        elements.append(line)
    
    # heading style already adds top spacing
    elements.append(Paragraph("RÉSUMÉ EXÉCUTIF", heading1_style))
    elements.append(Spacer(1, 8))
    elements.append(
        Paragraph(
            "Ce devis présente une solution photovoltaïque sur mesure visant à réduire durablement votre facture d’électricité, améliorer votre autonomie énergétique et valoriser votre patrimoine. L’installation proposée repose sur des équipements premium (Canadian Solar, Huawei, Deye) et s’adapte à votre profil de consommation afin de maximiser votre taux d’autoconsommation et votre retour sur investissement.",
            style_normal,
        )
    )
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("L’étude ci-dessous inclut :", heading1_style))
    bullet_intro = [
        f"Une configuration de {nombre_panneaux} panneaux de {puissance_panneau} W (puissance totale {puissance_totale_kwc:.2f} kWc)",
        "Une analyse comparative entre une installation SANS batterie et une installation AVEC batterie",
        "Une estimation économique complète (production annuelle, économies, ROI)",
        "Les garanties et engagements TAQINOR",
    ]
    elements.append(
        ListFlowable(
            [ListItem(Paragraph(txt, style_bullet)) for txt in bullet_intro],
            bulletType="bullet",
            bulletText="•",
            leftIndent=14,
        )
    )
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("OBJECTIFS DU CLIENT", heading1_style))
    elements.append(Spacer(1, 8))
    client_objectifs = [
        "Réduire significativement la facture d’électricité mensuelle",
        "Gagner en confort et en sécurité énergétique en cas de coupure",
        "Préserver la possibilité d’une évolution future (batterie, puissance supplémentaire)",
    ]
    elements.append(
        ListFlowable(
            [ListItem(Paragraph(txt, style_bullet)) for txt in client_objectifs],
            bulletType="bullet",
            bulletText="•",
            leftIndent=14,
        )
    )
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("CONFIGURATION RECOMMANDÉE", heading1_style))
    elements.append(Spacer(1, 8))
    elements.append(
        Paragraph(
            f"TAQINOR propose deux configurations optimisées : une installation SANS batterie, privilégiant le meilleur retour sur investissement, et une installation AVEC batterie, offrant davantage de confort et d’autonomie lors des coupures réseau. Les deux scénarios reposent sur une puissance totale installée de {puissance_totale_kwc:.2f} kWc via {nombre_panneaux} modules de {puissance_panneau} W.",
            style_normal,
        )
    )
    elements.append(Spacer(1, 6))

    # ========== PAGE 2 : OPTION SANS BATTERIE ==========
    # SECTION SANS
    options_heading_shown = False
    if scenario_choice in ("Sans batterie uniquement", "Les deux (Sans + Avec)"):
        elements.append(PageBreak())
        if not options_heading_shown:
            elements.append(Spacer(1, 12))
            add_divider()
            elements.append(Spacer(1, 6))
            elements.append(Paragraph("PRÉSENTATION DES OPTIONS", heading1_style))
            elements.append(Spacer(1, 8))
            options_heading_shown = True
        elements.append(Paragraph("Option 1 : Installation SANS batterie", heading3_style))
        elements.append(Spacer(1, 6))
        elements.append(Paragraph("Solution optimisée pour le meilleur retour sur investissement.", style_normal))
        elements.append(Spacer(1, 6))
        elements.append(
            Paragraph(
                "Cette configuration est idéale si votre objectif principal est de réduire votre facture au meilleur coût initial.<br/>"
                "Elle offre le meilleur retour sur investissement car toute l’énergie produite est directement utilisée par votre foyer.",
                style_normal,
            )
        )
        elements.append(Spacer(1, 8))
        
        sec_sans, total_sans = build_devis_section_elements(
            df_sans, notes_sans, styles, "Devis SANS batterie"
        )
        elements += sec_sans
        elements.append(Spacer(1, 12))

    # ========== PAGE 3 : OPTION AVEC BATTERIE ==========
    # SECTION AVEC
    if scenario_choice in ("Avec batterie uniquement", "Les deux (Sans + Avec)"):
        elements.append(PageBreak())
        if not options_heading_shown:
            elements.append(Spacer(1, 12))
            add_divider()
            elements.append(Spacer(1, 6))
            elements.append(Paragraph("PRÉSENTATION DES OPTIONS", heading1_style))
            elements.append(Spacer(1, 8))
            options_heading_shown = True
        elements.append(Paragraph("Option 2 : Installation AVEC batterie", heading3_style))
        elements.append(Spacer(1, 6))
        elements.append(Paragraph("Solution orientée confort et autonomie grâce à la batterie.", style_normal))
        elements.append(Spacer(1, 6))
        elements.append(
            Paragraph(
                "Cette option apporte un confort supérieur grâce au stockage d’énergie.<br/>"
                "Elle assure une autonomie en cas de coupure, optimise la consommation nocturne et augmente votre taux d’autoconsommation globale.",
                style_normal,
            )
        )
        elements.append(Spacer(1, 8))
        
        sec_avec, total_avec = build_devis_section_elements(
            df_avec, notes_avec, styles, "Devis AVEC batterie"
        )
        elements += sec_avec
        elements.append(Spacer(1, 12))

    # ========== PAGE 4 : ANALYSE ÉCONOMIQUE ET ROI ==========
    # PAGE ROI GRAPHIQUE
    if roi_fig_all_buf is not None:
        elements.append(Spacer(1, 12))
        add_divider()
        elements.append(Spacer(1, 6))
        elements.append(Paragraph("SYNTHÈSE FINANCIÈRE & ROI", heading1_style))
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("Analyse détaillée du retour sur investissement", heading2_style))
        elements.append(Spacer(1, 8))

        def fmt_nb(val, suffix=""):
            try:
                v = float(val)
            except Exception:
                return "—"
            return f"{v:,.2f}".replace(",", " ") + (f" {suffix}" if suffix else "")

        def fmt_int(val, suffix=""):
            try:
                v = float(val)
            except Exception:
                return "—"
            return f"{v:,.0f}".replace(",", " ") + (f" {suffix}" if suffix else "")

        sans_prod = fmt_int(roi_summary_sans.get("prod_annuelle", 0.0) if roi_summary_sans else "—", "kWh/an")
        sans_eco = fmt_int(roi_summary_sans.get("eco_annuelle", 0.0) if roi_summary_sans else "—", "MAD/an")
        sans_inv = fmt_int(roi_summary_sans.get("cout_systeme", 0.0) if roi_summary_sans else "—", "MAD")
        sans_payback = fmt_nb(roi_summary_sans.get("payback") if roi_summary_sans else "—", "années") if roi_summary_sans and roi_summary_sans.get("payback") is not None else "—"

        avec_prod = fmt_int(roi_summary_avec.get("prod_annuelle", 0.0) if roi_summary_avec else "—", "kWh/an")
        avec_eco = fmt_int(roi_summary_avec.get("eco_annuelle", 0.0) if roi_summary_avec else "—", "MAD/an")
        avec_inv = fmt_int(roi_summary_avec.get("cout_systeme", 0.0) if roi_summary_avec else "—", "MAD")
        avec_payback = fmt_nb(roi_summary_avec.get("payback") if roi_summary_avec else "—", "années") if roi_summary_avec and roi_summary_avec.get("payback") is not None else "—"

        puissance_sans = f"{puissance_totale_kwc:.2f} kWc"
        puissance_avec = puissance_sans

        summary_rows = [
            ["Puissance installée", puissance_sans, puissance_avec],
            ["Investissement TTC", sans_inv, avec_inv],
            ["Production annuelle estimée", sans_prod, avec_prod],
            ["Économie annuelle estimée", sans_eco, avec_eco],
            ["Temps de retour sur investissement", sans_payback, avec_payback],
        ]
        summary_table = Table(
            [
                [
                    Paragraph("", style_normal),
                    Paragraph("<b>Scénario SANS batterie</b>", style_header_top),
                    Paragraph("<b>Scénario AVEC batterie</b>", style_header_top),
                ]
            ]
            + [[Paragraph(label, style_normal), Paragraph(val_s, style_normal), Paragraph(val_a, style_normal)] for label, val_s, val_a in summary_rows],
            colWidths=[210, 135, 135],
            hAlign="CENTER",
        )
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BLUE_MAIN)),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, 0), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(BLUE_MAIN)),
                    ("INNERGRID", (0, 1), (-1, -1), 0.3, colors.HexColor("#D5E6F2")),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), (colors.white, colors.HexColor(BLUE_LIGHT))),
                    ("LEFTPADDING", (0, 1), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 1), (-1, -1), 6),
                    ("TOPPADDING", (0, 1), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ]
            )
        )
        elements.append(summary_table)
        elements.append(Spacer(1, 12))

        # Recommandation encadrée (affichée uniquement si sélectionnée)
        if recommended_option and recommended_option.lower() not in ("aucune recommandation", "aucune recommandation (client libre de choisir)"):
            reco_label = f"Recommandation TAQINOR : {recommended_option}"
            reco_text = Paragraph(f"<b>{reco_label}</b>", style_normal)
            reco_tbl = Table([[reco_text]], colWidths=[480], hAlign="CENTER")
            reco_tbl.setStyle(
                TableStyle(
                    [
                        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor(BLUE_MAIN)),
                        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            elements.append(reco_tbl)
            elements.append(Spacer(1, 10))

        elements.append(Paragraph("<b>Estimation des économies mensuelles</b>", style_header_top))
        elements.append(Spacer(1, 6))
        roi_fig_all_buf.seek(0)
        elements.append(Image(roi_fig_all_buf, width=360, height=200))
        elements.append(Spacer(1, 6))
        elements.append(Paragraph("Comparaison des économies mensuelles avec et sans batterie.", style_normal))
        elements.append(Spacer(1, 10))

        # Hypothèses de calcul & profil de consommation
        elements.append(Paragraph("Hypothèses de calcul & profil de consommation", heading2_style if "heading2_style" in locals() else heading_style))
        elements.append(Spacer(1, 6))
        hypotheses_items = [
            "Tarif SRM/LYDEC/ONEE en vigueur au moment de l’étude.",
            "Profil de consommation basé sur vos dernières factures (ajustable).",
            "Production estimée selon irradiation locale, orientation et inclinaison.",
            "Rendement système réaliste avec pertes usuelles.",
            "Taux d’autoconsommation estimé selon votre profil horaire.",
            "Durée de vie considérée 20–25 ans (remplacement onduleur éventuel).",
            "Évolutions tarifaires futures non intégrées (pourraient améliorer le ROI).",
        ]
        elements.append(
            ListFlowable(
                [ListItem(Paragraph(item, style_bullet)) for item in hypotheses_items],
                bulletType="bullet",
                bulletText="•",
                leftIndent=14,
            )
        )
        elements.append(Spacer(1, 16))

    # ========== PAGE 5 : GARANTIES ET POURQUOI TAQINOR ==========
    ensure_page_break()
    elements.append(Spacer(1, 12))
    add_divider()
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("GARANTIES & CONDITIONS GÉNÉRALES", heading1_style))
    elements.append(Spacer(1, 8))
    
    # Section Garanties
    elements.append(Paragraph("<b>Couverture de garantie</b>", style_header_top))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("<b>Tous nos équipements sont garantis au minimum 10 ans.</b>", style_normal))
    elements.append(Spacer(1, 8))
    
    warranty_points = [
        "Onduleurs Huawei et Deye : 10 ans de garantie constructeur",
        "Panneaux solaires Canadian Solar : 12 ans de garantie",
    ]
    
    # Détecter le type de structure utilisé dans les deux scénarios (préférence aluminium si présent)
    struct_used = None
    for df_check in (df_sans, df_avec):
        try:
            for _, rr in pd.DataFrame(df_check).iterrows():
                des = rr.get("Désignation", "")
                qty = int(rr.get("Quantité", 0) or 0)
                custom = str(rr.get("CustomLabel", "")).lower().strip()
                if qty > 0:
                    des_lower = str(des).lower() if des else ""
                    # Check both designation and CustomLabel for structure type
                    if "structures" in des_lower:
                        if "aluminium" in des_lower or "aluminium" in custom:
                            struct_used = "aluminium"
                            break
                        elif "acier" in des_lower or "acier" in custom:
                            struct_used = "acier"
                            break
        except Exception:
            continue
        # Stop if we found aluminium (preference for aluminium)
        if struct_used == "aluminium":
            break
    
    if struct_used == "aluminium":
        warranty_points.append("Structures en aluminium : 25 ans de garantie")
    elif struct_used == "acier":
        warranty_points.append("Structures en acier galvanisé : 20 ans de garantie")
    else:
        warranty_points.append("Structures : garantie selon type utilisé (acier galvanisé 20 ans ou aluminium 25 ans)")
    
    elements.append(
        ListFlowable(
            [ListItem(Paragraph(item, style_bullet)) for item in warranty_points],
            bulletType="bullet",
            bulletText="•",
            leftIndent=14,
        )
    )
    elements.append(Spacer(1, 12))
    
    # Section Conditions
    elements.append(Paragraph("<b>Conditions générales</b>", style_header_top))
    elements.append(Spacer(1, 6))
    elements.append(
        Paragraph(
            "Les conditions ci-dessous définissent le cadre contractuel de l’offre TAQINOR pour votre installation photovoltaïque.",
            style_normal,
        )
    )
    elements.append(Spacer(1, 6))
    
    conditions = [
        "Ce devis est valable <b>30 jours</b> à compter de sa date d'émission",
        "Toute commande implique l'adhésion sans réserve à nos conditions générales de vente",
        "Les prix indiqués incluent la TVA 20%",
        "La réalisation de ces travaux ne peut débuter sans signature du devis",
    ]
    elements.append(
        ListFlowable(
            [ListItem(Paragraph(item, style_bullet)) for item in conditions],
            bulletType="bullet",
            bulletText="•",
            leftIndent=14,
        )
    )
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Conditions financières & modalités de paiement", heading3_style if "heading3_style" in locals() else heading_style))
    elements.append(Spacer(1, 4))
    conditions_financieres_items = [
        "Un acompte de 30% du montant TTC est demandé à la commande pour lancer l’approvisionnement du matériel.",
        "Le solde de 70% est à régler à la fin de la pose, des tests fonctionnels et de la mise en service.",
        "Toute modification significative du projet (changement de matériel, modification de surface disponible, contraintes techniques particulières) pourra entraîner une révision du devis.",
        "Les paiements peuvent être effectués par virement bancaire ou par tout autre moyen accepté par TAQINOR et précisé sur la facture."
    ]
    conditions_financieres_list = ListFlowable(
        [ListItem(Paragraph(item, style_bullet)) for item in conditions_financieres_items],
        bulletType="bullet",
        bulletText="•",
        leftIndent=14,
    )
    elements.append(conditions_financieres_list)
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Délai indicatif de réalisation", heading3_style if "heading3_style" in locals() else heading_style))
    elements.append(Spacer(1, 4))
    delai_text = (
        "Sous réserve de disponibilité du matériel et de conditions météorologiques favorables, le délai indicatif de "
        "réalisation de l’installation est de 7 à 14 jours ouvrés à compter de la réception de l’acompte et de la "
        "validation définitive du projet. Ce délai pourra être affiné lors de la planification et confirmé par écrit."
    )
    elements.append(Paragraph(delai_text, style_normal))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Périmètre de la prestation, exclusions & prérequis", heading3_style if "heading3_style" in locals() else heading_style))
    elements.append(Spacer(1, 4))
    perimetre_items = [
        "Le présent devis inclut : la fourniture du matériel décrit, la pose des panneaux et des structures, le câblage AC/DC courant, le raccordement jusqu’au tableau électrique existant, la mise en service et la configuration de la supervision.",
        "Sont exclus sauf mention expresse : les travaux de maçonnerie, de renforcement de charpente ou de toiture, la mise aux normes complète de l’installation électrique existante, la création de longues tranchées ou gaines au-delà d’un linéaire standard, ainsi que toute autorisation administrative ou copropriété non spécifiée.",
        "Le client s’engage à garantir l’accès sécurisé au site (toiture, local technique, tableau électrique) pendant toute la durée du chantier.",
        "Toute contrainte découverte lors de la visite technique (toiture fragile, accès compliqué, non-conformité électrique majeure, etc.) pourra faire l’objet d’un avenant de devis avant démarrage des travaux."
    ]
    perimetre_list = ListFlowable(
        [ListItem(Paragraph(item, style_bullet)) for item in perimetre_items],
        bulletType="bullet",
        bulletText="•",
        leftIndent=14,
    )
    elements.append(perimetre_list)
    elements.append(Spacer(1, 12))
    
    # Page Pourquoi TAQINOR
    ensure_page_break()
    elements.append(Spacer(1, 12))
    add_divider()
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("POURQUOI CHOISIR TAQINOR ?", heading1_style))
    elements.append(Spacer(1, 8))
    pourquoi_lines = [
        "Installation réalisée par des ingénieurs spécialisés dans le solaire",
        "Matériel premium : Huawei, Deye, Canadian Solar",
        "Service après-vente disponible 7j/7 (WhatsApp & téléphone)",
        "Installation propre, sécurisée et conforme aux normes",
        "Optimisation anti-injection quand nécessaire",
        "Suivi de production en temps réel via application mobile",
        "Possibilité d’évolution future de l’installation",
    ]
    elements.append(
        ListFlowable(
            [ListItem(Paragraph(line, style_bullet)) for line in pourquoi_lines],
            bulletType="bullet",
            bulletText="•",
            leftIndent=14,
        )
    )
    elements.append(Spacer(1, 10))
    elements.append(
        Paragraph(
            "Notre équipe reste à votre disposition pour toute question complémentaire ou adaptation de cette proposition. La planification de l’installation sera effectuée dès validation du devis et organisation logistique avec le client.",
            style_normal,
        )
    )
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Étapes suivantes", heading1_style))
    elements.append(Spacer(1, 6))
    elements.append(
        Paragraph(
            "Pour valider ce devis, merci de nous retourner ce document signé ou de nous confirmer par e-mail / WhatsApp. Nous planifierons ensuite la visite technique et la date d’installation.",
            style_normal,
        )
    )
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("Signature du client : ___________________________    Date : ___ / ___ / ______", style_normal))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("Signature TAQINOR : ___________________________    Date : ___ / ___ / ______", style_normal))
    elements.append(Spacer(1, 12))

    # Footer on every page
    class NumberedCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            page_count = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self.draw_footer(page_count)
                super().showPage()
            super().save()

        def draw_footer(self, page_count):
            width, height = A4
            self.setStrokeColor(colors.HexColor("#E5E5E5"))
            self.setLineWidth(0.5)
            self.line(20 * mm, 14 * mm, width - 20 * mm, 14 * mm)

            left_text = "TAQINOR Solutions — contact@taqinor.com — +212 6 61 85 04 10"
            right_text = f"Page {self._pageNumber} / {page_count}"

            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor(TEXT_DARK))
            self.drawString(20 * mm, 8 * mm, left_text)
            self.drawRightString(width - 20 * mm, 8 * mm, right_text)

    doc.build(elements, canvasmaker=NumberedCanvas)
    return pdf_path

# ---------- PDF FACTURE SIMPLE ----------
def generate_single_pdf(df_in, client_name, client_address, client_phone,
                        doc_type, doc_number, notes):
    safe_client = re.sub(r"[^A-Za-z0-9]", "_", client_name or "Client")
    file_name = f"{doc_type}_{safe_client}_{int(doc_number)}.pdf"
    pdf_path = FACTURES_DIR / file_name

    # on réutilise le double devis mais avec un seul scénario sans ROI ni graph
    df_dummy_avec = pd.DataFrame(columns=df_in.columns)
    roi_buf = None
    pdf_path_final = generate_double_devis_pdf(
        df_sans=df_in,
        df_avec=df_dummy_avec,
        notes_sans=notes,
        notes_avec=[],
        client_name=client_name,
        client_address=client_address,
        client_phone=client_phone,
        doc_type=doc_type,
        doc_number=doc_number,
        roi_summary_sans=None,
        roi_summary_avec=None,
        roi_fig_all_buf=roi_buf,
        scenario_choice="Sans batterie uniquement",
        recommended_option=None,
    )
    return pdf_path_final, file_name

# ---------- STREAMLIT UI ----------
st.title("📄 Générateur de Devis & ROI — TAQINOR")

with st.sidebar.expander("📚 Mémoire des prix"):
    st.json(load_catalog())

mode = st.radio("Action :", ["Créer un Devis (1 ou 2 scénarios)", "Transformer un Devis en Facture"])

def line_editor(designation, label, default_qty, default_tva, catalog,
                custom_label=None, default_photo_key=None,
                default_brand=None, default_sell=None, default_buy=None,
                brand_only=False, default_power=None, default_phase=None):
    st.markdown(f"##### {label}")
    
    # For onduleurs, use special 3-column layout (Marque / Puissance / Phase)
    if designation in ("Onduleur réseau", "Onduleur hybride"):
        cols_ondu = st.columns([1.2, 1.0, 1.0, 0.8, 1.0, 1.0, 0.8])
        base_key = _catalog_key_for_designation(designation)

        # If autofill previously stored preferred onduleur choices in session_state,
        # copy them into the widget keys so the selectboxes reflect the autofill.
        # Only set these values if the widget keys don't already exist to avoid
        # overwriting user edits on each rerun.
        widget_brand_key = f"sel_brand_{designation}_{label}"
        widget_power_key = f"sel_power_{designation}_{label}"
        widget_phase_key = f"sel_phase_{designation}_{label}"

        if designation == "Onduleur réseau":
            pref_brand = st.session_state.get("ondu_res_brand")



            pref_power = st.session_state.get("ondu_res_power")
            pref_phase = st.session_state.get("ondu_res_phase")
        else:
            pref_brand = st.session_state.get("ondu_hyb_brand")
            pref_power = st.session_state.get("ondu_hyb_power")
            pref_phase = st.session_state.get("ondu_hyb_phase")

        try:
            force_cnt = int(st.session_state.get("force_autofill_update_count", 0) or 0)
        except Exception:
            force_cnt = 0
        try:
            if pref_brand and (widget_brand_key not in st.session_state or force_cnt > 0):
                st.session_state[widget_brand_key] = pref_brand
        except Exception:
            pass
        try:
            if pref_power is not None and (widget_power_key not in st.session_state or force_cnt > 0):
                # selectbox displays numeric powers as e.g. '10 kW'
                try:
                    power_display = f"{float(pref_power):g} kW"
                except Exception:
                    power_display = str(pref_power)
                st.session_state[widget_power_key] = power_display
        except Exception:
            pass
        try:
            if pref_phase and (widget_phase_key not in st.session_state or force_cnt > 0):
                st.session_state[widget_phase_key] = pref_phase
        except Exception:
            pass
        # If we consumed a forced update, decrement the counter so only the
        # two onduleur editors consume it.
        try:
            if force_cnt > 0:
                st.session_state["force_autofill_update_count"] = max(0, force_cnt - 1)
        except Exception:
            pass

        # Allow adding a new brand/model directly from the onduleur editor.
        # Put these controls into a small expander so they don't clutter the UI.
        catalog_load = load_catalog()
        with cols_ondu[0].expander("Ajouter une nouvelle marque / modèle au catalogue", expanded=False):
            new_brand_input = st.text_input("Nouvelle marque (laisser vide si non)", value="", key=f"new_brand_{designation}_{label}")
            new_power_input = st.number_input("Puissance (kW)", min_value=0.0, step=0.1, value=0.0, key=f"new_power_{designation}_{label}")
            new_phase_input = st.selectbox("Phase", ["Monophase", "Triphase", "Autre"], key=f"new_phase_choice_{designation}_{label}")
            new_phase_other = ""
            if new_phase_input == "Autre":
                new_phase_other = st.text_input("Préciser la phase", key=f"new_phase_other_{designation}_{label}")
            new_sell = st.number_input("Prix Unit. TTC (nouveau)", min_value=0.0, step=1.0, value=0.0, key=f"new_sell_{designation}_{label}")
            new_buy = st.number_input("Prix Achat TTC (nouveau)", min_value=0.0, step=1.0, value=0.0, key=f"new_buy_{designation}_{label}")
            if st.button("Ajouter au catalogue", key=f"btn_add_{designation}_{label}"):
                nb_added = 0
                if new_brand_input and new_power_input > 0:
                    phase_to_use = new_phase_other.strip() if new_phase_input == "Autre" and new_phase_other else new_phase_input
                    # Persist the new model into the catalog
                    try:
                        set_prices(catalog_load, designation, new_brand_input.strip(), new_sell or None, new_buy or None, power_key=str(int(new_power_input) if float(new_power_input).is_integer() else str(new_power_input)), phase=phase_to_use or None)
                        st.success(f"Modèle {new_brand_input} {new_power_input} kW ({phase_to_use}) ajouté au catalogue.")
                        # ensure next render shows the new selection
                        st.session_state[widget_brand_key] = new_brand_input.strip()
                        st.session_state[widget_power_key] = f"{float(new_power_input):g} kW"
                        if phase_to_use:
                            st.session_state[widget_phase_key] = phase_to_use
                        nb_added = 1
                    except Exception as e:
                        st.error(f"Impossible d'ajouter au catalogue: {e}")
                else:
                    st.warning("Veuillez renseigner une nouvelle marque et une puissance > 0.")
                if nb_added:
                    # reload catalog variable for immediate use below
                    catalog_load = load_catalog()
        
        # Col 0: Marque (dropdown from catalog)
        available_brands = get_onduleur_brands(load_catalog(), base_key)
        default_brand_idx = 0
        if default_brand and default_brand in available_brands:
            default_brand_idx = available_brands.index(default_brand)
        brand_final = cols_ondu[0].selectbox(
            "Marque",
            available_brands,
            index=default_brand_idx,
            key=f"sel_brand_{designation}_{label}"
        )
        
        # Get available powers for this brand (keys may include phase suffixes like '10_Monophase')
        catalog_load = load_catalog()
        powers_phases = get_onduleur_powers_and_phases(catalog_load, base_key, brand_final) if brand_final else {}

        # Group keys by numeric power: {num: [(key, phase), ...]}
        powers_grouped = {}
        for k, ph in powers_phases.items():
            m = re.search(r"(\d+(?:[.,]\d+)?)", str(k))
            if m:
                try:
                    num = float(m.group(1).replace(",", "."))
                except Exception:
                    num = None
            else:
                num = None
            if isinstance(ph, (list, tuple)):
                for single_ph in ph:
                    if num is None:
                        powers_grouped.setdefault(None, []).append((k, single_ph))
                    else:
                        powers_grouped.setdefault(num, []).append((k, single_ph))
            else:
                if num is None:
                    powers_grouped.setdefault(None, []).append((k, ph))
                else:
                    powers_grouped.setdefault(num, []).append((k, ph))

        # Build display list containing unique numeric powers (no duplicate per phase)
        numeric_powers = sorted([p for p in powers_grouped.keys() if p is not None])
        if not numeric_powers and None in powers_grouped:
            # fallback to any key names
            numeric_powers = [None]

        display_list = [f"{p:g} kW" if p is not None else "Autre" for p in numeric_powers]

        # Col 1: Puissance (unique numeric values)
        power_idx = 0
        if default_power is not None:
            try:
                dpf = float(default_power)
                for i, p in enumerate(numeric_powers):
                    if p is None:
                        continue
                    try:
                        if abs(p - dpf) < 1e-6:
                            power_idx = i
                            break
                    except Exception:
                        continue
            except Exception:
                pass
        power_selected_display = cols_ondu[1].selectbox(
            "Puissance (kW)",
            display_list if display_list else ["5 kW"],
            index=power_idx,
            key=f"sel_power_{designation}_{label}"
        )

        # Resolve selected numeric power
        power_num = None
        if power_selected_display != "Autre":
            m_match = re.search(r"(\d+(?:[.,]\d+)?)", power_selected_display)
            if m_match:
                try:
                    power_num = float(m_match.group(1).replace(",", "."))
                except Exception:
                    power_num = None

        # Col 2: Phase (selectable among phases available for that numeric power)
        phase_options = []
        if power_num in powers_grouped:
            phase_options = [ph for (_k, ph) in powers_grouped[power_num]]
        elif None in powers_grouped:
            phase_options = [ph for (_k, ph) in powers_grouped[None]]
        if not phase_options:
            phase_options = [default_phase or "Monophase"]

        phase_idx = 0
        if default_phase and default_phase in phase_options:
            phase_idx = phase_options.index(default_phase)
        phase_final = cols_ondu[2].selectbox("Phase", phase_options, index=phase_idx, key=f"sel_phase_{designation}_{label}")
        
        # Col 3: Quantité
        qty = cols_ondu[3].number_input(
            "Quantité",
            min_value=0,
            step=1,
            value=int(default_qty),
            key=f"qty_{designation}_{label}",
        )
        # Determine lookup_key in catalog for selected numeric power + phase
        lookup_key = ""
        if brand_final and base_key in catalog_load and brand_final in catalog_load[base_key]:
            # find the catalog key for this numeric power and chosen phase
            choices = []
            if power_num in powers_grouped:
                choices = powers_grouped[power_num]
            elif None in powers_grouped:
                choices = powers_grouped[None]
            # choices: list of (key, phase)
            found = None
            for k, ph in choices:
                if ph == phase_final:
                    found = k
                    break
            if not found and choices:
                found = choices[0][0]
            lookup_key = found or ""

        sell_price = 0.0
        buy_price = 0.0
        if lookup_key and base_key in catalog_load and brand_final in catalog_load[base_key]:
            power_entry = catalog_load[base_key][brand_final].get(lookup_key, {})
            if isinstance(power_entry, dict) and "variants" in power_entry and isinstance(power_entry["variants"], dict):
                var = power_entry["variants"].get(phase_final, {})
                sell_price = float(var.get("sell_ttc", 0.0) or 0.0)
                buy_price = float(var.get("buy_ttc", 0.0) or 0.0)
            else:
                sell_price = float(power_entry.get("sell_ttc", 0.0) or 0.0)
                buy_price = float(power_entry.get("buy_ttc", 0.0) or 0.0)
        
        # Col 4 & 5: Prix (auto-filled from catalog, but editable)
        sell_val = cols_ondu[4].number_input(
            "Prix Unit. TTC",
            min_value=0.0,
            step=10.0,
            value=sell_price if sell_price > 0 else (default_sell or 0.0),
            key=f"sell_{designation}_{label}_{brand_final}_{lookup_key}",
        )
        buy_val = cols_ondu[5].number_input(
            "Prix Achat TTC",
            min_value=0.0,
            step=10.0,
            value=buy_price if buy_price > 0 else (default_buy or 0.0),
            key=f"buy_{designation}_{label}_{brand_final}_{lookup_key}",
        )
        
        # Col 6: TVA
        tva = cols_ondu[6].number_input(
            "TVA (%)",
            min_value=0,
            step=1,
            value=int(default_tva),
            key=f"tva_{designation}_{label}",
        )
        
        # Build display marque including numeric power if available
        power_display = f"{power_num:g}" if power_num is not None else ""
        brand_display = f"{brand_final} {power_display}kW {phase_final}".strip()
        
        result = {
            "Désignation": designation,
            "Marque": brand_display,
            "Quantité": qty,
            "Prix Achat TTC": buy_val,
            "Prix Unit. TTC": sell_val,
            "TVA (%)": tva,
        }
        if custom_label is not None:
            result["CustomLabel"] = custom_label
        if default_photo_key is not None:
            result["PhotoKey"] = default_photo_key
        
        return result
    
    # For non-onduleur items, use standard layout
    cols = st.columns([1.2, 1.0, 0.8, 1.0, 1.0, 0.8])
    brand_final = ""
    
    if designation == "Panneaux":
        # Panneaux: Marque + Puissance
        catalog_load = load_catalog()
        # Allow adding a new panel model from the editor
        with st.expander("Ajouter un nouveau panneau au catalogue", expanded=False):
            new_brand_pan = st.text_input("Nouvelle marque (laisser vide si non)", value="", key=f"new_brand_Panneaux_{label}")
            new_power_pan = st.number_input("Puissance (W)", min_value=1, step=10, value=710, key=f"new_power_Panneaux_{label}")
            new_sell_pan = st.number_input("Prix Unit. TTC (nouveau)", min_value=0.0, step=1.0, value=0.0, key=f"new_sell_Panneaux_{label}")
            new_buy_pan = st.number_input("Prix Achat TTC (nouveau)", min_value=0.0, step=1.0, value=0.0, key=f"new_buy_Panneaux_{label}")
            if st.button("Ajouter panneau au catalogue", key=f"btn_add_Panneaux_{label}"):
                if new_brand_pan and new_power_pan > 0:
                    try:
                        set_prices(catalog_load, "Panneaux", new_brand_pan.strip(), new_sell_pan or None, new_buy_pan or None, power_key=str(int(new_power_pan) if float(new_power_pan).is_integer() else str(new_power_pan)), phase=None)
                        st.success(f"Panneau {new_brand_pan} {new_power_pan}W ajouté au catalogue.")
                        # preselect newly added values
                        st.session_state[f"sel_brand_Panneaux_{label}"] = new_brand_pan.strip()
                        st.session_state[f"sel_power_Panneaux_{label}"] = str(int(new_power_pan) if float(new_power_pan).is_integer() else str(new_power_pan))
                    except Exception as e:
                        st.error(f"Impossible d'ajouter le panneau: {e}")
                else:
                    st.warning("Veuillez renseigner une marque et une puissance > 0.")

        available_brands = get_panel_brands(catalog_load)
        default_brand_idx = 0
        if default_brand and default_brand in available_brands:
            default_brand_idx = available_brands.index(default_brand)
        elif available_brands and "Canadian Solar" in available_brands:
            default_brand_idx = available_brands.index("Canadian Solar")
        
        brand_final = cols[0].selectbox("Marque", available_brands, index=default_brand_idx, key=f"sel_brand_{designation}_{label}")
        
        powers_dict = get_panel_powers(catalog_load, brand_final) if brand_final else {}
        available_powers = sorted(powers_dict.keys(), key=lambda x: float(x) if x.replace('.','').isdigit() else 0)
        
        power_idx = 0
        if default_power and str(default_power) in available_powers:
            power_idx = available_powers.index(str(default_power))
        elif available_powers and "710" in available_powers:
            power_idx = available_powers.index("710")
        
        power_selected = cols[1].selectbox("Puissance (W)", available_powers if available_powers else ["710"], index=power_idx, key=f"sel_power_{designation}_{label}")
        
        sell_price = 0.0
        buy_price = 0.0
        if brand_final and power_selected in powers_dict:
            sell_price = float(powers_dict[power_selected].get("sell_ttc", 0.0))
            buy_price = float(powers_dict[power_selected].get("buy_ttc", 0.0))
        
        brand_final = f"{brand_final} {power_selected}W"
        
    elif designation == "Batterie":
        # Batterie: Marque + Capacité
        catalog_load = load_catalog()
        # Allow adding a new battery model from the editor
        with st.expander("Ajouter une nouvelle batterie au catalogue", expanded=False):
            new_brand_bat = st.text_input("Nouvelle marque (laisser vide si non)", value="", key=f"new_brand_Batterie_{label}")
            new_capacity_bat = st.number_input("Capacité (kWh)", min_value=1.0, step=0.5, value=5.0, key=f"new_capacity_Batterie_{label}")
            new_sell_bat = st.number_input("Prix Unit. TTC (nouveau)", min_value=0.0, step=1.0, value=0.0, key=f"new_sell_Batterie_{label}")
            new_buy_bat = st.number_input("Prix Achat TTC (nouveau)", min_value=0.0, step=1.0, value=0.0, key=f"new_buy_Batterie_{label}")
            if st.button("Ajouter batterie au catalogue", key=f"btn_add_Batterie_{label}"):
                if new_brand_bat and new_capacity_bat > 0:
                    try:
                        cap_key = str(int(new_capacity_bat) if float(new_capacity_bat).is_integer() else str(new_capacity_bat))
                        set_prices(catalog_load, "Batterie", new_brand_bat.strip(), new_sell_bat or None, new_buy_bat or None, power_key=cap_key, phase=None)
                        st.success(f"Batterie {new_brand_bat} {cap_key}kWh ajoutée au catalogue.")
                        st.session_state[f"sel_brand_Batterie_{label}"] = new_brand_bat.strip()
                        st.session_state[f"sel_capacity_Batterie_{label}"] = cap_key
                    except Exception as e:
                        st.error(f"Impossible d'ajouter la batterie: {e}")
                else:
                    st.warning("Veuillez renseigner une marque et une capacité > 0.")

        available_brands = get_battery_brands(catalog_load)
        default_brand_idx = 0
        if default_brand and default_brand in available_brands:
            default_brand_idx = available_brands.index(default_brand)
        elif available_brands and "Deyness" in available_brands:
            default_brand_idx = available_brands.index("Deyness")
        
        brand_final = cols[0].selectbox("Marque", available_brands, index=default_brand_idx, key=f"sel_brand_{designation}_{label}")
        
        capacities_dict = get_battery_capacities(load_catalog(), brand_final) if brand_final else {}
        available_capacities = sorted(capacities_dict.keys(), key=lambda x: float(x) if x.replace('.','').isdigit() else 0)
        
        capacity_idx = 0
        if default_power and str(default_power) in available_capacities:
            capacity_idx = available_capacities.index(str(default_power))
        elif available_capacities and "5" in available_capacities:
            capacity_idx = available_capacities.index("5")
        
        capacity_selected = cols[1].selectbox("Capacité (kWh)", available_capacities if available_capacities else ["5"], index=capacity_idx, key=f"sel_capacity_{designation}_{label}")
        
        sell_price = 0.0
        buy_price = 0.0
        if brand_final and capacity_selected in capacities_dict:
            sell_price = float(capacities_dict[capacity_selected].get("sell_ttc", 0.0))
            buy_price = float(capacities_dict[capacity_selected].get("buy_ttc", 0.0))
        
        brand_final = f"{brand_final} {capacity_selected}kWh"
    
    else:
        brand_sel_list = known_brands(catalog, designation)
        brand_sel = cols[0].selectbox("Marque", brand_sel_list, key=f"sel_{designation}_{label}")
        new_brand = cols[1].text_input("Nouvelle marque", value=(default_brand or ""), key=f"new_{designation}_{label}")
        brand_final = (new_brand.strip() or brand_sel)

    qty = cols[2].number_input(
        "Quantité",
        min_value=0,
        step=1,
        value=int(default_qty),
        key=f"qty_{designation}_{label}",
    )

    # Price lookup with stable keys for non-onduleur items
    stable_price_key_sell = f"sell_{designation}_{label}"
    stable_price_key_buy = f"buy_{designation}_{label}"
    brand_tracking_key = f"brand_tracked_{designation}_{label}"
    
    if brand_tracking_key not in st.session_state:
        st.session_state[brand_tracking_key] = brand_final
    
    # If brand changed, refresh prices from catalog
    if st.session_state[brand_tracking_key] != brand_final:
        st.session_state[brand_tracking_key] = brand_final
        if brand_final:
            catalog_sell, catalog_buy = get_prices(load_catalog(), designation, brand_final)
            if catalog_sell is not None:
                st.session_state[stable_price_key_sell] = float(catalog_sell)
            if catalog_buy is not None:
                st.session_state[stable_price_key_buy] = float(catalog_buy)

    auto_sell, auto_buy = get_prices(load_catalog(), designation, brand_final)
    initial_sell = float(default_sell) if default_sell is not None else float(auto_sell or 0.0)
    initial_buy = float(default_buy) if default_buy is not None else float(auto_buy or 0.0)
    
    if stable_price_key_sell in st.session_state:
        initial_sell = st.session_state[stable_price_key_sell]
    if stable_price_key_buy in st.session_state:
        initial_buy = st.session_state[stable_price_key_buy]
    
    sell_val = cols[3].number_input(
        "Prix Unit. TTC",
        min_value=0.0,
        step=10.0,
        value=initial_sell,
        key=stable_price_key_sell,
    )
    buy_val = cols[4].number_input(
        "Prix Achat TTC",
        min_value=0.0,
        step=10.0,
        value=initial_buy,
        key=stable_price_key_buy,
    )
    tva = cols[5].number_input(
        "TVA (%)",
        min_value=0,
        step=1,
        value=int(default_tva),
        key=f"tva_{designation}_{label}",
    )

    result = {
        "Désignation": designation,
        "Marque": brand_final,
        "Quantité": qty,
        "Prix Achat TTC": buy_val,
        "Prix Unit. TTC": sell_val,
        "TVA (%)": tva,
    }
    if custom_label is not None:
        result["CustomLabel"] = custom_label
    if default_photo_key is not None:
        result["PhotoKey"] = default_photo_key

    return result

# ---------- MODE DEVIS ----------
if mode == "Créer un Devis (1 ou 2 scénarios)":
    doc_type = "Devis"
    default_num = config["devis_counter"]
    doc_number = st.number_input(f"Numéro {doc_type}", value=int(default_num), step=1)

    st.subheader("Infos Client")
    client_name = st.text_input("Nom du client")
    client_address = st.text_input("Adresse")
    client_phone = st.text_input("Téléphone")

    scenario_choice = st.selectbox(
        "Scénarios à inclure dans le devis PDF :",
        ["Sans batterie uniquement", "Avec batterie uniquement", "Les deux (Sans + Avec)"],
        index=2
    )
    recommended_option = st.selectbox(
        "Recommandation TAQINOR à afficher dans le PDF :",
        ["Aucune recommandation", "Option SANS batterie", "Option AVEC batterie"],
        index=0,
        help="Choisissez l’option à mettre en avant dans le bandeau ROI, ou aucune recommandation.",
    )

    # Puissance PV
    st.subheader("⚡ Puissance PV pour le ROI et le devis")
    col_est1, col_est2 = st.columns(2)
    with col_est1:
        puissance_kwp = st.number_input(
            "Puissance PV (kWc)",
            min_value=1.0,
            max_value=200.0,
            value=5.0,
            step=0.5,
            key="puissance_kwp",
        )
    with col_est2:
        puissance_panneau_w = 710  # toujours Jinko 710
        st.markdown("Puissance d'un panneau : **710 Wc (Jinko)**")

    # FACTURES ROI
    st.subheader("💡 Factures d'électricité (pour le ROI)")
    use_ws_roi = st.checkbox("Utiliser une estimation Hiver / Été (ROI)", key="roi_use_ws")
    if use_ws_roi:
        col_h, col_e = st.columns(2)
        with col_h:
            f_hiver = st.number_input("Facture typique en hiver (MAD)", 0.0, 1_000_000.0, 500.0, key="roi_f_hiver")
        with col_e:
            f_ete = st.number_input("Facture typique en été (MAD)", 0.0, 1_000_000.0, 1000.0, key="roi_f_ete")
        if st.button("🧮 Estimer les 12 mois (factures ROI)"):
            estimees = interpoler_factures(f_hiver, f_ete)

            for i, m in enumerate(MOIS):
                valeur = round(estimees[i], 2)

                # 1) Met à jour la structure interne qu'on utilise comme "référence"
                st.session_state.roi_fact_init[m] = valeur

                # 2) Surtout : met à jour les widgets eux-mêmes
                key_widget = f"roi_fact_{m}"
                st.session_state[key_widget] = valeur

    factures_roi = []
    cols_roi = st.columns(3)
    for i, m in enumerate(MOIS):
        with cols_roi[i % 3]:
            val = st.number_input(
                f"Facture {m} (MAD)",
                0.0,
                1_000_000.0,
                st.session_state.roi_fact_init.get(m, 2000.0),
                10.0,
                key=f"roi_fact_{m}",
            )
            factures_roi.append(val)

    roi_total_annuel = sum(factures_roi)
    roi_total_kwh = roi_total_annuel / KWH_PRICE if KWH_PRICE > 0 else 0
    st.write(f"**Facture annuelle (ROI) :** {roi_total_annuel:,.0f} MAD")
    st.write(f"**Consommation annuelle (ROI) :** {roi_total_kwh:,.0f} kWh")

    roi_part_couvrable = st.slider(
        "Part de la facture couverte par le solaire en scénario SANS batterie (%)",
        min_value=0,
        max_value=100,
        value=50,
        step=5,
        key="roi_part_couvrable",
    ) / 100.0

    st.markdown("---")

    st.subheader("Produits / Services (base)")

    catalog_now = load_catalog()
    # Choix du type de structures (par défaut automatique selon la puissance)
    try:
        default_struct = "Structures acier" if puissance_kwp < 30 else "Structures aluminium"
    except Exception:
        default_struct = "Structures acier"
    struct_idx = 0 if default_struct == "Structures acier" else 1
    structure_choice = st.radio(
        "Type de structures à utiliser :",
        ("Structures acier", "Structures aluminium"),
        index=struct_idx,
        key="structure_type_choice",
    )
    custom_templates = load_custom_templates()

    # Bouton pour remplir automatiquement — construit un gabarit minimal puis appelle auto_fill
    if st.button("⚙️ Remplir automatiquement les lignes (panneaux, onduleurs, structures, smart meter, wifi)"):
        # Signal to line_editor that this run is an explicit autofill and
        # widget values should be overwritten with autofill results.
        st.session_state["force_autofill_update"] = True
        # gabarit minimal reprenant les désignations standard et valeurs par défaut
        template_rows = [
            {"Désignation": "Onduleur réseau", "Marque": "", "Quantité": 1, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
            {"Désignation": "Onduleur hybride", "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
            {"Désignation": "Smart Meter", "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
            {"Désignation": "Wifi Dongle", "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
            {"Désignation": "Panneaux", "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 10},
            {"Désignation": "Batterie", "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
            {"Désignation": "Structures acier", "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
            {"Désignation": "Structures aluminium", "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
            {"Désignation": "Socles", "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
            {"Désignation": "Accessoires", "Marque": "", "Quantité": 1, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
            {"Désignation": "Tableau De Protection AC/DC", "Marque": "", "Quantité": 1, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
            {"Désignation": "Installation", "Marque": "", "Quantité": 1, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
            {"Désignation": "Transport", "Marque": "", "Quantité": 1, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
            {"Désignation": "Suivi journalier, maintenance chaque 12 mois pendent 2 ans", "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
        ]
        df_template = pd.DataFrame(template_rows)
        df_auto = auto_fill_from_power(df_template, catalog_now, puissance_kwp, puissance_panneau_w)
        # Respecter le choix manuel de l'utilisateur pour le type de structure (si présent)
        try:
            import math
            nb_panneaux = math.ceil(puissance_kwp * 1000.0 / puissance_panneau_w) if puissance_kwp > 0 else 0
        except Exception:
            nb_panneaux = 0
        struct_choice = st.session_state.get("structure_type_choice", None)
        if struct_choice in ("Structures acier", "Structures aluminium") and nb_panneaux > 0:
            if struct_choice == "Structures acier":
                mask_a = df_auto["Désignation"] == "Structures acier"
                mask_b = df_auto["Désignation"] == "Structures aluminium"
                if mask_a.any():
                    idx = mask_a.idxmax()
                    df_auto.at[idx, "Quantité"] = nb_panneaux
                    df_auto.at[idx, "CustomLabel"] = "Structures en acier galvanisé"
                if mask_b.any():
                    idx2 = mask_b.idxmax()
                    df_auto.at[idx2, "Quantité"] = 0
            else:
                mask_a = df_auto["Désignation"] == "Structures acier"
                mask_b = df_auto["Désignation"] == "Structures aluminium"
                if mask_b.any():
                    idx = mask_b.idxmax()
                    df_auto.at[idx, "Quantité"] = nb_panneaux
                    df_auto.at[idx, "CustomLabel"] = "Structures en aluminium"
                if mask_a.any():
                    idx2 = mask_a.idxmax()
                    df_auto.at[idx2, "Quantité"] = 0

        st.session_state.df_common_overrides = df_auto
        # Mark that autofill ran and that onduleur widgets should be updated
        # We set a small counter equal to the number of onduleur editors
        # (réseau + hybride) so each will consume one update.
        st.session_state["force_autofill_update_count"] = 2
        # Remplir aussi les clés de session pour que les widgets éditables soient préremplis
        label_map = {
            "Onduleur réseau": "Onduleur réseau (scénario SANS batterie)",
            "Onduleur hybride": "Onduleur hybride (scénario AVEC batterie)",
            "Smart Meter": "Smart Meter",
            "Wifi Dongle": "Wifi Dongle",
            "Panneaux": "Panneaux solaires (Jinko 710)",
            "Batterie": "Batterie de stockage (scénario AVEC batterie)",
            "Structures acier": "Structures acier",
            "Structures aluminium": "Structures aluminium",
            "Socles": "Socles béton",
            "Accessoires": "Accessoires & câblage",
            "Tableau De Protection AC/DC": "Tableau de protection AC/DC",
            "Installation": "Installation",
            "Transport": "Transport",
            "Suivi journalier, maintenance chaque 12 mois pendent 2 ans": "Suivi journalier & maintenance (2 ans)",
        }

        try:
            for _, r in pd.DataFrame(df_auto).iterrows():
                des = r.get("Désignation")
                if not isinstance(des, str):
                    continue
                label = label_map.get(des, des)
                brand = (r.get("Marque") or "").strip()
                qty = int(r.get("Quantité") or 0)
                tva = int(r.get("TVA (%)") or 0)
                sell = float(r.get("Prix Unit. TTC") or 0.0)
                buy = float(r.get("Prix Achat TTC") or 0.0)

                # new_ input will be used preferentially by line_editor to set the marque
                st.session_state[f"new_{des}_{label}"] = brand
                st.session_state[f"qty_{des}_{label}"] = qty
                st.session_state[f"tva_{des}_{label}"] = tva
                # For onduleurs, use the brand + power lookup key used by line_editor
                def _format_power_key(p):
                    try:
                        if p is None:
                            return ""
                        pf = float(p)
                        if pf.is_integer():
                            return str(int(pf))
                        return str(pf)
                    except Exception:
                        return str(p)

                if des == "Onduleur réseau":
                    ondu_power = st.session_state.get("ondu_res_power")
                    ondu_phase = st.session_state.get("ondu_res_phase")
                    lookup_key = _format_power_key(ondu_power)
                    st.session_state[f"sell_{des}_{label}_{brand}_{lookup_key}"] = sell
                    st.session_state[f"buy_{des}_{label}_{brand}_{lookup_key}"] = buy
                    # also keep short named keys for components that expect them
                    st.session_state["ondu_res_brand"] = brand
                    st.session_state["ondu_res_power"] = ondu_power
                    st.session_state["ondu_res_phase"] = ondu_phase
                elif des == "Onduleur hybride":
                    ondu_power = st.session_state.get("ondu_hyb_power")
                    ondu_phase = st.session_state.get("ondu_hyb_phase")
                    lookup_key = _format_power_key(ondu_power)
                    st.session_state[f"sell_{des}_{label}_{brand}_{lookup_key}"] = sell
                    st.session_state[f"buy_{des}_{label}_{brand}_{lookup_key}"] = buy
                    st.session_state["ondu_hyb_brand"] = brand
                    st.session_state["ondu_hyb_power"] = ondu_power
                    st.session_state["ondu_hyb_phase"] = ondu_phase
                elif des in ("Panneaux", "Batterie"):
                    # non-onduleur items use stable sell/buy keys in line_editor
                    stable_price_key_sell = f"sell_{des}_{label}"
                    stable_price_key_buy = f"buy_{des}_{label}"
                    st.session_state[stable_price_key_sell] = sell
                    st.session_state[stable_price_key_buy] = buy
                    # store brand tracking too
                    st.session_state[f"brand_tracked_{des}_{label}"] = brand
                else:
                    # fallback: store under stable keys per-designation
                    stable_price_key_sell = f"sell_{des}_{label}"
                    stable_price_key_buy = f"buy_{des}_{label}"
                    st.session_state[stable_price_key_sell] = sell
                    st.session_state[stable_price_key_buy] = buy
        except Exception:
            pass

        st.success("Lignes remplies automatiquement : Jinko 710, Huawei (sans batt), Deye (avec batt), structures, smart meter et wifi.")

    # Lignes standard communes — utiliser overrides si l'auto-fill a été exécuté
    overrides = {}
    if st.session_state.get("df_common_overrides") is not None:
        try:
            tmp = sanitize_df(pd.DataFrame(st.session_state.df_common_overrides).copy())
            for _, r in tmp.iterrows():
                des = r.get("Désignation")
                if not isinstance(des, str):
                    continue
                overrides[des] = {
                    "Marque": r.get("Marque", ""),
                    "Quantité": int(r.get("Quantité") or 0),
                    "Prix Unit. TTC": float(r.get("Prix Unit. TTC") or 0.0),
                    "Prix Achat TTC": float(r.get("Prix Achat TTC") or 0.0),
                    "TVA (%)": int(r.get("TVA (%)") or 0),
                    "PhotoKey": r.get("PhotoKey", None),
                    "CustomLabel": r.get("CustomLabel", None),
                }
        except Exception:
            overrides = {}
    # Si un onduleur réseau est présent (quantité > 0), on ajoute par défaut Smart Meter et Wifi Dongle
    # (avec quantité 1) afin que les widgets correspondants soient préremplis et éditables.
    try:
        ond_res_qty = overrides.get("Onduleur réseau", {}).get("Quantité", 0)
        if ond_res_qty > 0:
            # Smart Meter
            if "Smart Meter" not in overrides:
                sell_sm, buy_sm = get_prices(load_catalog(), "Smart Meter", "")
                overrides["Smart Meter"] = {
                    "Marque": "",
                    "Quantité": 1,
                    "Prix Unit. TTC": float(sell_sm or 0.0),
                    "Prix Achat TTC": float(buy_sm or 0.0),
                    "TVA (%)": 20,
                }
            else:
                if overrides["Smart Meter"].get("Quantité", 0) == 0:
                    overrides["Smart Meter"]["Quantité"] = 1
            # Wifi Dongle
            if "Wifi Dongle" not in overrides:
                sell_wd, buy_wd = get_prices(load_catalog(), "Wifi Dongle", "")
                overrides["Wifi Dongle"] = {
                    "Marque": "",
                    "Quantité": 1,
                    "Prix Unit. TTC": float(sell_wd or 0.0),
                    "Prix Achat TTC": float(buy_wd or 0.0),
                    "TVA (%)": 20,
                }
            else:
                if overrides["Wifi Dongle"].get("Quantité", 0) == 0:
                    overrides["Wifi Dongle"]["Quantité"] = 1
    except Exception:
        pass

    rows_common = [
        line_editor(
            "Onduleur réseau",
            "Onduleur réseau (scénario SANS batterie)",
            overrides.get("Onduleur réseau", {}).get("Quantité", 1),
            overrides.get("Onduleur réseau", {}).get("TVA (%)", 20),
            catalog_now,
            default_brand=overrides.get("Onduleur réseau", {}).get("Marque", ""),
            default_sell=overrides.get("Onduleur réseau", {}).get("Prix Unit. TTC", None),
            default_buy=overrides.get("Onduleur réseau", {}).get("Prix Achat TTC", None),
            brand_only=True,
            default_power=st.session_state.get("ondu_res_power"),
            default_phase=st.session_state.get("ondu_res_phase"),
        ),
        line_editor(
            "Onduleur hybride",
            "Onduleur hybride (scénario AVEC batterie)",
            overrides.get("Onduleur hybride", {}).get("Quantité", 0),
            overrides.get("Onduleur hybride", {}).get("TVA (%)", 20),
            catalog_now,
            default_brand=overrides.get("Onduleur hybride", {}).get("Marque", ""),
            default_sell=overrides.get("Onduleur hybride", {}).get("Prix Unit. TTC", None),
            default_buy=overrides.get("Onduleur hybride", {}).get("Prix Achat TTC", None),
            brand_only=True,
            default_power=st.session_state.get("ondu_hyb_power"),
            default_phase=st.session_state.get("ondu_hyb_phase"),
        ),
        line_editor(
            "Smart Meter",
            "Smart Meter",
            overrides.get("Smart Meter", {}).get("Quantité", 0),
            overrides.get("Smart Meter", {}).get("TVA (%)", 20),
            catalog_now,
            default_sell=overrides.get("Smart Meter", {}).get("Prix Unit. TTC", None),
            default_buy=overrides.get("Smart Meter", {}).get("Prix Achat TTC", None),
        ),
        line_editor(
            "Wifi Dongle",
            "Wifi Dongle",
            overrides.get("Wifi Dongle", {}).get("Quantité", 0),
            overrides.get("Wifi Dongle", {}).get("TVA (%)", 20),
            catalog_now,
            default_sell=overrides.get("Wifi Dongle", {}).get("Prix Unit. TTC", None),
            default_buy=overrides.get("Wifi Dongle", {}).get("Prix Achat TTC", None),
        ),
        line_editor(
            "Panneaux",
            "Panneaux solaires (Jinko 710)",
            overrides.get("Panneaux", {}).get("Quantité", 0),
            overrides.get("Panneaux", {}).get("TVA (%)", 10),
            catalog_now,
            default_brand=overrides.get("Panneaux", {}).get("Marque", ""),
            default_sell=overrides.get("Panneaux", {}).get("Prix Unit. TTC", None),
            default_buy=overrides.get("Panneaux", {}).get("Prix Achat TTC", None),
        ),
        line_editor(
            "Batterie",
            "Batterie de stockage (scénario AVEC batterie)",
            overrides.get("Batterie", {}).get("Quantité", 0),
            overrides.get("Batterie", {}).get("TVA (%)", 20),
            catalog_now,
            default_brand=overrides.get("Batterie", {}).get("Marque", ""),
            default_sell=overrides.get("Batterie", {}).get("Prix Unit. TTC", None),
            default_buy=overrides.get("Batterie", {}).get("Prix Achat TTC", None),
        ),
        line_editor(
            "Structures acier",
            "Structures acier",
            overrides.get("Structures acier", {}).get("Quantité", 0),
            overrides.get("Structures acier", {}).get("TVA (%)", 20),
            catalog_now,
            default_sell=overrides.get("Structures acier", {}).get("Prix Unit. TTC", None),
            default_buy=overrides.get("Structures acier", {}).get("Prix Achat TTC", None),
        ),
        line_editor(
            "Structures aluminium",
            "Structures aluminium",
            overrides.get("Structures aluminium", {}).get("Quantité", 0),
            overrides.get("Structures aluminium", {}).get("TVA (%)", 20),
            catalog_now,
            default_sell=overrides.get("Structures aluminium", {}).get("Prix Unit. TTC", None),
            default_buy=overrides.get("Structures aluminium", {}).get("Prix Achat TTC", None),
        ),
        line_editor(
            "Socles",
            "Socles béton",
            overrides.get("Socles", {}).get("Quantité", 0),
            overrides.get("Socles", {}).get("TVA (%)", 20),
            catalog_now,
            default_sell=overrides.get("Socles", {}).get("Prix Unit. TTC", None),
            default_buy=overrides.get("Socles", {}).get("Prix Achat TTC", None),
        ),
        line_editor(
            "Accessoires",
            "Accessoires & câblage",
            overrides.get("Accessoires", {}).get("Quantité", 1),
            overrides.get("Accessoires", {}).get("TVA (%)", 20),
            catalog_now,
            default_sell=overrides.get("Accessoires", {}).get("Prix Unit. TTC", None),
            default_buy=overrides.get("Accessoires", {}).get("Prix Achat TTC", None),
        ),
        line_editor(
            "Tableau De Protection AC/DC",
            "Tableau de protection AC/DC",
            overrides.get("Tableau De Protection AC/DC", {}).get("Quantité", 1),
            overrides.get("Tableau De Protection AC/DC", {}).get("TVA (%)", 20),
            catalog_now,
            default_sell=overrides.get("Tableau De Protection AC/DC", {}).get("Prix Unit. TTC", None),
            default_buy=overrides.get("Tableau De Protection AC/DC", {}).get("Prix Achat TTC", None),
        ),
        line_editor(
            "Installation",
            "Installation",
            overrides.get("Installation", {}).get("Quantité", 1),
            overrides.get("Installation", {}).get("TVA (%)", 20),
            catalog_now,
            default_sell=overrides.get("Installation", {}).get("Prix Unit. TTC", None),
            default_buy=overrides.get("Installation", {}).get("Prix Achat TTC", None),
        ),
        line_editor(
            "Transport",
            "Transport",
            overrides.get("Transport", {}).get("Quantité", 1),
            overrides.get("Transport", {}).get("TVA (%)", 20),
            catalog_now,

            default_sell=overrides.get("Transport", {}).get("Prix Unit. TTC", None),
            default_buy=overrides.get("Transport", {}).get("Prix Achat TTC", None),
        ),
        line_editor(
            "Suivi journalier, maintenance chaque 12 mois pendent 2 ans",
            "Suivi journalier & maintenance (2 ans)",
            overrides.get("Suivi journalier, maintenance chaque 12 mois pendent 2 ans", {}).get("Quantité", 1),
            overrides.get("Suivi journalier, maintenance chaque 12 mois pendent 2 ans", {}).get("TVA (%)", 20),
            catalog_now,
        ),
    ]

    # Lignes perso mémorisées comme templates
    for tpl in custom_templates:
        label = tpl.get("label", "Ligne personnalisée")
        default_tva = tpl.get("default_tva", 20)
        default_photo = tpl.get("default_photo", "")
        rows_common.append(
            line_editor(
                designation=label,
                label=label,
                default_qty=0,
                default_tva=default_tva,
                catalog=catalog_now,
                custom_label=label,
                default_photo_key=default_photo,
            )
        )

    df_common = pd.DataFrame(rows_common)

    if st.session_state.df_common_overrides is not None:
        df_auto = st.session_state.df_common_overrides.copy()
        with st.expander("DEBUG : Valeurs auto-fill (overrides)"):
            try:
                st.dataframe(pd.DataFrame(df_auto), use_container_width=True)
            except Exception:
                st.write(df_auto)
    else:
        df_auto = df_common.copy()

    st.markdown("Aperçu des lignes utilisées pour le calcul (après auto-fill éventuel) :")
    st.dataframe(df_auto, use_container_width=True)

    # Lignes perso SANS
    st.subheader("Lignes personnalisées — scénario SANS batterie")
    if st.button("➕ Ajouter une ligne personnalisée (SANS batterie)"):
        st.session_state.custom_lines_sans.append(
            {"desc": "", "photo": "", "qty": 0, "sell": 0.0, "buy": 0.0, "tva": 20}
        )

    new_custom_sans = []
    for i, line in enumerate(st.session_state.custom_lines_sans):
        st.markdown(f"**Ligne perso SANS n°{i+1}**")
        c1, c2, c3, c4, c5, c6, c7 = st.columns([3, 1, 1, 1, 1, 1, 0.8])
        with c1:
            desc = st.text_input(
                "Nom / Désignation",
                value=line.get("desc", ""),
                key=f"sans_desc_{i}",
            )
        with c2:
            qty = st.number_input(
                "Quantité",
                min_value=0,
                step=1,
                value=int(line.get("qty", 0)),
                key=f"sans_qty_{i}",
            )
        with c3:
            sell = st.number_input(
                "PU TTC",
                min_value=0.0,
                step=10.0,
                value=float(line.get("sell", 0.0)),
                key=f"sans_sell_{i}",
            )
        with c4:
            buy = st.number_input(
                "Achat TTC",
                min_value=0.0,
                step=10.0,
                value=float(line.get("buy", 0.0)),
                key=f"sans_buy_{i}",
            )
        with c5:
            tva = st.number_input(
                "TVA (%)",
                min_value=0,
                step=1,
                value=int(line.get("tva", 20)),
                key=f"sans_tva_{i}",
            )
        with c6:
            photo = st.text_input(
                "Nom photo (facultatif)",
                value=line.get("photo", ""),
                key=f"sans_photo_{i}",
            )
        with c7:
            remove = st.checkbox("❌", key=f"sans_rem_{i}")

        if not remove:
            new_custom_sans.append(
                {"desc": desc, "photo": photo, "qty": qty, "sell": sell, "buy": buy, "tva": tva}
            )
    st.session_state.custom_lines_sans = new_custom_sans

    if st.session_state.custom_lines_sans:
        df_custom_sans = pd.DataFrame(
            [
                {
                    "Désignation": l["desc"] or "Ligne personnalisée",
                    "Marque": "",
                    "Quantité": l["qty"],
                    "Prix Achat TTC": l["buy"],
                    "Prix Unit. TTC": l["sell"],
                    "TVA (%)": l["tva"],
                    "CustomLabel": l["desc"],
                    "PhotoKey": l.get("photo", ""),
                }
                for l in st.session_state.custom_lines_sans
            ]
        )
    else:
        df_custom_sans = pd.DataFrame(columns=["Désignation","Marque","Quantité","Prix Achat TTC","Prix Unit. TTC","TVA (%)","CustomLabel","PhotoKey"])

    # Lignes perso AVEC
    st.subheader("Lignes personnalisées — scénario AVEC batterie")
    if st.button("➕ Ajouter une ligne personnalisée (AVEC batterie)"):
        st.session_state.custom_lines_avec.append(
            {"desc": "", "photo": "", "qty": 0, "sell": 0.0, "buy": 0.0, "tva": 20}
        )

    new_custom_avec = []
    for i, line in enumerate(st.session_state.custom_lines_avec):
        st.markdown(f"**Ligne perso AVEC n°{i+1}**")
        c1, c2, c3, c4, c5, c6, c7 = st.columns([3, 1, 1, 1, 1, 1, 0.8])
        with c1:
            desc = st.text_input(
                "Nom / Désignation",
                value=line.get("desc", ""),
                key=f"avec_desc_{i}",
            )
        with c2:
            qty = st.number_input(
                "Quantité",
                min_value=0,
                step=1,
                value=int(line.get("qty", 0)),
                key=f"avec_qty_{i}",
            )
        with c3:
            sell = st.number_input(
                "PU TTC",
                min_value=0.0,
                step=10.0,
                value=float(line.get("sell", 0.0)),
                key=f"avec_sell_{i}",
            )
        with c4:
            buy = st.number_input(
                "Achat TTC",
                min_value=0.0,
                step=10.0,
                value=float(line.get("buy", 0.0)),
                key=f"avec_buy_{i}",
            )
        with c5:
            tva = st.number_input(
                "TVA (%)",
                min_value=0,
                step=1,
                value=int(line.get("tva", 20)),
                key=f"avec_tva_{i}",
            )
        with c6:
            photo = st.text_input(
                "Nom photo (facultatif)",
                value=line.get("photo", ""),
                key=f"avec_photo_{i}",
            )
        with c7:
            remove = st.checkbox("❌", key=f"avec_rem_{i}")

        if not remove:
            new_custom_avec.append(
                {"desc": desc, "photo": photo, "qty": qty, "sell": sell, "buy": buy, "tva": tva}
            )
    st.session_state.custom_lines_avec = new_custom_avec

    if st.session_state.custom_lines_avec:
        df_custom_avec = pd.DataFrame(
            [
                {
                    "Désignation": l["desc"] or "Ligne personnalisée",
                    "Marque": "",
                    "Quantité": l["qty"],
                    "Prix Achat TTC": l["buy"],
                    "Prix Unit. TTC": l["sell"],
                    "TVA (%)": l["tva"],
                    "CustomLabel": l["desc"],
                    "PhotoKey": l.get("photo", ""),
                }
                for l in st.session_state.custom_lines_avec
            ]
        )
    else:
        df_custom_avec = pd.DataFrame(columns=["Désignation","Marque","Quantité","Prix Achat TTC","Prix Unit. TTC","TVA (%)","CustomLabel","PhotoKey"])

    # NOTES séparées
    st.subheader("Notes pour le devis SANS batterie")
    if st.button("➕ Ajouter une note (SANS)"):
        st.session_state.notes_sans.append("")
    notes_sans_new = []
    for i, note in enumerate(st.session_state.notes_sans):
        col_note, col_del = st.columns([6, 1])
        with col_note:
            text = st.text_area(
                f"Note SANS {i+1}",
                value=note,
                key=f"note_sans_{i}",
                height=60,
            )
        with col_del:
            delete = st.checkbox("❌", key=f"note_sans_del_{i}")
        if not delete:
            notes_sans_new.append(text)
    st.session_state.notes_sans = notes_sans_new

    st.subheader("Notes pour le devis AVEC batterie")
    if st.button("➕ Ajouter une note (AVEC)"):
        st.session_state.notes_avec.append("")
    notes_avec_new = []
    for i, note in enumerate(st.session_state.notes_avec):
        col_note, col_del = st.columns([6, 1])
        with col_note:
            text = st.text_area(
                f"Note AVEC {i+1}",
                value=note,
                key=f"note_avec_{i}",
                height=60,
            )
        with col_del:
            delete = st.checkbox("❌", key=f"note_avec_del_{i}")
        if not delete:
            notes_avec_new.append(text)
    st.session_state.notes_avec = notes_avec_new

    # Construction DF scénarios
    # IMPORTANT: use the values returned by the editable widgets (`df_common`) as source of truth.
    # `df_auto` is only a helper/preview of what auto-fill suggested; the user can edit the widgets
    # and those edited values must be used for the PDF and cost calculations.
    df_common_full = df_common.copy()

    df_sans_all = pd.concat([df_common_full, df_custom_sans], ignore_index=True)
    df_avec_all = pd.concat([df_common_full, df_custom_avec], ignore_index=True)

    df_sans_all = sanitize_df(df_sans_all)
    df_avec_all = sanitize_df(df_avec_all)

    df_sans_final = df_sans_all[
        ~df_sans_all["Désignation"].isin(["Batterie", "Onduleur hybride"])
    ].copy()
    df_avec_final = df_avec_all[
        ~df_avec_all["Désignation"].isin(["Onduleur réseau"])
    ].copy()

    # --- Si le scénario AVEC contient une batterie ou un onduleur Deye,
    #     on retire systématiquement Smart Meter et Wifi Dongle du devis AVEC
    try:
        has_battery = (df_avec_final["Désignation"] == "Batterie").any()
        has_deye = False
        if (df_avec_final["Désignation"] == "Onduleur hybride").any():
            # regarde si la marque contient 'deye'
            mask = (df_avec_final["Désignation"] == "Onduleur hybride") & df_avec_final["Marque"].astype(str).str.lower().str.contains("deye", na=False)
            has_deye = mask.any()

        if has_battery or has_deye:
            df_avec_final = df_avec_final[~df_avec_final["Désignation"].isin(["Smart Meter", "Wifi Dongle"])].copy()
    except Exception:
        # ne pas faire échouer l'application si quelque chose d'inattendu survient
        pass

    for df_tmp in (df_sans_final, df_avec_final):
        df_tmp["Total TTC"] = df_tmp["Prix Unit. TTC"] * df_tmp["Quantité"]

    total_ttc_sans = float(df_sans_final["Total TTC"].sum())
    total_ttc_avec = float(df_avec_final["Total TTC"].sum())

    st.markdown("### Récapitulatif devis")
    c1, c2 = st.columns(2)
    c1.metric("Total TTC scénario SANS batterie", f"{total_ttc_sans:,.2f} DH")
    c2.metric("Total TTC scénario AVEC batterie", f"{total_ttc_avec:,.2f} DH")

    # ROI
    kwh_mensuels = [f / KWH_PRICE if KWH_PRICE > 0 else 0 for f in factures_roi]
    prod_pv = [GHI[i] * puissance_kwp * EFFICIENCY for i in range(12)]
    conso_couvrable = [k * roi_part_couvrable for k in kwh_mensuels]

    pv_used_sans = [min(prod_pv[i], conso_couvrable[i]) for i in range(12)]
    pv_used_avec = [min(prod_pv[i], kwh_mensuels[i]) for i in range(12)]

    eco_mens_sans = [x * KWH_PRICE for x in pv_used_sans]
    eco_mens_avec = [x * KWH_PRICE for x in pv_used_avec]

    eco_ann_sans = sum(eco_mens_sans)
    eco_ann_avec = sum(eco_mens_avec)

    payback_sans = total_ttc_sans / eco_ann_sans if eco_ann_sans > 0 and total_ttc_sans > 0 else None
    payback_avec = total_ttc_avec / eco_ann_avec if eco_ann_avec > 0 and total_ttc_avec > 0 else None

    st.subheader("📈 ROI (Retour sur investissement)")

    st.write(f"**Production PV annuelle estimée :** {sum(prod_pv):,.0f} kWh/an")

    col_roi1, col_roi2 = st.columns(2)
    with col_roi1:
        st.markdown("### 🔋 Scénario SANS batterie")
        st.write(f"**Coût système SANS batterie :** {total_ttc_sans:,.0f} MAD")
        st.write(f"**Économie annuelle estimée :** {eco_ann_sans:,.0f} MAD/an")
        if payback_sans:
            st.write(f"**Temps de retour estimé :** {payback_sans:.1f} ans")
        else:
            st.write("Temps de retour non calculable (économie annuelle nulle).")

    with col_roi2:
        st.markdown("### 🔋 Scénario AVEC batterie")
        st.write(f"**Coût système AVEC batterie :** {total_ttc_avec:,.0f} MAD")
        st.write(f"**Économie annuelle estimée :** {eco_ann_avec:,.0f} MAD/an")
        if payback_avec:
            st.write(f"**Temps de retour estimé :** {payback_avec:.1f} ans")
        else:
            st.write("Temps de retour non calculable (économie annuelle nulle).")

    df_roi = pd.DataFrame({
        "Mois": MOIS,
        "Facture (MAD)": factures_roi,
        "Production PV (kWh)": prod_pv,
        "PV utilisée SANS batt (kWh)": pv_used_sans,
        "PV utilisée AVEC batt (kWh)": pv_used_avec,
        "Économie SANS batt (MAD)": eco_mens_sans,
        "Économie AVEC batt (MAD)": eco_mens_avec,
    })
    st.markdown("#### Détail mensuel ROI")
    st.dataframe(df_roi, use_container_width=True)

    fig_roi = build_roi_figure(MOIS, factures_roi, eco_mens_sans, eco_mens_avec)
    st.pyplot(fig_roi)
    roi_fig_all_buf = roi_figure_buffer(MOIS, factures_roi, eco_mens_sans, eco_mens_avec)

    # ROIs résumé pour PDF
    roi_summary_sans = {
        "prod_annuelle": sum(prod_pv),
        "eco_annuelle": eco_ann_sans,
        "cout_systeme": total_ttc_sans,
        "payback": payback_sans,
    }
    roi_summary_avec = {
        "prod_annuelle": sum(prod_pv),
        "eco_annuelle": eco_ann_avec,
        "cout_systeme": total_ttc_avec,
        "payback": payback_avec,
    }

    if st.button("Générer le devis complet en PDF"):
        cat_now = load_catalog()
        learn_from_df(pd.concat([df_sans_final, df_avec_final], ignore_index=True), cat_now)

        # Sauvegarde des nouveaux templates
        templates = load_custom_templates()
        existing_labels = {t["label"] for t in templates if "label" in t}
        for l in (st.session_state.custom_lines_sans + st.session_state.custom_lines_avec):
            label = (l.get("desc") or "").strip()
            photo = (l.get("photo") or "").strip()
            if label and label not in existing_labels:
                templates.append(
                    {
                        "label": label,
                        "default_tva": int(l.get("tva", 20)),
                        "default_photo": photo,
                    }
                )
                existing_labels.add(label)
        save_custom_templates(templates)

        # Selon le choix de scénarios
        df_sans_used = df_sans_final if scenario_choice in ("Sans batterie uniquement", "Les deux (Sans + Avec)") else df_sans_final.iloc[0:0]
        df_avec_used = df_avec_final if scenario_choice in ("Avec batterie uniquement", "Les deux (Sans + Avec)") else df_avec_final.iloc[0:0]

        pdf_path = generate_double_devis_pdf(
            df_sans=df_sans_used,
            df_avec=df_avec_used,
            notes_sans=st.session_state.notes_sans,
            notes_avec=st.session_state.notes_avec,
            client_name=client_name,
            client_address=client_address,
            client_phone=client_phone,
            doc_type=doc_type,
            doc_number=doc_number,
            roi_summary_sans=roi_summary_sans if scenario_choice != "Avec batterie uniquement" else None,
            roi_summary_avec=roi_summary_avec if scenario_choice != "Sans batterie uniquement" else None,
            roi_fig_all_buf=roi_fig_all_buf,
            scenario_choice=scenario_choice,
            recommended_option=recommended_option,
        )

        st.success(f"Devis généré ✅ → {pdf_path}")
        with open(pdf_path, "rb") as f:
            st.download_button(
                "⬇️ Télécharger le PDF du devis",
                f,
                file_name=pdf_path.name,
                mime="application/pdf",
            )

        # On stocke comme référence la version AVEC (ou SANS, peu importe, il en faut une pour la facture)
        config["devis_counter"] = int(doc_number) + 1
        devis_history[str(int(doc_number))] = {
            "client_name": client_name,
            "client_address": client_address,
            "client_phone": client_phone,
            "df": df_avec_final.to_dict(),
            "total_ttc": float(total_ttc_avec),
            "notes": st.session_state.notes_avec,
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        with open(DEVIS_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(devis_history, f, ensure_ascii=False, indent=2)

# ---------- MODE FACTURE ----------
else:
    if not devis_history:
        st.warning("Aucun devis trouvé.")
    else:
        st.subheader("Transformer un Devis en Facture")

        devis_nums = sorted(devis_history.keys(), key=lambda x: int(x))
        selected_devis = st.selectbox(
            "Choisir le devis à facturer :",
            devis_nums,
            format_func=lambda x: f"Devis {x} — {devis_history[x].get('client_name','')}",
        )

        default_fact_num = config["facture_counter"]
        fact_number = st.number_input("Numéro Facture", value=int(default_fact_num), step=1)

        if st.button("Générer la Facture en PDF"):
            data = devis_history[selected_devis]
            client_name = data.get("client_name", "")
            client_address = data.get("client_address", "")
            client_phone = data.get("client_phone", "")
            df_saved = pd.DataFrame(data.get("df", {}))
            notes_saved = data.get("notes", [])

            doc_type = "Facture"
            pdf_path, file_name = generate_single_pdf(
                df_saved,
                client_name,
                client_address,
                client_phone,
                doc_type,
                int(fact_number),
                notes_saved,
            )

            st.success(f"{doc_type} {int(fact_number)} générée ✅ → {pdf_path}")
            with open(pdf_path, "rb") as f:
                st.download_button(
                    "⬇️ Télécharger la Facture PDF",
                    f,
                    file_name=file_name,
                    mime="application/pdf",
                )

            config["facture_counter"] = int(fact_number) + 1
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

