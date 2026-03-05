# ---------- CONSTANTES VISUELLES ----------
BLUE_MAIN = "#0A5275"        # Bleu TAQINOR
BLUE_LIGHT = "#E6F1F7"
TEXT_DARK = "#222222"
ORANGE_ACCENT = "#F28E2B"
GREY_NEUTRAL = "#555555"

# ---------- CONSTANTES ROI / PRODUCTION ----------
GHI = [83.99, 96.79, 133.43, 155.30, 175.28, 179.62, 179.56, 161.17, 137.03, 111.59, 81.91, 74.61]
MOIS = ["Jan","Fév","Mar","Avr","Mai","Juin","Juil","Août","Sep","Oct","Nov","Déc"]
DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
EFFICIENCY = 0.8  # rendement global
KWH_PRICE = 1.75  # MAD/kWh FIXE (utilisé en interne — ne pas afficher dans les PDF/UI)

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
