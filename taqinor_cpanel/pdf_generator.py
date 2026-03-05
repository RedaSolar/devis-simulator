import re
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
from reportlab.graphics.shapes import Drawing, Line
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.pdfgen import canvas

from constants import BLUE_MAIN, BLUE_LIGHT, TEXT_DARK, ORANGE_ACCENT
from utils import sanitize_df

# Paths that can be overridden by the router after import
DEVIS_DIR = Path("devis_client")
FACTURES_DIR = Path("factures_client")
LOGO_PATH = Path("logo.png")
PICTURES_DIR = Path("pictures")  # overridden by devis_router with absolute path

# pdf_generator.py lives in the project root — use __file__ for guaranteed absolute path
_PDF_GEN_DIR = Path(__file__).resolve().parent
_PICTURES_DIR_ABS = _PDF_GEN_DIR / "pictures"

# Designation → image filename stem (no extension)
_DESIGNATION_IMAGE_MAP = {
    "Onduleur réseau":    "onduleur",
    "Onduleur hybride":   "onduleur",
    "Smart Meter":        "smart_meter",
    "Wifi Dongle":        "wifi_dongle",
    "Panneaux":           "panneaux",
    "Batterie":           "batterie",
    "Structures":         "structures",
    "Structures acier":   "structures",
    "Structures aluminium": "structure_alimumium",
    "Socles":             "socles",
    "Accessoires":        "accessoires",
    "Tableau De Protection AC/DC": "tableau_protection",
    "Installation":       "installation",
    "Transport":          "Transport",
    "Suivi journalier, maintenance chaque 12 mois pendent 2 ans": "suivi_maintenance",
}


def _find_product_image(designation: str):
    """Return absolute path string to product image, or None if not found."""
    stem = _DESIGNATION_IMAGE_MAP.get(designation)
    if not stem and isinstance(designation, str) and designation.lower().startswith("structures"):
        stem = "structures"
    if not stem:
        print(f"[IMG] No stem for designation: {designation!r}")
        return None
    stem_lower = stem.lower()
    # Search by listing the directory — handles any case/extension variation
    for d in [_PICTURES_DIR_ABS, PICTURES_DIR]:
        try:
            d_resolved = d.resolve() if not d.is_absolute() else d
            print(f"[IMG] Searching {d_resolved} (exists={d_resolved.exists()}) for stem={stem_lower!r}")
            if not d_resolved.exists():
                continue
            for f in d_resolved.iterdir():
                if f.stem.lower() == stem_lower and f.suffix.lower() in ('.png', '.jpg', '.jpeg'):
                    print(f"[IMG] FOUND: {f}")
                    return str(f)
        except Exception as e:
            print(f"[IMG] Exception searching {d}: {e}")
    print(f"[IMG] NOT FOUND for {designation!r} (stem={stem_lower!r})")
    return None


# ---------- PDF DOUBLE DEVIS ----------
def build_devis_section_elements(df, notes, styles, scenario_title):
    elements = []
    style_normal = styles["Normal"]
    style_normal.fontName = "Helvetica"
    style_normal.fontSize = 9.5
    style_normal.leading = 11.5
    style_normal.textColor = colors.HexColor(TEXT_DARK)
    style_normal.spaceAfter = 3

    style_header = ParagraphStyle(
        "header",
        parent=style_normal,
        fontSize=11,
        leading=13,
    )
    style_small = ParagraphStyle(
        "small",
        parent=style_normal,
        fontSize=9,
        leading=11,
    )
    style_header_white = ParagraphStyle(
        "header_white",
        parent=style_header,
        textColor=colors.white,
        fontSize=9,
    )

    df = sanitize_df(df.copy())
    # Inclure toutes les lignes avec Quantité > 0, même si le prix est à 0.0
    df = df[(df["Quantité"] > 0)].reset_index(drop=True)

    # Clean CustomLabel: Remove dict artifacts (from deserialization issues)
    if "CustomLabel" in df.columns:
        for idx, row in df.iterrows():
            custom_label = row.get("CustomLabel", "")
            # If CustomLabel is a dict, convert to empty string
            if isinstance(custom_label, dict):
                df.at[idx, "CustomLabel"] = ""
            # If it's a string containing only "nan", convert to empty string
            elif isinstance(custom_label, str) and custom_label.strip().lower() == "nan":
                df.at[idx, "CustomLabel"] = ""
    df["Prix Unit. HT"] = df["Prix Unit. TTC"] / (1 + df["TVA (%)"] / 100)
    df["Total HT"] = df["Prix Unit. HT"] * df["Quantité"]
    df["Total TTC"] = df["Prix Unit. TTC"] * df["Quantité"]
    total_ht, total_ttc = float(df["Total HT"].sum()), float(df["Total TTC"].sum())

    def fmt_money(val):
        try:
            v = float(val)
        except Exception:
            return str(val)
        return f"{v:,.2f}".replace(",", " ") + "\u00a0MAD"

    header_row = [
        Paragraph("<b>Photo</b>", style_header_white),
        Paragraph("<b>Désignation</b>", style_header_white),
        Paragraph("<b>Spécifications techniques</b>", style_header_white),
        Paragraph("<b>Garantie</b>", style_header_white),
        Paragraph("<b>Qté</b>", style_header_white),
        Paragraph("<b>PU TTC (MAD)</b>", style_header_white),
        Paragraph("<b>Total TTC (MAD)</b>", style_header_white),
    ]
    data = [header_row]

    spec_map = {
        "smart meter": (
            "Compteur intelligent pour suivi et limitation de puissance",
            "2 ans",
        ),
        "wifi dongle": (
            "Communication et supervision à distance via application",
            "2 ans",
        ),
        "panneaux – canadian solar 710w": (
            "Modules 710 Wc, haute performance, technologie mono",
            "12 ans produit",
        ),
        "panneaux - canadian solar 710w": (
            "Modules 710 Wc, haute performance, technologie mono",
            "12 ans produit",
        ),
        "structures acier": (
            "Structure acier galvanisé adaptée à la toiture",
            "20 ans",
        ),
        "socles": (
            "Socles de support et lestage pour structure",
            "—",
        ),
        "accessoires": (
            "Câblage, connecteurs, protections AC/DC",
            "—",
        ),
        "tableau de protection ac/dc": (
            "Tableau de protection AC/DC complet",
            "—",
        ),
        "installation": (
            "Main d'œuvre, mise en service et tests",
            "Garantie de bonne exécution",
        ),
        "instalation": (
            "Main d'œuvre, mise en service et tests",
            "Garantie de bonne exécution",
        ),
        "transport": (
            "Acheminement du matériel jusqu'au site",
            "—",
        ),
        "batterie – deyness 5kwh": (
            "Batterie lithium 5 kWh pour stockage et secours",
            "10 ans",
        ),
        "batterie - deyness 5kwh": (
            "Batterie lithium 5 kWh pour stockage et secours",
            "10 ans",
        ),
        "onduleur réseau": (
            "Onduleur 5 kW monophasé haute efficacité",
            "10 ans",
        ),
        "onduleur rÅ½seau": (
            "Onduleur 5 kW monophasé haute efficacité",
            "10 ans",
        ),
        "onduleur rÇ¸seau": (
            "Onduleur 5 kW monophasé haute efficacité",
            "10 ans",
        ),
        "onduleur hybride": (
            "Onduleur 5 kW monophasé haute efficacité",
            "10 ans",
        ),
    }

    for _, r in df.iterrows():
        des = r["Désignation"]
        custom_label = r.get("CustomLabel", "")

        # Clean custom_label: remove dict, empty, or "nan" values
        if isinstance(custom_label, dict) or (isinstance(custom_label, str) and custom_label.strip().lower() in ("nan", "")):
            custom_label = ""

        # Determine designation text
        if isinstance(des, str) and des.startswith("Structures"):
            # For structures, prefer CustomLabel if it's valid, else use designation
            if custom_label and isinstance(custom_label, str) and custom_label.strip():
                des_txt = custom_label.strip()
            else:
                des_txt = des
        elif des == "Suivi journalier, maintenance chaque 12 mois pendent 2 ans":
            des_txt = "Suivi journalier<br/>Maintenance chaque 12 mois pendent 2 ans"
        else:
            des_txt = des

        # Add brand name for relevant items
        if r.get("Marque") and des in ("Onduleur réseau", "Onduleur hybride", "Panneaux", "Batterie"):
            des_txt = f"{des_txt} – {r['Marque']}"

        # Ensure we always pass a string to Paragraph (ReportLab fails on non-strings)
        if des_txt is None:
            des_txt = ""
        des_txt = str(des_txt).strip()
        des_cell = Paragraph(des_txt, style_normal)

        spec_txt = "—"
        garantie_txt = "—"
        des_key = des_txt.lower()
        if des_key in spec_map:
            spec_txt, garantie_txt = spec_map[des_key]
        elif "panneaux" in des_key:
            spec_txt = "Modules solaires haute performance"
            garantie_txt = "12 ans produit"
        elif "batterie" in des_key:
            spec_txt = "Batterie lithium pour stockage et secours"
            garantie_txt = "10 ans"
        elif "onduleur" in des_key:
            spec_txt = "Onduleur haute efficacité"
            garantie_txt = "10 ans"
        spec_cell = Paragraph(spec_txt, style_normal)
        garantie_cell = Paragraph(garantie_txt, style_normal)

        img_path = _find_product_image(des)

        if img_path:
            img_cell = Image(img_path)
            img_cell._restrictSize(45, 45)
            img_cell.hAlign = "CENTER"
        else:
            img_cell = Table(
                [[Paragraph("Photo", style_small)]],
                colWidths=[45],
                rowHeights=[45],
                style=TableStyle(
                    [
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#777777")),
                    ]
                ),
            )

        data.append(
            [
                img_cell,
                des_cell,
                spec_cell,
                garantie_cell,
                int(r["Quantité"]),
                fmt_money(r["Prix Unit. TTC"]),
                fmt_money(r["Total TTC"]),
            ]
        )

    total_ht_lbl = Paragraph("<b>TOTAL HT</b>", style_normal)
    total_ttc_lbl = Paragraph("<b>TOTAL TTC</b>", style_normal)
    total_ht_fmt = f"{total_ht:,.2f} MAD".replace(",", " ")
    total_ttc_fmt = f"{total_ttc:,.2f} MAD".replace(",", " ")
    data.append([total_ht_lbl, "", "", "", "", "", total_ht_fmt])
    data.append([total_ttc_lbl, "", "", "", "", "", total_ttc_fmt])

    elements.append(Spacer(1, 6))

    def make_premium_table(data_table):
        table = Table(
            data_table,
            repeatRows=1,
        )

        last_row = len(data_table) - 1
        before_last_row = len(data_table) - 2
        body_end = before_last_row - 1

        style = TableStyle(
            [
                # Header styling
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BLUE_MAIN)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
                ("FONTSIZE", (0, 0), (-1, 0), 8.5),
                ("TOPPADDING", (0, 0), (-1, 0), 7),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
                ("LINEBELOW", (0, 0), (-1, 0), 1.0, colors.white),
                # Body styling
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -3), 8),
                ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#222222")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CCCCCC")),
                ("INNERGRID", (0, 1), (-1, -3), 0.3, colors.HexColor("#DDDDDD")),
                ("LEFTPADDING", (0, 1), (-1, -1), 6),
                ("RIGHTPADDING", (0, 1), (-1, -1), 6),
                ("TOPPADDING", (0, 1), (-1, -3), 3),
                ("BOTTOMPADDING", (0, 1), (-1, -3), 3),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 1), (0, -1), "CENTER"),
                ("ALIGN", (1, 1), (2, -1), "LEFT"),
                ("ALIGN", (3, 1), (3, -3), "CENTER"),
                ("ALIGN", (4, 1), (4, -1), "RIGHT"),
                ("ALIGN", (5, 1), (5, -1), "RIGHT"),
                ("ALIGN", (6, 1), (6, -1), "RIGHT"),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("WORDWRAP", (1, 1), (2, -1), None),
            ]
        )

        # Highlight numeric columns with slightly larger font
        style.add("FONTSIZE", (4, 1), (6, -3), 9.5)
        style.add("FONTSIZE", (4, before_last_row), (-1, -1), 10)

        if body_end >= 1:
            style.add(
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, body_end),
                (colors.white, colors.HexColor(BLUE_LIGHT)),
            )

        style.add("SPAN", (0, before_last_row), (5, before_last_row))
        style.add("SPAN", (0, last_row), (5, last_row))
        style.add("BACKGROUND", (0, before_last_row), (-1, last_row), colors.whitesmoke)
        style.add("FONTNAME", (0, before_last_row), (-1, last_row), "Helvetica-Bold")
        style.add("LINEABOVE", (0, before_last_row), (-1, before_last_row), 1, colors.HexColor(TEXT_DARK))
        style.add("TOPPADDING", (0, before_last_row), (-1, last_row), 4)
        style.add("BOTTOMPADDING", (0, before_last_row), (-1, last_row), 4)

        table.setStyle(style)
        table._argW = [
            1.6 * cm,  # Photo
            4.6 * cm,  # Désignation
            4.6 * cm,  # Spécifications techniques
            2.4 * cm,  # Garantie
            1.1 * cm,  # Quantité
            2.7 * cm,  # Prix Unit
            2.7 * cm,  # Total TTC
        ]
        return table

    table = make_premium_table(data)
    elements += [table, Spacer(1, 6)]

    # Notes
    if notes:
        clean_notes = [n.strip() for n in notes if isinstance(n, str) and n.strip()]
        if clean_notes:
            elements.append(Paragraph("<b>Notes :</b>", style_normal))
            elements.append(Spacer(1, 4))
            for n in clean_notes:
                safe_n = n.replace("<", "&lt;").replace(">", "&gt;")
                elements.append(Paragraph(f"- {safe_n}", style_normal))
                elements.append(Spacer(1, 2))
            elements.append(Spacer(1, 8))

    return elements, total_ttc


def generate_double_devis_pdf(
    df_sans,
    df_avec,
    notes_sans,
    notes_avec,
    client_name,
    client_address,
    client_phone,
    doc_type,
    doc_number,
    roi_summary_sans,
    roi_summary_avec,
    roi_fig_all_buf,
    roi_fig_cumul_buf,
    scenario_choice,
    recommended_option=None,
    installation_type="Résidentielle",
    type_label="résidentielle",
    type_phrase="Installation photovoltaïque résidentielle",
    puissance_kwp=0.0,
    puissance_panneau_w=0,
):
    print(f"[PDF] generate_double_devis_pdf called: scenario_choice={scenario_choice!r}")
    print(f"[PDF] df_sans rows={len(df_sans)}, df_avec rows={len(df_avec)}")
    print(f"[PDF] _PICTURES_DIR_ABS={_PICTURES_DIR_ABS} exists={_PICTURES_DIR_ABS.exists()}")
    safe_client = re.sub(r"[^A-Za-z0-9]", "_", client_name or "Client")
    file_name = f"{doc_type}_{safe_client}_{int(doc_number)}.pdf"
    pdf_path = DEVIS_DIR / file_name

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=56,  # ~2 cm
        leftMargin=56,   # ~2 cm
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
    )
    elements = []
    styles = getSampleStyleSheet()
    style_normal = ParagraphStyle(
        "body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=11.5,
        textColor=colors.HexColor(TEXT_DARK),
        spaceAfter=4,
    )
    style_body = style_normal
    style_small = ParagraphStyle(
        "small",
        parent=style_body,
        fontSize=9,
        leading=11,
    )
    style_bullet = ParagraphStyle(
        "bullet",
        parent=style_body,
        leftIndent=14,
        bulletIndent=0,
        spaceAfter=4,
    )
    style_long_text = ParagraphStyle(
        "long_text",
        parent=style_body,
        fontSize=9,
        leading=11,
        spaceAfter=3,
    )
    style_cond_bullet = ParagraphStyle(
        "cond_bullet",
        parent=style_long_text,
        leftIndent=14,
        bulletIndent=0,
        spaceAfter=2,
    )
    style_h1 = ParagraphStyle(
        "style_h1",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=21,
        textColor=colors.HexColor(BLUE_MAIN),
        spaceBefore=10,
        spaceAfter=5,
        alignment=0,
    )
    style_h2 = ParagraphStyle(
        "style_h2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13.5,
        leading=17,
        textColor=colors.HexColor(TEXT_DARK),
        spaceBefore=7,
        spaceAfter=4,
        alignment=0,
    )
    style_company = ParagraphStyle(
        "company",
        parent=style_body,
        fontSize=9,
        leading=14,
    )
    style_header_top = ParagraphStyle(
        "header_top",
        parent=style_normal,
        fontSize=11,
        leading=13,
    )
    cover_title_style = ParagraphStyle(
        "cover_title_style",
        parent=styles["Heading1"],
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#0A5275"),
        alignment=0,
    )

    cover_subtitle_style = ParagraphStyle(
        "cover_subtitle_style",
        parent=styles["Normal"],
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#555555"),
        alignment=0,
    )

    cover_label_style = ParagraphStyle(
        "cover_label_style",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#777777"),
        uppercase=True,
    )

    cover_value_style = ParagraphStyle(
        "cover_value_style",
        parent=styles["Normal"],
        fontSize=11,
        leading=13,
        textColor=colors.HexColor("#222222"),
        spaceAfter=2,
    )
    style_project_header = ParagraphStyle(
        "style_project_header",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor(TEXT_DARK),
        alignment=2,  # right
    )

    today = datetime.now().strftime("%d/%m/%Y")

    # Panel metrics for hero chips and summaries
    def _extract_panel_power(value):
        try:
            s = str(value)
        except Exception:
            return 0
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*[wW]", s)
        if m:
            try:
                return int(float(m.group(1).replace(",", ".")))
            except Exception:
                return 0
        try:
            return int(float(re.sub(r"[^0-9.,]", "", s).replace(",", ".")))
        except Exception:
            return 0

    def _panels_info(df_obj):
        total_qty = 0
        watt = 0
        if isinstance(df_obj, pd.DataFrame):
            try:
                mask = df_obj["Désignation"] == "Panneaux"
                if mask.any():
                    panneaux_rows = df_obj[mask]
                    total_qty = int(panneaux_rows["Quantité"].sum())
                    first_row = panneaux_rows.iloc[0]
                    power_candidate = first_row.get("Power", None)
                    if power_candidate in (None, ""):
                        power_candidate = first_row.get("Marque", "")
                    watt = _extract_panel_power(power_candidate)
            except Exception:
                pass
        elif isinstance(df_obj, list):
            for row_data in df_obj:
                if isinstance(row_data, dict) and row_data.get("Désignation") == "Panneaux":
                    total_qty += int(row_data.get("Quantité", 0) or 0)
                    if watt == 0:
                        power_candidate = row_data.get("Power", row_data.get("Marque", ""))
                        watt = _extract_panel_power(power_candidate)
        return total_qty, watt

    nombre_panneaux, puissance_panneau = _panels_info(df_sans)
    if nombre_panneaux == 0 and isinstance(df_avec, (pd.DataFrame, list)):
        nb_alt, power_alt = _panels_info(df_avec)
        if nb_alt:
            nombre_panneaux = nb_alt
        if puissance_panneau == 0:
            puissance_panneau = power_alt
    # Use passed panel watt as fallback if not parsed from product table
    if puissance_panneau == 0 and puissance_panneau_w > 0:
        puissance_panneau = puissance_panneau_w
    puissance_totale_kwc = round(nombre_panneaux * puissance_panneau / 1000, 2) if puissance_panneau else 0.0
    # Use passed kWp as fallback if panel arithmetic gives 0
    if puissance_totale_kwc == 0.0 and puissance_kwp > 0:
        puissance_totale_kwc = puissance_kwp

    # ========== PAGE 1 : PRÉSENTATION DU PROJET ==========
    heading_style = style_h1
    heading2_for_intro = style_h1

    # --- PREMIUM HEADER BAR (PAGE 1 ONLY) ---
    if LOGO_PATH.exists():
        logo = Image(str(LOGO_PATH), width=120)
    else:
        logo = Image("taqinor_logo.png", width=120)
    try:
        logo.drawHeight = logo.drawWidth * logo.imageHeight / logo.imageWidth
    except Exception:
        pass

    # Determine project text (city if possible)
    project_text = type_phrase
    if client_address:
        parts = [p.strip() for p in str(client_address).split(",") if p.strip()]
        if parts:
            project_text = f"{parts[0]} – Maroc"

    project_summary_html = (
        f"<b>Proposition commerciale – {type_phrase}</b><br/>"
        f"Réf. : {int(doc_number)} – {today}"
    )
    header_para = Paragraph(project_summary_html, style_project_header)

    header_table = Table([[logo, header_para]], colWidths=[140, 340])
    header_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BLUE_LIGHT)),
                ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "LEFT"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, 0), 10),
                ("RIGHTPADDING", (0, 0), (-1, 0), 10),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ]
        )
    )
    elements.append(header_table)
    elements.append(Spacer(1, 6))

    title_para = Paragraph("Devis Installation Photovoltaïque", cover_title_style)
    subtitle_para = Paragraph(
        "<i>Solution premium et sur-mesure pour votre autonomie énergétique</i>",
        cover_subtitle_style,
    )

    right_block = Table(
        [[title_para], [subtitle_para]],
        colWidths=[380],
    )
    right_block.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    hero_table = Table([[right_block]], colWidths=[480], hAlign="CENTER")
    hero_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#E6F1F7")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#0A5275")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )

    elements.append(hero_table)
    elements.append(Spacer(1, 4))

    client_box_table = Table(
        [
            [
                Paragraph(
                    f"Client : {client_name or '-'}<br/>"
                    f"Adresse : {client_address or '-'}<br/>"
                    f"Téléphone : {client_phone or '-'}<br/>"
                    f"Projet : {type_phrase}<br/>"
                    f"Puissance totale installée : {puissance_totale_kwc:.2f} kWc via {nombre_panneaux} panneaux de {puissance_panneau} W",
                    style_normal,
                )
            ]
        ],
        colWidths=[17 * cm],
    )
    client_box_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1.2, colors.HexColor(BLUE_MAIN)),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(BLUE_LIGHT)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ]
        )
    )

    elements.append(client_box_table)
    elements.append(Spacer(1, 6))

    # RÉSUMÉ DU PROJET
    heading1_style = style_h1
    heading2_style = style_h2
    heading3_style = style_h2

    def ensure_page_break():
        if not elements or not isinstance(elements[-1], PageBreak):
            elements.append(PageBreak())

    def add_divider():
        line = Drawing(480, 1)
        line.add(Line(0, 0, 480, 0, strokeColor=colors.HexColor("#E0E0E0"), strokeWidth=0.7))
        elements.append(line)

    # heading style already adds top spacing
    elements.append(Paragraph("RÉSUMÉ EXÉCUTIF", heading1_style))
    elements.append(Spacer(1, 6))
    elements.append(
        Paragraph(
            "Ce devis présente une solution photovoltaïque clé en main pour réduire durablement votre facture d'électricité et renforcer votre autonomie énergétique. L'installation proposée utilise des équipements premium (Canadian Solar, Huawei, Deye) dimensionnés pour maximiser l'autoconsommation et le retour sur investissement.",
            style_long_text,
        )
    )
    elements.append(Spacer(1, 6))
    bullet_intro = [
        f"Une installation de {puissance_totale_kwc:.2f} kWc composée de {nombre_panneaux} panneaux de {puissance_panneau} W",
        "Une comparaison entre une configuration SANS batterie et une configuration AVEC batterie",
        "Une estimation économique complète (production annuelle, économies, temps de retour sur investissement)",
        "Les garanties et engagements TAQINOR",
    ]
    elements.append(
        ListFlowable(
            [ListItem(Paragraph(txt, style_bullet)) for txt in bullet_intro],
            bulletType="bullet",
            bulletText="•",
            leftIndent=14,
        )
    )
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("OBJECTIFS DU CLIENT", heading1_style))
    elements.append(Spacer(1, 6))
    client_objectifs = [
        "Réduire de façon significative la facture d'électricité mensuelle",
        "Gagner en confort et en sécurité énergétique grâce à une installation évolutive (batterie ou extension future de puissance)",
    ]
    elements.append(
        ListFlowable(
            [ListItem(Paragraph(txt, style_bullet)) for txt in client_objectifs],
            bulletType="bullet",
            bulletText="•",
            leftIndent=14,
        )
    )
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("CONFIGURATION RECOMMANDÉE", heading1_style))
    elements.append(Spacer(1, 6))
    elements.append(
        Paragraph(
            f"TAQINOR propose deux scénarios adaptés à votre profil de consommation :<br/>"
            f"• Une installation SANS batterie, idéale lorsque la majorité de la consommation a lieu en journée.<br/>"
            f"• Une installation AVEC batterie, qui augmente fortement le taux d'autoconsommation, particulièrement en cas de consommation nocturne importante ou de coupures réseau.<br/>"
            f"Les deux scénarios reposent sur une puissance totale installée de {puissance_totale_kwc:.2f} kWc via {nombre_panneaux} modules de {puissance_panneau} W.",
            style_long_text,
        )
    )
    elements.append(Spacer(1, 4))

    # ========== PAGE 2 : OPTION SANS BATTERIE ==========
    # SECTION SANS
    options_heading_shown = False
    options_pagebreak_done = False
    print(f"[PDF] Checking SANS condition: scenario_choice={scenario_choice!r}")
    if scenario_choice in ("Sans batterie uniquement", "Sans batterie", "Les deux (Sans + Avec)", "Les deux (Sans + Avec batterie)"):
        if not options_pagebreak_done:
            elements.append(PageBreak())
            options_pagebreak_done = True
        if not options_heading_shown:
            elements.append(Spacer(1, 6))
            add_divider()
            elements.append(Spacer(1, 6))
            elements.append(Paragraph("PRÉSENTATION DES OPTIONS", heading1_style))
            elements.append(Spacer(1, 8))
            options_heading_shown = True
        context_term_map = {
            "Résidentielle": "foyer",
            "Commerciale": "activité",
            "Industrielle": "site",
            "Agricole": "exploitation",
        }
        context_term = context_term_map.get(installation_type, "site")
        elements.append(Paragraph("Option 1 : Installation SANS batterie", heading3_style))
        elements.append(Spacer(1, 6))
        elements.append(
            Paragraph(
                "Cette configuration SANS batterie convient lorsque la consommation est majoritairement diurne. "
                "Elle maximise directement l'autoconsommation sans stockage et constitue une solution simple, fiable et économiquement optimisée lorsque les usages nocturnes restent limités.",
                style_long_text,
            )
        )
        elements.append(Spacer(1, 6))

        sec_sans, total_sans = build_devis_section_elements(
            df_sans, notes_sans, styles, "Devis SANS batterie"
        )
        elements += sec_sans
        elements.append(Spacer(1, 10))

    # ========== PAGE 3 : OPTION AVEC BATTERIE ==========
    # SECTION AVEC
    if scenario_choice in ("Avec batterie uniquement", "Avec batterie", "Les deux (Sans + Avec)", "Les deux (Sans + Avec batterie)"):
        if not options_pagebreak_done:
            elements.append(PageBreak())
            options_pagebreak_done = True
        if not options_heading_shown:
            elements.append(Spacer(1, 6))
            add_divider()
            elements.append(Spacer(1, 6))
            elements.append(Paragraph("PRÉSENTATION DES OPTIONS", heading1_style))
            elements.append(Spacer(1, 8))
            options_heading_shown = True
        elements.append(Paragraph("Option 2 : Installation AVEC batterie", heading3_style))
        elements.append(Spacer(1, 6))
        elements.append(
            Paragraph(
                "Cette configuration AVEC batterie est adaptée lorsque la consommation nocturne est importante ou lorsque la continuité d'alimentation est un enjeu. "
                "Le stockage augmente fortement le taux d'autoconsommation, améliore le confort énergétique et réduit la dépendance au réseau en cas de coupure.",
                style_long_text,
            )
        )
        elements.append(Spacer(1, 6))

        sec_avec, total_avec = build_devis_section_elements(
            df_avec, notes_avec, styles, "Devis AVEC batterie"
        )
        elements += sec_avec
        elements.append(Spacer(1, 10))

    # ========== PAGE 4 : ANALYSE ÉCONOMIQUE ET ROI ==========
    # PAGE ROI GRAPHIQUE
    if roi_fig_all_buf is not None:
        elements.append(Spacer(1, 10))
        add_divider()
        elements.append(Spacer(1, 6))
        elements.append(PageBreak())
        elements.append(Paragraph("SYNTHÈSE FINANCIÈRE & ROI", heading1_style))
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("Analyse détaillée du retour sur investissement", heading2_style))
        elements.append(Spacer(1, 8))

        def fmt_nb(val, suffix=""):
            try:
                v = float(val)
            except Exception:
                return "—"
            return f"{v:,.2f}".replace(",", " ") + (f" {suffix}" if suffix else "")

        def fmt_int(val, suffix=""):
            try:
                v = float(val)
            except Exception:
                return "—"
            return f"{v:,.0f}".replace(",", " ") + (f" {suffix}" if suffix else "")

        sans_prod = fmt_int(roi_summary_sans.get("prod_annuelle", 0.0) if roi_summary_sans else "—", "kWh/an")
        sans_eco = fmt_int(roi_summary_sans.get("eco_annuelle", 0.0) if roi_summary_sans else "—", "MAD/an")
        sans_inv = fmt_int(roi_summary_sans.get("cout_systeme", 0.0) if roi_summary_sans else "—", "MAD")
        sans_payback = fmt_nb(roi_summary_sans.get("payback") if roi_summary_sans else "—", "années") if roi_summary_sans and roi_summary_sans.get("payback") is not None else "—"

        avec_prod = fmt_int(roi_summary_avec.get("prod_annuelle", 0.0) if roi_summary_avec else "—", "kWh/an")
        avec_eco = fmt_int(roi_summary_avec.get("eco_annuelle", 0.0) if roi_summary_avec else "—", "MAD/an")
        avec_inv = fmt_int(roi_summary_avec.get("cout_systeme", 0.0) if roi_summary_avec else "—", "MAD")
        avec_payback = fmt_nb(roi_summary_avec.get("payback") if roi_summary_avec else "—", "années") if roi_summary_avec and roi_summary_avec.get("payback") is not None else "—"

        puissance_sans = f"{puissance_totale_kwc:.2f} kWc"
        puissance_avec = puissance_sans

        summary_rows = [
            ["Puissance installée", puissance_sans, puissance_avec],
            ["Investissement TTC", sans_inv, avec_inv],
            ["Production annuelle estimée", sans_prod, avec_prod],
            ["Économie annuelle estimée", sans_eco, avec_eco],
            ["Temps de retour sur investissement", sans_payback, avec_payback],
        ]
        summary_table = Table(
            [
                [
                    Paragraph("", style_normal),
                    Paragraph("<b>Scénario SANS batterie</b>", style_header_top),
                    Paragraph("<b>Scénario AVEC batterie</b>", style_header_top),
                ]
            ]
            + [[Paragraph(label, style_normal), Paragraph(val_s, style_normal), Paragraph(val_a, style_normal)] for label, val_s, val_a in summary_rows],
            colWidths=[210, 135, 135],
            hAlign="CENTER",
        )
        roi_style = TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BLUE_MAIN)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, 0), 7),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(BLUE_MAIN)),
                ("INNERGRID", (0, 1), (-1, -1), 0.3, colors.HexColor("#D5E6F2")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), (colors.white, colors.HexColor(BLUE_LIGHT))),
                ("LEFTPADDING", (0, 1), (-1, -1), 6),
                ("RIGHTPADDING", (0, 1), (-1, -1), 6),
                ("TOPPADDING", (0, 1), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ]
        )
        label_to_row = {label: idx for idx, (label, *_rest) in enumerate(summary_rows, start=1)}
        highlight_labels = [
            "Investissement TTC",
            "Économie annuelle estimée",
            "Temps de retour sur investissement",
        ]
        for label in highlight_labels:
            row_idx = label_to_row.get(label)
            if row_idx:
                roi_style.add("FONTNAME", (1, row_idx), (2, row_idx), "Helvetica-Bold")
                roi_style.add("TEXTCOLOR", (1, row_idx), (2, row_idx), colors.HexColor(TEXT_DARK))
                roi_style.add("FONTSIZE", (1, row_idx), (2, row_idx), 10)
        summary_table.setStyle(roi_style)
        elements.append(summary_table)
        elements.append(Spacer(1, 6))

        # Recommandation encadrée (affichée uniquement si sélectionnée)
        if recommended_option and recommended_option.lower() not in ("aucune recommandation", "aucune recommandation (client libre de choisir)"):
            reco_label = f"Recommandation TAQINOR : {recommended_option}"
            reco_text = Paragraph(f"<b>{reco_label}</b>", style_normal)
            reco_tbl = Table([[reco_text]], colWidths=[480], hAlign="CENTER")
            reco_tbl.setStyle(
                TableStyle(
                    [
                        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor(BLUE_MAIN)),
                        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            elements.append(reco_tbl)
            elements.append(Spacer(1, 10))

    if roi_fig_all_buf is not None:
        elements.append(Paragraph("<b>Estimation des économies mensuelles</b>", style_header_top))
        roi_fig_all_buf.seek(0)
        img_roi = Image(roi_fig_all_buf)
        graph_max_width = doc.width
        graph_max_height = doc.width * 0.45
        img_roi._restrictSize(graph_max_width, graph_max_height)
        elements.append(img_roi)
        elements.append(Spacer(1, 6))
        elements.append(Paragraph("Comparaison des économies mensuelles avec et sans batterie.", style_long_text))
        elements.append(Spacer(1, 8))

    # Graphique cumulatif 25 ans
    if roi_fig_cumul_buf is not None:
        elements.append(Paragraph("Projection des gains cumulés sur 25 ans", heading2_style))
        roi_fig_cumul_buf.seek(0)
        img_cumul = Image(roi_fig_cumul_buf)
        cum_max_w = doc.width
        cum_max_h = doc.width * 0.5
        img_cumul._restrictSize(cum_max_w, cum_max_h)
        elements.append(img_cumul)
        elements.append(Spacer(1, 6))
        elements.append(Paragraph("Ce graphique illustre le gain cumulé sur 25 ans et le point d'équilibre (ROI) pour chaque configuration.", style_long_text))
        elements.append(Spacer(1, 8))

    # Hypothèses de calcul & profil de consommation
    elements.append(Paragraph("Hypothèses de calcul & profil de consommation", heading2_style))
    elements.append(Spacer(1, 6))
    hypotheses_items = [
        "Tarifs SRM/LYDEC/ONEE en vigueur au moment de l'étude.",
        "Profil de consommation basé sur vos dernières factures, ajusté si nécessaire.",
        "Production estimée selon l'irradiation locale, l'orientation, l'inclinaison et un rendement système réaliste.",
        "Taux d'autoconsommation estimé à partir de votre profil horaire, sur une durée de vie de 20 à 25 ans.",
    ]
    elements.append(
        ListFlowable(
            [ListItem(Paragraph(item, style_bullet)) for item in hypotheses_items],
            bulletType="bullet",
            bulletText="•",
            leftIndent=14,
        )
    )
    elements.append(Spacer(1, 10))

    # ========== PAGE 5 : GARANTIES ET POURQUOI TAQINOR ==========
    add_divider()
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("GARANTIES & CONDITIONS GÉNÉRALES", heading1_style))
    elements.append(Spacer(1, 8))

    # Section Garanties
    elements.append(Paragraph("<b>Couverture de garantie</b>", style_header_top))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("<b>Tous nos équipements sont garantis au minimum 10 ans.</b>", style_normal))
    elements.append(Spacer(1, 8))

    warranty_points = [
        "Onduleurs Huawei et Deye : 10 ans de garantie constructeur",
        "Panneaux solaires Canadian Solar : 12 ans de garantie",
    ]

    # Détecter le type de structure utilisé dans les deux scénarios (préférence aluminium si présent)
    struct_used = None
    for df_check in (df_sans, df_avec):
        try:
            for _, rr in pd.DataFrame(df_check).iterrows():
                des = rr.get("Désignation", "")
                qty = int(rr.get("Quantité", 0) or 0)
                custom = str(rr.get("CustomLabel", "")).lower().strip()
                if qty > 0:
                    des_lower = str(des).lower() if des else ""
                    # Check both designation and CustomLabel for structure type
                    if "structures" in des_lower:
                        if "aluminium" in des_lower or "aluminium" in custom:
                            struct_used = "aluminium"
                            break
                        elif "acier" in des_lower or "acier" in custom:
                            struct_used = "acier"
                            break
        except Exception:
            continue
        # Stop if we found aluminium (preference for aluminium)
        if struct_used == "aluminium":
            break

    if struct_used == "aluminium":
        warranty_points.append("Structures en aluminium : 25 ans de garantie")
    elif struct_used == "acier":
        warranty_points.append("Structures en acier galvanisé : 20 ans de garantie")
    else:
        warranty_points.append("Structures : garantie selon type utilisé (acier galvanisé 20 ans ou aluminium 25 ans)")

    elements.append(
        ListFlowable(
            [ListItem(Paragraph(item, style_bullet)) for item in warranty_points],
            bulletType="bullet",
            bulletText="•",
            leftIndent=14,
        )
    )
    elements.append(Spacer(1, 6))

    # Section Conditions
    elements.append(Paragraph("<b>Conditions générales</b>", style_header_top))
    elements.append(Spacer(1, 4))
    elements.append(
        Paragraph(
            "Les conditions ci-dessous définissent le cadre contractuel de l'offre TAQINOR pour votre installation photovoltaïque.",
            style_long_text,
        )
    )
    elements.append(Spacer(1, 4))

    conditions = [
        "Ce devis est valable <b>30 jours</b> à compter de sa date d'émission",
        "Toute commande implique l'adhésion sans réserve à nos conditions générales de vente",
        "Les prix indiquent la TVA applicable : 10% sur les modules photovoltaïques et 20% sur les autres équipements et prestations.",
        "La réalisation de ces travaux ne peut débuter sans signature du devis",
    ]
    elements.append(
        ListFlowable(
            [ListItem(Paragraph(item, style_cond_bullet)) for item in conditions],
            bulletType="bullet",
            bulletText="•",
            leftIndent=14,
        )
    )
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("Conditions financières & modalités de paiement", heading3_style))
    elements.append(Spacer(1, 4))
    if installation_type == "Résidentielle":
        conditions_financieres_items = [
            "Un acompte de 30% du montant TTC est demandé à la commande pour lancer l'approvisionnement du matériel.",
            "Le solde de 70% est à régler à la fin de la pose, des tests fonctionnels et de la mise en service.",
            "Toute modification significative du projet (changement de matériel, modification de surface disponible, contraintes techniques particulières) pourra entraîner une révision du devis.",
            "Les paiements peuvent être effectués par virement bancaire ou par tout autre moyen accepté par TAQINOR et précisé sur la facture.",
        ]
    else:
        conditions_financieres_items = [
            "Un acompte de 30% du montant TTC est demandé à la commande pour lancer l'approvisionnement du matériel.",
            "50% du montant TTC sont à régler après la livraison complète du matériel sur site.",
            "Les 20% restants sont à régler après la fin de la pose, des tests fonctionnels et de la mise en service.",
            "Toute modification significative du projet (changement de matériel, modification de surface disponible, contraintes techniques particulières) pourra entraîner une révision du devis.",
            "Les paiements peuvent être effectués par virement bancaire ou par tout autre moyen accepté par TAQINOR et précisé sur la facture.",
        ]
    conditions_financieres_list = ListFlowable(
        [ListItem(Paragraph(item, style_cond_bullet)) for item in conditions_financieres_items],
        bulletType="bullet",
        bulletText="•",
        leftIndent=14,
    )
    elements.append(conditions_financieres_list)
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("Délai indicatif de réalisation", heading3_style))
    elements.append(Spacer(1, 4))
    delai_text = (
        "Sous réserve de disponibilité du matériel et de conditions météorologiques favorables, le délai indicatif de "
        "réalisation de l'installation est de 7 à 14 jours ouvrés à compter de la réception de l'acompte et de la "
        "validation définitive du projet. Ce délai pourra être affiné lors de la planification et confirmé par écrit."
    )
    elements.append(Paragraph(delai_text, style_long_text))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("Périmètre de la prestation, exclusions & prérequis", heading3_style))
    elements.append(Spacer(1, 4))
    perimetre_items = [
        "Le présent devis inclut : la fourniture du matériel décrit, la pose des panneaux et des structures, le câblage AC/DC courant, le raccordement jusqu'au tableau électrique existant, la mise en service et la configuration de la supervision.",
        "Sont exclus sauf mention expresse : les travaux de maçonnerie, de renforcement de charpente ou de toiture, la mise aux normes complète de l'installation électrique existante, la création de longues tranchées ou gaines au-delà d'un linéaire standard, ainsi que toute autorisation administrative ou copropriété non spécifiée.",
        "Le client s'engage à garantir l'accès sécurisé au site (toiture, local technique, tableau électrique) pendant toute la durée du chantier.",
        "Toute contrainte découverte lors de la visite technique (toiture fragile, accès compliqué, non-conformité électrique majeure, etc.) pourra faire l'objet d'un avenant de devis avant démarrage des travaux."
    ]
    perimetre_list = ListFlowable(
        [ListItem(Paragraph(item, style_cond_bullet)) for item in perimetre_items],
        bulletType="bullet",
        bulletText="•",
        leftIndent=14,
    )
    elements.append(perimetre_list)
    elements.append(Spacer(1, 4))

    # Page Pourquoi TAQINOR
    ensure_page_break()
    elements.append(Spacer(1, 4))
    add_divider()
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("POURQUOI CHOISIR TAQINOR ?", heading1_style))
    elements.append(Spacer(1, 4))
    pourquoi_lines = [
        "Une équipe d'ingénieurs spécialisés en photovoltaïque, habitués aux projets résidentiels et tertiaires au Maroc.",
        "Des équipements premium (panneaux Canadian Solar, onduleurs Huawei / Deye) dimensionnés spécifiquement pour votre profil de consommation.",
        "Une installation réalisée dans les règles de l'art, avec contrôles, tests et mise en service détaillée sur site.",
        "Un suivi dans la durée, un SAV réactif et un accès à votre production en temps réel via l'application de monitoring.",
    ]
    elements.append(
        ListFlowable(
            [ListItem(Paragraph(line, style_cond_bullet)) for line in pourquoi_lines],
            bulletType="bullet",
            bulletText="•",
            leftIndent=14,
        )
    )
    elements.append(Spacer(1, 4))
    elements.append(
        Paragraph(
            "Notre équipe reste à votre disposition pour toute question complémentaire ou adaptation de cette proposition. La planification de l'installation sera effectuée dès validation du devis et organisation logistique avec le client.",
            style_long_text,
        )
    )
    elements.append(Spacer(1, 4))

    elements.append(Paragraph("Étapes suivantes", heading1_style))
    elements.append(Spacer(1, 4))
    elements.append(
        Paragraph(
            "Pour valider ce devis, merci de nous retourner ce document signé ou de nous confirmer par e-mail / WhatsApp. Nous planifierons ensuite la visite technique et la date d'installation.",
            style_long_text,
        )
    )
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("Signature du client : ___________________________    Date : ___ / ___ / ______", style_normal))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("Signature TAQINOR : ___________________________    Date : ___ / ___ / ______", style_normal))
    elements.append(Spacer(1, 4))

    # Footer on every page
    class NumberedCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            page_count = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self.draw_footer(page_count)
                super().showPage()
            super().save()

        def draw_footer(self, page_count):
            width, height = A4
            self.setStrokeColor(colors.HexColor("#E5E5E5"))
            self.setLineWidth(0.5)
            self.line(20 * mm, 14 * mm, width - 20 * mm, 14 * mm)

            left_text = "TAQINOR Solutions — contact@taqinor.com — +212 6 61 85 04 10"
            right_text = f"Page {self._pageNumber} / {page_count}"

            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor(TEXT_DARK))
            self.drawString(20 * mm, 8 * mm, left_text)
            self.drawRightString(width - 20 * mm, 8 * mm, right_text)

    doc.build(elements, canvasmaker=NumberedCanvas)
    return pdf_path


# ---------- PDF FACTURE SIMPLE ----------
def generate_single_pdf(df_in, client_name, client_address, client_phone,
                        doc_type, doc_number, notes):
    safe_client = re.sub(r"[^A-Za-z0-9]", "_", client_name or "Client")
    file_name = f"{doc_type}_{safe_client}_{int(doc_number)}.pdf"
    pdf_path = FACTURES_DIR / file_name

    # on réutilise le double devis mais avec un seul scénario sans ROI ni graph
    df_dummy_avec = pd.DataFrame(columns=df_in.columns)
    roi_buf = None
    pdf_path_final = generate_double_devis_pdf(
        df_sans=df_in,
        df_avec=df_dummy_avec,
        notes_sans=notes,
        notes_avec=[],
        client_name=client_name,
        client_address=client_address,
        client_phone=client_phone,
        doc_type=doc_type,
        doc_number=doc_number,
        roi_summary_sans=None,
        roi_summary_avec=None,
        roi_fig_all_buf=roi_buf,
        roi_fig_cumul_buf=None,
        scenario_choice="Sans batterie uniquement",
        recommended_option=None,
        installation_type="Résidentielle",
        type_label="résidentielle",
        type_phrase="Installation photovoltaïque résidentielle",
    )
    return pdf_path_final, file_name
