# -*- coding: utf-8 -*-
from pathlib import Path
p=Path('app.py')
text=p.read_text(errors='ignore')
alt=['    # Production PV mensuelle recalcul\uff23 avec la puissance effective','    # Production PV mensuelle recalculé avec la puissance effective','    # Production PV mensuelle recalculＦ avec la puissance effective']
found=None
for n in alt:
    if n in text:
        found=n
        break
if not found:
    raise SystemExit('needle not found')
insert = "    # Si une valeur manuelle a été rafraîchie, on l'utilise en priorité\n    if \"last_kwp_from_df_common\" in st.session_state:\n        puissance_kwp_effective = st.session_state[\"last_kwp_from_df_common\"]\n\n" + found
p.write_text(text.replace(found, insert, 1), encoding='utf-8')
