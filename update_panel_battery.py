#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

# Lire le fichier app.py
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Nouvelle section pour remplacer "if designation in ("Panneaux", "Batterie"):"
old_section = r'''    if designation in \("Panneaux", "Batterie"\):
        brand_sel_list = known_brands\(catalog, designation\)
        brand_sel = cols\[0\].selectbox\(
            "Marque", brand_sel_list, key=f"sel_{designation}_{label}"
        \)
        new_brand = cols\[1\].text_input\("Nouvelle marque", value=\(default_brand or ""\), key=f"new_{designation}_{label}"\)
        brand_final = \(new_brand.strip\(\) or brand_sel\)'''

new_section = '''    if designation == "Panneaux":
        # Panneaux: Marque + Puissance
        available_brands = get_panel_brands(load_catalog())
        default_brand_idx = 0
        if default_brand and default_brand in available_brands:
            default_brand_idx = available_brands.index(default_brand)
        elif available_brands and "Canadien Solar" in available_brands:
            default_brand_idx = available_brands.index("Canadien Solar")
        
        brand_final = cols[0].selectbox("Marque", available_brands, index=default_brand_idx, key=f"sel_brand_{designation}_{label}")
        
        powers_dict = get_panel_powers(load_catalog(), brand_final) if brand_final else {}
        available_powers = sorted(powers_dict.keys(), key=lambda x: float(x) if x.replace('.','').isdigit() else 0)
        
        power_idx = 0
        if default_power and str(default_power) in available_powers:
            power_idx = available_powers.index(str(default_power))
        elif available_powers and "710" in available_powers:
            power_idx = available_powers.index("710")
        
        power_selected = cols[1].selectbox("Puissance (W)", available_powers if available_powers else ["710"], index=power_idx, key=f"sel_power_{designation}_{label}")
        
        sell_price = 0.0
        buy_price = 0.0
        if brand_final and power_selected in powers_dict:
            sell_price = float(powers_dict[power_selected].get("sell_ttc", 0.0))
            buy_price = float(powers_dict[power_selected].get("buy_ttc", 0.0))
        
        brand_final = f"{brand_final} {power_selected}W"
        
    elif designation == "Batterie":
        # Batterie: Marque + Capacité
        available_brands = get_battery_brands(load_catalog())
        default_brand_idx = 0
        if default_brand and default_brand in available_brands:
            default_brand_idx = available_brands.index(default_brand)
        elif available_brands and "Deyness" in available_brands:
            default_brand_idx = available_brands.index("Deyness")
        
        brand_final = cols[0].selectbox("Marque", available_brands, index=default_brand_idx, key=f"sel_brand_{designation}_{label}")
        
        capacities_dict = get_battery_capacities(load_catalog(), brand_final) if brand_final else {}
        available_capacities = sorted(capacities_dict.keys(), key=lambda x: float(x) if x.replace('.','').isdigit() else 0)
        
        capacity_idx = 0
        if default_power and str(default_power) in available_capacities:
            capacity_idx = available_capacities.index(str(default_power))
        elif available_capacities and "5" in available_capacities:
            capacity_idx = available_capacities.index("5")
        
        capacity_selected = cols[1].selectbox("Capacité (kWh)", available_capacities if available_capacities else ["5"], index=capacity_idx, key=f"sel_capacity_{designation}_{label}")
        
        sell_price = 0.0
        buy_price = 0.0
        if brand_final and capacity_selected in capacities_dict:
            sell_price = float(capacities_dict[capacity_selected].get("sell_ttc", 0.0))
            buy_price = float(capacities_dict[capacity_selected].get("buy_ttc", 0.0))
        
        brand_final = f"{brand_final} {capacity_selected}kWh"
    
    else:
        brand_sel_list = known_brands(catalog, designation)
        brand_sel = cols[0].selectbox("Marque", brand_sel_list, key=f"sel_{designation}_{label}")
        new_brand = cols[1].text_input("Nouvelle marque", value=(default_brand or ""), key=f"new_{designation}_{label}")
        brand_final = (new_brand.strip() or brand_sel)'''

# Remplacer
content = re.sub(old_section, new_section, content, flags=re.MULTILINE | re.DOTALL)

# Écrire le fichier
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Successfully updated Panneaux and Batterie sections!")
