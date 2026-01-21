import pathlib
from datetime import datetime

replacements = {
    "CÃblage": "Câblage",
    "cÃblage": "câblage",
    "TÃlÃcharger": "Télécharger",
    "â¬ï": "",
}

p = pathlib.Path("app_old.py")
raw = p.read_bytes()
text = raw.decode("utf-8", errors="strict")
backup = p.with_suffix(p.suffix + f".bak_manualfix_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
backup.write_bytes(raw)

for old, new in replacements.items():
    text = text.replace(old, new)

p.write_text(text, encoding="utf-8", newline="")
print("backup:", backup.name)
print("Ã count after:", text.count('Ã'))
