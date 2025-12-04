import json, re
p = r"c:\Users\kasri\OneDrive - Atlencia\Solar Panels\Simulator\brand_catalog.json"
with open(p, 'r', encoding='utf-8') as f:
    catalog = json.load(f)

def normalize(catalog):
    changed = False
    for on_key in ("Onduleur Injection", "Onduleur Hybride"):
        if on_key not in catalog:
            continue
        for brand, brand_dict in list(catalog[on_key].items()):
            if brand == "__default__" or not isinstance(brand_dict, dict):
                continue
            temp = {}
            for power_key, info in brand_dict.items():
                power_key = str(power_key)
                m = re.match(r"^(\d+(?:[.,]\d+)?)(?:[_\s-]?(Monophase|Triphase))?$,", power_key, re.IGNORECASE)
                # Note: the regex above mistakenly has an extra comma; fix below with safe approach
                m = re.match(r"^(\d+(?:[.,]\d+)?)(?:[_\s-]?(Monophase|Triphase))?", power_key, re.IGNORECASE)
                if m and m.group(2):
                    num = m.group(1).replace(',', '.')
                    phase = m.group(2).capitalize()
                    temp.setdefault(num, {}).setdefault('variants', {})[phase] = info
                else:
                    if isinstance(info, dict) and 'phase' in info:
                        m2 = re.search(r"(\d+(?:[.,]\d+)?)", power_key)
                        num = m2.group(1).replace(',', '.') if m2 else power_key
                        phase = info.get('phase', 'Monophase')
                        temp.setdefault(str(num), {}).setdefault('variants', {})[phase] = info
                    else:
                        temp.setdefault(power_key, info)
            new_brand_dict = {k: v for k, v in temp.items()}
            if new_brand_dict != brand_dict:
                catalog[on_key][brand] = new_brand_dict
                changed = True
    return changed

changed = normalize(catalog)
if changed:
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
print('Catalog normalized:', changed)
