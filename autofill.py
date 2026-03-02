import math
import re

import pandas as pd

from catalog import (
    load_catalog,
    get_prices,
    _catalog_key_for_designation,
)


# ---------- AUTO-CHOIX ONDULEUR & STRUCTURES & PANNEAUX ----------
def get_onduleur_powers_and_phases(catalog, onduleur_type: str, brand: str):
    """
    Récupère les puissances et phases disponibles pour une marque d'onduleur.
    Retourne : dict {power_str: phase_str, ...} ex: {"5": "Monophase", "10": "Monophase", "15": "Triphase"}
    """
    result = {}
    if onduleur_type in catalog and brand in catalog[onduleur_type]:
        brand_dict = catalog[onduleur_type][brand]
        for power_str, power_info in brand_dict.items():
            phases = []
            if isinstance(power_info, dict):
                # New format: variants per power
                if "variants" in power_info and isinstance(power_info["variants"], dict):
                    phases = list(power_info["variants"].keys())
                elif "phase" in power_info:
                    phases = [power_info.get("phase", "Monophase")]
            if not phases:
                phases = ["Monophase"]
            result[power_str] = phases
    return result


def get_onduleur_brands(catalog, onduleur_type: str):
    """Retourne liste des marques disponibles pour un type d'onduleur."""
    result = []
    if onduleur_type in catalog:
        for brand in catalog[onduleur_type].keys():
            if brand != "__default__":
                result.append(brand)
    return sorted(result)


def parse_kw_from_brand(name: str):
    if not name:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(k[wW]|kva|KVA)?", name)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except Exception:
        return None


def select_inverter_for_power(catalog, onduleur_type: str, puissance_kwp: float):
    """
    Sélectionne un onduleur basé sur le type (Injection ou Hybride) et la puissance.
    Retourne le plus petit onduleur avec puissance >= puissance_kwp.
    onduleur_type: "Onduleur Injection" ou "Onduleur Hybride"
    Retourne: {marque, power, phase, sell, buy} ou None
    """
    ond_dict = catalog.get(onduleur_type, {})
    candidates = []

    for marque, powers_dict in ond_dict.items():
        if marque == "__default__" or not isinstance(powers_dict, dict):
            continue

        # Itérer sur les puissances disponibles pour cette marque
        for power_str, power_info in powers_dict.items():
            if isinstance(power_info, dict):
                # Parse numeric kW from power_str like '10', '10_Monophase' or '10 kW'
                power_kw = parse_kw_from_brand(power_str)
                phase = power_info.get("phase", "Monophase")
                sell = power_info.get("sell_ttc")
                buy = power_info.get("buy_ttc")
                if power_kw is None:
                    # try to fallback to numeric conversion of keys directly
                    m = re.search(r"(\d+(?:[.,]\d+)?)", str(power_str))
                    if m:
                        try:
                            power_kw = float(m.group(1).replace(",", "."))
                        except Exception:
                            power_kw = None

                # If this power key contains multiple variants, iterate them
                if isinstance(power_info, dict) and "variants" in power_info and isinstance(power_info["variants"], dict):
                    for vphase, vinfo in power_info["variants"].items():
                        vsell = vinfo.get("sell_ttc")
                        vbuy = vinfo.get("buy_ttc")
                        if power_kw is None:
                            # try to extract numeric from power_str
                            m = re.search(r"(\d+(?:[.,]\d+)?)", str(power_str))
                            if m:
                                try:
                                    power_kw = float(m.group(1).replace(",", "."))
                                except Exception:
                                    power_kw = None
                        if power_kw is not None and vsell is not None:
                            candidates.append((power_kw, marque, power_str, vphase, vsell, vbuy))
                else:
                    if power_kw is not None and sell is not None:
                        candidates.append((power_kw, marque, power_str, phase, sell, buy))

    if not candidates:
        return None

    def _best_from(collection):
        return min(collection, key=lambda x: x[0])

    if puissance_kwp > 0:
        min_threshold = max(puissance_kwp * 0.8, 0.0)
        valid = [c for c in candidates if c[0] >= min_threshold]
        best = _best_from(valid) if valid else max(candidates, key=lambda x: x[0])
    else:
        best = _best_from(candidates)

    power_kw, marque, power_str, phase, sell, buy = best
    return {
        "marque": marque,
        "power": power_kw,
        "power_str": power_str,
        "phase": phase,
        "sell": sell,
        "buy": buy,
    }


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


def select_jinko_710(catalog):
    """Cherche un panneau Jinko 710 dans le catalog['Panneaux']."""
    pan_dict = catalog.get("Panneaux", {})
    candidates = []
    for marque, vals in pan_dict.items():
        if marque == "__default__":
            continue
        if "jinko" in marque.lower() and "710" in marque:
            candidates.append((marque, vals.get("sell_ttc"), vals.get("buy_ttc")))
    if not candidates:
        # fallback : premier Jinko tout court
        for marque, vals in pan_dict.items():
            if marque == "__default__":
                continue
            if "jinko" in marque.lower():
                candidates.append((marque, vals.get("sell_ttc"), vals.get("buy_ttc")))
    if not candidates:
        return None
    return {
        "marque": candidates[0][0],
        "sell": candidates[0][1],
        "buy": candidates[0][2],
    }


def auto_fill_from_power(df_common: pd.DataFrame, catalog, puissance_kwp: float, puissance_panneau_w: int):
    import streamlit as st

    df = df_common.copy()

    # Nb panneaux (toujours Jinko 710)
    if puissance_kwp > 0 and puissance_panneau_w > 0:
        ratio = puissance_kwp * 1000.0 / puissance_panneau_w
        nb_panneaux = max(1, int(round(ratio)))
    else:
        nb_panneaux = 0

    # Panneaux
    mask_pan = df["Désignation"] == "Panneaux"
    if mask_pan.any():
        idx = mask_pan.idxmax()
        if nb_panneaux > 0:
            df.at[idx, "Quantité"] = nb_panneaux
        # Prefer 'Canadian Solar' 710W if available, otherwise pick first brand/power
        pan_dict = catalog.get("Panneaux", {})
        sel_brand = None
        sel_power = None
        sell_price = None
        buy_price = None
        if pan_dict:
            if "Canadian Solar" in pan_dict and "710" in pan_dict["Canadian Solar"]:
                sel_brand = "Canadian Solar"
                sel_power = "710"
                sell_price = pan_dict[sel_brand][sel_power].get("sell_ttc")
                buy_price = pan_dict[sel_brand][sel_power].get("buy_ttc")
            else:
                # fallback: first brand and its first power
                for b, powers in pan_dict.items():
                    if b == "__default__":
                        continue
                    sel_brand = b
                    # pick first numeric power key
                    for p in powers.keys():
                        if p == "__default__":
                            continue
                        sel_power = p
                        sell_price = powers[p].get("sell_ttc")
                        buy_price = powers[p].get("buy_ttc")
                        break
                    break

        if sel_brand:
            # store brand and power separately so widgets can preselect them
            df.at[idx, "Marque"] = sel_brand
            df.at[idx, "Power"] = sel_power
            if df.at[idx, "Prix Unit. TTC"] == 0 and sell_price is not None:
                df.at[idx, "Prix Unit. TTC"] = sell_price
            if df.at[idx, "Prix Achat TTC"] == 0 and buy_price is not None:
                df.at[idx, "Prix Achat TTC"] = buy_price
            # also keep in session_state for immediate widget defaults
            st.session_state["pan_brand"] = sel_brand
            st.session_state["pan_power"] = float(sel_power) if sel_power is not None else None

        # Socles en béton : 2 par panneau
        mask_socles = df["Désignation"] == "Socles"
        if mask_socles.any():
            idx_soc = mask_socles.idxmax()
            if nb_panneaux > 0:
                df.at[idx_soc, "Quantité"] = int(nb_panneaux * 2)

    # Structures : acier <30kW, alu >=30kW (1 structure par panneau)
    mask_struct_acier = df["Désignation"] == "Structures acier"
    mask_struct_aluminium = df["Désignation"] == "Structures aluminium"
    if nb_panneaux > 0:
        if puissance_kwp < 30:
            # utiliser acier
            if mask_struct_acier.any():
                idx = mask_struct_acier.idxmax()
                df.at[idx, "Quantité"] = nb_panneaux
                df.at[idx, "CustomLabel"] = "Structures en acier galvanisé"
            if mask_struct_aluminium.any():
                idx2 = mask_struct_aluminium.idxmax()
                df.at[idx2, "Quantité"] = 0
        else:
            # utiliser aluminium
            if mask_struct_aluminium.any():
                idx = mask_struct_aluminium.idxmax()
                df.at[idx, "Quantité"] = nb_panneaux
                df.at[idx, "CustomLabel"] = "Structures en aluminium"
            if mask_struct_acier.any():
                idx2 = mask_struct_acier.idxmax()
                df.at[idx2, "Quantité"] = 0

    # Onduleur réseau (Injection) → Sélectionner par puissance
    mask_ondu_res = df["Désignation"] == "Onduleur réseau"
    info_hw = None
    if mask_ondu_res.any():
        idx = mask_ondu_res.idxmax()
        info_hw = select_inverter_for_power(catalog, "Onduleur Injection", puissance_kwp)
        if info_hw:
            # Store brand, power, and phase in session state for widget to retrieve
            st.session_state["ondu_res_brand"] = info_hw["marque"]
            st.session_state["ondu_res_power"] = info_hw["power"]
            st.session_state["ondu_res_phase"] = info_hw["phase"]

            df.at[idx, "Marque"] = info_hw["marque"]
            # Compute number of inverters needed
            min_threshold = max(puissance_kwp * 0.8, 0.0)
            if info_hw.get("power") and info_hw["power"] > 0:
                if info_hw["power"] >= min_threshold:
                    nb_ondu = 1
                else:
                    ratio = puissance_kwp / float(info_hw["power"])
                    nb_ondu = int(math.ceil(ratio)) if puissance_kwp > 0 else 1
            else:
                nb_ondu = 1
            df.at[idx, "Quantité"] = max(0, nb_ondu)
            if df.at[idx, "Prix Unit. TTC"] == 0 and info_hw["sell"] is not None:
                df.at[idx, "Prix Unit. TTC"] = info_hw["sell"]
            if df.at[idx, "Prix Achat TTC"] == 0 and info_hw["buy"] is not None:
                df.at[idx, "Prix Achat TTC"] = info_hw["buy"]

    # Onduleur hybride → Sélectionner par puissance
    mask_ondu_hyb = df["Désignation"] == "Onduleur hybride"
    if mask_ondu_hyb.any():
        idx = mask_ondu_hyb.idxmax()
        info_deye = select_inverter_for_power(catalog, "Onduleur Hybride", puissance_kwp)
        if info_deye:
            # Store brand, power, and phase in session state for widget to retrieve
            st.session_state["ondu_hyb_brand"] = info_deye["marque"]
            st.session_state["ondu_hyb_power"] = info_deye["power"]
            st.session_state["ondu_hyb_phase"] = info_deye["phase"]

            df.at[idx, "Marque"] = info_deye["marque"]
            # Compute number of hybrid inverters needed
            min_threshold = max(puissance_kwp * 0.8, 0.0)
            if info_deye.get("power") and info_deye["power"] > 0:
                if info_deye["power"] >= min_threshold:
                    nb_ondu_h = 1
                else:
                    ratio = puissance_kwp / float(info_deye["power"])
                    nb_ondu_h = int(math.ceil(ratio)) if puissance_kwp > 0 else 1
            else:
                nb_ondu_h = 1
            if puissance_kwp > 0:
                nb_ondu_h = max(1, nb_ondu_h)
            df.at[idx, "Quantité"] = max(0, nb_ondu_h)
            if df.at[idx, "Prix Unit. TTC"] == 0 and info_deye["sell"] is not None:
                df.at[idx, "Prix Unit. TTC"] = info_deye["sell"]
            if df.at[idx, "Prix Achat TTC"] == 0 and info_deye["buy"] is not None:
                df.at[idx, "Prix Achat TTC"] = info_deye["buy"]

        if puissance_kwp > 0 and df.at[idx, "Quantité"] <= 0:
            # fallback to at least one hybrid inverter so the UI reflects a real system
            df.at[idx, "Quantité"] = 1

    # Pour TOUS les items, chercher les prix dans le catalogue si pas déjà remplis
    for idx, row in df.iterrows():
        des = row.get("Désignation")
        if not isinstance(des, str):
            continue
        # Si Prix Unit. TTC est à 0 ou vide, chercher dans le catalogue
        if row.get("Prix Unit. TTC") == 0 or pd.isna(row.get("Prix Unit. TTC")):
            sell_price, buy_price = get_prices(catalog, des, row.get("Marque", ""))
            if sell_price is not None:
                df.at[idx, "Prix Unit. TTC"] = sell_price
            if buy_price is not None and (row.get("Prix Achat TTC") == 0 or pd.isna(row.get("Prix Achat TTC"))):
                df.at[idx, "Prix Achat TTC"] = buy_price

    # Si Huawei utilisé → Smart Meter + Wifi Dongle auto (quantité 1 + prix du catalog si dispo)
    if info_hw is not None:
        for des in ["Smart Meter", "Wifi Dongle"]:
            mask = df["Désignation"] == des
            if mask.any():
                idx = mask.idxmax()
                if df.at[idx, "Quantité"] == 0:
                    df.at[idx, "Quantité"] = 1
                sell, buy = get_prices(catalog, des, "")
                if df.at[idx, "Prix Unit. TTC"] == 0 and sell is not None:
                    df.at[idx, "Prix Unit. TTC"] = sell
                if df.at[idx, "Prix Achat TTC"] == 0 and buy is not None:
                    df.at[idx, "Prix Achat TTC"] = buy

    # Accessoires, Tableau De Protection, Installation — prix basés sur la puissance
    # Arrondir la puissance au multiple de 5 kWc le plus proche (min 1 bloc de 5 kWc)
    _nb_blocks = max(1, round(puissance_kwp / 5))
    _power_prices = {
        "Accessoires":                    _nb_blocks * 1000,
        "Tableau De Protection AC/DC":    _nb_blocks * 1500,
        "Installation":                   (_nb_blocks + 1) * 2400,
    }
    for _des, _prix in _power_prices.items():
        _mask = df["Désignation"] == _des
        if _mask.any():
            _idx = _mask.idxmax()
            df.at[_idx, "Prix Unit. TTC"] = _prix

    # Batterie : ligne 1 = Deyness 5kWh (qté 1), ligne 2 = Deyness 10kWh (qté 1)
    mask_bat = df["Désignation"] == "Batterie"
    if mask_bat.any():
        bat_indices = df[mask_bat].index.tolist()
        idx_bat_primary = bat_indices[0] if bat_indices else None
        idx_bat_secondary = bat_indices[1] if len(bat_indices) > 1 else None

        # Chercher Deyness 5kWh et 10kWh dans le catalogue
        bat_dict = catalog.get("Batterie", {})
        dey_5_info = None
        dey_10_info = None
        for marque, vals in bat_dict.items():
            if marque == "__default__":
                continue
            if "deyness" in marque.lower():
                if "10" in marque and not dey_10_info:
                    dey_10_info = (marque, vals.get("sell_ttc"), vals.get("buy_ttc"))
                elif "5" in marque and not dey_5_info:
                    dey_5_info = (marque, vals.get("sell_ttc"), vals.get("buy_ttc"))

        # Compute target battery kWh: round PV power to nearest 5 kWh, minimum 5 kWh
        # e.g. 5.68 kWc → 5 kWh, 14 kWc → 15 kWh (1×10 + 1×5)
        _target_kwh = max(5, round(puissance_kwp / 5) * 5)
        _nb_10 = _target_kwh // 10
        _nb_5  = 1 if (_target_kwh % 10) >= 5 else 0

        # Ligne 1 : Batterie 5kWh
        if idx_bat_primary is not None and dey_5_info:
            df.at[idx_bat_primary, "Marque"] = dey_5_info[0]
            df.at[idx_bat_primary, "Quantité"] = _nb_5
            if dey_5_info[1] is not None:
                df.at[idx_bat_primary, "Prix Unit. TTC"] = dey_5_info[1]
            if dey_5_info[2] is not None:
                df.at[idx_bat_primary, "Prix Achat TTC"] = dey_5_info[2]

        # Ligne 2 : Batterie 10kWh
        if idx_bat_secondary is not None and dey_10_info:
            df.at[idx_bat_secondary, "Marque"] = dey_10_info[0]
            df.at[idx_bat_secondary, "Quantité"] = _nb_10
            if dey_10_info[1] is not None:
                df.at[idx_bat_secondary, "Prix Unit. TTC"] = dey_10_info[1]
            if dey_10_info[2] is not None:
                df.at[idx_bat_secondary, "Prix Achat TTC"] = dey_10_info[2]

    return df


# ---------- AUTO-CALCUL ROI & ÉCONOMIES ----------
def calculate_savings_roi(puissance_kwc: float, total_sans: float, total_avec: float) -> dict:
    """
    Auto-calcule la production annuelle, les économies et le ROI depuis la puissance
    et les totaux de chaque option.  À appeler depuis le simulateur pour pré-remplir
    les champs ROI dès que l'utilisateur saisit la puissance et que les prix sont connus.

    Formules :
      production_annuelle   = kwc × 1240 kWh/kWc/an  (GHI moyen Maroc)
      economie_opt1 (sans)  = production × 60 % autoconso × 1,20 MAD/kWh
      economie_opt2 (avec)  = production × 85 % autoconso × 1,20 MAD/kWh  (batterie)
      roi                   = total_option / economie_annuelle
      monthly               = economie_annuelle × facteur_saisonnier

    Retourne un dict directement utilisable pour remplir QUOTE_INPUT ou les champs du simulateur.
    """
    production_annuelle = round(puissance_kwc * 1240)

    # Taux d'autoconsommation × prix kWh ONEE de référence
    economie_opt1 = round(production_annuelle * 0.60 * 1.20)
    economie_opt2 = round(production_annuelle * 0.85 * 1.20)

    # Retour sur investissement (années)
    roi_opt1 = round(total_sans  / economie_opt1, 1) if economie_opt1 > 0 else 0.0
    roi_opt2 = round(total_avec  / economie_opt2, 1) if economie_opt2 > 0 else 0.0

    # Répartition mensuelle saisonnière (12 facteurs, somme = 1,000)
    _SF = [0.053, 0.062, 0.083, 0.098, 0.114, 0.116,
           0.116, 0.101, 0.087, 0.070, 0.052, 0.048]
    eco_s_monthly = [round(economie_opt1 * f) for f in _SF]
    eco_a_monthly = [round(economie_opt2 * f) for f in _SF]

    return {
        "prod_kwh":      production_annuelle,
        "eco_s_ann":     economie_opt1,
        "eco_a_ann":     economie_opt2,
        "eco_a_cumul":   economie_opt2,   # même taux utilisé pour la courbe ROI
        "roi_s":         roi_opt1,
        "roi_a":         roi_opt2,
        "eco_s_monthly": eco_s_monthly,
        "eco_a_monthly": eco_a_monthly,
    }
