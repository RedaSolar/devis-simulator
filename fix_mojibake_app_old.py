import pathlib
from datetime import datetime


def score(s: str) -> int:
    return (s.count("Ã") + s.count("Â") + s.count("â€") + s.count("â€") + s.count("â€œ") + s.count("â€"))


def try_fix(s: str, enc: str):
    try:
        return s.encode(enc, errors="strict").decode("utf-8", errors="strict")
    except Exception:
        return None


def fix_pass(s: str) -> str:
    if score(s) == 0:
        return s
    candidates = [s]
    for enc in ("latin1", "cp1252"):
        fixed = try_fix(s, enc)
        if fixed is not None:
            candidates.append(fixed)
    return min(candidates, key=score)


p = pathlib.Path("app_old.py")
raw = p.read_bytes()
text = raw.decode("utf-8", errors="strict")

backup = p.with_suffix(p.suffix + f".bak_mojibake_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
backup.write_bytes(raw)

before = score(text)
fixed = fix_pass(text)
fixed2 = fix_pass(fixed)
if score(fixed2) < score(fixed):
    fixed = fixed2

after = score(fixed)

p.write_text(fixed, encoding="utf-8", newline="")
print("backup:", backup.name)
print("before score:", before)
print("after  score:", after)
