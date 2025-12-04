import re

# Read the app.py file
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# New functions to add
new_functions = '''
def get_panel_brands(catalog):
    """Retourne liste des marques disponibles pour panneaux."""
    result = []
    if "Panneaux" in catalog:
        for brand in catalog["Panneaux"].keys():
            if brand != "__default__":
                result.append(brand)
    return sorted(result)

def get_panel_powers(catalog, brand: str):
    """Retourne dict {power_str: {sell_ttc, buy_ttc}} pour une marque de panneau."""
    result = {}
    if "Panneaux" in catalog and brand in catalog["Panneaux"]:
        brand_dict = catalog["Panneaux"][brand]
        for power_str, power_info in brand_dict.items():
            if isinstance(power_info, dict):
                result[power_str] = power_info
    return result

def get_battery_brands(catalog):
    """Retourne liste des marques disponibles pour batteries."""
    result = []
    if "Batterie" in catalog:
        for brand in catalog["Batterie"].keys():
            if brand != "__default__":
                result.append(brand)
    return sorted(result)

def get_battery_capacities(catalog, brand: str):
    """Retourne dict {capacity_str: {sell_ttc, buy_ttc}} pour une marque de batterie."""
    result = {}
    if "Batterie" in catalog and brand in catalog["Batterie"]:
        brand_dict = catalog["Batterie"][brand]
        for capacity_str, capacity_info in brand_dict.items():
            if isinstance(capacity_info, dict):
                result[capacity_str] = capacity_info
    return result
'''

# Find the position to insert (before select_jinko_710)
pattern = r'(\n)def select_jinko_710\('
match = re.search(pattern, content)
if match:
    insert_pos = match.start() + 1  # Start of the line
    content = content[:insert_pos] + new_functions + content[insert_pos:]
    
    # Write back
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("New functions added successfully!")
else:
    print("Could not find insertion point")
