with open('app_old.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the problematic section and replace it
old_section = '''    elements.append(Paragraph("<b>Estimation des économies mensuelles</b>", style_header_top))
    roi_fig_all_buf.seek(0)
    img_roi = Image(roi_fig_all_buf)
    graph_max_width = doc.width
    graph_max_height = doc.width * 0.45
    img_roi._restrictSize(graph_max_width, graph_max_height)
    elements.append(img_roi)
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("Comparaison des économies mensuelles avec et sans batterie.", style_long_text))
    elements.append(Spacer(1, 8))'''

new_section = '''    if roi_fig_all_buf is not None:
        elements.append(Paragraph("<b>Estimation des économies mensuelles</b>", style_header_top))
        roi_fig_all_buf.seek(0)
        img_roi = Image(roi_fig_all_buf)
        graph_max_width = doc.width
        graph_max_height = doc.width * 0.45
        img_roi._restrictSize(graph_max_width, graph_max_height)
        elements.append(img_roi)
        elements.append(Spacer(1, 6))
        elements.append(Paragraph("Comparaison des économies mensuelles avec et sans batterie.", style_long_text))
        elements.append(Spacer(1, 8))'''

if old_section in content:
    content = content.replace(old_section, new_section)
    with open('app_old.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Successfully fixed roi_fig_all_buf None check')
else:
    print('Section not found - may already be fixed or content differs')
