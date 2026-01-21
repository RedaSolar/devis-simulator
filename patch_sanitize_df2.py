import pathlib
import re
from datetime import datetime

p = pathlib.Path("app_old.py")
raw = p.read_bytes()
text = raw.decode("utf-8", errors="strict")
lines = text.splitlines(keepends=True)

# Backup
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = p.with_suffix(p.suffix + f".bak_sanitize_df_fix_{ts}")
backup.write_bytes(raw)

# Find sanitize_df line index robustly
idx = None
for i, ln in enumerate(lines):
    if ln.strip() == "def sanitize_df(df):":
        idx = i
        break
if idx is None:
    raise SystemExit("Could not locate def sanitize_df(df):")

# Ensure unicodedata import exists (needed by helper)
if "import unicodedata" not in text:
    inserted = False
    for i, ln in enumerate(lines[:400]):
        if ln.startswith("import re") or ln.startswith("from re"):
            lines.insert(i + 1, "import unicodedata\n")
            inserted = True
            if i + 1 <= idx:
                idx += 1
            break
    if not inserted:
        # Fallback: insert near the top after other imports
        for i, ln in enumerate(lines[:400]):
            if ln.startswith("import ") or ln.startswith("from "):
                continue
            lines.insert(i, "import unicodedata\n")
            if i <= idx:
                idx += 1
            break

# Insert helper block once
if "def _ensure_required_df_columns(df):" not in text:
    helper_block = (
        "def _normalize_colname(name: str) -> str:\n"
        "    name = str(name).strip()\n"
        "    name = re.sub(r\"\\s+\", \" \", name)\n"
        "    name = ''.join(ch for ch in unicodedata.normalize('NFKD', name) if not unicodedata.combining(ch))\n"
        "    return name.casefold()\n\n\n"
        "def _ensure_required_df_columns(df):\n"
        "    # Accept common variants like 'Designation' vs 'Désignation'\n"
        "    required = ['Désignation', 'Marque', 'Quantité', 'Prix Achat TTC', 'Prix Unit. TTC', 'TVA (%)']\n"
        "    norm_map = { _normalize_colname(c): c for c in df.columns }\n"
        "    for target in required:\n"
        "        if target in df.columns:\n"
        "            continue\n"
        "        want = _normalize_colname(target)\n"
        "        src = norm_map.get(want)\n"
        "        if src is None:\n"
        "            want2 = re.sub(r\"[^a-z0-9]+\", \"\", want)\n"
        "            for c in df.columns:\n"
        "                if re.sub(r\"[^a-z0-9]+\", \"\", _normalize_colname(c)) == want2:\n"
        "                    src = c\n"
        "                    break\n"
        "        if src is not None:\n"
        "            df.rename(columns={src: target}, inplace=True)\n"
        "        else:\n"
        "            raise KeyError(f\"Missing required column {target!r}. Columns: {list(df.columns)!r}\")\n\n\n"
    )
    # Insert helper immediately before sanitize_df
    lines.insert(idx, helper_block)
    idx += 1

# Ensure sanitize_df calls helper right after df = df.copy()
# Find df = df.copy() within next ~10 lines
for j in range(idx, min(idx + 20, len(lines))):
    if lines[j].strip() == "df = df.copy()":
        # If next lines don't already call it, insert
        lookahead = "".join(lines[j:j+6])
        if "_ensure_required_df_columns(df)" not in lookahead:
            lines.insert(j + 1, "    _ensure_required_df_columns(df)\n")
        break

new_text = "".join(lines)
# Preserve existing newline style by writing exactly what we built
p.write_text(new_text, encoding="utf-8", newline="")
print("backup:", backup.name)
print("patched sanitize_df")
