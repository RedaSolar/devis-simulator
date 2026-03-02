import json
import re
from pathlib import Path

from constants import CANONICALS, CANON_MAP

# ---------- PATHS (must match app.py) ----------
BASE_DIR = Path(__file__).resolve().parent
CATALOG_FILE = BASE_DIR / "brand_catalog.json"
CUSTOM_LINES_FILE = BASE_DIR / "custom_line_templates.json"


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
