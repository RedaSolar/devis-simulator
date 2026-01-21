import pathlib
from datetime import datetime


def mojiscore(s: str) -> int:
    # High-signal mojibake markers for UTF-8 decoded as cp1252/latin1
    return s.count("Ã") + s.count("Â") + s.count("â")


def try_fix_line(line: str, enc: str):
    try:
        return line.encode(enc, errors="strict").decode("utf-8", errors="strict")
    except Exception:
        return None


def fix_line(line: str) -> str:
    base = mojiscore(line)
    if base == 0:
        return line

    candidates = [line]
    for enc in ("latin1", "cp1252"):
        fixed = try_fix_line(line, enc)
        if fixed is not None:
            candidates.append(fixed)

    best = min(candidates, key=mojiscore)
    return best


p = pathlib.Path("app_old.py")
raw = p.read_bytes()
text = raw.decode("utf-8", errors="strict")
lines = text.splitlines(keepends=True)

backup = p.with_suffix(p.suffix + f".bak_mojibake_linefix_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
backup.write_bytes(raw)

before = mojiscore(text)
fixed_lines = [fix_line(ln) for ln in lines]
fixed_text = "".join(fixed_lines)
after = mojiscore(fixed_text)

p.write_text(fixed_text, encoding="utf-8", newline="")
print("backup:", backup.name)
print("before score:", before)
print("after  score:", after)

# Quick sanity samples
for needle in ("GÃn", "CrÃ", "RÃs", "FÃv", "AoÃt", "DÃc"):
    if needle in fixed_text:
        print("still contains:", needle)
