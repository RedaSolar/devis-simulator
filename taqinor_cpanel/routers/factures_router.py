import json
import re
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
import pandas as pd

from routers.auth_router import get_current_user
from pdf_generator import generate_single_pdf
import pdf_generator

router = APIRouter()

BASE_DIR = Path(".")
DEVIS_HISTORY_FILE = BASE_DIR / "devis_history.json"
CONFIG_FILE = BASE_DIR / "config.json"
FACTURES_DIR = BASE_DIR / "factures_client"
FACTURES_DIR.mkdir(exist_ok=True)

# Ensure pdf_generator paths are set
pdf_generator.DEVIS_DIR = BASE_DIR / "devis_client"
pdf_generator.FACTURES_DIR = FACTURES_DIR
pdf_generator.LOGO_PATH = BASE_DIR / "logo.png"


def _load_history() -> dict:
    if DEVIS_HISTORY_FILE.exists():
        with open(DEVIS_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"devis_counter": 1, "facture_counter": 1}


def _save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


class GenerateFactureRequest(BaseModel):
    devis_id: str
    facture_number: int = 0


@router.get("")
async def list_factures(current_user: dict = Depends(get_current_user)):
    factures = []
    if FACTURES_DIR.exists():
        for pdf_file in sorted(FACTURES_DIR.glob("*.pdf"), reverse=True):
            factures.append({
                "filename": pdf_file.name,
                "download_url": f"/api/factures/{pdf_file.name}/pdf",
                "size": pdf_file.stat().st_size,
            })
    return factures


@router.post("/generate")
async def generate_facture(body: GenerateFactureRequest, current_user: dict = Depends(get_current_user)):
    history = _load_history()
    entry = history.get(body.devis_id) or history.get(str(body.devis_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Devis not found in history")

    cfg = _load_config()
    facture_number = body.facture_number if body.facture_number > 0 else cfg.get("facture_counter", 1)

    # Reconstruct DataFrame from history
    df_data = entry.get("df_sans") or entry.get("df") or []
    if isinstance(df_data, list):
        df = pd.DataFrame(df_data)
    elif isinstance(df_data, dict):
        df = pd.DataFrame.from_dict(df_data)
    else:
        df = pd.DataFrame()

    # Ensure required columns exist
    for col in ["Désignation", "Marque", "Quantité", "Prix Achat TTC", "Prix Unit. TTC", "TVA (%)"]:
        if col not in df.columns:
            df[col] = 0 if col not in ["Désignation", "Marque"] else ""

    client_name = entry.get("client_name", "Client")
    client_address = entry.get("client_address", "")
    client_phone = entry.get("client_phone", "")
    doc_number = entry.get("doc_number", body.devis_id)
    notes = entry.get("notes_sans", [])
    scenario_choice = entry.get("scenario_choice", "Sans batterie")

    try:
        result = generate_single_pdf(
            df_in=df,
            client_name=client_name,
            client_address=client_address,
            client_phone=client_phone,
            doc_type="Facture",
            doc_number=facture_number,
            notes=notes,
        )
        # generate_single_pdf returns (pdf_path, file_name) or just a path string
        if isinstance(result, tuple):
            pdf_path_obj, pdf_filename = result
        else:
            pdf_path_obj = result
            pdf_filename = Path(str(result)).name if result else f"Facture_{client_name}_{facture_number}.pdf"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Facture PDF generation failed: {str(e)}")

    # Increment facture counter
    cfg["facture_counter"] = facture_number + 1
    _save_config(cfg)

    return {
        "pdf_filename": pdf_filename,
        "download_url": f"/api/factures/{pdf_filename}/pdf",
        "facture_number": facture_number,
    }


@router.get("/{filename}/pdf")
async def download_facture(filename: str, current_user: dict = Depends(get_current_user)):
    # Security: prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    pdf_path = FACTURES_DIR / filename
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"Facture file not found: {filename}")
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=filename,
    )
