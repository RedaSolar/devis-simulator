from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional
from routers.auth_router import get_current_user
from roi import interpoler_factures
from constants import GHI, MOIS, DAYS_IN_MONTH, EFFICIENCY, KWH_PRICE

router = APIRouter()


class EstimateMonthsRequest(BaseModel):
    f_hiver: float
    f_ete: float


class ROICalculateRequest(BaseModel):
    puissance_kwp: float
    factures_mensuelles: List[float]  # 12 values
    day_usage_percent: int = 50
    total_cost_sans: float = 0.0
    total_cost_avec: float = 0.0
    battery_capacity_kwh: float = 10.0


@router.post("/estimate-months")
async def estimate_months(body: EstimateMonthsRequest, current_user: dict = Depends(get_current_user)):
    monthly = interpoler_factures(body.f_hiver, body.f_ete)
    return {"monthly": monthly}


@router.post("/calculate")
async def calculate_roi(body: ROICalculateRequest, current_user: dict = Depends(get_current_user)):
    kwp = body.puissance_kwp
    factures = body.factures_mensuelles
    day_pct = body.day_usage_percent / 100.0
    battery_kwh = body.battery_capacity_kwh

    # Ensure 12 monthly bills
    if len(factures) < 12:
        factures = factures + [factures[-1] if factures else 500.0] * (12 - len(factures))
    factures = factures[:12]

    monthly_production = []
    eco_sans_monthly = []
    eco_avec_monthly = []
    monthly_detail = []

    for i in range(12):
        # Monthly production in kWh: GHI[i] * kwp * EFFICIENCY
        prod_kwh = GHI[i] * kwp * EFFICIENCY
        monthly_production.append(prod_kwh)

        # Self-consumed (day usage)
        self_consumed = prod_kwh * day_pct

        # Savings SANS battery: self-consumed * price
        eco_sans = self_consumed * KWH_PRICE

        # Savings AVEC battery: add battery storage savings
        # Battery can store (capacity_kwh * days_in_month) additional kWh
        days = DAYS_IN_MONTH[i]
        remaining_prod = prod_kwh - self_consumed
        battery_stored = min(battery_kwh * days, remaining_prod)
        eco_avec = (self_consumed + battery_stored) * KWH_PRICE

        eco_sans_monthly.append(eco_sans)
        eco_avec_monthly.append(eco_avec)

        monthly_detail.append({
            "month": MOIS[i],
            "production_kwh": round(prod_kwh, 1),
            "self_consumed_kwh": round(self_consumed, 1),
            "eco_sans": round(eco_sans, 2),
            "eco_avec": round(eco_avec, 2),
            "facture": round(factures[i], 2),
        })

    production_annuelle = sum(monthly_production)
    eco_annuelle_sans = sum(eco_sans_monthly)
    eco_annuelle_avec = sum(eco_avec_monthly)

    # Payback period (years)
    payback_sans = (body.total_cost_sans / eco_annuelle_sans) if eco_annuelle_sans > 0 and body.total_cost_sans > 0 else None
    payback_avec = (body.total_cost_avec / eco_annuelle_avec) if eco_annuelle_avec > 0 and body.total_cost_avec > 0 else None

    # 25-year cumulative savings (starting from -cost, adding annual savings each year)
    years = list(range(0, 26))
    cumul_sans = []
    cumul_avec = []
    val_sans = -body.total_cost_sans
    val_avec = -body.total_cost_avec
    cumul_sans.append(round(val_sans, 2))
    cumul_avec.append(round(val_avec, 2))
    for _ in range(1, 26):
        val_sans += eco_annuelle_sans
        val_avec += eco_annuelle_avec
        cumul_sans.append(round(val_sans, 2))
        cumul_avec.append(round(val_avec, 2))

    return {
        "production_annuelle_kwh": round(production_annuelle, 1),
        "monthly_detail": monthly_detail,
        "eco_annuelle_sans": round(eco_annuelle_sans, 2),
        "eco_annuelle_avec": round(eco_annuelle_avec, 2),
        "eco_sans_monthly": [round(v, 2) for v in eco_sans_monthly],
        "eco_avec_monthly": [round(v, 2) for v in eco_avec_monthly],
        "payback_sans": round(payback_sans, 1) if payback_sans else None,
        "payback_avec": round(payback_avec, 1) if payback_avec else None,
        "cumulative_25": {
            "years": years,
            "sans": cumul_sans,
            "avec": cumul_avec,
        },
    }
