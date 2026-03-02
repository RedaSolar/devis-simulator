from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Any
from routers.auth_router import get_current_user
from catalog import (
    load_catalog,
    save_catalog,
    set_prices,
    get_prices,
    known_brands,
    load_custom_templates,
    save_custom_templates,
)

router = APIRouter()


# ---------- Pydantic schemas ----------
class InverterEntry(BaseModel):
    onduleur_type: str  # "Onduleur Injection" or "Onduleur Hybride"
    brand: str
    power_kw: float
    phase: str = "Monophase"
    sell_ttc: float = 0.0
    buy_ttc: float = 0.0


class PanelEntry(BaseModel):
    brand: str
    power_w: int
    sell_ttc: float = 0.0
    buy_ttc: float = 0.0


class BatteryEntry(BaseModel):
    brand: str
    capacity_kwh: float
    sell_ttc: float = 0.0
    buy_ttc: float = 0.0


class TemplatesPayload(BaseModel):
    templates: List[Any]


class PriceUpdate(BaseModel):
    category: str
    brand: str = "__default__"
    power: str = ""
    phase: str = ""
    sell_ttc: float = 0.0
    buy_ttc: float = 0.0


# ---------- Endpoints ----------
@router.get("")
async def get_catalog(current_user: dict = Depends(get_current_user)):
    return load_catalog()


@router.get("/brands/{category}")
async def get_brands(category: str, current_user: dict = Depends(get_current_user)):
    catalog = load_catalog()
    brands = known_brands(catalog, category)
    return {"category": category, "brands": brands}


@router.post("/inverter")
async def add_inverter(entry: InverterEntry, current_user: dict = Depends(get_current_user)):
    catalog = load_catalog()
    # Build nested variant structure
    base_key = entry.onduleur_type
    if base_key not in ("Onduleur Injection", "Onduleur Hybride"):
        raise HTTPException(status_code=400, detail="onduleur_type must be 'Onduleur Injection' or 'Onduleur Hybride'")
    brand_entry = catalog.setdefault(base_key, {}).setdefault(entry.brand, {})
    power_str = str(entry.power_kw)
    power_entry = brand_entry.setdefault(power_str, {"variants": {}})
    if "variants" not in power_entry:
        power_entry["variants"] = {}
    power_entry["variants"][entry.phase] = {
        "sell_ttc": entry.sell_ttc,
        "buy_ttc": entry.buy_ttc,
        "phase": entry.phase,
    }
    save_catalog(catalog)
    return {"status": "ok", "message": f"Inverter {entry.brand} {entry.power_kw}kW ({entry.phase}) saved"}


@router.post("/panel")
async def add_panel(entry: PanelEntry, current_user: dict = Depends(get_current_user)):
    catalog = load_catalog()
    brand_entry = catalog.setdefault("Panneaux", {}).setdefault(entry.brand, {})
    brand_entry[str(entry.power_w)] = {
        "sell_ttc": entry.sell_ttc,
        "buy_ttc": entry.buy_ttc,
    }
    save_catalog(catalog)
    return {"status": "ok", "message": f"Panel {entry.brand} {entry.power_w}W saved"}


@router.post("/battery")
async def add_battery(entry: BatteryEntry, current_user: dict = Depends(get_current_user)):
    catalog = load_catalog()
    brand_entry = catalog.setdefault("Batterie", {}).setdefault(entry.brand, {})
    cap = entry.capacity_kwh
    cap_str = str(int(cap)) if cap == int(cap) else str(cap)
    brand_entry[cap_str] = {
        "sell_ttc": entry.sell_ttc,
        "buy_ttc": entry.buy_ttc,
    }
    save_catalog(catalog)
    return {"status": "ok", "message": f"Battery {entry.brand} {entry.capacity_kwh}kWh saved"}


@router.patch("/price")
async def update_price(entry: PriceUpdate, current_user: dict = Depends(get_current_user)):
    catalog = load_catalog()
    cat = catalog.get(entry.category)
    if cat is None:
        raise HTTPException(status_code=404, detail=f"Catégorie introuvable: {entry.category}")

    brand = entry.brand if entry.brand else "__default__"

    if entry.power and entry.phase:
        # Onduleur: category → brand → power → variants → phase
        target = (cat.get(brand, {})
                     .get(entry.power, {})
                     .get("variants", {})
                     .get(entry.phase))
        if target is None:
            raise HTTPException(status_code=404, detail="Variante onduleur introuvable")
    elif entry.power:
        # Panneaux / Batterie: category → brand → power
        target = cat.get(brand, {}).get(entry.power)
        if target is None:
            raise HTTPException(status_code=404, detail="Entrée introuvable")
    else:
        # Simple __default__ or brand-level entry
        target = cat.get(brand)
        if target is None:
            raise HTTPException(status_code=404, detail="Entrée introuvable")

    target["sell_ttc"] = entry.sell_ttc
    target["buy_ttc"] = entry.buy_ttc
    save_catalog(catalog)
    return {"status": "ok", "message": "Prix mis à jour"}


@router.get("/templates")
async def get_templates(current_user: dict = Depends(get_current_user)):
    return load_custom_templates()


@router.post("/templates")
async def save_templates(payload: TemplatesPayload, current_user: dict = Depends(get_current_user)):
    save_custom_templates(payload.templates)
    return {"status": "ok", "count": len(payload.templates)}
