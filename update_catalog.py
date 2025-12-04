import json

# Load the current catalog
with open('brand_catalog.json', 'r', encoding='utf-8') as f:
    catalog = json.load(f)

# Update Onduleur Injection with phase variants for 10kW
if "Onduleur Injection" in catalog and "Huawei" in catalog["Onduleur Injection"]:
    huawei = catalog["Onduleur Injection"]["Huawei"]
    # Replace "10" with "10_Monophase" and "10_Triphase"
    if "10" in huawei:
        old_10 = huawei.pop("10")
        huawei["10_Monophase"] = old_10
        huawei["10_Triphase"] = {
            "phase": "Triphase",
            "sell_ttc": 16500.0,
            "buy_ttc": 12500.0
        }

# Restructure Panneaux
catalog["Panneaux"] = {
    "__default__": {
        "sell_ttc": 1100.0,
        "buy_ttc": 900.0
    },
    "Canadien Solar": {
        "710": {
            "sell_ttc": 1100.0,
            "buy_ttc": 900.0
        },
        "630": {
            "sell_ttc": 950.0,
            "buy_ttc": 750.0
        }
    },
    "Jinko": {
        "620": {
            "sell_ttc": 900.0,
            "buy_ttc": 840.0
        },
        "590": {
            "sell_ttc": 850.0,
            "buy_ttc": 680.0
        }
    }
}

# Restructure Batterie
catalog["Batterie"] = {
    "__default__": {
        "sell_ttc": 16000.0,
        "buy_ttc": 12000.0
    },
    "Deyness": {
        "10": {
            "sell_ttc": 30000.0,
            "buy_ttc": 22000.0
        },
        "5": {
            "sell_ttc": 16000.0,
            "buy_ttc": 12000.0
        }
    },
    "Lithium": {
        "5": {
            "sell_ttc": 15500.0,
            "buy_ttc": 13200.0
        }
    },
    "Gel": {
        "2.2": {
            "sell_ttc": 5000.0,
            "buy_ttc": 3100.0
        }
    }
}

# Save the updated catalog
with open('brand_catalog.json', 'w', encoding='utf-8') as f:
    json.dump(catalog, f, indent=2, ensure_ascii=False)

print("Catalog updated successfully!")
