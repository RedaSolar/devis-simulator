#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_devis_premium.py  FINAL
Page 1 : white-background v1 layout
Pages 2-3 : v4 premium dark design
Usage : python generate_devis_premium.py
"""
import base64, io, json, subprocess, sys, tempfile
from pathlib import Path


def _render_pdf_weasyprint(html_string, out_path):
    """Render HTML to PDF using WeasyPrint (no browser needed)."""
    from weasyprint import HTML
    base_dir = str(Path(__file__).resolve().parent)
    HTML(string=html_string, base_url=f"file://{base_dir}/").write_pdf(str(out_path))
    if not Path(out_path).exists():
        raise RuntimeError("WeasyPrint PDF generation failed.")
    print(f"WeasyPrint rendered: {out_path}")


import os

import matplotlib
matplotlib.use("Agg")

BASE_DIR = Path(__file__).resolve().parent

# ── Inline SVG icons for Page 1 (WeasyPrint renders inline SVG perfectly) ────
SVG_CHECK   = '<svg width="14" height="14" viewBox="0 0 14 14" style="vertical-align:middle;margin-right:4px;"><circle cx="7" cy="7" r="7" fill="#2e7d32"/><path d="M4 7l2 2 4-4" stroke="white" stroke-width="1.5" fill="none" stroke-linecap="round"/></svg>'
SVG_BOLT    = '<svg width="14" height="14" viewBox="0 0 14 14" style="vertical-align:middle;margin-right:4px;"><circle cx="7" cy="7" r="7" fill="#d4a84b"/><path d="M8 3L5 8h3l-1 4 4-5H8l1-4z" fill="white"/></svg>'
SVG_CHART   = '<svg width="14" height="14" viewBox="0 0 14 14" style="vertical-align:middle;margin-right:3px;"><rect rx="3" width="14" height="14" fill="#e8f5e9"/><path d="M3 10L6 6l2 2 3-4" stroke="#2e7d32" stroke-width="1.5" fill="none" stroke-linecap="round"/></svg>'
SVG_CHART2  = '<svg width="14" height="14" viewBox="0 0 14 14" style="vertical-align:middle;margin-right:3px;"><rect rx="3" width="14" height="14" fill="#1a1a2e"/><path d="M3 10L6 6l2 2 3-4" stroke="white" stroke-width="1.5" fill="none" stroke-linecap="round"/></svg>'
SVG_STAR    = '<svg width="14" height="14" viewBox="0 0 14 14" style="vertical-align:middle;margin-right:3px;"><path d="M7 1l2 4h4l-3 3 1 4-4-2-4 2 1-4-3-3h4z" fill="#d4a84b"/></svg>'
SVG_HOUSE   = '<svg width="14" height="14" viewBox="0 0 14 14" style="vertical-align:middle;margin-right:3px;"><path d="M7 1L1 7h2v5h3V9h2v3h3V7h2L7 1z" fill="white"/></svg>'
SVG_FACTORY = '<svg width="14" height="14" viewBox="0 0 14 14" style="vertical-align:middle;margin-right:3px;"><rect x="1" y="7" width="12" height="6" fill="white" rx="1"/><rect x="3" y="4" width="3" height="3" fill="white"/><rect x="8" y="4" width="3" height="3" fill="white"/><rect x="5" y="1" width="4" height="3" fill="white"/></svg>'
SVG_SUN     = '<svg width="12" height="12" viewBox="0 0 12 12" style="vertical-align:middle;margin-right:3px;"><circle cx="6" cy="6" r="3" fill="#d4a84b"/><g stroke="#d4a84b" stroke-width="1"><line x1="6" y1="0" x2="6" y2="2"/><line x1="6" y1="10" x2="6" y2="12"/><line x1="0" y1="6" x2="2" y2="6"/><line x1="10" y1="6" x2="12" y2="6"/></g></svg>'
SVG_ZAP     = '<svg width="12" height="12" viewBox="0 0 12 12" style="vertical-align:middle;margin-right:3px;"><path d="M7 1L3 7h3l-1 4 5-6H7l1-4z" fill="#d4a84b"/></svg>'
SVG_GLOBE   = '<svg width="12" height="12" viewBox="0 0 12 12" style="vertical-align:middle;margin-right:3px;"><circle cx="6" cy="6" r="5" fill="none" stroke="#4caf50" stroke-width="1"/><ellipse cx="6" cy="6" rx="2.5" ry="5" fill="none" stroke="#4caf50" stroke-width="0.8"/><line x1="1" y1="6" x2="11" y2="6" stroke="#4caf50" stroke-width="0.8"/></svg>'

def svg_num(n):
    return (f'<svg width="16" height="16" viewBox="0 0 16 16" style="vertical-align:middle;margin-right:2px;">'
            f'<circle cx="8" cy="8" r="7" fill="#d4a84b"/>'
            f'<text x="8" y="11.5" text-anchor="middle" font-size="10" fill="white" font-weight="bold">{n}</text>'
            f'</svg>')

def _fetch_gfont(family_url, weight=400, style="normal"):
    """Download Google Font woff2 (Latin subset) and return base64; cached in temp dir."""
    import urllib.request, re as _re, tempfile as _tmp
    safe = family_url.replace("+", "_").lower()
    cache = Path(_tmp.gettempdir()) / f"taqinor_{safe}_{style}_{weight}.woff2"
    if cache.exists():
        return base64.b64encode(cache.read_bytes()).decode()
    try:
        _UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
               "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        sp = f":ital,wght@1,{weight}" if style == "italic" else f":wght@{weight}"
        url = f"https://fonts.googleapis.com/css2?family={family_url}{sp}&display=block"
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=10) as r:
            css = r.read().decode()
        woffs = _re.findall(r"url\((https://fonts\.gstatic\.com/[^)]+\.woff2)\)", css)
        if not woffs:
            return None
        with urllib.request.urlopen(woffs[-1], timeout=15) as r:
            data = r.read()
        cache.write_bytes(data)
        return base64.b64encode(data).decode()
    except Exception:
        return None

def _font_face(family, weight, style, b64):
    if not b64:
        return ""
    return (f'@font-face{{font-family:"{family}";font-style:{style};font-weight:{weight};'
            f'font-display:block;src:url("data:font/woff2;base64,{b64}") format("woff2");}}')

# Fetch and cache all fonts needed for page 1
_DS400     = _fetch_gfont("DM+Serif+Display", 400)   # DM Serif Display Regular
_DMSANS400 = _fetch_gfont("DM+Sans", 400)             # DM Sans Regular
_DMSANS500 = _fetch_gfont("DM+Sans", 500)             # DM Sans Medium
_DMSANS700 = _fetch_gfont("DM+Sans", 700)             # DM Sans Bold

# Playfair Display (pages 2-3 backward compat)
_PF700 = _fetch_gfont("Playfair+Display", 700)
_PF400 = _fetch_gfont("Playfair+Display", 400)

def _pf_face(weight, b64):
    if not b64:
        return ""
    return (f'@font-face{{font-family:"Playfair Display";font-style:normal;'
            f'font-weight:{weight};font-display:block;'
            f'src:url("data:font/woff2;base64,{b64}") format("woff2");}}')

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ── Design tokens ────────────────────────────────────────────────────────────
CN  = "#0F1E35"
CNM = "#1A2B4A"
CA  = "#F5A623"
CAL = "#FDF3E3"
CW  = "#FFFFFF"
CG1 = "#F7F8FA"
CG2 = "#EAECF0"
CG4 = "#9BA3AE"
CG7 = "#374151"
CGR = "#16A34A"

# ═══════════════════════════════════════════════════════════════════════════════
# QUOTE_INPUT — seule section à modifier pour changer un devis
# ═══════════════════════════════════════════════════════════════════════════════
QUOTE_INPUT = {
    "ref":              "412",
    "date":             "28/02/2026",
    "client_name":      "Reda Kasri",
    "client_addr":      "5 Rue Ennoussour RDC",
    "client_phone":     "0661850410",
    "inst_type":        "R\u00e9sidentielle",
    "puissance_kwc":    10.65,
    "nb_panneaux":      15,
    "watt_par_panneau": 710,
    "city":             "Casablanca",
    "prod_kwh":         13190,
    "eco_s_ann":        15828,   # \u00e9conomies/an affich\u00e9es \u2014 Option 1
    "eco_a_ann":        25232,   # \u00e9conomies/an affich\u00e9es \u2014 Option 2 (KPI)
    "eco_a_cumul":      19478,   # taux r\u00e9el pour courbe ROI cumulatif
    "roi_s":            3.3,
    "roi_a":            5.5,
    "eco_s_monthly":    [850, 980,1320,1560,1820,1850,1840,1610,1390,1120, 830, 760],
    "eco_a_monthly":    [1380,1590,2140,2220,2470,2640,2650,2510,2280,1890,1380,1230],
    # Batteries incluses dans l'Option 2
    "battery_option": [
        {"designation": "Batterie 5\u202fkWh",  "marque": "Deye", "quantite": 1, "prix_unit_ttc": 16000},
        {"designation": "Batterie 10\u202fkWh", "marque": "Deye", "quantite": 1, "prix_unit_ttc": 27000},
    ],
    # Overrides — None = formule bloc automatique
    "overrides": {
        "onduleur_reseau":   15000,
        "smart_meter":       1800,
        "wifi_dongle":       1200,
        "prix_panneau":      1100,
        "onduleur_hybride":  29000,
        "structures_unit":   450,
        "installation":      4000,   # override formule: (blocks+1)\u00d72400
        "tableau":           2000,   # override formule: blocks\u00d71500
        "accessoires":       None,   # None \u2192 blocks\u00d71000 = 2000
        "transport":         1000,
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# PRICING ENGINE
# ═══════════════════════════════════════════════════════════════════════════════
def calculate_quote(q):
    """Block-based pricing engine. blocks = max(1, round(kwc/5))."""
    kwc    = q["puissance_kwc"]
    nb_pan = q["nb_panneaux"]
    ovr    = q.get("overrides", {})

    blocks = max(1, round(kwc / 5))

    def ov(key, default):
        v = ovr.get(key)
        return v if v is not None else default

    installation     = ov("installation",     (blocks + 1) * 2400)
    accessoires      = ov("accessoires",      blocks * 1000)
    tableau          = ov("tableau",          blocks * 1500)
    transport        = ov("transport",        1000)
    structures_unit  = ov("structures_unit",  450)
    onduleur_reseau  = ov("onduleur_reseau",  14000)
    smart_meter      = ov("smart_meter",      1500)
    wifi_dongle      = ov("wifi_dongle",      0)
    prix_panneau     = ov("prix_panneau",     1100)
    onduleur_hybride = ov("onduleur_hybride", 29000)

    sans_items = [
        {"designation": "Onduleur r\u00e9seau",              "marque": "Huawei",         "quantite": 1,      "prix_unit_ttc": onduleur_reseau},
        {"designation": "Smart Meter",                       "marque": "Huawei",         "quantite": 1,      "prix_unit_ttc": smart_meter},
        {"designation": "Wifi Dongle",                       "marque": "Huawei",         "quantite": 1,      "prix_unit_ttc": wifi_dongle},
        {"designation": "Panneaux",                          "marque": "Canadian Solar", "quantite": nb_pan, "prix_unit_ttc": prix_panneau},
        {"designation": "Structures acier",                  "marque": "",               "quantite": nb_pan, "prix_unit_ttc": structures_unit},
        {"designation": "Socles",                            "marque": "",               "quantite": 30,     "prix_unit_ttc": 80},
        {"designation": "Accessoires",                       "marque": "",               "quantite": 1,      "prix_unit_ttc": accessoires},
        {"designation": "Tableau De Protection AC/DC",       "marque": "",               "quantite": 1,      "prix_unit_ttc": tableau},
        {"designation": "Installation",                      "marque": "",               "quantite": 1,      "prix_unit_ttc": installation},
        {"designation": "Transport",                         "marque": "",               "quantite": 1,      "prix_unit_ttc": transport},
    ]

    avec_base = [
        {"designation": "Onduleur hybride",                  "marque": "Deye",           "quantite": 1,      "prix_unit_ttc": onduleur_hybride},
        {"designation": "Panneaux",                          "marque": "Canadian Solar", "quantite": nb_pan, "prix_unit_ttc": prix_panneau},
    ]
    batteries = list(q.get("battery_option", []))
    avec_tail = [
        {"designation": "Structures acier",                  "marque": "",               "quantite": nb_pan, "prix_unit_ttc": structures_unit},
        {"designation": "Socles",                            "marque": "",               "quantite": 30,     "prix_unit_ttc": 80},
        {"designation": "Accessoires",                       "marque": "",               "quantite": 1,      "prix_unit_ttc": accessoires},
        {"designation": "Tableau De Protection AC/DC",       "marque": "",               "quantite": 1,      "prix_unit_ttc": tableau},
        {"designation": "Installation",                      "marque": "",               "quantite": 1,      "prix_unit_ttc": installation},
        {"designation": "Transport",                         "marque": "",               "quantite": 1,      "prix_unit_ttc": transport},
    ]
    avec_items = avec_base + batteries + avec_tail

    total_sans = sum(it["quantite"] * it["prix_unit_ttc"] for it in sans_items)
    total_avec = sum(it["quantite"] * it["prix_unit_ttc"] for it in avec_items)

    return {
        "sans_items": sans_items, "avec_items": avec_items,
        "total_sans": total_sans, "total_avec": total_avec,
        "blocks": blocks,
    }

# ── Run pricing engine ────────────────────────────────────────────────────────
_Q = calculate_quote(QUOTE_INPUT)

CLIENT_NAME  = QUOTE_INPUT["client_name"]
CLIENT_ADDR  = QUOTE_INPUT["client_addr"]
CLIENT_PHONE = QUOTE_INPUT["client_phone"]
CLIENT_ICE   = QUOTE_INPUT.get("client_ice", "")
REF          = QUOTE_INPUT["ref"]
DATE_STR     = QUOTE_INPUT["date"]
KWC          = QUOTE_INPUT["puissance_kwc"]
NB_PAN       = QUOTE_INPUT["nb_panneaux"]
WP           = QUOTE_INPUT["watt_par_panneau"]
PROD_KWH     = QUOTE_INPUT["prod_kwh"]
TOTAL_SANS        = _Q["total_sans"]
TOTAL_AVEC        = _Q["total_avec"]
DISCOUNT_PCT      = 0.0
TOTAL_SANS_BEFORE = _Q["total_sans"]
TOTAL_AVEC_BEFORE = _Q["total_avec"]
ECO_S_ANN    = QUOTE_INPUT["eco_s_ann"]
ECO_A_ANN    = QUOTE_INPUT["eco_a_ann"]
ROI_S        = QUOTE_INPUT["roi_s"]
ROI_A        = QUOTE_INPUT["roi_a"]
INST_TYPE    = QUOTE_INPUT["inst_type"]
SANS_ITEMS   = _Q["sans_items"]
AVEC_ITEMS   = _Q["avec_items"]

MONTHS  = ["Jan","F\u00e9v","Mar","Avr","Mai","Jun",
           "Jul","Ao\u00fb","Sep","Oct","Nov","D\u00e9c"]
ECO_S_M    = QUOTE_INPUT["eco_s_monthly"]
ECO_A_M    = QUOTE_INPUT["eco_a_monthly"]
# Actual monthly bills entered by user; fallback to proxy if not in QUOTE_INPUT
FACTURES_M = QUOTE_INPUT.get("factures_mensuelles") or [
    round(v * (ECO_S_ANN / 0.65) / max(1, sum(QUOTE_INPUT["eco_s_monthly"])))
    for v in QUOTE_INPUT["eco_s_monthly"]
]

YEARS   = list(range(26))
CUMUL_S = [-TOTAL_SANS + ECO_S_ANN * y for y in YEARS]
CUMUL_A = [-TOTAL_AVEC + QUOTE_INPUT["eco_a_cumul"] * y for y in YEARS]

SCENARIO    = "Les deux (Sans + Avec)"
RECOMMENDED = "Avec batterie"

# ── SVG equipment icons ──────────────────────────────────────────────────────
_SVG = {
"onduleur":     '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect width="40" height="40" rx="6" fill="#1A2B4A"/><rect x="6" y="8" width="28" height="20" rx="3" fill="none" stroke="#F5A623" stroke-width="2"/><circle cx="14" cy="18" r="4" fill="none" stroke="#F5A623" stroke-width="1.5"/><path d="M22 14 L28 18 L22 22" fill="none" stroke="#F5A623" stroke-width="1.5" stroke-linejoin="round"/><rect x="10" y="30" width="20" height="3" rx="1.5" fill="#F5A623" opacity="0.6"/></svg>',
"panneaux":     '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect width="40" height="40" rx="6" fill="#004B87"/><rect x="5" y="10" width="30" height="20" rx="2" fill="none" stroke="white" stroke-width="1.5"/><line x1="5" y1="20" x2="35" y2="20" stroke="white" stroke-width="1"/><line x1="18" y1="10" x2="18" y2="30" stroke="white" stroke-width="1"/><line x1="27" y1="10" x2="27" y2="30" stroke="white" stroke-width="1"/><circle cx="20" cy="5" r="3" fill="#F5A623"/><line x1="20" y1="8" x2="20" y2="10" stroke="#F5A623" stroke-width="1.5"/></svg>',
"batterie":     '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect width="40" height="40" rx="6" fill="#FF6B00"/><rect x="5" y="12" width="26" height="16" rx="3" fill="none" stroke="white" stroke-width="2"/><rect x="31" y="16" width="4" height="8" rx="2" fill="white"/><rect x="8" y="15" width="6" height="10" rx="1" fill="white" opacity="0.9"/><rect x="17" y="15" width="6" height="10" rx="1" fill="white" opacity="0.6"/></svg>',
"smart meter":  '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect width="40" height="40" rx="6" fill="#2C5F8A"/><rect x="8" y="8" width="24" height="24" rx="3" fill="none" stroke="white" stroke-width="1.5"/><path d="M14 20 Q20 12 26 20" fill="none" stroke="#F5A623" stroke-width="2"/><circle cx="20" cy="20" r="2" fill="#F5A623"/><line x1="20" y1="22" x2="20" y2="26" stroke="white" stroke-width="1.5"/></svg>',
"wifi":         '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect width="40" height="40" rx="6" fill="#2C5F8A"/><path d="M10 18 Q20 10 30 18" fill="none" stroke="white" stroke-width="2" stroke-linecap="round"/><path d="M13 22 Q20 16 27 22" fill="none" stroke="white" stroke-width="2" stroke-linecap="round"/><path d="M16 26 Q20 22 24 26" fill="none" stroke="#F5A623" stroke-width="2" stroke-linecap="round"/><circle cx="20" cy="30" r="2" fill="#F5A623"/></svg>',
"structures":   '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect width="40" height="40" rx="6" fill="#64748B"/><path d="M5 30 L15 15 L25 22 L35 10" fill="none" stroke="white" stroke-width="2" stroke-linejoin="round"/><line x1="5" y1="30" x2="35" y2="30" stroke="#F5A623" stroke-width="2"/><line x1="15" y1="15" x2="15" y2="30" stroke="white" stroke-width="1" stroke-dasharray="2,2"/><line x1="25" y1="22" x2="25" y2="30" stroke="white" stroke-width="1" stroke-dasharray="2,2"/></svg>',
"socles":       '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect width="40" height="40" rx="6" fill="#374151"/><rect x="8" y="28" width="24" height="4" rx="2" fill="#F5A623"/><rect x="12" y="20" width="16" height="4" rx="2" fill="white" opacity="0.8"/><rect x="16" y="13" width="8" height="5" rx="2" fill="white" opacity="0.6"/></svg>',
"accessoires":  '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect width="40" height="40" rx="6" fill="#374151"/><circle cx="12" cy="15" r="4" fill="none" stroke="#F5A623" stroke-width="2"/><circle cx="28" cy="15" r="4" fill="none" stroke="white" stroke-width="2"/><circle cx="20" cy="28" r="4" fill="none" stroke="#F5A623" stroke-width="2"/><line x1="16" y1="15" x2="24" y2="15" stroke="white" stroke-width="1.5"/><line x1="14" y1="19" x2="18" y2="24" stroke="white" stroke-width="1.5"/><line x1="26" y1="19" x2="22" y2="24" stroke="white" stroke-width="1.5"/></svg>',
"tableau":      '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect width="40" height="40" rx="6" fill="#1A2B4A"/><rect x="7" y="7" width="26" height="26" rx="3" fill="none" stroke="#F5A623" stroke-width="2"/><rect x="11" y="11" width="8" height="8" rx="1" fill="#F5A623" opacity="0.8"/><rect x="21" y="11" width="8" height="8" rx="1" fill="white" opacity="0.6"/><rect x="11" y="21" width="8" height="8" rx="1" fill="white" opacity="0.6"/><rect x="21" y="21" width="8" height="8" rx="1" fill="#F5A623" opacity="0.4"/></svg>',
"installation": '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect width="40" height="40" rx="6" fill="#F5A623"/><path d="M28 8 C32 8 34 12 32 16 L18 30 C15 33 11 33 9 30 C7 27 7 23 10 21 L24 7 C25.5 6.5 28 8 28 8Z" fill="white"/><circle cx="11" cy="29" r="3" fill="#F5A623"/></svg>',
"transport":    '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect width="40" height="40" rx="6" fill="#16A34A"/><rect x="3" y="14" width="22" height="13" rx="2" fill="white" opacity="0.9"/><path d="M25 19 L34 19 L37 25 L37 27 L25 27 Z" fill="white" opacity="0.9"/><circle cx="9" cy="30" r="3.5" fill="#16A34A" stroke="white" stroke-width="2"/><circle cx="29" cy="30" r="3.5" fill="#16A34A" stroke="white" stroke-width="2"/></svg>',
"suivi":        '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect width="40" height="40" rx="6" fill="#6B7280"/><rect x="6" y="9" width="28" height="24" rx="3" fill="none" stroke="white" stroke-width="1.5"/><rect x="6" y="9" width="28" height="8" rx="3" fill="white" opacity="0.15"/><line x1="13" y1="6" x2="13" y2="12" stroke="#F5A623" stroke-width="2" stroke-linecap="round"/><line x1="27" y1="6" x2="27" y2="12" stroke="#F5A623" stroke-width="2" stroke-linecap="round"/><path d="M11 24 L16 28 L29 19" fill="none" stroke="#F5A623" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
}

_BRAND_C = {
    "huawei":   ("#CF0A2C", "#fff"),
    "canadian": ("#004B87", "#fff"),
    "canadien": ("#004B87", "#fff"),
    "deye":     ("#FF6B00", "#fff"),
    "deyness":  ("#FF6B00", "#fff"),
}

_GAR = {
    "onduleur":"10 ans","panneaux":"12 ans","batterie":"10 ans","structures":"20 ans",
    "smart meter":"2 ans","wifi":"2 ans","tableau":"\u2014","installation":"\u2014",
    "transport":"\u2014","accessoires":"\u2014","socles":"\u2014","suivi":"\u2014",
}

# ── Helpers ──────────────────────────────────────────────────────────────────
def fmt(v):
    """Format as French MAD amount: 52\u202f650\u00a0MAD"""
    try:
        return f"{int(round(float(v))):,}".replace(",", "\u202f") + "\u00a0MAD"
    except Exception:
        return str(v)

def fnum(v):
    """Format number with French thin-space thousands separator."""
    try:
        return f"{int(round(float(v))):,}".replace(",", "\u202f")
    except Exception:
        return str(v)

def kwc_fr(v):
    """Format kWc value with French decimal comma: 10,65"""
    return f"{v:.2f}".replace(".", ",")

def b64(src):
    if isinstance(src, (str, Path)):
        raw = open(src, "rb").read()
        ext = str(src).rsplit(".", 1)[-1].lower()
        mime = "image/png" if ext == "png" else "image/jpeg"
    else:
        src.seek(0); raw = src.read(); mime = "image/png"
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"

def svg_uri(svg_str):
    return "data:image/svg+xml;base64," + base64.b64encode(svg_str.encode()).decode()

def icon_img(des, _mar=""):
    d = des.lower()
    key = None
    if   "panneaux"     in d: key = "panneaux"
    elif "batterie"     in d: key = "batterie"
    elif "smart meter"  in d: key = "smart meter"
    elif "wifi" in d or "dongle" in d: key = "wifi"
    elif "onduleur"     in d: key = "onduleur"
    elif "structures"   in d: key = "structures"
    elif "socles"       in d: key = "socles"
    elif "accessoires"  in d: key = "accessoires"
    elif "tableau"      in d: key = "tableau"
    elif "installation" in d: key = "installation"
    elif "transport"    in d: key = "transport"
    elif "suivi"        in d: key = "suivi"
    svg = _SVG.get(key, _SVG["accessoires"])
    return f'<img src="{svg_uri(svg)}" width="36" height="36" style="border-radius:5px;display:block;">'

def badge(mar):
    if not mar or mar.lower() in ("", "nan"): return ""
    bg, fg = CNM, "#fff"
    for k, (b_, f_) in _BRAND_C.items():
        if k in mar.lower(): bg, fg = b_, f_; break
    return (f'<span style="display:inline-block;background:{bg};color:{fg};border-radius:3px;'
            f'padding:1px 5px;font-size:5.5pt;font-weight:700;vertical-align:middle;">{mar}</span>')

def logo_html(h="36px"):
    """Dark logo for pages 2-3 navy headers — transparent, matching page 1 style."""
    try:
        b64_data = _logo_dark_b64()
    except Exception:
        b64_data = None
    if b64_data:
        return f'<img src="data:image/png;base64,{b64_data}" alt="TAQINOR" style="height:{h};width:auto;object-fit:contain;">'
    return (f'<span style="font-size:15pt;font-weight:900;letter-spacing:1px;color:white;">'
            f'TAQIN<span style="color:{CA};">&#9728;</span>R</span>')

def logo_badge_p1():
    """Navy badge for page 1 white header."""
    p = BASE_DIR / "logo.png"
    if p.exists():
        return f'<img src="{b64(p)}" alt="TAQINOR" style="height:44px;object-fit:contain;">'
    return f'''<div style="background:{CN};border-radius:8px;padding:7px 14px;display:inline-flex;flex-direction:column;align-items:flex-start;">
      <div style="font-size:14pt;font-weight:900;color:white;letter-spacing:1px;line-height:1.1;">TAQIN<span style="color:{CA};">&#9728;</span>R</div>
      <div style="font-size:5pt;letter-spacing:2.5px;color:{CA};font-weight:700;text-transform:uppercase;margin-top:1px;">TAQA&#183;INNOVATION&#183;NOR</div>
    </div>'''

def _logo_dark_b64():
    """Return base64 PNG of logo.png with white bg removed and dark pixels → white."""
    from PIL import Image
    p = BASE_DIR / "logo.png"
    if not p.exists():
        return None
    img = Image.open(p).convert("RGBA")
    arr = np.array(img, dtype=np.float32)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    lightness = (r + g + b) / 765.0
    # Near-white → transparent (removes white background)
    white = lightness > 0.88
    arr[white, 3] = 0
    # Dark pixels (navy/black text) → white for visibility on dark bg
    dark = (~white) & (lightness < 0.42)
    arr[dark, 0] = 255; arr[dark, 1] = 255; arr[dark, 2] = 255
    from PIL import Image as _I
    buf = io.BytesIO()
    _I.fromarray(arr.astype(np.uint8), 'RGBA').save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode()

def logo_p1_dark():
    """Logo for dark header — white bg removed, dark pixels → white, rendered on navy."""
    try:
        b64_data = _logo_dark_b64()
    except Exception:
        b64_data = None
    if b64_data:
        return (f'<img src="data:image/png;base64,{b64_data}" alt="TAQINOR" '
                f'style="height:144px;width:auto;object-fit:contain;display:block;">')
    # Fallback: text on dark background
    return (f'<div style="display:inline-block;">'
            f'<div style="font-size:17px;font-weight:900;color:white;letter-spacing:1px;line-height:1.1;">'
            f'TAQIN<span style="color:{CA};">&#9733;</span>R</div>'
            f'</div>')

def footer_p1():
    """Page 1 footer — white background."""
    return (f'<div style="background:white;padding:7px 24px;flex-shrink:0;display:flex;'
            f'align-items:center;justify-content:space-between;border-top:1px solid {CG2};">'
            f'<div style="font-size:9pt;font-weight:800;color:{CA};letter-spacing:1px;">TAQINOR</div>'
            f'<div style="font-size:7pt;color:#888888;text-align:center;">'
            f'contact@taqinor.com &nbsp;&#183;&nbsp; +212&#160;6&#160;61&#160;85&#160;04&#160;10 &nbsp;&#183;&nbsp; www.taqinor.ma</div>'
            f'<div style="font-size:7pt;color:#888888;">Page 1&nbsp;/&nbsp;3 &nbsp;|&nbsp; R\u00e9f.&nbsp;{REF}</div>'
            f'</div>')

def footer(n, total=3):
    """Pages 2-3 footer — dark navy."""
    return (f'<div style="background:{CN};padding:7px 24px;flex-shrink:0;display:flex;'
            f'align-items:center;justify-content:space-between;">'
            f'<div style="font-size:9pt;font-weight:800;color:{CA};letter-spacing:1px;">TAQINOR</div>'
            f'<div style="font-size:7pt;color:#888;text-align:center;">'
            f'contact@taqinor.com &nbsp;&#183;&nbsp; +212&#160;6&#160;61&#160;85&#160;04&#160;10 &nbsp;&#183;&nbsp; www.taqinor.ma</div>'
            f'<div style="font-size:7pt;color:#888;">Page {n}&nbsp;/&nbsp;{total} &nbsp;|&nbsp; R\u00e9f.&nbsp;{REF}</div>'
            f'</div>')

def footer_p3():
    """Page 3 footer — dark navy + legal identity line."""
    return (f'<div style="background:{CN};padding:6px 24px 5px;flex-shrink:0;margin-top:auto;">'
            f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">'
            f'<div style="font-size:9pt;font-weight:800;color:{CA};letter-spacing:1px;">TAQINOR</div>'
            f'<div style="font-size:7pt;color:#888;text-align:center;">'
            f'contact@taqinor.com &nbsp;&#183;&nbsp; +212&#160;6&#160;61&#160;85&#160;04&#160;10 &nbsp;&#183;&nbsp; www.taqinor.ma</div>'
            f'<div style="font-size:7pt;color:#888;">Page 3&nbsp;/&nbsp;3 &nbsp;|&nbsp; R\u00e9f.&nbsp;{REF}</div>'
            f'</div>'
            f'<div style="font-size:7.5px;color:#888;text-align:center;font-style:italic;">'
            f'Taqinor Solutions SARLAU &middot; RC 691213 &middot; ICE 003799642000067 &middot; '
            f'Capital 100&#8239;000 MAD &middot; Si\u00e8ge\u00a0: 5 Rue Ennoussour RDC, Casablanca'
            f'</div>'
            f'</div>')

# ── Data loading ─────────────────────────────────────────────────────────────
def load_equip(devis_id):
    """Load Option 1 equipment from devis_history.json."""
    f = BASE_DIR / "devis_history.json"
    if not f.exists(): return [], []
    try:
        with open(f, "r", encoding="utf-8") as fh: h = json.load(fh)
        e = h.get(str(devis_id), {})
        sys.path.insert(0, str(BASE_DIR))
        import pandas as pd
        from utils import sanitize_df
        def parse(recs):
            if not recs: return []
            df = pd.DataFrame(recs)
            try: df = sanitize_df(df)
            except Exception: pass
            cols = df.columns.tolist()
            def col(hints):
                for h in hints:
                    for c in cols:
                        if h in c.lower(): return c
                return None
            dc = col(["d\u00e9signation","designation","signation","design"])
            qc = col(["quantit\u00e9","quantit","qty","qt\u00e9"])
            pc = col(["unit. ttc","unit.ttc","unit ttc","prix unit","unit_ttc","prix_unit"])
            mc = col(["marque"])
            out = []
            for _, r in df.iterrows():
                qty = float(r[qc]) if qc else 0
                if qty <= 0: continue
                out.append({"designation": str(r[dc]).strip() if dc else "",
                             "marque":     str(r[mc]).strip() if mc else "",
                             "quantite":   qty,
                             "prix_unit_ttc": float(r[pc]) if pc else 0})
            return out
        return parse(e.get("df_sans", [])), parse(e.get("df_avec", []))
    except Exception:
        return [], []

# ── Charts ────────────────────────────────────────────────────────────────────
def _style_ax(fig, ax):
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    for s in ["top", "right"]: ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#E5E7EB"); ax.spines["bottom"].set_color("#E5E7EB")
    ax.tick_params(colors=CG4, labelsize=8)
    ax.grid(axis="y", color="#F3F4F6", linewidth=0.8, zorder=0)

def make_chart_roi():
    fig, ax = plt.subplots(figsize=(13, 4.5), dpi=130)
    _style_ax(fig, ax)
    x = np.array(YEARS); ys = np.array(CUMUL_S); ya = np.array(CUMUL_A)
    ax.axhline(0, color="#D1D5DB", linewidth=1.0, linestyle="--", zorder=1)
    _show_s = SCENARIO != 'Avec batterie'
    _show_a = SCENARIO != 'Sans batterie'
    if _show_s:
        ax.fill_between(x, ys, 0, where=(ys >= 0), alpha=0.08, color=CNM, zorder=2)
        ax.plot(x, ys, color=CNM, linewidth=2.5, label="Sans batterie", zorder=4, solid_capstyle="round")
    if _show_a:
        ax.fill_between(x, ya, 0, where=(ya >= 0), alpha=0.08, color=CA,  zorder=2)
        ax.plot(x, ya, color=CA,  linewidth=2.5, label="Avec batterie",  zorder=4, solid_capstyle="round")
    _roi_pts = []
    if _show_s: _roi_pts.append((ROI_S, CUMUL_S, CNM, f"ROI ~{ROI_S} ans"))
    if _show_a: _roi_pts.append((ROI_A, CUMUL_A, CA,  f"ROI ~{ROI_A} ans"))
    _y_offsets = [15, -25]  # Sans batterie above, Avec batterie below
    for i, (roi, cumul, color, lbl) in enumerate(_roi_pts):
        yr = int(roi); fr = roi - yr
        yv = cumul[yr] + fr * (cumul[yr+1] - cumul[yr]) if yr < 25 else cumul[25]
        ax.scatter([roi], [yv], color=color, s=120, zorder=6, marker="*")
        yoff = _y_offsets[i] if i < len(_y_offsets) else 10
        ax.annotate(lbl, (roi, yv), xytext=(6, yoff), textcoords="offset points",
                    fontsize=8.5, color=color, fontweight="bold",
                    arrowprops=dict(arrowstyle="-", color=color, lw=0.8))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v/1000:.0f}k"))
    ax.set_xlabel("Ann\u00e9es", fontsize=9, color=CG4, labelpad=4)
    ax.set_ylabel("Gain cumul\u00e9 (MAD)", fontsize=9, color=CG4, labelpad=4)
    ax.set_xlim(0, 25)
    leg = ax.legend(fontsize=9, frameon=True, loc="upper left", edgecolor="#E5E7EB", facecolor="white")
    leg.get_frame().set_linewidth(0.8)
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO(); plt.savefig(buf, format="png", bbox_inches="tight", facecolor="white"); plt.close(fig)
    return b64(buf)

def make_chart_monthly():
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    # Real monthly bills from the simulator input
    _onee_m = FACTURES_M

    fig, ax = plt.subplots(figsize=(13, 4.0), dpi=130)
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    for s in ["top", "right"]: ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#EAECF0"); ax.spines["bottom"].set_color("#EAECF0")
    ax.spines["left"].set_linewidth(0.8); ax.spines["bottom"].set_linewidth(0.8)

    x = np.arange(12)
    c_bar = "#B5C0CE"  # light steel-blue/grey for ONEE bill bars

    # Bars: ONEE bill — full-width, one per month
    ax.bar(x, _onee_m, 0.60, color=c_bar, alpha=0.60, zorder=2, linewidth=0)

    # Lines: Option 1 (navy) and/or Option 2 (amber) based on scenario
    _show_s = SCENARIO != 'Avec batterie'
    _show_a = SCENARIO != 'Sans batterie'
    if _show_s:
        ax.plot(x, ECO_S_M, color=CNM, linewidth=2.2, marker="o", markersize=5.5,
                markerfacecolor="white", markeredgewidth=1.8, markeredgecolor=CNM,
                zorder=4, solid_capstyle="round")
    if _show_a:
        ax.plot(x, ECO_A_M, color=CA,  linewidth=2.2, marker="o", markersize=5.5,
                markerfacecolor="white", markeredgewidth=1.8, markeredgecolor=CA,
                zorder=4, solid_capstyle="round")

    ax.set_xticks(x)
    ax.set_xticklabels(MONTHS, fontsize=9, color="#374151")
    ax.tick_params(axis="x", length=0, pad=5)
    ax.tick_params(axis="y", colors="#9BA3AE", labelsize=8)
    ax.set_ylabel("MAD / mois", fontsize=9, color="#9BA3AE", labelpad=6)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}".replace(",", "\u202f")))

    # Soft horizontal gridlines only — no vertical
    ax.grid(axis="y", color="#F0F2F5", linewidth=0.65, zorder=0)
    ax.grid(axis="x", visible=False)
    ax.set_axisbelow(True)
    ax.set_xlim(-0.55, 11.55)

    # Custom legend handles: patch for bar, line+marker for each line series
    legend_handles = [Patch(facecolor=c_bar, alpha=0.60, label="Facture ONEE sans PV", linewidth=0)]
    if _show_s:
        legend_handles.append(Line2D([0], [0], color=CNM, linewidth=2.2, marker="o", markersize=5.5,
               markerfacecolor="white", markeredgewidth=1.8, markeredgecolor=CNM,
               label="\u00c9conomies Option\u00a01 \u2013 Sans batterie"))
    if _show_a:
        legend_handles.append(Line2D([0], [0], color=CA,  linewidth=2.2, marker="o", markersize=5.5,
               markerfacecolor="white", markeredgewidth=1.8, markeredgecolor=CA,
               label="\u00c9conomies Option\u00a02 \u2013 Avec batterie"))
    leg = ax.legend(handles=legend_handles, fontsize=8.5, frameon=True,
                    loc="upper center", bbox_to_anchor=(0.5, 1.20), ncol=3,
                    edgecolor="#E5E7EB", facecolor="white",
                    handlelength=1.6, handleheight=0.9,
                    borderpad=0.7, columnspacing=1.6)
    leg.get_frame().set_linewidth(0.8)

    plt.tight_layout(pad=0.4); fig.subplots_adjust(top=0.82)
    buf = io.BytesIO(); plt.savefig(buf, format="png", bbox_inches="tight", facecolor="white"); plt.close(fig)
    return b64(buf)

# ── Equipment rows ────────────────────────────────────────────────────────────
def equip_rows(items, hi_bat=False):
    rows = ""; total = 0.0
    for i, it in enumerate(items):
        des = it["designation"]; qty = it["quantite"]; pu = it["prix_unit_ttc"]
        mar = (it.get("marque") or "").strip()
        total += qty * pu
        ico = icon_img(des, mar); bdg = badge(mar)
        gar = "\u2014"
        for k, v in _GAR.items():
            if k in des.lower(): gar = v; break
        is_bat = "batterie" in des.lower() and hi_bat
        bg = f"background:{CAL};" if is_bat else (f"background:{CG1};" if i % 2 == 1 else "")
        pu_s  = fmt(pu) if pu > 0 else "\u2014"
        qty_s = int(qty) if qty == int(qty) else qty
        rows += (f'<tr style="{bg}"><td class="ti">{ico}</td>'
                 f'<td class="tl">{des}{"<br>" + bdg if bdg else ""}</td>'
                 f'<td class="tc">{gar}</td><td class="tc">{qty_s}</td>'
                 f'<td class="tr">{pu_s}</td></tr>')
    rows += (f'<tr style="background:{CN};"><td></td>'
             f'<td colspan="3" style="text-align:right;color:{CA};font-weight:800;padding:5px 5px;">Total TTC</td>'
             f'<td style="text-align:right;color:{CA};font-weight:800;padding:5px 5px;">{fmt(total)}</td></tr>')
    return rows

# ── Global CSS ────────────────────────────────────────────────────────────────
CSS = f"""
{_font_face("DM Serif Display", 400, "normal", _DS400)}
{_font_face("DM Sans", 400, "normal", _DMSANS400)}
{_font_face("DM Sans", 500, "normal", _DMSANS500)}
{_font_face("DM Sans", 700, "normal", _DMSANS700)}
{_pf_face(700, _PF700)}
{_pf_face(400, _PF400)}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
html{{background:#FFFFFF !important;}}
body{{font-family:'DM Sans',sans-serif;font-size:9pt;color:{CG7};
  background:#FFFFFF !important;
  -webkit-print-color-adjust:exact;print-color-adjust:exact;}}
@page{{size:A4;margin:0;background:#FFFFFF;}}
.page{{width:210mm;height:297mm;overflow:hidden;break-after:page;display:flex;flex-direction:column;background:#FFFFFF !important;}}
.serif{{font-family:'DM Serif Display',Georgia,serif;}}
.hc-serif{{font-family:'Playfair Display','Palatino Linotype','Book Antiqua',Georgia,serif;}}
.eq{{width:100%;border-collapse:collapse;font-size:6.5pt;}}
.option-check{{color:#2e7d32;font-size:15px;font-weight:700;vertical-align:middle;margin-right:3px;}}
.eq th{{background:{CG1};color:{CG4};font-size:5.5pt;font-weight:700;text-transform:uppercase;
  letter-spacing:.5px;padding:4px 5px;border-bottom:1px solid {CG2};text-align:left;}}
.eq td{{padding:3px 4px;border-bottom:1px solid {CG2}80;vertical-align:middle;}}
.eq .ti{{width:44px;text-align:center;padding:2px 3px;}}
.eq .tl{{font-weight:500;}}
.eq .tc{{text-align:center;color:{CG4};}}
.eq .tr{{text-align:right;}}
/* page3-content: no individual page-break rules — handled by single wrapper */
"""

# ── PAGE 1 — exact match to v5 ──────────────────────────────────────────────
def page1():
    # Local formatters — use U+00A0 (NON-BREAKING SPACE) for reliable rendering in all fonts
    _s      = "\u00a0"
    ts      = f"{int(TOTAL_SANS):,}".replace(",", _s) + "\u00a0MAD"
    ta      = f"{int(TOTAL_AVEC):,}".replace(",", _s) + "\u00a0MAD"
    esa_mad = f"{int(ECO_S_ANN):,}".replace(",", _s) + "\u00a0MAD"
    eaa_mad = f"{int(ECO_A_ANN):,}".replace(",", _s) + "\u00a0MAD"
    pk      = f"{int(PROD_KWH):,}".replace(",", _s)
    # Scenario-aware option card visibility
    _s1   = 'display:none;' if SCENARIO == 'Avec batterie' else ''
    _s2   = 'display:none;' if SCENARIO == 'Sans batterie' else ''
    _both = not _s1 and not _s2
    # Badge: position:absolute at the top of the card — does NOT shift price downwards
    _badge_css = (f'position:absolute;top:0;left:0;right:0;background:{CA};color:{CN};'
                  f'font-size:7pt;font-weight:700;letter-spacing:1px;padding:5px 9px;'
                  f'border-radius:4px 4px 0 0;text-transform:uppercase;text-align:center;')
    _r1   = (f'<div style="{_badge_css}"><span style="color:#d4a84b;font-size:16px;">★</span> RECOMMAND\u00c9</div>'
             if _both and RECOMMENDED == 'Sans batterie' else '')
    _r2   = (f'<div style="{_badge_css}"><span style="color:#d4a84b;font-size:16px;">★</span> RECOMMAND\u00c9</div>'
             if _both and RECOMMENDED == 'Avec batterie' else '')
    # Price display — crossed-out original + discount badge + new price when discount active
    if DISCOUNT_PCT > 0:
        _s_before = f"{int(TOTAL_SANS_BEFORE):,}".replace(",", _s) + "\u00a0MAD"
        _a_before = f"{int(TOTAL_AVEC_BEFORE):,}".replace(",", _s) + "\u00a0MAD"
        _disc_str = f"\u2212{int(DISCOUNT_PCT)}\u202f%"
        _ts_price = (
            f'<div style="font-size:10pt;color:{CG4};text-decoration:line-through;'
            f'opacity:0.75;margin-bottom:1px;white-space:nowrap;">{_s_before}</div>'
            f'<div style="margin-bottom:4px;">'
            f'<span style="background:{CA};color:{CN};border-radius:3px;padding:2px 8px;'
            f'font-size:6pt;font-weight:800;letter-spacing:0.5px;">{_disc_str}\u00a0REMISE</span>'
            f'</div>'
            f'<div class="serif" style="font-size:27pt;font-weight:400;color:{CGR};'
            f'line-height:1.0;letter-spacing:-0.5px;margin-bottom:2px;">'
            f'<span style="white-space:nowrap;">{ts}</span></div>'
        )
        _ta_price = (
            f'<div style="font-size:10pt;color:{CG4};text-decoration:line-through;'
            f'opacity:0.75;margin-bottom:1px;white-space:nowrap;">{_a_before}</div>'
            f'<div style="margin-bottom:4px;">'
            f'<span style="background:{CA};color:{CN};border-radius:3px;padding:2px 8px;'
            f'font-size:6pt;font-weight:800;letter-spacing:0.5px;">{_disc_str}\u00a0REMISE</span>'
            f'</div>'
            f'<div class="serif" style="font-size:27pt;font-weight:400;color:{CGR};'
            f'line-height:1.0;letter-spacing:-0.5px;margin-bottom:2px;">'
            f'<span style="white-space:nowrap;">{ta}</span></div>'
        )
    else:
        _ts_price = (
            f'<div class="serif" style="font-size:30pt;font-weight:400;color:{CN};'
            f'line-height:1.0;letter-spacing:-0.5px;margin-bottom:2px;">'
            f'<span style="white-space:nowrap;">{ts}</span></div>'
        )
        _ta_price = (
            f'<div class="serif" style="font-size:30pt;font-weight:400;color:{CN};'
            f'line-height:1.0;letter-spacing:-0.5px;margin-bottom:2px;">'
            f'<span style="white-space:nowrap;">{ta}</span></div>'
        )
    # KPI economies card — scenario-aware
    if SCENARIO == 'Sans batterie':
        _eco_val   = f'<span style="white-space:nowrap;">{esa_mad}</span>'
        _eco_size  = "17pt"
        _eco_sub   = "&#233;conomies par an"
    elif SCENARIO == 'Avec batterie':
        _eco_val   = f'<span style="white-space:nowrap;">{eaa_mad}</span>'
        _eco_size  = "17pt"
        _eco_sub   = "&#233;conomies par an"
    else:
        _eco_val   = f'<span style="white-space:nowrap;">{esa_mad}&nbsp;&#8211;&nbsp;{eaa_mad}</span>'
        _eco_size  = "13pt"
        _eco_sub   = "selon option choisie"
    return f"""
<div class="page" style="background:#FFFFFF !important;">

  <!-- ═══ DARK NAVY HERO ═══ — min-height 37% of A4 (≈110 mm) -->
  <div style="background:{CN};flex-shrink:0;position:relative;padding:30px 28px 72px 28px;min-height:37%;">
    <!-- Amber radial glow — top-right, behind N°412 -->
    <div style="position:absolute;top:0;right:0;width:260px;height:170px;background:radial-gradient(ellipse at 82% 12%, rgba(245,166,35,0.26) 0%, transparent 62%);pointer-events:none;z-index:0;"></div>

    <!-- Row 1: Logo box (left) + subtitle text (right) -->
    <div style="display:flex;align-items:flex-start;justify-content:space-between;">
      {logo_p1_dark()}
      <div style="text-align:right;padding-top:2px;">
        <div style="font-size:7px;color:rgba(255,255,255,0.38);line-height:1.7;">Installation solaire photovolta&#239;que</div>
        <div style="font-size:7px;color:rgba(255,255,255,0.38);">Proposition commerciale &#8212; Confidentiel</div>
      </div>
    </div>

    <!-- Tagline BELOW logo box — 20px gap -->
    <div style="color:{CA};font-size:6px;letter-spacing:2.5px;font-weight:600;margin-top:8px;margin-bottom:3px;white-space:nowrap;">TAQA &nbsp;&#183;&nbsp; INNOVATION &nbsp;&#183;&nbsp; NOR</div>

    <!-- Gold separator — AFTER tagline, BEFORE PROPOSITION -->
    <div style="height:1px;background:{CA};opacity:0.80;margin-bottom:4px;"></div>

    <!-- Row 2: Title+client left / Ref+validity right -->
    <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:16px;">

      <!-- LEFT: PROPOSITION label + serif title -->
      <div style="flex:1;min-width:0;">
        <div style="font-size:6.5pt;letter-spacing:2.5px;color:{CA};font-weight:700;text-transform:uppercase;margin-bottom:6px;">PROPOSITION COMMERCIALE</div>
        <div class="serif" style="font-size:44pt;font-weight:400;color:white;line-height:1.0;letter-spacing:-0.5px;margin-bottom:8px;">Installation<br>Solaire</div>
      </div>

      <!-- RIGHT: Ref label + N°412 + date + Validité badge -->
      <div style="text-align:right;flex-shrink:0;">
        <div style="font-size:7pt;color:{CG4};margin-bottom:1px;">R&#233;f&#233;rence devis</div>
        <div class="serif" style="font-size:17.5pt;font-weight:400;color:{CA};line-height:0.90;letter-spacing:-1px;">N&#176;&nbsp;{REF}</div>
        <div style="font-size:8.5pt;color:rgba(255,255,255,0.82);margin-top:5px;">{DATE_STR}</div>
        <div style="margin-top:5px;display:inline-block;background:{CA};color:{CN};border-radius:5px;padding:3px 10px;font-size:6.5pt;font-weight:700;">Validit&#233;&#160;: 30 jours</div>
      </div>

    </div>

    <!-- Diagonal cut — very gentle slope: left 82% height, right 70% height -->
    <div style="position:absolute;bottom:0;left:0;right:0;line-height:0;overflow:hidden;">
      <svg viewBox="0 0 100 10" preserveAspectRatio="none" style="display:block;width:100%;height:20px;">
        <polygon points="0,10 0,8.2 100,7 100,10" fill="white"/>
      </svg>
    </div>
  </div>

  <!-- WHITE CONTENT AREA — fills remaining space, dark strip is compact -->
  <div style="display:flex;flex-direction:column;padding:0;margin:0;flex:1;background:#FFFFFF !important;">

  <!-- CLIENT INFO — white area, below header band, no overlap -->
  <div style="padding:8px 24px 4px;flex-shrink:0;background:#FFFFFF !important;">
    <div style="font-size:13pt;font-weight:700;color:{CA};margin-bottom:2px;">{CLIENT_NAME}</div>
    <div style="font-size:8pt;color:{CG4};line-height:1.6;">{CLIENT_ADDR}<br>{CLIENT_PHONE}{'<br><span style="color:' + CG7 + ';"><span style="font-weight:600;">ICE&#160;:</span>&#160;' + CLIENT_ICE + '</span>' if CLIENT_ICE else ''}</div>
    <div style="margin-top:4px;display:inline-block;background:{CN};border-radius:3px;padding:2px 7px;font-size:7.5px;color:white;">{SVG_FACTORY if 'ndustr' in INST_TYPE else SVG_HOUSE}{INST_TYPE}</div>
  </div>

  <!-- KPI CARDS -->
  <!-- FIX v39: removed box-shadow from all 3 KPI cards (was: 0 3px 14px rgba(0,0,0,0.07) and 0 2px 8px rgba(0,0,0,0.09)) -->
  <!-- FIX v39: padding-bottom on KPI container changed from 8px → 4px (shadow bleed zone closed) -->
  <div style="padding:2px 24px 4px;flex-shrink:0;background:#FFFFFF !important;">
    <div style="display:flex;gap:9px;background:#FFFFFF !important;">

      <div style="flex:1;border:1px solid {CG2};border-left:4px solid {CA};border-radius:6px;padding:14px 12px;background:white;">
        <div style="font-size:4.5pt;letter-spacing:1.5px;color:{CG4};font-weight:400;text-transform:uppercase;margin-bottom:4px;">Puissance Install&#233;e</div>
        <div class="serif" style="font-size:19pt;color:{CN};line-height:1.05;">{KWC}&nbsp;kWc</div>
        <div style="font-size:6.5pt;color:{CG4};margin-top:3px;">{NB_PAN} panneaux &#215; {WP}&nbsp;W</div>
      </div>

      <div style="flex:1;border:1px solid {CG2};border-left:4px solid {CA};border-radius:6px;padding:14px 12px;background:white;">
        <div style="font-size:4.5pt;letter-spacing:1.5px;color:{CG4};font-weight:400;text-transform:uppercase;margin-bottom:4px;">Production Annuelle</div>
        <div class="serif" style="font-size:19pt;color:{CN};line-height:1.05;">{pk}&nbsp;kWh</div>
        <div style="font-size:6.5pt;color:{CG4};margin-top:3px;">&#233;nergie propre / an</div>
      </div>

      <div style="flex:1;border:2px solid {CA};border-left:5px solid {CA};border-radius:6px;padding:14px 12px;background:#FFFBF2;box-shadow:0 2px 10px rgba(245,166,35,0.18);">
        <div style="font-size:4.5pt;letter-spacing:1.5px;color:{CA};font-weight:700;text-transform:uppercase;margin-bottom:4px;">&#201;conomies estim&#233;es / an</div>
        <div class="serif" style="font-size:{_eco_size};color:{CN};line-height:1.1;">{_eco_val}</div>
        <div style="font-size:6.5pt;color:{CA};font-weight:600;margin-top:3px;">{_eco_sub}</div>
      </div>

    </div>
  </div>

  <!-- SECTION TITLE -->
  <div style="padding:5px 24px 7px;flex-shrink:0;background:#FFFFFF !important;">
    <div style="display:block;background:#FFFFFF !important;">
      <div style="font-size:7pt;letter-spacing:3px;color:{CG4};font-weight:500;text-transform:uppercase;">Vos Options d&#8217;Installation</div>
      <div style="height:2px;background:{CA};border-radius:1px;margin-top:3px;width:40px;"></div>
    </div>
  </div>

  <!-- OPTION CARDS ROW — equal height, fill remaining space -->
  <div style="flex:1;min-height:0;display:flex;gap:12px;padding:0 24px 10px;align-items:stretch;background:#FFFFFF !important;">

    <!-- OPTION 1 -->
    <div style="flex:1;border:1.5px solid #E8A020;border-radius:6px;padding:28px 12px 12px;display:flex;flex-direction:column;background:#FFFFFF;position:relative;{_s1}">
      {_r1}
      <div style="font-size:6.5pt;letter-spacing:3px;color:{CA};font-weight:700;text-transform:uppercase;margin-bottom:4px;">Option 1</div>
      <div style="font-size:13pt;font-weight:500;color:{CN};margin-bottom:2px;">Sans batterie</div>
      <div style="font-size:7pt;color:{CGR};font-weight:600;margin-bottom:7px;">Autoconsommation directe</div>
      {_ts_price}
      <div style="font-size:7pt;color:{CG4};margin-bottom:5px;">Prix total TTC</div>
      <div style="display:inline-block;align-self:flex-start;background:#e8f5e9;color:#2e7d32;border-radius:12px;padding:4px 10px;font-size:13px;font-weight:600;margin-bottom:7px;">{SVG_CHART}Retour en {ROI_S} ans</div>
      <div style="height:1px;background:{CG2};margin-bottom:6px;"></div>
      <ul style="list-style:none;padding:0;font-size:7pt;line-height:1.8;color:{CG7};margin-bottom:6px;">
        <li><span class="option-check">✓</span>{NB_PAN} panneaux {WP}&nbsp;W</li>
        <li><span class="option-check">✓</span>Onduleur r&#233;seau Huawei</li>
        <li><span class="option-check">✓</span>Smart Meter + Wifi Dongle</li>
        <li><span class="option-check">✓</span>Monitoring int&#233;gr&#233; via app Huawei</li>
        <li><span class="option-check">✓</span>Structures + installation compl&#232;te</li>
      </ul>
      <div style="height:1px;background:{CG2};margin-top:auto;margin-bottom:6px;"></div>
      <div style="background:{CG1};border:1px solid {CG2};border-radius:5px;padding:5px 9px;">
        <span style="font-size:7pt;color:{CG4};">&#201;conomie estim&#233;e&#160;: </span>
        <span style="font-size:10pt;font-weight:800;color:{CN};">{esa_mad}/an</span>
      </div>
    </div>

    <!-- OPTION 2 -->
    <div style="flex:1;border:1.5px solid #E8A020;border-radius:6px;padding:28px 12px 12px;display:flex;flex-direction:column;background:#FFF3E0;position:relative;{_s2}">
      {_r2}
      <div style="font-size:6.5pt;letter-spacing:3px;color:{CA};font-weight:700;text-transform:uppercase;margin-bottom:4px;">Option 2</div>
      <div style="font-size:13pt;font-weight:500;color:{CN};margin-bottom:2px;">Avec batterie</div>
      <div style="font-size:7pt;color:{CGR};font-weight:600;margin-bottom:7px;">Stockage + autonomie nocturne</div>
      {_ta_price}
      <div style="font-size:7pt;color:{CG4};margin-bottom:5px;">Prix total TTC</div>
      <div style="display:inline-block;align-self:flex-start;background:#1a1a2e;color:white;border-radius:12px;padding:4px 10px;font-size:13px;font-weight:600;margin-bottom:7px;">{SVG_CHART2}Retour en {ROI_A} ans</div>
      <div style="height:1px;background:{CG2};margin-bottom:6px;"></div>
      <ul style="list-style:none;padding:0;font-size:7pt;line-height:1.8;color:{CG7};margin-bottom:6px;">
        <li><span class="option-check">✓</span>{NB_PAN} panneaux {WP}&nbsp;W</li>
        <li><span class="option-check">✓</span>Onduleur hybride Deye</li>
        <li><span style="color:#d4a84b;font-weight:bold;">⚡</span> Batterie de stockage incluse</li>
        <li><span class="option-check">✓</span>Monitoring int&#233;gr&#233; via app Deye</li>
        <li><span class="option-check">✓</span>Structures + installation compl&#232;te</li>
      </ul>
      <div style="height:1px;background:{CG2};margin-top:auto;margin-bottom:6px;"></div>
      <div style="background:white;border:1px solid {CG2};border-radius:5px;padding:5px 9px;">
        <span style="font-size:7pt;color:{CG4};">&#201;conomie estim&#233;e&#160;: </span>
        <span style="font-size:10pt;font-weight:800;color:{CN};">{eaa_mad}/an</span>
      </div>
    </div>

  </div>

  </div><!-- end white content area -->

  <!-- BOTTOM DARK STRIP — solid edge-to-edge dark navy, compact height -->
  <div style="background:{CN};flex-shrink:0;display:flex;flex-direction:row;align-items:center;justify-content:space-between;padding:8px 30px;">
    <div style="display:flex;gap:6px;">
      <span style="background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.40);border-radius:20px;padding:3px 10px;font-size:6.5pt;color:white;white-space:nowrap;">☀ 3&#8239;000&#160;h/an d&#8217;ensoleillement</span>
      <span style="background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.40);border-radius:20px;padding:3px 10px;font-size:6.5pt;color:white;white-space:nowrap;">⚡ Prix ONEE en hausse</span>
      <span style="background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.40);border-radius:20px;padding:3px 10px;font-size:6.5pt;color:white;white-space:nowrap;">{SVG_GLOBE}&#201;nergie 100&#37; propre</span>
    </div>
    <div style="font-size:6.5pt;color:rgba(255,255,255,0.70);white-space:nowrap;">
      ① Devis → ② Visite → ③ Installation 7&#8211;14&#160;j → ④ Mise en service
    </div>
  </div>

  {footer_p1()}
</div>
"""

# ── PAGE 2 — equipment tables + charts ───────────────────────────────────────
def page2(sans_items, img_roi, img_mon):
    sr = equip_rows(sans_items, hi_bat=False)
    ar = equip_rows(AVEC_ITEMS, hi_bat=True)

    # Scenario visibility
    _p2_s1 = 'display:none;' if SCENARIO == 'Avec batterie' else ''
    _p2_s2 = 'display:none;' if SCENARIO == 'Sans batterie' else ''

    # ── Dynamic table row scaling ─────────────────────────────────────────────
    # When one side has many rows the table section grows and squeezes the charts.
    # Scale row height/font proportionally so everything still fits on one page.
    if SCENARIO == 'Avec batterie':
        max_rows = len(AVEC_ITEMS)
    elif SCENARIO == 'Sans batterie':
        max_rows = len(sans_items)
    else:
        max_rows = max(len(sans_items), len(AVEC_ITEMS))
    scale = 1.0 if max_rows <= 11 else max(0.62, 11.0 / max_rows)
    if scale < 1.0:
        tbl_font = f"{6.5 * scale:.2f}pt"
        th_font  = f"{5.5 * scale:.2f}pt"
        td_pady  = f"{max(1.5, 3.0 * scale):.1f}px"
        td_padx  = f"{max(2.0, 4.0 * scale):.1f}px"
        icon_sz  = f"{max(22, int(36 * scale))}px"
        icon_col = f"{max(28, int(44 * scale))}px"
        tbl_css = (
            f'<style>.eq{{font-size:{tbl_font};}}'
            f'.eq th{{font-size:{th_font};padding:{td_pady} {td_padx};}}'
            f'.eq td{{padding:{td_pady} {td_padx};}}'
            f'.eq .ti{{width:{icon_col};padding:2px 2px;}}'
            f'.eq .ti img{{width:{icon_sz} !important;height:{icon_sz} !important;}}'
            f'</style>'
        )
    else:
        tbl_css = ""

    return f"""
<div class="page">
  {tbl_css}
  <div style="background:{CN};padding:9px 24px;flex-shrink:0;display:flex;align-items:center;justify-content:space-between;">
    <div>
      <div style="color:white;font-size:10pt;font-weight:700;">D\u00e9tail des \u00e9quipements &amp; Analyse financi\u00e8re</div>
      <div style="color:rgba(255,255,255,0.45);font-size:7pt;margin-top:2px;">Devis N\u00b0\u00a0{REF} \u2014 {CLIENT_NAME} \u2014 {DATE_STR}</div>
    </div>
    {logo_html("42px")}
  </div>
  <div style="height:3px;background:{CA};flex-shrink:0;"></div>

  <div style="padding:9px 24px 4px;flex-shrink:0;">
    <div style="display:flex;gap:10px;">

      <div style="flex:1;min-width:0;{_p2_s1}">
        <div style="background:{CN};color:white;font-size:7pt;font-weight:700;text-transform:uppercase;letter-spacing:.8px;padding:5px 9px;border-radius:5px 5px 0 0;">Option 1 \u2014 Sans batterie</div>
        <table class="eq">
          <thead><tr>
            <th class="ti"></th><th>D\u00e9signation</th>
            <th class="tc">Garantie</th><th class="tc">Qt\u00e9</th><th class="tr">P.U. TTC</th>
          </tr></thead>
          <tbody>{sr}</tbody>
        </table>
      </div>

      <div style="flex:1;min-width:0;{_p2_s2}">
        <div style="background:{CA};color:{CN};font-size:7pt;font-weight:700;text-transform:uppercase;letter-spacing:.8px;padding:5px 9px;border-radius:5px 5px 0 0;">Option 2 \u2014 Avec batterie</div>
        <table class="eq">
          <thead><tr>
            <th class="ti"></th><th>D\u00e9signation</th>
            <th class="tc">Garantie</th><th class="tc">Qt\u00e9</th><th class="tr">P.U. TTC</th>
          </tr></thead>
          <tbody>{ar}</tbody>
        </table>
      </div>

    </div>
    <div style="margin-top:4px;font-size:6pt;color:{CG4};font-style:italic;">
      * TVA&#160;: 10&#37; sur les modules photovolta\u00efques, 20&#37; sur les autres \u00e9quipements et travaux.
    </div>
  </div>

  <!-- Charts section: flex:1 so it always fills the remaining space;
       each card also flex:1 so both charts share equally;
       images use flex:1;min-height:0 so they scale to whatever height is available -->
  <div style="padding:4px 24px 6px;flex:1;min-height:0;display:flex;flex-direction:column;gap:10px;">
    <div style="flex:1;min-height:0;background:{CG1};border-radius:7px;padding:8px 11px;border:1px solid {CG2};display:flex;flex-direction:column;">
      <div style="font-size:7pt;font-weight:700;color:{CN};text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;flex-shrink:0;">
        &#128200; Gain cumul\u00e9 sur 25 ans \u2014 Point de retour sur investissement
      </div>
      <img src="{img_roi}" style="flex:1;min-height:0;width:100%;object-fit:contain;display:block;">
    </div>
    <div style="flex:1;min-height:0;background:{CG1};border-radius:7px;padding:8px 11px;border:1px solid {CG2};display:flex;flex-direction:column;">
      <div style="font-size:7pt;font-weight:700;color:{CN};text-transform:uppercase;letter-spacing:.5px;margin-bottom:1px;flex-shrink:0;">
        &#128197; \u00c9conomies mensuelles estim\u00e9es (MAD / mois)
      </div>
      <div style="font-size:6pt;color:{CG4};font-style:italic;margin-bottom:4px;flex-shrink:0;">Facture ONEE vs \u00e9conomies solaires par mois</div>
      <img src="{img_mon}" style="flex:1;min-height:0;width:100%;object-fit:contain;display:block;">
    </div>
  </div>

  {footer(2)}
</div>
"""

# ── PAGE 3 — trust, guarantees, conditions, prochaines étapes, signature ─────
def page3():
    # "Option choisie" tick-boxes — only shown when both options are presented
    _opt = (
        f'<div style="margin-bottom:6px;">'
        f'<div style="font-size:6.5pt;font-weight:700;color:{CG4};text-transform:uppercase;'
        f'letter-spacing:1px;margin-bottom:5px;">Option choisie par le client</div>'
        f'<div style="display:flex;gap:10px;">'
        # Sans batterie box
        f'<div style="flex:1;border:1.5px solid {CG2};border-radius:7px;padding:7px 11px;'
        f'background:white;display:flex;align-items:center;gap:9px;">'
        f'<div style="width:17px;height:17px;border:2px solid {CG7};border-radius:3px;flex-shrink:0;"></div>'
        f'<div>'
        f'<div style="font-size:9pt;font-weight:700;color:{CN};">Sans batterie</div>'
        f'<div style="font-size:6.5pt;color:{CG4};margin-top:1px;">Option 1 &#8212; R&#233;seau uniquement</div>'
        f'</div>'
        f'</div>'
        # Avec batterie box
        f'<div style="flex:1;border:1.5px solid {CA};border-radius:7px;padding:7px 11px;'
        f'background:{CAL};display:flex;align-items:center;gap:9px;">'
        f'<div style="width:17px;height:17px;border:2px solid {CA};border-radius:3px;flex-shrink:0;"></div>'
        f'<div>'
        f'<div style="font-size:9pt;font-weight:700;color:{CN};">Avec batterie</div>'
        f'<div style="font-size:6.5pt;color:{CG4};margin-top:1px;">Option 2 &#8212; R&#233;seau + Stockage</div>'
        f'</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    ) if SCENARIO == "Les deux (Sans + Avec)" else ""

    return f"""
<div class="page" style="overflow:visible;">
  <div style="background:{CN};padding:9px 24px;flex-shrink:0;display:flex;align-items:center;justify-content:space-between;">
    <div>
      <div style="color:white;font-size:10pt;font-weight:700;">Confiance, Garanties &amp; Bon pour accord</div>
      <div style="color:rgba(255,255,255,0.45);font-size:7pt;margin-top:2px;">Devis N\u00b0\u00a0{REF} \u2014 {CLIENT_NAME}</div>
    </div>
    {logo_html("42px")}
  </div>
  <div style="height:3px;background:{CA};flex-shrink:0;"></div>

  <!-- WHY TAQINOR -->
  <div style="padding:3px 24px 2px;margin-bottom:4px;flex-shrink:0;page-break-inside:auto !important;break-inside:auto !important;">
    <div class="serif" style="font-size:22px;color:{CN};margin-bottom:1px;">Pourquoi choisir TAQINOR&#160;?</div>
    <div style="font-size:7.5pt;color:{CG4};font-style:italic;margin-bottom:3px;">Des experts engag\u00e9s pour votre transition \u00e9nerg\u00e9tique</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:3px;">

      <div style="background:white;border:1px solid {CG2};border-radius:10px;padding:4px 9px;display:flex;gap:9px;align-items:flex-start;">
        <div style="width:28px;height:28px;border-radius:50%;background:{CAL};display:flex;align-items:center;justify-content:center;flex-shrink:0;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{CA}" stroke-width="2" stroke-linecap="round">
            <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
          </svg>
        </div>
        <div>
          <div style="font-size:9pt;font-weight:700;color:{CN};margin-bottom:2px;">Ing\u00e9nieurs sp\u00e9cialis\u00e9s</div>
          <div style="font-size:11px;color:{CG4};line-height:1.4;">Installation conforme aux normes marocaines et internationales, r\u00e9alis\u00e9e par des techniciens certifi\u00e9s.</div>
        </div>
      </div>

      <div style="background:white;border:1px solid {CG2};border-radius:10px;padding:4px 9px;display:flex;gap:9px;align-items:flex-start;">
        <div style="width:28px;height:28px;border-radius:50%;background:{CAL};display:flex;align-items:center;justify-content:center;flex-shrink:0;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="{CA}" stroke="{CA}" stroke-width="1">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
          </svg>
        </div>
        <div>
          <div style="font-size:9pt;font-weight:700;color:{CN};margin-bottom:2px;">\u00c9quipements premium certifi\u00e9s</div>
          <div style="font-size:11px;color:{CG4};line-height:1.4;">Panneaux Canadian Solar, onduleurs Huawei &amp; Deye \u2014 certifi\u00e9s IEC avec garantie fabricant compl\u00e8te.</div>
        </div>
      </div>

      <div style="background:white;border:1px solid {CG2};border-radius:10px;padding:4px 9px;display:flex;gap:9px;align-items:flex-start;">
        <div style="width:28px;height:28px;border-radius:50%;background:{CAL};display:flex;align-items:center;justify-content:center;flex-shrink:0;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{CA}" stroke-width="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
        </div>
        <div>
          <div style="font-size:9pt;font-weight:700;color:{CN};margin-bottom:2px;">Garanties jusqu&#8217;\u00e0 25 ans</div>
          <div style="font-size:11px;color:{CG4};line-height:1.4;">Structure 20 ans, panneaux 12 ans produit + 25 ans performance, onduleur 10 ans. S\u00e9r\u00e9nit\u00e9 totale.</div>
        </div>
      </div>

      <div style="background:white;border:1px solid {CG2};border-radius:10px;padding:4px 9px;display:flex;gap:9px;align-items:flex-start;">
        <div style="width:28px;height:28px;border-radius:50%;background:{CAL};display:flex;align-items:center;justify-content:center;flex-shrink:0;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{CA}" stroke-width="2">
            <rect x="5" y="2" width="14" height="20" rx="2" ry="2"/>
            <line x1="12" y1="18" x2="12.01" y2="18" stroke-width="3"/>
          </svg>
        </div>
        <div>
          <div style="font-size:9pt;font-weight:700;color:{CN};margin-bottom:2px;">Suivi en temps r\u00e9el</div>
          <div style="font-size:11px;color:{CG4};line-height:1.4;">Application de monitoring 24/7 pour suivre production, \u00e9conomies et \u00e9tat de votre installation.</div>
        </div>
      </div>

    </div>
  </div>

  <!-- GUARANTEE BADGES -->
  <div style="padding:0 24px 2px;margin-bottom:4px;flex-shrink:0;page-break-inside:auto !important;break-inside:auto !important;">
    <div style="display:flex;gap:3px;">
      <div style="flex:1;border:2px solid {CN};border-top:4px solid {CA};border-radius:8px;padding:2px 5px;text-align:center;background:white;">
        <div class="serif" style="font-size:28px;color:{CN};line-height:1.0;letter-spacing:-1px;">10</div>
        <div style="font-size:10px;font-weight:700;color:{CA};letter-spacing:1px;text-transform:uppercase;">ANS</div>
        <div style="font-size:6.5pt;color:{CG4};margin-top:1px;">Onduleur</div>
      </div>
      <div style="flex:1;border:2px solid {CN};border-top:4px solid {CA};border-radius:8px;padding:2px 5px;text-align:center;background:white;">
        <div class="serif" style="font-size:28px;color:{CN};line-height:1.0;letter-spacing:-1px;">12</div>
        <div style="font-size:10px;font-weight:700;color:{CA};letter-spacing:1px;text-transform:uppercase;">ANS</div>
        <div style="font-size:6.5pt;color:{CG4};margin-top:1px;">Panneaux (produit)</div>
      </div>
      <div style="flex:1;border:2px solid {CN};border-top:4px solid {CA};border-radius:8px;padding:2px 5px;text-align:center;background:white;">
        <div class="serif" style="font-size:28px;color:{CN};line-height:1.0;letter-spacing:-1px;">20</div>
        <div style="font-size:10px;font-weight:700;color:{CA};letter-spacing:1px;text-transform:uppercase;">ANS</div>
        <div style="font-size:6.5pt;color:{CG4};margin-top:1px;">Structure de montage</div>
      </div>
      <div style="flex:1;border:2px solid {CA};border-top:4px solid {CN};border-radius:8px;padding:2px 5px;text-align:center;background:{CAL};">
        <div class="serif" style="font-size:28px;color:{CA};line-height:1.0;letter-spacing:-1px;">25</div>
        <div style="font-size:10px;font-weight:700;color:{CN};letter-spacing:1px;text-transform:uppercase;">ANS</div>
        <div style="font-size:6.5pt;color:{CG4};margin-top:1px;">Performance panneau</div>
      </div>
    </div>
  </div>

  <!-- CONDITIONS GENERALES -->
  <div style="padding:0 24px 2px;margin-bottom:4px;flex-shrink:0;page-break-inside:auto !important;break-inside:auto !important;">
    <div style="background:{CG1};border-radius:8px;padding:4px 8px;border:1px solid {CG2};border-left:4px solid {CN};">
      <div style="font-size:7.5pt;font-weight:700;color:{CN};text-transform:uppercase;letter-spacing:.8px;margin-bottom:2px;">Conditions g\u00e9n\u00e9rales du devis</div>
      <ul style="list-style:none;padding:0;display:grid;grid-template-columns:1fr 1fr;gap:0px 14px;">
        <li style="font-size:11px;color:{CG7};padding-left:10px;position:relative;line-height:1.3;"><span style="position:absolute;left:0;color:{CA};font-size:10pt;line-height:1.1;">\u00b7</span>Validit\u00e9 de l&#8217;offre&#160;: 30 jours</li>
        <li style="font-size:11px;color:{CG7};padding-left:10px;position:relative;line-height:1.3;"><span style="position:absolute;left:0;color:{CA};font-size:10pt;line-height:1.1;">\u00b7</span>Acompte \u00e0 la commande&#160;: 30&#37;</li>
        <li style="font-size:11px;color:{CG7};padding-left:10px;position:relative;line-height:1.3;"><span style="position:absolute;left:0;color:{CA};font-size:10pt;line-height:1.1;">\u00b7</span>60&#37; \u00e0 la r\u00e9ception du mat\u00e9riel</li>
        <li style="font-size:11px;color:{CG7};padding-left:10px;position:relative;line-height:1.3;"><span style="position:absolute;left:0;color:{CA};font-size:10pt;line-height:1.1;">\u00b7</span>10&#37; apr\u00e8s la mise en marche</li>
        <li style="font-size:11px;color:{CG7};padding-left:10px;position:relative;line-height:1.3;"><span style="position:absolute;left:0;color:{CA};font-size:10pt;line-height:1.1;">\u00b7</span>D\u00e9lai d&#8217;installation&#160;: 7\u201314 jours ouvr\u00e9s</li>
        <li style="font-size:11px;color:{CG7};padding-left:10px;position:relative;line-height:1.3;"><span style="position:absolute;left:0;color:{CA};font-size:10pt;line-height:1.1;">\u00b7</span>TVA 10&#37; modules / 20&#37; autres</li>
        <li style="font-size:11px;color:{CG7};padding-left:10px;position:relative;line-height:1.3;"><span style="position:absolute;left:0;color:{CA};font-size:10pt;line-height:1.1;">\u00b7</span>Tarifs de r\u00e9f\u00e9rence&#160;: bar\u00e8me ONEE/SRM</li>
      </ul>
    </div>
  </div>

  <!-- NOTRE ENGAGEMENT -->
  <div style="background:{CA};padding:4px 15px;flex-shrink:0;text-align:center;margin:0 24px 4px;border-radius:8px;page-break-inside:auto !important;break-inside:auto !important;">
    <div style="font-size:6.5pt;letter-spacing:2px;color:{CN};font-weight:800;text-transform:uppercase;margin-bottom:1px;">Notre Engagement</div>
    <div style="font-style:italic;color:white;font-size:8pt;line-height:1.4;">
      Notre \u00e9quipe reste \u00e0 votre disposition pour toute question.<br>
      Nous planifierons l&#8217;installation d\u00e8s validation du devis.
    </div>
  </div>

  <!-- PROCHAINES ÉTAPES -->
  <div style="padding:0 24px;margin-bottom:4px;flex-shrink:0;page-break-inside:auto !important;break-inside:auto !important;">
    <div style="background:#F8F6F0;border:1px solid #EAECF0;border-radius:10px;padding:4px 8px;margin:2px 0;">
      <div style="border-left:4px solid #F5A623;padding-left:10px;margin-bottom:3px;">
        <div style="font-size:10px;font-weight:700;letter-spacing:2px;color:{CN};text-transform:uppercase;">PROCHAINES \u00c9TAPES</div>
      </div>
      <div style="display:flex;gap:4px;">
        <div style="flex:1;text-align:center;padding:4px 6px;background:white;border-radius:8px;border:1px solid #EAECF0;">
          <div class="serif" style="font-size:28px;font-weight:800;color:{CA};line-height:1.0;">1</div>
          <div style="font-size:11px;color:{CN};font-weight:700;margin-top:1px;">Signature du devis</div>
          <div style="font-size:9px;color:{CG4};margin-top:1px;">+ acompte 30&#37;</div>
        </div>
        <div style="flex:1;text-align:center;padding:4px 6px;background:white;border-radius:8px;border:1px solid #EAECF0;">
          <div class="serif" style="font-size:28px;font-weight:800;color:{CA};line-height:1.0;">2</div>
          <div style="font-size:11px;color:{CN};font-weight:700;margin-top:1px;">Visite technique</div>
          <div style="font-size:9px;color:{CG4};margin-top:1px;">Sous 48\u201372&#160;h</div>
        </div>
        <div style="flex:1;text-align:center;padding:4px 6px;background:white;border-radius:8px;border:1px solid #EAECF0;">
          <div class="serif" style="font-size:28px;font-weight:800;color:{CA};line-height:1.0;">3</div>
          <div style="font-size:11px;color:{CN};font-weight:700;margin-top:1px;">Installation</div>
          <div style="font-size:9px;color:{CG4};margin-top:1px;">7\u201314 jours ouvr\u00e9s</div>
        </div>
        <div style="flex:1;text-align:center;padding:4px 6px;background:white;border-radius:8px;border:1px solid #EAECF0;">
          <div class="serif" style="font-size:28px;font-weight:800;color:{CA};line-height:1.0;">4</div>
          <div style="font-size:11px;color:{CN};font-weight:700;margin-top:1px;">Mise en service</div>
          <div style="font-size:9px;color:{CG4};margin-top:1px;">Tests + formation</div>
        </div>
      </div>
    </div>
  </div>

  <!-- BON POUR ACCORD -->
  <div style="padding:0 24px;flex-grow:1;display:flex;flex-direction:column;justify-content:flex-end;page-break-inside:auto !important;break-inside:auto !important;">
    <div style="border-left:4px solid {CA};padding-left:8px;margin-bottom:4px;">
      <div style="font-size:8pt;font-weight:700;color:{CN};text-transform:uppercase;letter-spacing:1.5px;">Bon pour accord</div>
    </div>
    {_opt}
    <div style="display:flex;gap:16px;margin-bottom:3px;">
      <div style="flex:1;border:1px solid {CG2};border-radius:8px;padding:4px 8px;min-height:45px;background:white;">
        <div style="font-size:6.5pt;font-weight:700;color:{CG4};text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Signature du client</div>
        <div style="border-bottom:1px solid {CG2};min-height:10px;margin-bottom:2px;"></div>
        <div style="font-size:7pt;color:{CG4};margin-top:1px;">Nom&#160;: <strong style="color:{CG7};">{CLIENT_NAME}</strong></div>
        <div style="border-bottom:1px solid {CG2};min-height:8px;margin-top:2px;margin-bottom:2px;"></div>
        <div style="font-size:7pt;color:{CG4};">Date&#160;: _______________</div>
        <div style="font-size:5.5pt;color:{CG4};margin-top:2px;font-style:italic;">Lu et approuv\u00e9 \u2014 Signature pr\u00e9c\u00e9d\u00e9e de \u00ab\u00a0Bon pour accord\u00a0\u00bb</div>
      </div>
      <div style="flex:1;border:1px solid {CG2};border-radius:8px;padding:4px 8px;min-height:45px;background:white;">
        <div style="font-size:6.5pt;font-weight:700;color:{CG4};text-transform:uppercase;letter-spacing:1px;margin-bottom:3px;">Signature TAQINOR</div>
        <div style="border-bottom:1px solid {CG2};min-height:10px;margin-bottom:2px;"></div>
        <div style="font-size:7pt;color:{CG4};margin-top:1px;">Repr\u00e9sentant&#160;: <strong style="color:{CG7};">TAQINOR</strong></div>
        <div style="border-bottom:1px solid {CG2};min-height:8px;margin-top:2px;margin-bottom:2px;"></div>
        <div style="font-size:7pt;color:{CG4};">Date&#160;: _______________</div>
        <div style="font-size:5.5pt;color:{CG4};margin-top:3px;font-style:italic;">Cachet et signature de la soci\u00e9t\u00e9</div>
      </div>
    </div>

  </div>

  {footer_p3()}
</div>
"""

# ── Assemble HTML ─────────────────────────────────────────────────────────────
def build_html():
    print("  Generating charts...")
    img_roi = make_chart_roi()
    img_mon = make_chart_monthly()
    return f"""<!DOCTYPE html>
<html lang="fr" style="background:#FFFFFF !important;"><head><meta charset="UTF-8">
<title>Devis TAQINOR N\u00b0 {REF}</title>
<style>{CSS}</style></head>
<body style="background:#FFFFFF !important;">
{page1()}
{page2(SANS_ITEMS, img_roi, img_mon)}
{page3()}
</body></html>"""

# ── ONE-PAGE MODE ─────────────────────────────────────────────────────────────
def page_onepage(items):
    """Single A4 page: header + amber strip + client block + product table + footer."""
    # Compute total (skip zero-qty rows just in case)
    total_raw = sum(
        float(it.get("quantite", 0)) * float(it.get("prix_unit_ttc", 0))
        for it in items
        if float(it.get("quantite", 0)) > 0
    )
    if DISCOUNT_PCT > 0:
        total = round(total_raw * (1 - DISCOUNT_PCT / 100))
    else:
        total = total_raw

    # Build table rows
    rows_html = ""
    row_idx = 0
    for it in items:
        qty = float(it.get("quantite", 0))
        if qty == 0:
            continue
        bg = "white" if row_idx % 2 == 0 else CG1
        pu = float(it.get("prix_unit_ttc", 0))
        line_total = qty * pu
        marque = it.get("marque", "") or ""
        des = it.get("designation", "")
        qty_str = str(int(qty)) if qty == int(qty) else fnum(qty)
        marque_html = badge(marque) if marque else ""
        rows_html += (
            f'<tr style="background:{bg};">'
            f'<td style="padding:6px 10px;font-weight:500;color:{CN};word-break:break-word;">{des}</td>'
            f'<td style="padding:6px 10px;">{marque_html}</td>'
            f'<td style="padding:6px 10px;text-align:center;color:{CG7};">{qty_str}</td>'
            f'<td style="padding:6px 10px;text-align:right;color:{CG7};">{fnum(pu)}</td>'
            f'<td style="padding:6px 10px;text-align:right;font-weight:500;color:{CN};">{fnum(line_total)}</td>'
            f'</tr>'
        )
        row_idx += 1

    return f"""
<div class="page">

  <!-- HEADER: navy -->
  <div style="background:{CN};padding:14px 24px;flex-shrink:0;display:flex;align-items:center;justify-content:space-between;">
    {logo_html("80px")}
    <div style="text-align:right;">
      <div style="color:white;font-size:11pt;font-weight:700;">DEVIS&nbsp;<span style="color:{CA};">N&#176;&#160;{REF}</span></div>
      <div style="color:rgba(255,255,255,0.6);font-size:8pt;margin-top:2px;">{DATE_STR}</div>
    </div>
  </div>

  <!-- CLIENT BLOCK -->
  <div style="background:{CG1};padding:12px 24px;flex-shrink:0;border-bottom:1px solid {CG2};">
    <div style="font-size:6.5pt;font-weight:700;color:{CG4};text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Client</div>
    <div style="font-size:11pt;font-weight:700;color:{CN};">{CLIENT_NAME}</div>
    <div style="font-size:8.5pt;color:{CG7};margin-top:2px;">{CLIENT_ADDR}</div>
    <div style="font-size:8.5pt;color:{CG4};margin-top:1px;">{CLIENT_PHONE}</div>
    {'<div style="font-size:8pt;color:' + CG7 + ';margin-top:3px;"><span style="color:' + CG4 + ';font-weight:600;">ICE&#160;:</span>&#160;' + CLIENT_ICE + '</div>' if CLIENT_ICE else ''}
  </div>

  <!-- PRODUCT TABLE -->
  <div style="flex:1;overflow:hidden;padding:0 24px 0;">
    <table style="width:100%;border-collapse:collapse;font-size:8.5pt;table-layout:fixed;">
      <colgroup>
        <col style="width:40%">
        <col style="width:15%">
        <col style="width:8%">
        <col style="width:17%">
        <col style="width:20%">
      </colgroup>
      <thead>
        <tr style="background:{CN};">
          <th style="padding:8px 10px;color:white;font-weight:700;font-size:7.5pt;text-align:left;text-transform:uppercase;letter-spacing:.5px;">D&#233;signation</th>
          <th style="padding:8px 10px;color:white;font-weight:700;font-size:7.5pt;text-align:left;text-transform:uppercase;letter-spacing:.5px;">Marque</th>
          <th style="padding:8px 10px;color:white;font-weight:700;font-size:7.5pt;text-align:center;text-transform:uppercase;letter-spacing:.5px;">Qt&#233;</th>
          <th style="padding:8px 10px;color:white;font-weight:700;font-size:7.5pt;text-align:right;text-transform:uppercase;letter-spacing:.5px;">P.U. TTC (MAD)</th>
          <th style="padding:8px 10px;color:white;font-weight:700;font-size:7.5pt;text-align:right;text-transform:uppercase;letter-spacing:.5px;">Total TTC (MAD)</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
  </div>

  <!-- TOTAL ROW -->
  <div style="background:{CAL};border-top:2px solid {CA};padding:10px 24px;flex-shrink:0;display:flex;justify-content:flex-end;align-items:center;gap:16px;margin:0 24px;">
    <span style="font-size:9.5pt;font-weight:700;color:{CN};text-transform:uppercase;letter-spacing:.5px;">Total TTC</span>
    {'<div style="display:flex;flex-direction:column;align-items:flex-end;gap:2px;">'
     '<span style="font-size:9pt;color:' + CG4 + ';text-decoration:line-through;opacity:0.8;white-space:nowrap;">' + fnum(total_raw) + '&nbsp;MAD</span>'
     '<span style="background:' + CA + ';color:' + CN + ';border-radius:3px;padding:1px 7px;font-size:6pt;font-weight:800;align-self:flex-end;">\u2212' + str(int(DISCOUNT_PCT)) + '\u202f%\u00a0REMISE</span>'
     '<span style="font-size:13pt;font-weight:800;color:' + CGR + ';white-space:nowrap;">' + fmt(total) + '</span>'
     '</div>'
     if DISCOUNT_PCT > 0 else
     '<span style="font-size:13pt;font-weight:800;color:' + CN + ';">' + fmt(total) + '</span>'}
  </div>

  <!-- CONDITIONS -->
  <div style="padding:8px 24px;flex-shrink:0;">
    <div style="font-size:7pt;color:{CG4};display:flex;gap:20px;flex-wrap:wrap;">
      <span>&#183; Validit&#233;&#160;: 30 jours</span>
      <span>&#183; Acompte&#160;: 50&#37;</span>
      <span>&#183; Solde &#224; la livraison&#160;: 50&#37;</span>
    </div>
  </div>

  <!-- FOOTER: navy + legal identity -->
  <div style="background:{CN};padding:6px 24px 5px;flex-shrink:0;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
      <div style="font-size:9pt;font-weight:800;color:{CA};letter-spacing:1px;">TAQINOR</div>
      <div style="font-size:7pt;color:#888;text-align:center;">
        contact@taqinor.com &nbsp;&#183;&nbsp; +212&#160;6&#160;61&#160;85&#160;04&#160;10 &nbsp;&#183;&nbsp; www.taqinor.ma
      </div>
      <div style="font-size:7pt;color:#888;">R&#233;f.&#160;{REF}</div>
    </div>
    <div style="font-size:7.5px;color:#888;text-align:center;font-style:italic;">
      Taqinor Solutions SARLAU &middot; RC 691213 &middot; ICE 003799642000067 &middot;
      Capital 100&#8239;000 MAD &middot; Si&#232;ge&#160;: 5 Rue Ennoussour RDC, Casablanca
    </div>
  </div>

</div>
"""


def build_html_onepage(items):
    """Minimal HTML shell for the one-page PDF."""
    return f"""<!DOCTYPE html>
<html lang="fr" style="background:#FFFFFF !important;"><head><meta charset="UTF-8">
<title>Devis TAQINOR N\u00b0 {REF}</title>
<style>{CSS}</style></head>
<body style="background:#FFFFFF !important;">
{page_onepage(items)}
</body></html>"""


# ── Generate PDF ──────────────────────────────────────────────────────────────
def generate():
    ref = QUOTE_INPUT["ref"]
    print(f"[1/3] Building HTML for devis {ref}...")
    sys.stdout.buffer.write(
        f"  blocks={_Q['blocks']} | TOTAL_SANS={fmt(TOTAL_SANS)} | TOTAL_AVEC={fmt(TOTAL_AVEC)}\n"
        .encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()
    html = build_html()

    out_dir = BASE_DIR / "devis_client"
    out_dir.mkdir(exist_ok=True)
    import re as _re
    _safe_c = _re.sub(r"[^A-Za-z0-9]", "_", QUOTE_INPUT.get("client_name", "Client"))
    _kwc_str = f"{QUOTE_INPUT['puissance_kwc']:g}kWc"
    if SCENARIO == "Les deux (Sans + Avec)":
        _scen_str = "Hybride+Injection"
    elif SCENARIO == "Avec batterie":
        _scen_str = "Hybride"
    else:
        _scen_str = "Injection"
    out = out_dir / f"TAQINOR_Devis_{ref}_{_safe_c}_{_kwc_str}_{_scen_str}.pdf"

    print("[2/3] Writing temp HTML...")
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False,
                                     mode="w", encoding="utf-8") as tf:
        tf.write(html)
        tmp = tf.name

    print("[3/3] Rendering with WeasyPrint...")
    _render_pdf_weasyprint(html, str(out))
    Path(tmp).unlink(missing_ok=True)

    kb = out.stat().st_size // 1024
    msg = (f"\n\u2705 Saved: {out.name} | Pages: 3 | {kb} KB\n")
    sys.stdout.buffer.write(msg.encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()
    return str(out)

# ── Public API for web app ────────────────────────────────────────────────────
def generate_premium_pdf(data: dict, out_path) -> str:
    """Generate premium PDF from a dynamic data dict; returns str(out_path).

    Required keys in data: ref, date, client_name, client_addr, client_phone,
    inst_type, puissance_kwc, nb_panneaux, watt_par_panneau, prod_kwh,
    total_sans, total_avec, eco_s_ann, eco_a_ann, eco_a_cumul,
    roi_s, roi_a, eco_s_monthly, eco_a_monthly, sans_items, avec_items.

    Items dicts must have: designation, quantite, prix_unit_ttc, marque.
    """
    global CLIENT_NAME, CLIENT_ADDR, CLIENT_PHONE, CLIENT_ICE, REF, DATE_STR
    global KWC, NB_PAN, WP, PROD_KWH, TOTAL_SANS, TOTAL_AVEC
    global DISCOUNT_PCT, TOTAL_SANS_BEFORE, TOTAL_AVEC_BEFORE
    global ECO_S_ANN, ECO_A_ANN, ROI_S, ROI_A, INST_TYPE
    global SANS_ITEMS, AVEC_ITEMS, ECO_S_M, ECO_A_M, CUMUL_S, CUMUL_A
    global FACTURES_M
    global SCENARIO, RECOMMENDED

    CLIENT_NAME  = data["client_name"]
    CLIENT_ADDR  = data["client_addr"]
    CLIENT_PHONE = data["client_phone"]
    CLIENT_ICE   = data.get("client_ice", "")
    REF          = str(data["ref"])
    DATE_STR     = data["date"]
    KWC          = float(data["puissance_kwc"])
    NB_PAN       = int(data["nb_panneaux"])
    WP           = int(data["watt_par_panneau"])
    PROD_KWH     = int(data["prod_kwh"])
    TOTAL_SANS        = float(data["total_sans"])
    TOTAL_AVEC        = float(data["total_avec"])
    DISCOUNT_PCT      = float(data.get("discount_pct", 0))
    TOTAL_SANS_BEFORE = float(data.get("total_sans_before", TOTAL_SANS))
    TOTAL_AVEC_BEFORE = float(data.get("total_avec_before", TOTAL_AVEC))
    ECO_S_ANN    = int(data["eco_s_ann"])
    ECO_A_ANN    = int(data["eco_a_ann"])
    ROI_S        = float(data["roi_s"])
    ROI_A        = float(data["roi_a"])
    INST_TYPE    = data["inst_type"]
    SCENARIO     = data.get("scenario", "Les deux (Sans + Avec)")
    RECOMMENDED  = data.get("recommended", "Avec batterie")
    SANS_ITEMS   = data["sans_items"]
    AVEC_ITEMS   = data["avec_items"]
    ECO_S_M      = data["eco_s_monthly"]
    ECO_A_M      = data["eco_a_monthly"]
    FACTURES_M   = list(data["factures_mensuelles"])
    eco_a_cumul  = int(data["eco_a_cumul"])
    CUMUL_S      = [-TOTAL_SANS + ECO_S_ANN * y for y in YEARS]
    CUMUL_A      = [-TOTAL_AVEC + eco_a_cumul  * y for y in YEARS]

    out_path = Path(out_path)
    mode = data.get("pdf_mode", "full")
    if mode == "onepage":
        html = build_html_onepage(data.get("all_items", []))
    else:
        html = build_html()

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False,
                                     mode="w", encoding="utf-8") as tf:
        tf.write(html)
        tmp = tf.name

    _render_pdf_weasyprint(html, str(out_path))
    Path(tmp).unlink(missing_ok=True)

    return str(out_path)


if __name__ == "__main__":
    try:
        generate()
    except Exception:
        import traceback; traceback.print_exc(); sys.exit(1)
