"""Generate a test PDF directly — run: python test_pdf_generate.py"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

import pdf_generator
from pdf_generator import generate_double_devis_pdf
from roi import roi_figure_buffer, roi_cumulative_buffer
from constants import GHI, MOIS, DAYS_IN_MONTH, EFFICIENCY, KWH_PRICE

# Force correct paths
pdf_generator.DEVIS_DIR = Path(__file__).parent / "devis_client"
pdf_generator.DEVIS_DIR.mkdir(exist_ok=True)
pdf_generator.LOGO_PATH = Path(__file__).parent / "logo.png"
pdf_generator.PICTURES_DIR = Path(__file__).parent / "pictures"

# Build test DataFrames
df_sans = pd.DataFrame([
    {"Désignation": "Panneaux",        "Marque": "JA Solar 415W", "Quantité": 10, "Prix Achat TTC": 1000, "Prix Unit. TTC": 1200, "TVA (%)": 20},
    {"Désignation": "Onduleur réseau", "Marque": "Huawei 5kW",    "Quantité": 1,  "Prix Achat TTC": 3000, "Prix Unit. TTC": 3500, "TVA (%)": 20},
    {"Désignation": "Structures",      "Marque": "",               "Quantité": 1,  "Prix Achat TTC": 500,  "Prix Unit. TTC": 600,  "TVA (%)": 20},
    {"Désignation": "Installation",    "Marque": "",               "Quantité": 1,  "Prix Achat TTC": 2000, "Prix Unit. TTC": 2500, "TVA (%)": 20},
])
df_avec = pd.DataFrame([
    {"Désignation": "Panneaux",         "Marque": "JA Solar 415W", "Quantité": 10, "Prix Achat TTC": 1000, "Prix Unit. TTC": 1200, "TVA (%)": 20},
    {"Désignation": "Onduleur hybride", "Marque": "Huawei 5kW",    "Quantité": 1,  "Prix Achat TTC": 4000, "Prix Unit. TTC": 4500, "TVA (%)": 20},
    {"Désignation": "Batterie",         "Marque": "Pylontech 5kWh","Quantité": 2,  "Prix Achat TTC": 5000, "Prix Unit. TTC": 6000, "TVA (%)": 20},
    {"Désignation": "Structures",       "Marque": "",               "Quantité": 1,  "Prix Achat TTC": 500,  "Prix Unit. TTC": 600,  "TVA (%)": 20},
    {"Désignation": "Installation",     "Marque": "",               "Quantité": 1,  "Prix Achat TTC": 2000, "Prix Unit. TTC": 2500, "TVA (%)": 20},
])

factures = [500] * 6 + [700] * 6
kwp = 4.15
day_pct = 0.6
battery_kwh = 10.0

eco_sans = [GHI[i] * kwp * EFFICIENCY * day_pct * KWH_PRICE for i in range(12)]
eco_avec = [(GHI[i] * kwp * EFFICIENCY * day_pct + min(battery_kwh * DAYS_IN_MONTH[i], GHI[i] * kwp * EFFICIENCY * (1 - day_pct))) * KWH_PRICE for i in range(12)]

years = list(range(0, 26))
total_sans = 17600.0
total_avec = 28800.0
cumul_sans = [-total_sans] + [-total_sans + sum(eco_sans) * i for i in range(1, 26)]
cumul_avec = [-total_avec] + [-total_avec + sum(eco_avec) * i for i in range(1, 26)]

roi_fig = roi_figure_buffer(MOIS, factures, eco_sans, eco_avec)
roi_cumul = roi_cumulative_buffer(years, cumul_sans, cumul_avec)

scenario = "Les deux (Sans + Avec)"

print(f"Generating PDF with scenario={scenario!r}...")
generate_double_devis_pdf(
    df_sans, df_avec,
    "Notes test SANS", "Notes test AVEC",
    "Client Test", "123 Rue Test, Casablanca", "+212 600 000000",
    "Devis", 9999,
    {"Puissance installée": "4.15 kWc", "Économies annuelles estimées": "5000 MAD"},
    {"Puissance installée": "4.15 kWc", "Économies annuelles estimées": "6000 MAD"},
    roi_fig, roi_cumul,
    scenario,
    recommended_option="Avec batterie",
    installation_type="Résidentielle",
    type_label="résidentielle",
    type_phrase="Installation photovoltaïque résidentielle",
    puissance_kwp=kwp,
    puissance_panneau_w=415,
)

out = pdf_generator.DEVIS_DIR / "Devis_Client_Test_9999.pdf"
print(f"PDF saved: {out}")
print(f"File exists: {out.exists()}")
if out.exists():
    size = out.stat().st_size
    print(f"File size: {size} bytes")
    # Count images in PDF
    with open(out, "rb") as f:
        content = f.read()
    img_count = content.count(b"/Subtype /Image")
    print(f"Images in PDF (/Subtype /Image markers): {img_count}")
