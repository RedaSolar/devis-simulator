from pydantic import BaseModel
from typing import Optional, List


class ProductLine(BaseModel):
    designation: str
    marque: str = ""
    quantite: float = 0
    prix_achat_ttc: float = 0
    prix_unit_ttc: float = 0
    tva: float = 20
    photo: str = ""


class RoiData(BaseModel):
    factures_mensuelles: List[float]  # 12 values
    day_usage_percent: int = 60


class DevisRequest(BaseModel):
    doc_number: int
    installation_type: str = "Résidentielle"
    client_name: str
    client_address: str = ""
    client_phone: str = ""
    scenario_choice: str = "Les deux (Sans + Avec)"
    recommended_option: str = "Aucune recommandation"
    puissance_kwp: float
    puissance_panneau_w: int = 710
    roi_data: RoiData
    product_lines: List[ProductLine]
    custom_lines_sans: List[ProductLine] = []
    custom_lines_avec: List[ProductLine] = []
    notes_sans: List[str] = []
    notes_avec: List[str] = []
    structure_type: str = "acier"
