from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from routers.auth_router import get_current_user
from catalog import load_catalog
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

    from autofill import auto_fill_from_power

    catalog = load_catalog()
    df = _get_base_df()

    try:
        result_df = auto_fill_from_power(df, catalog, body.puissance_kwp, body.puissance_panneau_w)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Autofill error: {str(e)}")

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
    return cleaned
