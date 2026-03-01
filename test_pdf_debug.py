"""Quick debug script — run from project root: python test_pdf_debug.py"""
import sys
from pathlib import Path

# Make sure we import from the project root
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("STEP 1: Check pictures directory")
pictures_dir = Path(__file__).parent / "pictures"
print(f"  Path: {pictures_dir}")
print(f"  Exists: {pictures_dir.exists()}")
if pictures_dir.exists():
    files = list(pictures_dir.iterdir())
    print(f"  Files ({len(files)}):")
    for f in sorted(files):
        print(f"    {f.name}")

print()
print("=" * 60)
print("STEP 2: Test _find_product_image for each designation")
import pdf_generator

test_designations = [
    "Onduleur réseau",
    "Onduleur hybride",
    "Smart Meter",
    "Wifi Dongle",
    "Panneaux",
    "Batterie",
    "Structures",
    "Structures acier",
    "Structures aluminium",
    "Socles",
    "Accessoires",
    "Tableau De Protection AC/DC",
    "Installation",
    "Transport",
    "Suivi journalier, maintenance chaque 12 mois pendent 2 ans",
]

for d in test_designations:
    result = pdf_generator._find_product_image(d)
    status = "OK" if result else "MISSING"
    print(f"  [{status}] {d!r} -> {result}")

print()
print("=" * 60)
print("STEP 3: Check scenario condition logic")
scenarios = ["Les deux (Sans + Avec)", "Sans batterie", "Avec batterie", "Les deux (Sans + Avec batterie)"]
for s in scenarios:
    sans_match = s in ("Sans batterie uniquement", "Sans batterie", "Les deux (Sans + Avec)", "Les deux (Sans + Avec batterie)")
    avec_match = s in ("Avec batterie uniquement", "Avec batterie", "Les deux (Sans + Avec)", "Les deux (Sans + Avec batterie)")
    print(f"  scenario={s!r}")
    print(f"    -> SANS section triggered: {sans_match}")
    print(f"    -> AVEC section triggered: {avec_match}")

print()
print("Done.")
