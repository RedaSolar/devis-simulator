import re
import unicodedata
from pathlib import Path

import pandas as pd

from constants import CANONICALS, CANON_MAP
from catalog import _catalog_key_for_designation, set_prices

# IMAGE_FILES is imported here from app context — but to avoid circular imports,
# utils.py declares get_first_existing_image and get_dynamic_image as functions
# that receive the IMAGE_FILES dict and PICTURES_DIR as parameters, OR we import
# them lazily. The cleanest approach: import IMAGE_FILES from app at runtime.
# However, to keep utils.py standalone we replicate the helper that uses the
# PICTURES_DIR path only (app.py will provide IMAGE_FILES via a module-level
# variable set after imports).

# This will be set by app.py after it defines IMAGE_FILES and PICTURES_DIR.
IMAGE_FILES = {}
PICTURES_DIR = Path(".")


def _num(s):
    try:
        s = str(s).replace(",", ".")
        s = re.sub(r"[^0-9.\-]", "", s)
        return float(s) if s not in ("", "-", ".", "-.") else 0.0
    except Exception:
        return 0.0


def _normalize_colname(name: str) -> str:
    name = str(name).strip()
    # Fix common mojibake in incoming column names (UTF-8 bytes decoded as latin1/cp1252)
    # Example: "DÃ©signation" -> "Désignation"
    if "Ã" in name or "Â" in name or "â" in name:
        def _m_score(s: str) -> int:
            return s.count("Ã") + s.count("Â") + s.count("â")

        best = name
        best_score = _m_score(name)

        # Strict round-trip first
        for enc in ("latin1", "cp1252"):
            try:
                candidate = name.encode(enc, errors="strict").decode("utf-8", errors="strict")
            except Exception:
                continue
            cand_score = _m_score(candidate)
            if cand_score < best_score:
                best, best_score = candidate, cand_score
                if best_score == 0:
                    break

        # Fallback: permissive decode can salvage partially-broken sequences
        if best_score > 0:
            for enc in ("latin1", "cp1252"):
                try:
                    candidate = name.encode(enc, errors="ignore").decode("utf-8", errors="ignore")
                except Exception:
                    continue
                cand_score = _m_score(candidate)
                if cand_score < best_score:
                    best, best_score = candidate, cand_score
                    if best_score == 0:
                        break

        name = best

    name = re.sub(r"\s+", " ", name)
    name = ''.join(ch for ch in unicodedata.normalize('NFKD', name) if not unicodedata.combining(ch))
    return name.casefold()


def _ensure_required_df_columns(df):
    # Accept common variants like 'Designation' vs 'Désignation'
    required = ['Désignation', 'Marque', 'Quantité', 'Prix Achat TTC', 'Prix Unit. TTC', 'TVA (%)']
    norm_map = { _normalize_colname(c): c for c in df.columns }
    for target in required:
        if target in df.columns:
            continue
        want = _normalize_colname(target)
        src = norm_map.get(want)
        if src is None:
            want2 = re.sub(r"[^a-z0-9]+", "", want)
            for c in df.columns:
                if re.sub(r"[^a-z0-9]+", "", _normalize_colname(c)) == want2:
                    src = c
                    break
        if src is not None:
            df.rename(columns={src: target}, inplace=True)
        else:
            raise KeyError(f"Missing required column {target!r}. Columns: {list(df.columns)!r}")


def sanitize_df(df):
    df = df.copy()
    _ensure_required_df_columns(df)
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


def _img_candidates(name_base: str):
    return [
        PICTURES_DIR / f"{name_base}.png",
        PICTURES_DIR / f"{name_base}.jpg",
        PICTURES_DIR / f"{name_base}.jpeg",
    ]


def get_dynamic_image(photo_key: str):
    if not photo_key:
        return None
    for p in _img_candidates(photo_key):
        if p.exists():
            return str(p)
    return None
