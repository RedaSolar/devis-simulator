import pathlib
import re
import unicodedata
from datetime import datetime


def norm_col(name: str) -> str:
    name = str(name)
    name = name.strip()
    name = re.sub(r"\s+", " ", name)
    # remove accents
    name = "".join(
        ch for ch in unicodedata.normalize("NFKD", name)
        if not unicodedata.combining(ch)
    )
    return name.casefold()


def ensure_column(df, target: str) -> None:
    if target in df.columns:
        return
    want = norm_col(target)
    # First pass: exact normalized match
    for col in df.columns:
        if norm_col(col) == want:
            df.rename(columns={col: target}, inplace=True)
            return
    # Second pass: tolerate common separators
    for col in df.columns:
        if norm_col(col).replace(" ", "") == want.replace(" ", ""):
            df.rename(columns={col: target}, inplace=True)
            return
    raise KeyError(f"Missing required column {target!r}. Columns: {list(df.columns)!r}")


p = pathlib.Path('app_old.py')
raw = p.read_bytes()
text = raw.decode('utf-8', errors='strict')
lines = text.splitlines(keepends=True)

# Backup
backup = p.with_suffix(p.suffix + f".bak_sanitize_df_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
backup.write_bytes(raw)

# Insert helper functions just above sanitize_df, if not already present
needle = "def sanitize_df(df):\n"
idx = None
for i, ln in enumerate(lines):
    if ln == needle:
        idx = i
        break
if idx is None:
    raise SystemExit('Could not find sanitize_df')

helpers_marker = "def _ensure_required_df_columns(df):\n"
if helpers_marker not in text:
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
        "            # try ignoring spaces/punctuation\n"
        "            want2 = re.sub(r\"[^a-z0-9]+\", \"\", want)\n"
        "            src = next((c for c in df.columns if re.sub(r\"[^a-z0-9]+\", \"\", _normalize_colname(c)) == want2), None)\n"
        "        if src is not None:\n"
        "            df.rename(columns={src: target}, inplace=True)\n"
        "        else:\n"
        "            raise KeyError(f\"Missing required column {target!r}. Columns: {list(df.columns)!r}\")\n\n\n"
    )
    # We need imports re/unicodedata already exist? 're' exists above; unicodedata might not.
    # We'll insert a safe import near existing imports if missing.

    # Ensure unicodedata imported somewhere near top: if not, insert after first 'import re'
    if 'import unicodedata' not in text:
        for j, ln in enumerate(lines[:300]):
            if ln.startswith('import re'):
                lines.insert(j+1, 'import unicodedata\n')
                idx += 1
                break

    lines.insert(idx, helper_block)

# Now patch sanitize_df to call _ensure_required_df_columns at start
# Find the line 'df = df.copy()' after sanitize_df and insert call after it if not present
for i in range(idx, min(idx+50, len(lines))):
    if lines[i].strip() == 'df = df.copy()':
        # check next few lines
        window = ''.join(lines[i:i+5])
        if '_ensure_required_df_columns' not in window:
            lines.insert(i+1, '    _ensure_required_df_columns(df)\n')
        break

p.write_text(''.join(lines), encoding='utf-8', newline='')
print('backup:', backup.name)
print('patched sanitize_df')
