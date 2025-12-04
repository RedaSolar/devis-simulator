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
    scenario_choice,
):
    safe_client = re.sub(r"[^A-Za-z0-9]", "_", client_name or "Client")
    file_name = f"{doc_type}_{safe_client}_{int(doc_number)}.pdf"
    pdf_path = DEVIS_DIR / file_name

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=35,
        bottomMargin=40,
    )
    elements = []
    styles = getSampleStyleSheet()
    style_normal = styles["Normal"]
    style_normal.fontSize = 9
    style_normal.leading = 11
    style_small = styles["Normal"].clone("small")
    style_small.fontSize = 9
    style_small.leading = 11
    from reportlab.lib.styles import ParagraphStyle
    style_company = ParagraphStyle(
        "company",
        parent=style_normal,
        fontSize=9,
        leading=14,
    )
    style_header_top = ParagraphStyle(
        "header_top",
        parent=style_normal,
        fontSize=11,
        leading=13,
    )

    today = datetime.now().strftime("%d/%m/%Y")
    
    # ========== PAGE 1 : PRÉSENTATION DU PROJET ==========
    # HEADER GLOBAL (logo left, company small text top-right)
    if LOGO_PATH.exists():
        left = [Image(str(LOGO_PATH), width=200, height=200)]
    else:
        left = [Paragraph("<b>TAQINOR</b>", styles["Title"])]

    company_txt = (
        "<b>TAQINOR Solutions SARLAU</b><br/>"
        "RC 691213 | ICE 003799642000067<br/>"
        "5 Rue Annoussour, Casablanca 20250<br/>"
        "Tél : 0661 85 04 10<br/>"
        "Email : contact@taqinor.com"
    )
    right = [Paragraph(company_txt, style_company)]
    header = Table([[left, right]], colWidths=[240, 240])
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements += [header, Spacer(1, 4)]

    line_tbl = Table([[""]], colWidths=[480])
    line_tbl.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, -1), 1.0, colors.HexColor(BLUE_MAIN)),
            ]
        )
    )
    elements += [line_tbl, Spacer(1, 6)]

    # TITRE PAGE 1
    title_page1 = ParagraphStyle(
        "title_page1",
        parent=style_normal,
        fontSize=18,
        leading=22,
        textColor=colors.HexColor(BLUE_MAIN),
        spaceAfter=12,
        alignment=1
    )
    elements.append(Paragraph("Devis Installation Photovoltaïque", title_page1))
    elements.append(Spacer(1, 12))

    # INFOS CLIENT + DOC (côte à côte)
    client_info = (
        f"<b>Client :</b><br/>{client_name or '-'}<br/>{client_address or '-'}<br/>{client_phone or '-'}"
    )
    doc_info = (
        f"<b>Numéro du {doc_type} :</b> {int(doc_number)}<br/>"
        f"<b>Date d'émission :</b> {today}"
    )
    info = Table(
        [
            [
                Paragraph(client_info, style_normal),
                Paragraph(doc_info, style_normal),
            ]
        ],
        colWidths=[310, 170],
    )
    info.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements += [info, Spacer(1, 20)]

    # RÉSUMÉ DU PROJET
    heading_style = ParagraphStyle(
        "heading",
        parent=style_normal,
        fontSize=12,
        leading=14,
        textColor=colors.HexColor(BLUE_MAIN),
        spaceAfter=8,
    )
    
    # Calculer le nombre de panneaux et la puissance totale
    nb_panneaux = 0
    puissance_panneau = 0
    try:
        for row_data in (df_sans if isinstance(df_sans, list) else []):
            if isinstance(row_data, dict) and row_data.get("Désignation") == "Panneaux":
                nb_panneaux = int(row_data.get("Quantité", 0))
                # Extraire la puissance du modèle de panneau (ex: "Canadian Solar 710W")
                marque = str(row_data.get("Marque", ""))
                if "710" in marque:
                    puissance_panneau = 710
                elif "620" in marque:
                    puissance_panneau = 620
                elif "590" in marque:
                    puissance_panneau = 590
                break
    except Exception:
        pass
    
    puissance_totale = (nb_panneaux * puissance_panneau) / 1000 if puissance_panneau > 0 else 0
    
    # Extraire la capacité de batterie (en kWh) si présente
    batterie_capacite_kwh = 0.0
    try:
        for row_data in (df_avec if isinstance(df_avec, list) else []):
            if isinstance(row_data, dict) and row_data.get("Désignation") == "Batterie":
                marque_bat = str(row_data.get("Marque", ""))
                qty_bat = int(row_data.get("Quantité", 0))
                if "10" in marque_bat:
                    batterie_capacite_kwh += qty_bat * 10.0
                elif "5" in marque_bat:
                    batterie_capacite_kwh += qty_bat * 5.0
    except Exception:
        pass
    
    # Déterminer quels scénarios sont présents
    scenario_text = ""
    if scenario_choice == "Sans batterie uniquement":
        scenario_text = "scénario sans batterie"
    elif scenario_choice == "Avec batterie uniquement":
        scenario_text = "scénario avec batterie"
    elif scenario_choice == "Les deux (Sans + Avec)":
        scenario_text = "deux scénarios : sans batterie et avec batterie"
    
    project_summary = (
        f"<b>Installation photovoltaïque de {nb_panneaux} panneaux de {puissance_panneau}W "
        f"(puissance totale : {puissance_totale:.2f} kWc)</b><br/>"
        f"avec {scenario_text}."
    )
    elements.append(Paragraph("<b>Résumé du projet :</b>", heading_style))
    elements.append(Paragraph(project_summary, style_normal))
    elements.append(Spacer(1, 12))
    
    # Description des deux options
    elements.append(Paragraph("<b>Description des options :</b>", heading_style))
    options_desc = (
        "<b>• Option 1 - Installation SANS batterie :</b> Système connecté au réseau électrique national, "
        "sans stockage d'énergie. L'électricité produite est consommée directement ou injectée dans le réseau.<br/>"
        "<br/>"
    )
    if batterie_capacite_kwh > 0:
        options_desc += (
            f"<b>• Option 2 - Installation AVEC batterie :</b> Système hybride avec batterie de {batterie_capacite_kwh} kWh."
        )
    else:
        options_desc += (
            "<b>• Option 2 - Installation AVEC batterie :</b> Système hybride avec batterie de stockage. "
            "Maximise l'autoconsommation et offre une autonomie énergétique."
        )
    elements.append(Paragraph(options_desc, style_normal))
    elements.append(Spacer(1, 12))
    
    # Description des avantages
    elements.append(Paragraph("<b>Avantages de cette installation :</b>", heading_style))
    advantages = (
        "• Réduction significative de vos factures d'électricité dès les premiers mois<br/>"
        "• Production d'une énergie propre et renouvelable, adaptée au climat marocain<br/>"
        "• Amélioration de la valeur de votre bien immobilier<br/>"
        "• Technologie fiable, avec des garanties allant de 10 à 25 ans selon les équipements<br/>"
        "• Accompagnement technique complet par TAQINOR, avant et après l'installation"
    )
    elements.append(Paragraph(advantages, style_normal))
    elements.append(Spacer(1, 16))
    
    # Ajouter un PageBreak après la première page
    elements.append(PageBreak())
    
    # ========== PAGE 2 : OPTION SANS BATTERIE ==========
    # SECTION SANS
    if scenario_choice in ("Sans batterie uniquement", "Les deux (Sans + Avec)"):
        heading_scenario = ParagraphStyle(
            "heading_scenario",
            parent=style_normal,
            fontSize=14,
            leading=16,
            textColor=colors.HexColor(BLUE_MAIN),
            spaceAfter=10,
        )
        elements.append(Paragraph("Option 1 : Installation SANS batterie", heading_scenario))
        elements.append(Spacer(1, 8))
        
        sec_sans, total_sans = build_devis_section_elements(
            df_sans, notes_sans, styles, "Devis SANS batterie"
        )
        elements += sec_sans
        elements.append(Spacer(1, 12))

    # PAGE BREAK entre les deux scénarios si on affiche les deux
    if scenario_choice == "Les deux (Sans + Avec)":
        elements.append(PageBreak())
        
    # ========== PAGE 3 : OPTION AVEC BATTERIE ==========
    # SECTION AVEC
    if scenario_choice in ("Avec batterie uniquement", "Les deux (Sans + Avec)"):
        heading_scenario = ParagraphStyle(
            "heading_scenario",
            parent=style_normal,
            fontSize=14,
            leading=16,
            textColor=colors.HexColor(BLUE_MAIN),
            spaceAfter=10,
        )
        elements.append(Paragraph("Option 2 : Installation AVEC batterie", heading_scenario))
        elements.append(Spacer(1, 8))
        
        sec_avec, total_avec = build_devis_section_elements(
            df_avec, notes_avec, styles, "Devis AVEC batterie"
        )
        elements += sec_avec
        elements.append(Spacer(1, 12))

    # ========== PAGE 4 : ANALYSE ÉCONOMIQUE ET ROI ==========
    # PAGE ROI GRAPHIQUE
    if roi_fig_all_buf is not None:
        elements.append(PageBreak())
        
        heading_roi = ParagraphStyle(
            "heading_roi",
            parent=style_normal,
            fontSize=14,
            leading=16,
            textColor=colors.HexColor(BLUE_MAIN),
            spaceAfter=10,
        )
        elements.append(Paragraph("Analyse Économique et Retour sur Investissement", heading_roi))
        elements.append(Spacer(1, 12))
        
        elements.append(Paragraph("<b>Estimation des économies mensuelles</b>", style_header_top))
        elements.append(Spacer(1, 6))
        roi_fig_all_buf.seek(0)
        elements.append(Image(roi_fig_all_buf, width=420, height=260))
        elements.append(Spacer(1, 10))

        # Explication du graphique
        elements.append(Paragraph("<b>Interprétation du graphique</b>", style_header_top))
        elements.append(Spacer(1, 4))
        expl = (
            "Le graphique ci-dessus présente l'estimation des économies mensuelles générées par l'installation photovoltaïque "
            "sur 12 mois. Chaque série correspond à un scénario : économies sans batterie et économies avec batterie. "
            "Ces valeurs servent à comparer l'impact financier mensuel entre les deux configurations et à alimenter le calcul de retour sur investissement."
        )
        elements.append(Paragraph(expl, style_normal))
        elements.append(Spacer(1, 12))

        # Résumés ROI pour les deux scénarios (rassemblés après le graphique)
        if roi_summary_sans is not None:
            elements.append(Paragraph("<b>Scénario SANS batterie</b>", style_header_top))
            elements.append(Spacer(1, 4))
            prod_ann = roi_summary_sans.get("prod_annuelle", 0.0)
            eco_ann = roi_summary_sans.get("eco_annuelle", 0.0)
            cout_sys = roi_summary_sans.get("cout_systeme", 0.0)
            payback = roi_summary_sans.get("payback", None)
            txt = (
                f"<b>Production photovoltaïque annuelle estimée :</b> {prod_ann:,.0f} kWh/an<br/>"
                f"<b>Économie annuelle estimée :</b> {eco_ann:,.0f} MAD/an<br/>"
                f"<b>Coût d'investissement estimé :</b> {cout_sys:,.0f} MAD<br/>"
            )
            if payback is not None:
                txt += f"<b>Temps de retour sur investissement :</b> {payback:.1f} années<br/>"
            else:
                txt += "<b>Temps de retour sur investissement :</b> non calculable (économie annuelle nulle)<br/>"
            elements.append(Paragraph(txt, style_normal))
            elements.append(Spacer(1, 10))

        if roi_summary_avec is not None:
            elements.append(Paragraph("<b>Scénario AVEC batterie</b>", style_header_top))
            elements.append(Spacer(1, 4))
            prod_ann = roi_summary_avec.get("prod_annuelle", 0.0)
            eco_ann = roi_summary_avec.get("eco_annuelle", 0.0)
            cout_sys = roi_summary_avec.get("cout_systeme", 0.0)
            payback = roi_summary_avec.get("payback", None)
            txt = (
                f"<b>Production photovoltaïque annuelle estimée :</b> {prod_ann:,.0f} kWh/an<br/>"
                f"<b>Économie annuelle estimée :</b> {eco_ann:,.0f} MAD/an<br/>"
                f"<b>Coût d'investissement estimé :</b> {cout_sys:,.0f} MAD<br/>"
            )
            if payback is not None:
                txt += f"<b>Temps de retour sur investissement :</b> {payback:.1f} années<br/>"
            else:
                txt += "<b>Temps de retour sur investissement :</b> non calculable (économie annuelle nulle)<br/>"
            elements.append(Paragraph(txt, style_normal))
            elements.append(Spacer(1, 10))

    # ========== PAGE 5 : GARANTIES ET POURQUOI TAQINOR ==========
    elements.append(PageBreak())

    # ========== PAGE 5 : GARANTIES ET POURQUOI TAQINOR ==========
    elements.append(PageBreak())
    
    heading_warranty = ParagraphStyle(
        "heading_warranty",
        parent=style_normal,
        fontSize=14,
        leading=16,
        textColor=colors.HexColor(BLUE_MAIN),
        spaceAfter=10,
    )
    elements.append(Paragraph("Garanties et Engagement Qualité", heading_warranty))
    elements.append(Spacer(1, 12))
    
    # Section Garanties
    elements.append(Paragraph("<b>Couverture de garantie</b>", style_header_top))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("<b>Tous nos équipements sont garantis au minimum 10 ans.</b>", style_normal))
    elements.append(Spacer(1, 8))
    
    warranty_details = (
        "<b>• Onduleurs Huawei et Deye :</b> 10 ans de garantie constructeur<br/>"
        "<b>• Panneaux solaires Canadian Solar :</b> 12 ans de garantie<br/>"
    )
    
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
        warranty_details += "<b>• Structures en aluminium :</b> 25 ans de garantie<br/>"
    elif struct_used == "acier":
        warranty_details += "<b>• Structures en acier galvanisé :</b> 20 ans de garantie<br/>"
    else:
        warranty_details += "<b>• Structures :</b> garantie selon type utilisé (acier galvanisé 20 ans ou aluminium 25 ans)<br/>"
    
    elements.append(Paragraph(warranty_details, style_normal))
    elements.append(Spacer(1, 12))
    
    # Section Pourquoi TAQINOR
    elements.append(Paragraph("<b>Pourquoi choisir TAQINOR ?</b>", style_header_top))
    elements.append(Spacer(1, 6))
    
    why_taqinor = (
        "<b>✓ Expertise reconnue :</b> Spécialiste en solutions photovoltaïques et batteries depuis plus de 10 ans<br/>"
        "<b>✓ Équipements de qualité :</b> Marques réputées (Huawei, Deye, Canadian Solar)<br/>"
        "<b>✓ Accompagnement complet :</b> Études gratuites, devis précis, installation professionnelle<br/>"
        "<b>✓ Suivi technique :</b> Maintenance et support 24/7 après installation<br/>"
        "<b>✓ Rentabilité garantie :</b> Étude ROI personnalisée avec simulation de production<br/>"
        "<b>✓ Respect des normes :</b> Conformité aux standards marocains et internationaux"
    )
    elements.append(Paragraph(why_taqinor, style_normal))
    elements.append(Spacer(1, 12))
    
    # Section Conditions
    elements.append(Paragraph("<b>Conditions générales</b>", style_header_top))
    elements.append(Spacer(1, 6))
    
    conditions = (
        "• Ce devis est valable <b>30 jours</b> à compter de sa date d'émission<br/>"
        "• Toute commande implique l'adhésion sans réserve à nos conditions générales de vente<br/>"
        "• Les prix indiqués incluent la TVA 20%<br/>"
        "• La réalisation de ces travaux ne peut débuter sans signature du devis"
    )
    elements.append(Paragraph(conditions, style_normal))

    # FOOTER
    # Footer content to be drawn on the last page only (at fixed bottom position)
    footer_lines = [
        "Ce devis est valable 30 jours à compter de sa date d'émission.",
        "Toute commande implique l'adhésion sans réserve à nos conditions générales de vente.",
        "TAQINOR Solutions SARLAU — RC 691213 | ICE 003799642000067",
        "Adresse : 5 Rue Annoussour, Casablanca 20250 | Tél : 0661 85 04 10 | Email : contact@taqinor.com",
    ]

    # Custom canvas that will draw the footer only on the last page
    from reportlab.pdfgen import canvas as pdfcanvas

    def _draw_footer(c: pdfcanvas.Canvas):
        c.saveState()
        width, height = A4
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.HexColor("#555555"))
        # Start a little above the bottom margin
        y = 28
        x = 40
        for i, line in enumerate(footer_lines):
            c.drawString(x, y + i * 10, line)
        c.restoreState()

    class LastPageCanvas(pdfcanvas.Canvas):
        def __init__(self, *args, **kwargs):
            pdfcanvas.Canvas.__init__(self, *args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            # add footer only on the last page
            num_pages = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                if self._pageNumber == num_pages:
                    _draw_footer(self)
                pdfcanvas.Canvas.showPage(self)
            pdfcanvas.Canvas.save(self)

    doc.build(elements, canvasmaker=LastPageCanvas)
    return pdf_path
