import re

# Read the app.py file
with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the line_editor function and replace it
new_line_editor = '''def line_editor(designation, label, default_qty, default_tva, catalog,
                custom_label=None, default_photo_key=None,
                default_brand=None, default_sell=None, default_buy=None,
                brand_only=False, default_power=None, default_phase=None):
    st.markdown(f"##### {label}")
    
    # For onduleurs, use special 3-column layout (Marque / Puissance / Phase)
    if designation in ("Onduleur réseau", "Onduleur hybride"):
        cols_ondu = st.columns([1.2, 1.0, 1.0, 0.8, 1.0, 1.0, 0.8])
        base_key = _catalog_key_for_designation(designation)
        
        # Col 0: Marque (dropdown from catalog)
        available_brands = get_onduleur_brands(load_catalog(), base_key)
        default_brand_idx = 0
        if default_brand and default_brand in available_brands:
            default_brand_idx = available_brands.index(default_brand)
        brand_final = cols_ondu[0].selectbox(
            "Marque",
            available_brands,
            index=default_brand_idx,
            key=f"sel_brand_{designation}_{label}"
        )
        
        # Get available powers for this brand
        powers_phases = get_onduleur_powers_and_phases(load_catalog(), base_key, brand_final) if brand_final else {}
        available_powers = sorted([float(p) if p[0].isdigit() else None for p in powers_phases.keys()])
        available_powers = [p for p in available_powers if p is not None]
        
        # Col 1: Puissance (dropdown from available for this brand)
        power_idx = 0
        if default_power is not None:
            if available_powers and default_power in available_powers:
                power_idx = available_powers.index(default_power)
        elif default_brand and " " in default_brand:
            try:
                extracted_power = float(default_brand.split()[-2])
                if available_powers and extracted_power in available_powers:
                    power_idx = available_powers.index(extracted_power)
            except (ValueError, IndexError):
                power_idx = 0
        
        power_selected = cols_ondu[1].selectbox(
            "Puissance (kW)",
            available_powers if available_powers else [5.0],
            index=power_idx,
            key=f"sel_power_{designation}_{label}"
        )
        
        # Col 2: Phase (read-only from catalog or dropdown)
        power_str = str(int(power_selected) if power_selected == int(power_selected) else power_selected)
        phase_from_catalog = powers_phases.get(power_str, default_phase or "Monophase")
        cols_ondu[2].markdown(f"Phase: **{phase_from_catalog}**")
        phase_final = phase_from_catalog
        
        # Col 3: Quantité
        qty = cols_ondu[3].number_input(
            "Quantité",
            min_value=0,
            step=1,
            value=int(default_qty),
            key=f"qty_{designation}_{label}",
        )
        
        # Lookup prices for this marque/power combination
        catalog_load = load_catalog()
        sell_price = 0.0
        buy_price = 0.0
        
        if base_key in catalog_load and brand_final in catalog_load[base_key]:
            power_dict = catalog_load[base_key][brand_final].get(power_str, {})
            sell_price = float(power_dict.get("sell_ttc", 0.0))
            buy_price = float(power_dict.get("buy_ttc", 0.0))
        
        # Col 4 & 5: Prix (auto-filled from catalog, but editable)
        sell_val = cols_ondu[4].number_input(
            "Prix Unit. TTC",
            min_value=0.0,
            step=10.0,
            value=sell_price if sell_price > 0 else (default_sell or 0.0),
            key=f"sell_{designation}_{label}_{brand_final}_{power_str}",
        )
        buy_val = cols_ondu[5].number_input(
            "Prix Achat TTC",
            min_value=0.0,
            step=10.0,
            value=buy_price if buy_price > 0 else (default_buy or 0.0),
            key=f"buy_{designation}_{label}_{brand_final}_{power_str}",
        )
        
        # Col 6: TVA
        tva = cols_ondu[6].number_input(
            "TVA (%)",
            min_value=0,
            step=1,
            value=int(default_tva),
            key=f"tva_{designation}_{label}",
        )
        
        brand_final = f"{brand_final} {power_selected}kW {phase_final}"
        
        result = {
            "Désignation": designation,
            "Marque": brand_final,
            "Quantité": qty,
            "Prix Achat TTC": buy_val,
            "Prix Unit. TTC": sell_val,
            "TVA (%)": tva,
        }
        if custom_label is not None:
            result["CustomLabel"] = custom_label
        if default_photo_key is not None:
            result["PhotoKey"] = default_photo_key
        
        return result
    
    # For Panneaux, use marque / puissance selection
    elif designation == "Panneaux":
        cols_pan = st.columns([1.2, 1.0, 0.8, 1.0, 1.0, 0.8])
        
        # Col 0: Marque (dropdown)
        available_brands = get_panel_brands(load_catalog())
        default_brand_idx = 0
        if default_brand and default_brand in available_brands:
            default_brand_idx = available_brands.index(default_brand)
        elif available_brands and "Canadien Solar" in available_brands:
            default_brand_idx = available_brands.index("Canadien Solar")
        
        brand_final = cols_pan[0].selectbox(
            "Marque",
            available_brands,
            index=default_brand_idx,
            key=f"sel_brand_Panneaux_{label}"
        )
        
        # Get available powers for this brand
        powers_dict = get_panel_powers(load_catalog(), brand_final) if brand_final else {}
        available_powers = sorted(powers_dict.keys(), key=lambda x: float(x) if x.replace('.','').isdigit() else 0)
        
        # Col 1: Puissance (dropdown)
        power_idx = 0
        if default_power and str(default_power) in available_powers:
            power_idx = available_powers.index(str(default_power))
        elif available_powers and "710" in available_powers:
            power_idx = available_powers.index("710")
        
        power_selected = cols_pan[1].selectbox(
            "Puissance (W)",
            available_powers if available_powers else ["710"],
            index=power_idx,
            key=f"sel_power_Panneaux_{label}"
        )
        
        # Col 2: Quantité
        qty = cols_pan[2].number_input(
            "Quantité",
            min_value=0,
            step=1,
            value=int(default_qty),
            key=f"qty_Panneaux_{label}",
        )
        
        # Lookup prices
        sell_price = 0.0
        buy_price = 0.0
        if brand_final and power_selected in powers_dict:
            sell_price = float(powers_dict[power_selected].get("sell_ttc", 0.0))
            buy_price = float(powers_dict[power_selected].get("buy_ttc", 0.0))
        
        # Col 3 & 4: Prix
        sell_val = cols_pan[3].number_input(
            "Prix Unit. TTC",
            min_value=0.0,
            step=10.0,
            value=sell_price if sell_price > 0 else (default_sell or 0.0),
            key=f"sell_Panneaux_{label}_{brand_final}_{power_selected}",
        )
        buy_val = cols_pan[4].number_input(
            "Prix Achat TTC",
            min_value=0.0,
            step=10.0,
            value=buy_price if buy_price > 0 else (default_buy or 0.0),
            key=f"buy_Panneaux_{label}_{brand_final}_{power_selected}",
        )
        
        # Col 5: TVA
        tva = cols_pan[5].number_input(
            "TVA (%)",
            min_value=0,
            step=1,
            value=int(default_tva),
            key=f"tva_Panneaux_{label}",
        )
        
        marque_display = f"{brand_final} {power_selected}W"
        
        result = {
            "Désignation": designation,
            "Marque": marque_display,
            "Quantité": qty,
            "Prix Achat TTC": buy_val,
            "Prix Unit. TTC": sell_val,
            "TVA (%)": tva,
        }
        if custom_label is not None:
            result["CustomLabel"] = custom_label
        if default_photo_key is not None:
            result["PhotoKey"] = default_photo_key
        
        return result
    
    # For Batterie, use marque / capacité selection
    elif designation == "Batterie":
        cols_bat = st.columns([1.2, 1.0, 0.8, 1.0, 1.0, 0.8])
        
        # Col 0: Marque (dropdown)
        available_brands = get_battery_brands(load_catalog())
        default_brand_idx = 0
        if default_brand and default_brand in available_brands:
            default_brand_idx = available_brands.index(default_brand)
        elif available_brands and "Deyness" in available_brands:
            default_brand_idx = available_brands.index("Deyness")
        
        brand_final = cols_bat[0].selectbox(
            "Marque",
            available_brands,
            index=default_brand_idx,
            key=f"sel_brand_Batterie_{label}"
        )
        
        # Get available capacities for this brand
        capacities_dict = get_battery_capacities(load_catalog(), brand_final) if brand_final else {}
        available_capacities = sorted(capacities_dict.keys(), key=lambda x: float(x) if x.replace('.','').isdigit() else 0)
        
        # Col 1: Capacité (dropdown)
        capacity_idx = 0
        if default_power and str(default_power) in available_capacities:
            capacity_idx = available_capacities.index(str(default_power))
        elif available_capacities and "5" in available_capacities:
            capacity_idx = available_capacities.index("5")
        
        capacity_selected = cols_bat[1].selectbox(
            "Capacité (kWh)",
            available_capacities if available_capacities else ["5"],
            index=capacity_idx,
            key=f"sel_capacity_Batterie_{label}"
        )
        
        # Col 2: Quantité
        qty = cols_bat[2].number_input(
            "Quantité",
            min_value=0,
            step=1,
            value=int(default_qty),
            key=f"qty_Batterie_{label}",
        )
        
        # Lookup prices
        sell_price = 0.0
        buy_price = 0.0
        if brand_final and capacity_selected in capacities_dict:
            sell_price = float(capacities_dict[capacity_selected].get("sell_ttc", 0.0))
            buy_price = float(capacities_dict[capacity_selected].get("buy_ttc", 0.0))
        
        # Col 3 & 4: Prix
        sell_val = cols_bat[3].number_input(
            "Prix Unit. TTC",
            min_value=0.0,
            step=10.0,
            value=sell_price if sell_price > 0 else (default_sell or 0.0),
            key=f"sell_Batterie_{label}_{brand_final}_{capacity_selected}",
        )
        buy_val = cols_bat[4].number_input(
            "Prix Achat TTC",
            min_value=0.0,
            step=10.0,
            value=buy_price if buy_price > 0 else (default_buy or 0.0),
            key=f"buy_Batterie_{label}_{brand_final}_{capacity_selected}",
        )
        
        # Col 5: TVA
        tva = cols_bat[5].number_input(
            "TVA (%)",
            min_value=0,
            step=1,
            value=int(default_tva),
            key=f"tva_Batterie_{label}",
        )
        
        marque_display = f"{brand_final} {capacity_selected}kWh"
        
        result = {
            "Désignation": designation,
            "Marque": marque_display,
            "Quantité": qty,
            "Prix Achat TTC": buy_val,
            "Prix Unit. TTC": sell_val,
            "TVA (%)": tva,
        }
        if custom_label is not None:
            result["CustomLabel"] = custom_label
        if default_photo_key is not None:
            result["PhotoKey"] = default_photo_key
        
        return result
    
    # For non-onduleur/panneau/batterie items, use standard layout
    cols = st.columns([1.2, 1.0, 0.8, 1.0, 1.0, 0.8])
    brand_final = ""
    
    if designation in ("Smart Meter", "Wifi Dongle", "Accessoires", "Structures", "Socles", "Tableau De Protection AC/DC", "Instalation", "Installation + transport", "Transport", "Suivi journalier, maintenance chaque 12 mois pendent 2 ans", "Autre"):
        cols[0].markdown("—")
        cols[1].markdown("—")
    else:
        brand_sel_list = known_brands(catalog, designation)
        brand_sel = cols[0].selectbox(
            "Marque", brand_sel_list, key=f"sel_{designation}_{label}"
        )
        new_brand = cols[1].text_input("Nouvelle marque", value=(default_brand or ""), key=f"new_{designation}_{label}")
        brand_final = (new_brand.strip() or brand_sel)

    qty = cols[2].number_input(
        "Quantité",
        min_value=0,
        step=1,
        value=int(default_qty),
        key=f"qty_{designation}_{label}",
    )

    # Price lookup with stable keys
    stable_price_key_sell = f"sell_{designation}_{label}"
    stable_price_key_buy = f"buy_{designation}_{label}"
    brand_tracking_key = f"brand_tracked_{designation}_{label}"
    
    if brand_tracking_key not in st.session_state:
        st.session_state[brand_tracking_key] = brand_final
    
    # If brand changed, refresh prices from catalog
    if st.session_state[brand_tracking_key] != brand_final:
        st.session_state[brand_tracking_key] = brand_final
        if brand_final:
            catalog_sell, catalog_buy = get_prices(load_catalog(), designation, brand_final)
            if catalog_sell is not None:
                st.session_state[stable_price_key_sell] = float(catalog_sell)
            if catalog_buy is not None:
                st.session_state[stable_price_key_buy] = float(catalog_buy)

    auto_sell, auto_buy = get_prices(load_catalog(), designation, brand_final)
    initial_sell = float(default_sell) if default_sell is not None else float(auto_sell or 0.0)
    initial_buy = float(default_buy) if default_buy is not None else float(auto_buy or 0.0)
    
    if stable_price_key_sell in st.session_state:
        initial_sell = st.session_state[stable_price_key_sell]
    if stable_price_key_buy in st.session_state:
        initial_buy = st.session_state[stable_price_key_buy]
    
    sell_val = cols[3].number_input(
        "Prix Unit. TTC",
        min_value=0.0,
        step=10.0,
        value=initial_sell,
        key=stable_price_key_sell,
    )
    buy_val = cols[4].number_input(
        "Prix Achat TTC",
        min_value=0.0,
        step=10.0,
        value=initial_buy,
        key=stable_price_key_buy,
    )
    tva = cols[5].number_input(
        "TVA (%)",
        min_value=0,
        step=1,
        value=int(default_tva),
        key=f"tva_{designation}_{label}",
    )

    result = {
        "Désignation": designation,
        "Marque": brand_final,
        "Quantité": qty,
        "Prix Achat TTC": buy_val,
        "Prix Unit. TTC": sell_val,
        "TVA (%)": tva,
    }
    if custom_label is not None:
        result["CustomLabel"] = custom_label
    if default_photo_key is not None:
        result["PhotoKey"] = default_photo_key

    return result
'''

# Find and replace the old line_editor function
start_marker = 'def line_editor(designation, label, default_qty, default_tva, catalog,'
end_marker = 'def build_devis_from_scenario('

start_idx = None
end_idx = None

for i, line in enumerate(lines):
    if start_marker in line:
        start_idx = i
    if end_marker in line and start_idx is not None:
        end_idx = i
        break

if start_idx is not None and end_idx is not None:
    # Replace the old function with the new one
    new_lines = lines[:start_idx] + [new_line_editor + '\n\n'] + lines[end_idx:]
    
    with open('app.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print(f"Replaced line_editor function (lines {start_idx} to {end_idx})")
else:
    print(f"Could not find line_editor function boundaries. start_idx={start_idx}, end_idx={end_idx}")
