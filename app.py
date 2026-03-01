import json
import re
import shutil
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st

# ---------- MODULE IMPORTS ----------
from constants import (
    BLUE_MAIN, BLUE_LIGHT, TEXT_DARK, ORANGE_ACCENT, GREY_NEUTRAL,
    GHI, MOIS, DAYS_IN_MONTH, EFFICIENCY, KWH_PRICE,
    CANONICALS, CANON_MAP,
)
from catalog import (
    load_catalog,
    save_catalog,
    _catalog_key_for_designation,
    set_prices,
    get_prices,
    known_brands,
    load_custom_templates,
    save_custom_templates,
)
from utils import (
    _num,
    sanitize_df,
    learn_from_df,
    get_first_existing_image,
    get_dynamic_image,
)
from roi import (
    taqinor_graph_style,
    interpoler_factures,
    build_roi_figure,
    roi_figure_buffer,
    find_break_even_year,
    build_roi_cumulative_figure,
    roi_cumulative_buffer,
    create_monthly_savings_chart,
    create_monthly_production_chart,
    create_cumulative_savings_chart,
)
from autofill import (
    get_onduleur_powers_and_phases,
    get_onduleur_brands,
    parse_kw_from_brand,
    select_inverter_for_power,
    get_panel_brands,
    get_panel_powers,
    get_battery_brands,
    get_battery_capacities,
    select_jinko_710,
    auto_fill_from_power,
)
import pdf_generator as _pdf_gen
from pdf_generator import (
    build_devis_section_elements,
    generate_double_devis_pdf,
    generate_single_pdf,
)

# ---------- DOSSIERS ----------
BASE_DIR = Path(".")
CONFIG_FILE = BASE_DIR / "config.json"
DEVIS_HISTORY_FILE = BASE_DIR / "devis_history.json"
LOGO_PATH = BASE_DIR / "logo.png"
CATALOG_FILE = BASE_DIR / "brand_catalog.json"
CUSTOM_LINES_FILE = BASE_DIR / "custom_line_templates.json"

DEVIS_DIR = BASE_DIR / "devis_client"
FACTURES_DIR = BASE_DIR / "factures_client"
PICTURES_DIR = BASE_DIR / "pictures"

for d in [DEVIS_DIR, FACTURES_DIR, PICTURES_DIR]:
    d.mkdir(exist_ok=True)


def img_candidates(name_base: str):
    return [
        PICTURES_DIR / f"{name_base}.png",
        PICTURES_DIR / f"{name_base}.jpg",
        PICTURES_DIR / f"{name_base}.jpeg",
    ]


IMAGE_FILES = {
    "Onduleur réseau": img_candidates("onduler") + img_candidates("onduleur"),
    "Onduleur hybride": img_candidates("onduler") + img_candidates("onduleur"),
    "Smart Meter": img_candidates("smart_meter"),
    "Wifi Dongle": img_candidates("wifi_dongle"),
    "Panneaux": img_candidates("panneaux"),
    "Batterie": img_candidates("batterie"),
    "Structures": img_candidates("structures"),
    "Socles": img_candidates("socles"),
    "Accessoires": img_candidates("accessoires"),
    "Tableau De Protection AC/DC": img_candidates("tableau_protection"),
    "Installation": img_candidates("installation"),
    "Transport": img_candidates("transport"),
    "Suivi journalier, maintenance chaque 12 mois pendent 2 ans": img_candidates("suivi_maintenance"),
}

# Inject runtime state into utils and pdf_generator so they can resolve images
import utils as _utils_mod
_utils_mod.IMAGE_FILES = IMAGE_FILES
_utils_mod.PICTURES_DIR = PICTURES_DIR

# Inject paths into pdf_generator
_pdf_gen.DEVIS_DIR = DEVIS_DIR
_pdf_gen.FACTURES_DIR = FACTURES_DIR
_pdf_gen.LOGO_PATH = LOGO_PATH

# ---------- INIT CONFIG / HISTORY ----------
if CONFIG_FILE.exists():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
else:
    config = {"devis_counter": 1, "facture_counter": 1}

if DEVIS_HISTORY_FILE.exists():
    with open(DEVIS_HISTORY_FILE, "r", encoding="utf-8") as f:
        devis_history = json.load(f)
else:
    devis_history = {}

# ---------- SESSION STATE ----------
if "custom_lines_sans" not in st.session_state:
    st.session_state.custom_lines_sans = []

if "custom_lines_avec" not in st.session_state:
    st.session_state.custom_lines_avec = []

if "notes_sans" not in st.session_state:
    st.session_state.notes_sans = []

if "notes_avec" not in st.session_state:
    st.session_state.notes_avec = []

if "roi_fact_init" not in st.session_state:
    st.session_state.roi_fact_init = {m: 2000.0 for m in MOIS}

if "df_common_overrides" not in st.session_state:
    st.session_state.df_common_overrides = None

if "puissance_panneau_w" not in st.session_state:
    st.session_state["puissance_panneau_w"] = 710

# ---------- STREAMLIT UI ----------
st.title("📄 Générateur de Devis & ROI — TAQINOR")

with st.sidebar.expander("📚 Mémoire des prix"):
    st.json(load_catalog())

mode = st.radio("Action :", ["Créer un Devis (1 ou 2 scénarios)", "Transformer un Devis en Facture"])


def line_editor(designation, label, default_qty, default_tva, catalog,
                custom_label=None, default_photo_key=None,
                default_brand=None, default_sell=None, default_buy=None,
                brand_only=False, default_power=None, default_phase=None):
    st.markdown(f"##### {label}")
    sell_price = 0.0
    buy_price = 0.0

    # For onduleurs, use special 3-column layout (Marque / Puissance / Phase)
    if designation in ("Onduleur réseau", "Onduleur hybride"):
        cols_ondu = st.columns([1.2, 1.0, 1.0, 0.8, 1.0, 1.0, 0.8])
        base_key = _catalog_key_for_designation(designation)

        # If autofill previously stored preferred onduleur choices in session_state,
        # copy them into the widget keys so the selectboxes reflect the autofill.
        # Only set these values if the widget keys don't already exist to avoid
        # overwriting user edits on each rerun.
        widget_brand_key = f"sel_brand_{designation}_{label}"
        widget_power_key = f"sel_power_{designation}_{label}"
        widget_phase_key = f"sel_phase_{designation}_{label}"

        if designation == "Onduleur réseau":
            pref_brand = st.session_state.get("ondu_res_brand")
            pref_power = st.session_state.get("ondu_res_power")
            pref_phase = st.session_state.get("ondu_res_phase")
        else:
            pref_brand = st.session_state.get("ondu_hyb_brand")
            pref_power = st.session_state.get("ondu_hyb_power")
            pref_phase = st.session_state.get("ondu_hyb_phase")

        try:
            force_cnt = int(st.session_state.get("force_autofill_update_count", 0) or 0)
        except Exception:
            force_cnt = 0
        try:
            if pref_brand and (widget_brand_key not in st.session_state or force_cnt > 0):
                st.session_state[widget_brand_key] = pref_brand
        except Exception:
            pass
        try:
            if pref_power is not None and (widget_power_key not in st.session_state or force_cnt > 0):
                # selectbox displays numeric powers as e.g. '10 kW'
                try:
                    power_display = f"{float(pref_power):g} kW"
                except Exception:
                    power_display = str(pref_power)
                st.session_state[widget_power_key] = power_display
        except Exception:
            pass
        try:
            if pref_phase and (widget_phase_key not in st.session_state or force_cnt > 0):
                st.session_state[widget_phase_key] = pref_phase
        except Exception:
            pass
        # If we consumed a forced update, decrement the counter so only the
        # two onduleur editors consume it.
        try:
            if force_cnt > 0:
                st.session_state["force_autofill_update_count"] = max(0, force_cnt - 1)
        except Exception:
            pass

        # Col 0: Marque (dropdown from catalog)
        available_brands = get_onduleur_brands(load_catalog(), base_key)
        default_brand_idx = 0
        if default_brand and default_brand in available_brands:
            default_brand_idx = available_brands.index(default_brand)
        # allow pending brand change to be applied before widget instantiation
        pending_brand_key = f"{widget_brand_key}_pending"
        pending_brand = st.session_state.pop(pending_brand_key, None)
        if pending_brand:
            st.session_state[widget_brand_key] = pending_brand
        pending_power_key = f"{widget_power_key}_pending"
        pending_power = st.session_state.pop(pending_power_key, None)
        if pending_power:
            st.session_state[widget_power_key] = pending_power
        pending_phase_key = f"{widget_phase_key}_pending"
        pending_phase = st.session_state.pop(pending_phase_key, None)
        if pending_phase:
            st.session_state[widget_phase_key] = pending_phase
        brand_col = cols_ondu[0]
        brand_sel = brand_col.selectbox(
            "Marque",
            available_brands,
            index=default_brand_idx,
            key=f"sel_brand_{designation}_{label}",
        )
        brand_final = brand_sel

        # Get available powers for this brand (keys may include phase suffixes like '10_Monophase')
        catalog_load = load_catalog()
        powers_phases = get_onduleur_powers_and_phases(catalog_load, base_key, brand_final) if brand_final else {}

        # Group keys by numeric power: {num: [(key, phase), ...]}
        powers_grouped = {}
        for k, ph in powers_phases.items():
            m = re.search(r"(\d+(?:[.,]\d+)?)", str(k))
            if m:
                try:
                    num = float(m.group(1).replace(",", "."))
                except Exception:
                    num = None
            else:
                num = None
            if isinstance(ph, (list, tuple)):
                for single_ph in ph:
                    if num is None:
                        powers_grouped.setdefault(None, []).append((k, single_ph))
                    else:
                        powers_grouped.setdefault(num, []).append((k, single_ph))
            else:
                if num is None:
                    powers_grouped.setdefault(None, []).append((k, ph))
                else:
                    powers_grouped.setdefault(num, []).append((k, ph))

        # Build display list containing unique numeric powers (no duplicate per phase)
        numeric_powers = sorted([p for p in powers_grouped.keys() if p is not None])
        if not numeric_powers and None in powers_grouped:
            # fallback to any key names
            numeric_powers = [None]

        display_list = [f"{p:g} kW" if p is not None else "Autre" for p in numeric_powers]

        # Col 1: Puissance (unique numeric values)
        power_idx = 0
        if default_power is not None:
            try:
                dpf = float(default_power)
                for i, p in enumerate(numeric_powers):
                    if p is None:
                        continue
                    try:
                        if abs(p - dpf) < 1e-6:
                            power_idx = i
                            break
                    except Exception:
                        continue
            except Exception:
                pass
        power_selected_display = cols_ondu[1].selectbox(
            "Puissance (kW)",
            display_list if display_list else ["5 kW"],
            index=power_idx,
            key=f"sel_power_{designation}_{label}"
        )

        # Resolve selected numeric power
        power_num = None
        if power_selected_display != "Autre":
            m_match = re.search(r"(\d+(?:[.,]\d+)?)", power_selected_display)
            if m_match:
                try:
                    power_num = float(m_match.group(1).replace(",", "."))
                except Exception:
                    power_num = None

        # Col 2: Phase (selectable among phases available for that numeric power)
        phase_options = []
        if power_num in powers_grouped:
            phase_options = [ph for (_k, ph) in powers_grouped[power_num]]
        elif None in powers_grouped:
            phase_options = [ph for (_k, ph) in powers_grouped[None]]
        if not phase_options:
            phase_options = [default_phase or "Monophase"]

        phase_idx = 0
        if default_phase and default_phase in phase_options:
            phase_idx = phase_options.index(default_phase)
        phase_final = cols_ondu[2].selectbox("Phase", phase_options, index=phase_idx, key=f"sel_phase_{designation}_{label}")

        # Bloc d'ajout rapide d'une nouvelle marque/modèle d'onduleur (horizontal)
        add_cols = st.columns([2.5, 1.2, 1.2, 1.2, 1.2])
        new_brand_prefix = f"add_ondu_{designation}_{label}"
        with add_cols[0]:
            new_brand_name = st.text_input("Nouvelle marque", value="", key=f"{new_brand_prefix}_brand")
        with add_cols[1]:
            new_power_kw = st.number_input("Puissance (kW)", min_value=0.0, step=0.1, value=0.0, key=f"{new_brand_prefix}_power")
        with add_cols[2]:
            new_phase_val = st.selectbox("Phase", ["Monophase", "Triphase", "Autre"], key=f"{new_brand_prefix}_phase")
        with add_cols[3]:
            new_sell_val = st.number_input("Prix Unit. TTC", min_value=0.0, step=10.0, value=0.0, key=f"{new_brand_prefix}_sell")
        with add_cols[4]:
            new_buy_val = st.number_input("Prix Achat TTC", min_value=0.0, step=10.0, value=0.0, key=f"{new_brand_prefix}_buy")

        if st.button("Ajouter la marque", key=f"{new_brand_prefix}_btn"):
            if new_brand_name and new_power_kw > 0:
                phase_to_use = new_phase_val if new_phase_val != "Autre" else "Autre"
                try:
                    power_key = str(int(new_power_kw) if float(new_power_kw).is_integer() else new_power_kw)
                    set_prices(load_catalog(), designation, new_brand_name.strip(), sell_ttc=new_sell_val or None, buy_ttc=new_buy_val or None, power_key=power_key, phase=phase_to_use)
                    st.success(f"Marque {new_brand_name} {power_key} kW ({phase_to_use}) ajoutée.")
                    st.session_state[pending_brand_key] = new_brand_name.strip()
                    st.session_state[f"{widget_power_key}_pending"] = f"{float(new_power_kw):g} kW"
                    st.session_state[f"{widget_phase_key}_pending"] = phase_to_use
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Impossible d'ajouter la marque : {e}")
            else:
                st.warning("Renseignez au minimum une marque et une puissance > 0.")

        # Col 3: Quantité
        qty_key = f"qty_{designation}_{label}"
        qty_default = st.session_state.get(qty_key, int(default_qty))
        qty = cols_ondu[3].number_input(
            "Quantité",
            min_value=0,
            step=1,
            value=int(qty_default),
            key=qty_key,
        )
        # Determine lookup_key in catalog for selected numeric power + phase
        lookup_key = ""
        if brand_final and base_key in catalog_load and brand_final in catalog_load[base_key]:
            # find the catalog key for this numeric power and chosen phase
            choices = []
            if power_num in powers_grouped:
                choices = powers_grouped[power_num]
            elif None in powers_grouped:
                choices = powers_grouped[None]
            # choices: list of (key, phase)
            found = None
            for k, ph in choices:
                if ph == phase_final:
                    found = k
                    break
            if not found and choices:
                found = choices[0][0]
            lookup_key = found or ""

        sell_price = 0.0
        buy_price = 0.0
        if lookup_key and base_key in catalog_load and brand_final in catalog_load[base_key]:
            power_entry = catalog_load[base_key][brand_final].get(lookup_key, {})
            if isinstance(power_entry, dict) and "variants" in power_entry and isinstance(power_entry["variants"], dict):
                var = power_entry["variants"].get(phase_final, {})
                sell_price = float(var.get("sell_ttc", 0.0) or 0.0)
                buy_price = float(var.get("buy_ttc", 0.0) or 0.0)
            else:
                sell_price = float(power_entry.get("sell_ttc", 0.0) or 0.0)
                buy_price = float(power_entry.get("buy_ttc", 0.0) or 0.0)

        # Col 4 & 5: Prix (auto-filled from catalog, but editable)
        sell_val = cols_ondu[4].number_input(
            "Prix Unit. TTC",
            min_value=0.0,
            step=10.0,
            value=sell_price if sell_price > 0 else (default_sell or 0.0),
            key=f"sell_{designation}_{label}_{brand_final}_{lookup_key}",
        )
        buy_val = cols_ondu[5].number_input(
            "Prix Achat TTC",
            min_value=0.0,
            step=10.0,
            value=buy_price if buy_price > 0 else (default_buy or 0.0),
            key=f"buy_{designation}_{label}_{brand_final}_{lookup_key}",
        )

        # Col 6: TVA
        tva = cols_ondu[6].number_input(
            "TVA (%)",
            min_value=0,
            step=1,
            value=int(default_tva),
            key=f"tva_{designation}_{label}",
        )

        # Build display marque including numeric power if available
        power_display = f"{power_num:g}" if power_num is not None else ""
        brand_display = f"{brand_final} {power_display}kW {phase_final}".strip()

        result = {
            "Désignation": designation,
            "Marque": brand_display,
            "Quantité": qty,
            "Prix Achat TTC": buy_val,
            "Prix Unit. TTC": sell_val,
            "TVA (%)": tva,
        }
        if custom_label is not None:
            result["CustomLabel"] = custom_label
        if default_photo_key is not None:
            result["PhotoKey"] = default_photo_key

        return result

    # For non-onduleur items, use standard layout
    cols = st.columns([1.2, 1.0, 0.8, 1.0, 1.0, 0.8])
    brand_final = ""
    sell_price = 0.0
    buy_price = 0.0

    if designation == "Panneaux":
        # Panneaux: Marque + Puissance
        catalog_load = load_catalog()
        # Allow adding a new panel model from the editor
        with st.expander("Ajouter un nouveau panneau au catalogue", expanded=False):
            new_brand_pan = st.text_input("Nouvelle marque (laisser vide si non)", value="", key=f"new_brand_Panneaux_{label}")
            new_power_pan = st.number_input("Puissance (W)", min_value=1, step=10, value=710, key=f"new_power_Panneaux_{label}")
            new_sell_pan = st.number_input("Prix Unit. TTC (nouveau)", min_value=0.0, step=1.0, value=0.0, key=f"new_sell_Panneaux_{label}")
            new_buy_pan = st.number_input("Prix Achat TTC (nouveau)", min_value=0.0, step=1.0, value=0.0, key=f"new_buy_Panneaux_{label}")
            if st.button("Ajouter panneau au catalogue", key=f"btn_add_Panneaux_{label}"):
                if new_brand_pan and new_power_pan > 0:
                    try:
                        set_prices(catalog_load, "Panneaux", new_brand_pan.strip(), new_sell_pan or None, new_buy_pan or None, power_key=str(int(new_power_pan) if float(new_power_pan).is_integer() else str(new_power_pan)), phase=None)
                        st.success(f"Panneau {new_brand_pan} {new_power_pan}W ajouté au catalogue.")
                        # preselect newly added values
                        st.session_state[f"sel_brand_Panneaux_{label}"] = new_brand_pan.strip()
                        st.session_state[f"sel_power_Panneaux_{label}"] = str(int(new_power_pan) if float(new_power_pan).is_integer() else str(new_power_pan))
                    except Exception as e:
                        st.error(f"Impossible d'ajouter le panneau: {e}")
                else:
                    st.warning("Veuillez renseigner une marque et une puissance > 0.")

        available_brands = get_panel_brands(catalog_load)
        default_brand_idx = 0
        if default_brand and default_brand in available_brands:
            default_brand_idx = available_brands.index(default_brand)
        elif available_brands and "Canadian Solar" in available_brands:
            default_brand_idx = available_brands.index("Canadian Solar")

        brand_final = cols[0].selectbox("Marque", available_brands, index=default_brand_idx, key=f"sel_brand_{designation}_{label}")

        powers_dict = get_panel_powers(catalog_load, brand_final) if brand_final else {}
        available_powers = sorted(powers_dict.keys(), key=lambda x: float(x) if x.replace('.','').isdigit() else 0)

        power_idx = 0
        if default_power and str(default_power) in available_powers:
            power_idx = available_powers.index(str(default_power))
        elif available_powers and "710" in available_powers:
            power_idx = available_powers.index("710")

        power_selected = cols[1].selectbox("Puissance (W)", available_powers if available_powers else ["710"], index=power_idx, key=f"sel_power_{designation}_{label}")

        sell_price = 0.0
        buy_price = 0.0
        if brand_final and power_selected in powers_dict:
            sell_price = float(powers_dict[power_selected].get("sell_ttc", 0.0))
            buy_price = float(powers_dict[power_selected].get("buy_ttc", 0.0))

        brand_final = f"{brand_final} {power_selected}W"

    elif designation == "Batterie":
        # Batterie: Marque + Capacité
        catalog_load = load_catalog()
        # Allow adding a new battery model from the editor
        with st.expander("Ajouter une nouvelle batterie au catalogue", expanded=False):
            new_brand_bat = st.text_input("Nouvelle marque (laisser vide si non)", value="", key=f"new_brand_Batterie_{label}")
            new_capacity_bat = st.number_input("Capacité (kWh)", min_value=1.0, step=0.5, value=5.0, key=f"new_capacity_Batterie_{label}")
            new_sell_bat = st.number_input("Prix Unit. TTC (nouveau)", min_value=0.0, step=1.0, value=0.0, key=f"new_sell_Batterie_{label}")
            new_buy_bat = st.number_input("Prix Achat TTC (nouveau)", min_value=0.0, step=1.0, value=0.0, key=f"new_buy_Batterie_{label}")
            if st.button("Ajouter batterie au catalogue", key=f"btn_add_Batterie_{label}"):
                if new_brand_bat and new_capacity_bat > 0:
                    try:
                        cap_key = str(int(new_capacity_bat) if float(new_capacity_bat).is_integer() else str(new_capacity_bat))
                        set_prices(catalog_load, "Batterie", new_brand_bat.strip(), new_sell_bat or None, new_buy_bat or None, power_key=cap_key, phase=None)
                        st.success(f"Batterie {new_brand_bat} {cap_key}kWh ajoutée au catalogue.")
                        st.session_state[f"sel_brand_Batterie_{label}"] = new_brand_bat.strip()
                        st.session_state[f"sel_capacity_Batterie_{label}"] = cap_key
                    except Exception as e:
                        st.error(f"Impossible d'ajouter la batterie: {e}")
                else:
                    st.warning("Veuillez renseigner une marque et une capacité > 0.")

        available_brands = get_battery_brands(catalog_load)
        default_brand_idx = 0
        if default_brand and default_brand in available_brands:
            default_brand_idx = available_brands.index(default_brand)
        elif available_brands and "Deyness" in available_brands:
            default_brand_idx = available_brands.index("Deyness")

        brand_final = cols[0].selectbox("Marque", available_brands, index=default_brand_idx, key=f"sel_brand_{designation}_{label}")

        capacities_dict = get_battery_capacities(load_catalog(), brand_final) if brand_final else {}
        available_capacities = sorted(capacities_dict.keys(), key=lambda x: float(x) if x.replace('.','').isdigit() else 0)

        capacity_idx = 0
        if default_power and str(default_power) in available_capacities:
            capacity_idx = available_capacities.index(str(default_power))
        elif available_capacities and "5" in available_capacities:
            capacity_idx = available_capacities.index("5")

        capacity_selected = cols[1].selectbox("Capacité (kWh)", available_capacities if available_capacities else ["5"], index=capacity_idx, key=f"sel_capacity_{designation}_{label}")

        sell_price = 0.0
        buy_price = 0.0
        brand_base = brand_final
        if brand_base and capacity_selected in capacities_dict:
            sell_price = float(capacities_dict[capacity_selected].get("sell_ttc", 0.0))
            buy_price = float(capacities_dict[capacity_selected].get("buy_ttc", 0.0))

        brand_final = f"{brand_base} {capacity_selected}kWh"

    else:
        brand_sel_list = known_brands(catalog, designation)
        brand_sel = cols[0].selectbox("Marque", brand_sel_list, key=f"sel_{designation}_{label}")
        new_brand = cols[1].text_input("Nouvelle marque", value=(default_brand or ""), key=f"new_{designation}_{label}")
        brand_final = (new_brand.strip() or brand_sel)
        brand_base = brand_final

    # Determine brand to use for price lookup (use base brand for batteries)
    lookup_brand_for_price = brand_base if designation == "Batterie" else brand_final

    qty = cols[2].number_input(
        "Quantité",
        min_value=0,
        step=1,
        value=int(default_qty),
        key=f"qty_{designation}_{label}",
    )

    # Price lookup with stable keys for non-onduleur items
    stable_price_key_sell = f"sell_{designation}_{label}"
    stable_price_key_buy = f"buy_{designation}_{label}"
    brand_tracking_key = f"brand_tracked_{designation}_{label}"

    if brand_tracking_key not in st.session_state:
        st.session_state[brand_tracking_key] = brand_final

    # If brand changed, refresh prices from catalog (use base brand for batteries)
    if st.session_state[brand_tracking_key] != brand_final:
        st.session_state[brand_tracking_key] = brand_final
        if lookup_brand_for_price:
            catalog_sell, catalog_buy = get_prices(load_catalog(), designation, lookup_brand_for_price)
            if catalog_sell is not None:
                st.session_state[stable_price_key_sell] = float(catalog_sell)
            if catalog_buy is not None:
                st.session_state[stable_price_key_buy] = float(catalog_buy)

    auto_sell, auto_buy = get_prices(load_catalog(), designation, lookup_brand_for_price)
    initial_sell = float(default_sell) if default_sell is not None else float(auto_sell or sell_price or 0.0)
    initial_buy = float(default_buy) if default_buy is not None else float(auto_buy or buy_price or 0.0)

    if stable_price_key_sell in st.session_state:
        initial_sell = st.session_state[stable_price_key_sell]
    if stable_price_key_buy in st.session_state:
        initial_buy = st.session_state[stable_price_key_buy]

    sell_val = cols[3].number_input(
        "Prix Unit. TTC",
        min_value=0.0,
        step=10.0,
        value=initial_sell,
        key=stable_price_key_sell,
    )
    buy_val = cols[4].number_input(
        "Prix Achat TTC",
        min_value=0.0,
        step=10.0,
        value=initial_buy,
        key=stable_price_key_buy,
    )
    tva = cols[5].number_input(
        "TVA (%)",
        min_value=0,
        step=1,
        value=int(default_tva),
        key=f"tva_{designation}_{label}",
    )

    result = {
        "Désignation": designation,
        "Marque": brand_final,
        "Quantité": qty,
        "Prix Achat TTC": buy_val,
        "Prix Unit. TTC": sell_val,
        "TVA (%)": tva,
    }
    if custom_label is not None:
        result["CustomLabel"] = custom_label
    if default_photo_key is not None:
        result["PhotoKey"] = default_photo_key

    return result


# ---------- MODE DEVIS ----------
if mode == "Créer un Devis (1 ou 2 scénarios)":
    doc_type = "Devis"
    default_num = config["devis_counter"]
    doc_number = st.number_input(f"Numéro {doc_type}", value=int(default_num), step=1)

    installation_type = st.selectbox(
        "Type d'installation",
        ["Résidentielle", "Commerciale", "Industrielle", "Agricole"],
        index=0,
    )
    type_label_map = {
        "Résidentielle": "résidentielle",
        "Commerciale": "commerciale",
        "Industrielle": "industrielle",
        "Agricole": "agricole",
    }
    type_phrase_map = {
        "Résidentielle": "Installation photovoltaïque résidentielle",
        "Commerciale": "Installation photovoltaïque commerciale",
        "Industrielle": "Installation photovoltaïque industrielle",
        "Agricole": "Installation photovoltaïque agricole",
    }
    type_label = type_label_map.get(installation_type, "résidentielle")
    type_phrase = type_phrase_map.get(installation_type, "Installation photovoltaïque résidentielle")

    st.subheader("Infos Client")
    client_name = st.text_input("Nom du client")
    client_address = st.text_input("Adresse")
    client_phone = st.text_input("Téléphone")

    scenario_choice = st.selectbox(
        "Scénarios à inclure dans le devis PDF :",
        ["Sans batterie uniquement", "Avec batterie uniquement", "Les deux (Sans + Avec)"],
        index=2
    )
    recommended_option = st.selectbox(
        "Recommandation TAQINOR à afficher dans le PDF :",
        ["Aucune recommandation", "Option SANS batterie", "Option AVEC batterie"],
        index=0,
        help="Choisissez l'option à mettre en avant dans le bandeau ROI, ou aucune recommandation.",
    )

    # Puissance PV
    st.subheader("⚡ Puissance PV pour le ROI et le devis")
    default_panel_power = st.session_state.get("puissance_panneau_w", 710)
    default_kwp_value = max(1.0, 8 * default_panel_power / 1000.0)
    panel_step_kw = max(0.01, default_panel_power / 1000.0)
    col_est1, col_est2 = st.columns(2)
    with col_est1:
        puissance_kwp = st.number_input(
            "Puissance PV (kWc)",
            min_value=1.0,
            max_value=200.0,
            value=default_kwp_value,
            step=panel_step_kw,
            key="puissance_kwp",
        )
    with col_est2:
        puissance_panneau_w = st.number_input(
            "Puissance d'un panneau (Wc)",
            min_value=100,
            max_value=1000,
            value=default_panel_power,
            step=10,
            key="puissance_panneau_w",
        )
        st.markdown(f"Référence actuelle : **{puissance_panneau_w} Wc** (Jinko 710 par défaut)")

    # FACTURES ROI
    st.subheader("💡 Factures d'électricité (pour le ROI)")
    use_ws_roi = st.checkbox("Utiliser une estimation Hiver / Été (ROI)", key="roi_use_ws")
    if use_ws_roi:
        col_h, col_e = st.columns(2)
        with col_h:
            f_hiver = st.number_input("Facture typique en hiver (MAD)", 0.0, 1_000_000.0, 500.0, key="roi_f_hiver")
        with col_e:
            f_ete = st.number_input("Facture typique en été (MAD)", 0.0, 1_000_000.0, 1000.0, key="roi_f_ete")
        if st.button("🧮 Estimer les 12 mois (factures ROI)"):
            estimees = interpoler_factures(f_hiver, f_ete)

            for i, m in enumerate(MOIS):
                valeur = round(estimees[i], 2)

                # 1) Met à jour la structure interne qu'on utilise comme "référence"
                st.session_state.roi_fact_init[m] = valeur

                # 2) Surtout : met à jour les widgets eux-mêmes
                key_widget = f"roi_fact_{m}"
                st.session_state[key_widget] = valeur

    factures_roi = []
    cols_roi = st.columns(3)
    for i, m in enumerate(MOIS):
        with cols_roi[i % 3]:
            val = st.number_input(
                f"Facture {m} (MAD)",
                0.0,
                1_000_000.0,
                st.session_state.roi_fact_init.get(m, 2000.0),
                10.0,
                key=f"roi_fact_{m}",
            )
            factures_roi.append(val)

    roi_total_annuel = sum(factures_roi)
    roi_total_kwh = roi_total_annuel / KWH_PRICE if KWH_PRICE > 0 else 0
    st.write(f"**Facture annuelle (ROI) :** {roi_total_annuel:,.0f} MAD")
    st.write(f"**Consommation annuelle (ROI) :** {roi_total_kwh:,.0f} kWh")

    day_usage_defaults = {
        "Résidentielle": 35,
        "Commerciale": 45,
        "Industrielle": 40,
        "Agricole": 30,
    }
    default_day_usage = min(90, max(20, day_usage_defaults.get(installation_type, 35)))
    day_usage_percent = st.slider(
        "Pourcentage de la production PV consommée pendant la journée (%)",
        min_value=20,
        max_value=90,
        value=default_day_usage,
        step=5,
        key="roi_day_usage_percent",
        help="Détermine la part de la production photovoltaïque utilisée sur place pendant les heures de jour (pour tous les scénarios).",
    )
    st.caption(f"Profil « {installation_type} » : base à {default_day_usage}% de la production consommée en journée.")
    day_usage_ratio = day_usage_percent / 100.0

    st.markdown("---")

    st.subheader("Produits / Services (base)")

    catalog_now = load_catalog()
    # Choix du type de structures (par défaut automatique selon la puissance)
    try:
        default_struct = "Structures acier" if puissance_kwp < 30 else "Structures aluminium"
    except Exception:
        default_struct = "Structures acier"
    struct_idx = 0 if default_struct == "Structures acier" else 1
    structure_choice = st.radio(
        "Type de structures à utiliser :",
        ("Structures acier", "Structures aluminium"),
        index=struct_idx,
        key="structure_type_choice",
    )
    custom_templates = load_custom_templates()

    label_map = {
        "Onduleur réseau": "Onduleur injection (scénario SANS batterie)",
        "Onduleur hybride": "Onduleur hybride (scénario AVEC batterie)",
        "Smart Meter": "Smart Meter",
        "Wifi Dongle": "Wifi Dongle",
        "Panneaux": "Panneaux solaires (Jinko 710)",
        "Batterie": "Batterie de stockage (scénario AVEC batterie)",
        "Structures acier": "Structures acier",
        "Structures aluminium": "Structures aluminium",
        "Socles": "Socles béton",
        "Accessoires": "Accessoires & câblage",
        "Tableau De Protection AC/DC": "Tableau de protection AC/DC",
        "Installation": "Installation",
        "Transport": "Transport",
        "Suivi journalier, maintenance chaque 12 mois pendent 2 ans": "Suivi journalier & maintenance (2 ans)",
    }

    def _resolve_label(designation, custom_label):
        """Return the label used by the line editor so overrides keep matching."""
        cleaned = custom_label
        if pd.isna(cleaned):
            cleaned = None
        if isinstance(cleaned, str):
            cleaned = cleaned.strip()
            if not cleaned:
                cleaned = None
        return cleaned or label_map.get(designation, designation)

    # Bouton pour remplir automatiquement — construit un gabarit minimal puis appelle auto_fill
    if st.button("⚙️ Remplir automatiquement les lignes (panneaux, onduleurs, structures, smart meter, wifi)"):
        # Signal to line_editor that this run is an explicit autofill and
        # widget values should be overwritten with autofill results.
        st.session_state["force_autofill_update"] = True
        battery_label_primary = "Batterie 10 kWh (scénario AVEC batterie)"
        battery_label_secondary = "Batterie 5 kWh (scénario AVEC batterie)"
        # gabarit minimal reprenant les désignations standard et valeurs par défaut
        template_rows = [
            {"Désignation": "Onduleur réseau", "Marque": "", "Quantité": 1, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
            {"Désignation": "Onduleur hybride", "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
            {"Désignation": "Smart Meter", "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
            {"Désignation": "Wifi Dongle", "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
            {"Désignation": "Panneaux", "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 10},
            {"Désignation": "Batterie", "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20, "CustomLabel": battery_label_primary},
            {"Désignation": "Batterie", "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20, "CustomLabel": battery_label_secondary},
            {"Désignation": "Structures acier", "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
            {"Désignation": "Structures aluminium", "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
            {"Désignation": "Socles", "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
            {"Désignation": "Accessoires", "Marque": "", "Quantité": 1, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
            {"Désignation": "Tableau De Protection AC/DC", "Marque": "", "Quantité": 1, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
            {"Désignation": "Installation", "Marque": "", "Quantité": 1, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
            {"Désignation": "Transport", "Marque": "", "Quantité": 1, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
            {"Désignation": "Suivi journalier, maintenance chaque 12 mois pendent 2 ans", "Marque": "", "Quantité": 0, "Prix Achat TTC": 0.0, "Prix Unit. TTC": 0.0, "TVA (%)": 20},
        ]
        df_template = pd.DataFrame(template_rows)
        df_auto = auto_fill_from_power(df_template, catalog_now, puissance_kwp, puissance_panneau_w)
        mask_bat_template = df_template["Désignation"] == "Batterie"
        bat_template_labels = df_template.loc[mask_bat_template, "CustomLabel"].reset_index(drop=True)
        mask_bat_auto = df_auto["Désignation"] == "Batterie"
        if mask_bat_template.sum() == mask_bat_auto.sum():
            df_auto.loc[mask_bat_auto, "CustomLabel"] = bat_template_labels.values
        # Respecter le choix manuel de l'utilisateur pour le type de structure (si présent)
        try:
            import math
            nb_panneaux = math.ceil(puissance_kwp * 1000.0 / puissance_panneau_w) if puissance_kwp > 0 else 0
        except Exception:
            nb_panneaux = 0
        struct_choice = st.session_state.get("structure_type_choice", None)
        if struct_choice in ("Structures acier", "Structures aluminium") and nb_panneaux > 0:
            if struct_choice == "Structures acier":
                mask_a = df_auto["Désignation"] == "Structures acier"
                mask_b = df_auto["Désignation"] == "Structures aluminium"
                if mask_a.any():
                    idx = mask_a.idxmax()
                    df_auto.at[idx, "Quantité"] = nb_panneaux
                    df_auto.at[idx, "CustomLabel"] = "Structures en acier galvanisé"
                if mask_b.any():
                    idx2 = mask_b.idxmax()
                    df_auto.at[idx2, "Quantité"] = 0
            else:
                mask_a = df_auto["Désignation"] == "Structures acier"
                mask_b = df_auto["Désignation"] == "Structures aluminium"
                if mask_b.any():
                    idx = mask_b.idxmax()
                    df_auto.at[idx, "Quantité"] = nb_panneaux
                    df_auto.at[idx, "CustomLabel"] = "Structures en aluminium"
                if mask_a.any():
                    idx2 = mask_a.idxmax()
                    df_auto.at[idx2, "Quantité"] = 0

        st.session_state.df_common_overrides = df_auto
        # Mark that autofill ran and that onduleur widgets should be updated
        # We set a small counter equal to the number of onduleur editors
        # (réseau + hybride) so each will consume one update.
        st.session_state["force_autofill_update_count"] = 2
        # Remplir aussi les clés de session pour que les widgets éditables soient préremplis
        try:
            for _, r in pd.DataFrame(df_auto).iterrows():
                des = r.get("Désignation")
                if not isinstance(des, str):
                    continue
                custom_label = r.get("CustomLabel")
                label = _resolve_label(des, custom_label)
                brand = (r.get("Marque") or "").strip()
                qty = int(r.get("Quantité") or 0)
                tva = int(r.get("TVA (%)") or 0)
                sell = float(r.get("Prix Unit. TTC") or 0.0)
                buy = float(r.get("Prix Achat TTC") or 0.0)

                # ensure widgets pick up autofill qty/TVA when not yet set
                try:
                    st.session_state.setdefault(f"qty_{des}_{label}", qty)
                    st.session_state.setdefault(f"tva_{des}_{label}", tva)
                except Exception:
                    pass

                # push qty / TVA so widgets pick them up on next render
                try:
                    st.session_state[f"qty_{des}_{label}"] = qty
                    st.session_state[f"tva_{des}_{label}"] = tva
                except Exception:
                    pass

                # For onduleurs, use the brand + power lookup key used by line_editor
                def _format_power_key(p):
                    try:
                        if p is None:
                            return ""
                        pf = float(p)
                        if pf.is_integer():
                            return str(int(pf))
                        return str(pf)
                    except Exception:
                        return str(p)

                if des == "Onduleur réseau":
                    ondu_power = st.session_state.get("ondu_res_power")
                    ondu_phase = st.session_state.get("ondu_res_phase")
                    lookup_key = _format_power_key(ondu_power)
                    # also keep short named keys for components that expect them
                    st.session_state["ondu_res_brand"] = brand
                    st.session_state["ondu_res_power"] = ondu_power
                    st.session_state["ondu_res_phase"] = ondu_phase
                elif des == "Onduleur hybride":
                    ondu_power = st.session_state.get("ondu_hyb_power")
                    ondu_phase = st.session_state.get("ondu_hyb_phase")
                    lookup_key = _format_power_key(ondu_power)
                    st.session_state["ondu_hyb_brand"] = brand
                    st.session_state["ondu_hyb_power"] = ondu_power
                    st.session_state["ondu_hyb_phase"] = ondu_phase
                elif des in ("Panneaux", "Batterie"):
                    # non-onduleur items use stable sell/buy keys in line_editor
                    # store brand tracking too
                    st.session_state[f"brand_tracked_{des}_{label}"] = brand
                else:
                    # fallback: nothing to push into widget state to avoid conflicts
                    pass
        except Exception:
            pass

        st.success("Lignes remplies automatiquement : Jinko 710, Huawei (sans batt), Deye (avec batt), structures, smart meter et wifi.")

    # Lignes standard communes — utiliser overrides si l'auto-fill a été exécuté
    overrides = {}
    if st.session_state.get("df_common_overrides") is not None:
        try:
            tmp = sanitize_df(pd.DataFrame(st.session_state.df_common_overrides).copy())
            for _, r in tmp.iterrows():
                des = r.get("Désignation")
                if not isinstance(des, str):
                    continue
                label = _resolve_label(des, r.get("CustomLabel"))
                overrides[(des, label)] = {
                    "Marque": r.get("Marque", ""),
                    "Quantité": int(r.get("Quantité") or 0),
                    "Prix Unit. TTC": float(r.get("Prix Unit. TTC") or 0.0),
                    "Prix Achat TTC": float(r.get("Prix Achat TTC") or 0.0),
                    "TVA (%)": int(r.get("TVA (%)") or 0),
                    "PhotoKey": r.get("PhotoKey", None),
                    "CustomLabel": r.get("CustomLabel", None),
                }
        except Exception:
            overrides = {}

    def override_entry(designation, label):
        return overrides.get((designation, label), {})

    def override_value(designation, label, key, default=None):
        return override_entry(designation, label).get(key, default)

    # Si un onduleur réseau est présent (quantité > 0), on ajoute par défaut Smart Meter et Wifi Dongle
    # (avec quantité 1) afin que les widgets correspondants soient préremplis et éditables.
    try:
        ond_res_label = label_map["Onduleur réseau"]
        ond_res_qty = override_value("Onduleur réseau", ond_res_label, "Quantité", 0)
        if ond_res_qty > 0:
            smart_label = label_map["Smart Meter"]
            if ("Smart Meter", smart_label) not in overrides:
                sell_sm, buy_sm = get_prices(load_catalog(), "Smart Meter", "")
                overrides[("Smart Meter", smart_label)] = {
                    "Marque": "",
                    "Quantité": 1,
                    "Prix Unit. TTC": float(sell_sm or 0.0),
                    "Prix Achat TTC": float(buy_sm or 0.0),
                    "TVA (%)": 20,
                }
            else:
                if override_value("Smart Meter", smart_label, "Quantité", 0) == 0:
                    overrides[("Smart Meter", smart_label)]["Quantité"] = 1
            wifi_label = label_map["Wifi Dongle"]
            if ("Wifi Dongle", wifi_label) not in overrides:
                sell_wd, buy_wd = get_prices(load_catalog(), "Wifi Dongle", "")
                overrides[("Wifi Dongle", wifi_label)] = {
                    "Marque": "",
                    "Quantité": 1,
                    "Prix Unit. TTC": float(sell_wd or 0.0),
                    "Prix Achat TTC": float(buy_wd or 0.0),
                    "TVA (%)": 20,
                }
            else:
                if override_value("Wifi Dongle", wifi_label, "Quantité", 0) == 0:
                    overrides[("Wifi Dongle", wifi_label)]["Quantité"] = 1
    except Exception:
        pass

    label_ondu_res = label_map["Onduleur réseau"]
    label_ondu_hyb = label_map["Onduleur hybride"]
    label_smart_meter = label_map["Smart Meter"]
    label_wifi = label_map["Wifi Dongle"]
    label_panneaux = label_map["Panneaux"]
    label_bat_10 = "Batterie 10 kWh (scénario AVEC batterie)"
    label_bat_5 = "Batterie 5 kWh (scénario AVEC batterie)"
    label_struct_acier = label_map["Structures acier"]
    label_struct_aluminium = label_map["Structures aluminium"]
    label_socles = label_map["Socles"]
    label_accessoires = label_map["Accessoires"]
    label_tableau = label_map["Tableau De Protection AC/DC"]
    label_installation = label_map["Installation"]
    label_transport = label_map["Transport"]
    label_suivi = label_map["Suivi journalier, maintenance chaque 12 mois pendent 2 ans"]

    rows_common = [
        line_editor(
            "Onduleur réseau",
            label_ondu_res,
            override_value("Onduleur réseau", label_ondu_res, "Quantité", 1),
            override_value("Onduleur réseau", label_ondu_res, "TVA (%)", 20),
            catalog_now,
            default_brand=override_value("Onduleur réseau", label_ondu_res, "Marque", ""),
            default_sell=override_value("Onduleur réseau", label_ondu_res, "Prix Unit. TTC", None),
            default_buy=override_value("Onduleur réseau", label_ondu_res, "Prix Achat TTC", None),
            brand_only=True,
            default_power=st.session_state.get("ondu_res_power"),
            default_phase=st.session_state.get("ondu_res_phase"),
        ),
        line_editor(
            "Onduleur hybride",
            label_ondu_hyb,
            override_value("Onduleur hybride", label_ondu_hyb, "Quantité", 0),
            override_value("Onduleur hybride", label_ondu_hyb, "TVA (%)", 20),
            catalog_now,
            default_brand=override_value("Onduleur hybride", label_ondu_hyb, "Marque", ""),
            default_sell=override_value("Onduleur hybride", label_ondu_hyb, "Prix Unit. TTC", None),
            default_buy=override_value("Onduleur hybride", label_ondu_hyb, "Prix Achat TTC", None),
            brand_only=True,
            default_power=st.session_state.get("ondu_hyb_power"),
            default_phase=st.session_state.get("ondu_hyb_phase"),
        ),
        line_editor(
            "Smart Meter",
            label_smart_meter,
            override_value("Smart Meter", label_smart_meter, "Quantité", 0),
            override_value("Smart Meter", label_smart_meter, "TVA (%)", 20),
            catalog_now,
            default_sell=override_value("Smart Meter", label_smart_meter, "Prix Unit. TTC", None),
            default_buy=override_value("Smart Meter", label_smart_meter, "Prix Achat TTC", None),
        ),
        line_editor(
            "Wifi Dongle",
            label_wifi,
            override_value("Wifi Dongle", label_wifi, "Quantité", 0),
            override_value("Wifi Dongle", label_wifi, "TVA (%)", 20),
            catalog_now,
            default_sell=override_value("Wifi Dongle", label_wifi, "Prix Unit. TTC", None),
            default_buy=override_value("Wifi Dongle", label_wifi, "Prix Achat TTC", None),
        ),
        line_editor(
            "Panneaux",
            label_panneaux,
            override_value("Panneaux", label_panneaux, "Quantité", 0),
            override_value("Panneaux", label_panneaux, "TVA (%)", 10),
            catalog_now,
            default_brand=override_value("Panneaux", label_panneaux, "Marque", ""),
            default_sell=override_value("Panneaux", label_panneaux, "Prix Unit. TTC", None),
            default_buy=override_value("Panneaux", label_panneaux, "Prix Achat TTC", None),
        ),
        line_editor(
            "Batterie",
            label_bat_10,
            override_value("Batterie", label_bat_10, "Quantité", 0),
            override_value("Batterie", label_bat_10, "TVA (%)", 20),
            catalog_now,
            custom_label=label_bat_10,
            default_brand=override_value("Batterie", label_bat_10, "Marque", ""),
            default_sell=override_value("Batterie", label_bat_10, "Prix Unit. TTC", None),
            default_buy=override_value("Batterie", label_bat_10, "Prix Achat TTC", None),
            default_power=10,
        ),
        line_editor(
            "Batterie",
            label_bat_5,
            override_value("Batterie", label_bat_5, "Quantité", 0),
            override_value("Batterie", label_bat_5, "TVA (%)", 20),
            catalog_now,
            custom_label=label_bat_5,
            default_brand=override_value("Batterie", label_bat_5, "Marque", ""),
            default_sell=override_value("Batterie", label_bat_5, "Prix Unit. TTC", None),
            default_buy=override_value("Batterie", label_bat_5, "Prix Achat TTC", None),
            default_power=5,
        ),
        line_editor(
            "Structures acier",
            label_struct_acier,
            override_value("Structures acier", label_struct_acier, "Quantité", 0),
            override_value("Structures acier", label_struct_acier, "TVA (%)", 20),
            catalog_now,
            default_sell=override_value("Structures acier", label_struct_acier, "Prix Unit. TTC", None),
            default_buy=override_value("Structures acier", label_struct_acier, "Prix Achat TTC", None),
        ),
        line_editor(
            "Structures aluminium",
            label_struct_aluminium,
            override_value("Structures aluminium", label_struct_aluminium, "Quantité", 0),
            override_value("Structures aluminium", label_struct_aluminium, "TVA (%)", 20),
            catalog_now,
            default_sell=override_value("Structures aluminium", label_struct_aluminium, "Prix Unit. TTC", None),
            default_buy=override_value("Structures aluminium", label_struct_aluminium, "Prix Achat TTC", None),
        ),
        line_editor(
            "Socles",
            label_socles,
            override_value("Socles", label_socles, "Quantité", 0),
            override_value("Socles", label_socles, "TVA (%)", 20),
            catalog_now,
            default_sell=override_value("Socles", label_socles, "Prix Unit. TTC", None),
            default_buy=override_value("Socles", label_socles, "Prix Achat TTC", None),
        ),
        line_editor(
            "Accessoires",
            label_accessoires,
            override_value("Accessoires", label_accessoires, "Quantité", 1),
            override_value("Accessoires", label_accessoires, "TVA (%)", 20),
            catalog_now,
            default_sell=override_value("Accessoires", label_accessoires, "Prix Unit. TTC", None),
            default_buy=override_value("Accessoires", label_accessoires, "Prix Achat TTC", None),
        ),
        line_editor(
            "Tableau De Protection AC/DC",
            label_tableau,
            override_value("Tableau De Protection AC/DC", label_tableau, "Quantité", 1),
            override_value("Tableau De Protection AC/DC", label_tableau, "TVA (%)", 20),
            catalog_now,
            default_sell=override_value("Tableau De Protection AC/DC", label_tableau, "Prix Unit. TTC", None),
            default_buy=override_value("Tableau De Protection AC/DC", label_tableau, "Prix Achat TTC", None),
        ),
        line_editor(
            "Installation",
            label_installation,
            override_value("Installation", label_installation, "Quantité", 1),
            override_value("Installation", label_installation, "TVA (%)", 20),
            catalog_now,
            default_sell=override_value("Installation", label_installation, "Prix Unit. TTC", None),
            default_buy=override_value("Installation", label_installation, "Prix Achat TTC", None),
        ),
        line_editor(
            "Transport",
            label_transport,
            override_value("Transport", label_transport, "Quantité", 1),
            override_value("Transport", label_transport, "TVA (%)", 20),
            catalog_now,
            default_sell=override_value("Transport", label_transport, "Prix Unit. TTC", None),
            default_buy=override_value("Transport", label_transport, "Prix Achat TTC", None),
        ),
        line_editor(
            "Suivi journalier, maintenance chaque 12 mois pendent 2 ans",
            label_suivi,
            override_value("Suivi journalier, maintenance chaque 12 mois pendent 2 ans", label_suivi, "Quantité", 1),
            override_value("Suivi journalier, maintenance chaque 12 mois pendent 2 ans", label_suivi, "TVA (%)", 20),
            catalog_now,
        ),
    ]

    # Lignes perso mémorisées comme templates
    for tpl in custom_templates:
        label = tpl.get("label", "Ligne personnalisée")
        default_tva = tpl.get("default_tva", 20)
        default_photo = tpl.get("default_photo", "")
        rows_common.append(
            line_editor(
                designation=label,
                label=label,
                default_qty=0,
                default_tva=default_tva,
                catalog=catalog_now,
                custom_label=label,
                default_photo_key=default_photo,
            )
        )

    df_common = pd.DataFrame(rows_common)

    st.markdown("Aperçu des lignes utilisées pour le calcul (après ajustements manuels ou auto-fill) :")
    st.dataframe(df_common, use_container_width=True)

    # Lignes perso SANS
    st.subheader("Lignes personnalisées — scénario SANS batterie")
    if st.button("➕ Ajouter une ligne personnalisée (SANS batterie)"):
        st.session_state.custom_lines_sans.append(
            {"desc": "", "photo": "", "qty": 0, "sell": 0.0, "buy": 0.0, "tva": 20}
        )

    new_custom_sans = []
    for i, line in enumerate(st.session_state.custom_lines_sans):
        st.markdown(f"**Ligne perso SANS n°{i+1}**")
        c1, c2, c3, c4, c5, c6, c7 = st.columns([3, 1, 1, 1, 1, 1, 0.8])
        with c1:
            desc = st.text_input(
                "Nom / Désignation",
                value=line.get("desc", ""),
                key=f"sans_desc_{i}",
            )
        with c2:
            qty = st.number_input(
                "Quantité",
                min_value=0,
                step=1,
                value=int(line.get("qty", 0)),
                key=f"sans_qty_{i}",
            )
        with c3:
            sell = st.number_input(
                "PU TTC",
                min_value=0.0,
                step=10.0,
                value=float(line.get("sell", 0.0)),
                key=f"sans_sell_{i}",
            )
        with c4:
            buy = st.number_input(
                "Achat TTC",
                min_value=0.0,
                step=10.0,
                value=float(line.get("buy", 0.0)),
                key=f"sans_buy_{i}",
            )
        with c5:
            tva = st.number_input(
                "TVA (%)",
                min_value=0,
                step=1,
                value=int(line.get("tva", 20)),
                key=f"sans_tva_{i}",
            )
        with c6:
            photo = st.text_input(
                "Nom photo (facultatif)",
                value=line.get("photo", ""),
                key=f"sans_photo_{i}",
            )
        with c7:
            remove = st.checkbox("❌", key=f"sans_rem_{i}")

        if not remove:
            new_custom_sans.append(
                {"desc": desc, "photo": photo, "qty": qty, "sell": sell, "buy": buy, "tva": tva}
            )
    st.session_state.custom_lines_sans = new_custom_sans

    if st.session_state.custom_lines_sans:
        df_custom_sans = pd.DataFrame(
            [
                {
                    "Désignation": l["desc"] or "Ligne personnalisée",
                    "Marque": "",
                    "Quantité": l["qty"],
                    "Prix Achat TTC": l["buy"],
                    "Prix Unit. TTC": l["sell"],
                    "TVA (%)": l["tva"],
                    "CustomLabel": l["desc"],
                    "PhotoKey": l.get("photo", ""),
                }
                for l in st.session_state.custom_lines_sans
            ]
        )
    else:
        df_custom_sans = pd.DataFrame(columns=["Désignation","Marque","Quantité","Prix Achat TTC","Prix Unit. TTC","TVA (%)","CustomLabel","PhotoKey"])

    # Lignes perso AVEC
    st.subheader("Lignes personnalisées — scénario AVEC batterie")
    if st.button("➕ Ajouter une ligne personnalisée (AVEC batterie)"):
        st.session_state.custom_lines_avec.append(
            {"desc": "", "photo": "", "qty": 0, "sell": 0.0, "buy": 0.0, "tva": 20}
        )

    new_custom_avec = []
    for i, line in enumerate(st.session_state.custom_lines_avec):
        st.markdown(f"**Ligne perso AVEC n°{i+1}**")
        c1, c2, c3, c4, c5, c6, c7 = st.columns([3, 1, 1, 1, 1, 1, 0.8])
        with c1:
            desc = st.text_input(
                "Nom / Désignation",
                value=line.get("desc", ""),
                key=f"avec_desc_{i}",
            )
        with c2:
            qty = st.number_input(
                "Quantité",
                min_value=0,
                step=1,
                value=int(line.get("qty", 0)),
                key=f"avec_qty_{i}",
            )
        with c3:
            sell = st.number_input(
                "PU TTC",
                min_value=0.0,
                step=10.0,
                value=float(line.get("sell", 0.0)),
                key=f"avec_sell_{i}",
            )
        with c4:
            buy = st.number_input(
                "Achat TTC",
                min_value=0.0,
                step=10.0,
                value=float(line.get("buy", 0.0)),
                key=f"avec_buy_{i}",
            )
        with c5:
            tva = st.number_input(
                "TVA (%)",
                min_value=0,
                step=1,
                value=int(line.get("tva", 20)),
                key=f"avec_tva_{i}",
            )
        with c6:
            photo = st.text_input(
                "Nom photo (facultatif)",
                value=line.get("photo", ""),
                key=f"avec_photo_{i}",
            )
        with c7:
            remove = st.checkbox("❌", key=f"avec_rem_{i}")

        if not remove:
            new_custom_avec.append(
                {"desc": desc, "photo": photo, "qty": qty, "sell": sell, "buy": buy, "tva": tva}
            )
    st.session_state.custom_lines_avec = new_custom_avec

    if st.session_state.custom_lines_avec:
        df_custom_avec = pd.DataFrame(
            [
                {
                    "Désignation": l["desc"] or "Ligne personnalisée",
                    "Marque": "",
                    "Quantité": l["qty"],
                    "Prix Achat TTC": l["buy"],
                    "Prix Unit. TTC": l["sell"],
                    "TVA (%)": l["tva"],
                    "CustomLabel": l["desc"],
                    "PhotoKey": l.get("photo", ""),
                }
                for l in st.session_state.custom_lines_avec
            ]
        )
    else:
        df_custom_avec = pd.DataFrame(columns=["Désignation","Marque","Quantité","Prix Achat TTC","Prix Unit. TTC","TVA (%)","CustomLabel","PhotoKey"])

    # NOTES séparées
    st.subheader("Notes pour le devis SANS batterie")
    if st.button("➕ Ajouter une note (SANS)"):
        st.session_state.notes_sans.append("")
    notes_sans_new = []
    for i, note in enumerate(st.session_state.notes_sans):
        col_note, col_del = st.columns([6, 1])
        with col_note:
            text = st.text_area(
                f"Note SANS {i+1}",
                value=note,
                key=f"note_sans_{i}",
                height=60,
            )
        with col_del:
            delete = st.checkbox("❌", key=f"note_sans_del_{i}")
        if not delete:
            notes_sans_new.append(text)
    st.session_state.notes_sans = notes_sans_new

    st.subheader("Notes pour le devis AVEC batterie")
    if st.button("➕ Ajouter une note (AVEC)"):
        st.session_state.notes_avec.append("")
    notes_avec_new = []
    for i, note in enumerate(st.session_state.notes_avec):
        col_note, col_del = st.columns([6, 1])
        with col_note:
            text = st.text_area(
                f"Note AVEC {i+1}",
                value=note,
                key=f"note_avec_{i}",
                height=60,
            )
        with col_del:
            delete = st.checkbox("❌", key=f"note_avec_del_{i}")
        if not delete:
            notes_avec_new.append(text)
    st.session_state.notes_avec = notes_avec_new

    # Construction DF scénarios
    # IMPORTANT: use the values returned by the editable widgets (`df_common`) as source of truth.
    df_common_full = df_common.copy()

    df_sans_all = pd.concat([df_common_full, df_custom_sans], ignore_index=True)
    df_avec_all = pd.concat([df_common_full, df_custom_avec], ignore_index=True)

    df_sans_all = sanitize_df(df_sans_all)
    df_avec_all = sanitize_df(df_avec_all)

    df_sans_final = df_sans_all[
        ~df_sans_all["Désignation"].isin(["Batterie", "Onduleur hybride"])
    ].copy()
    df_avec_final = df_avec_all[
        ~df_avec_all["Désignation"].isin(["Onduleur réseau"])
    ].copy()

    # --- Si le scénario AVEC contient une batterie ou un onduleur Deye,
    #     on retire systématiquement Smart Meter et Wifi Dongle du devis AVEC
    try:
        has_battery = (df_avec_final["Désignation"] == "Batterie").any()
        has_deye = False
        if (df_avec_final["Désignation"] == "Onduleur hybride").any():
            # regarde si la marque contient 'deye'
            mask = (df_avec_final["Désignation"] == "Onduleur hybride") & df_avec_final["Marque"].astype(str).str.lower().str.contains("deye", na=False)
            has_deye = mask.any()

        if has_battery or has_deye:
            df_avec_final = df_avec_final[~df_avec_final["Désignation"].isin(["Smart Meter", "Wifi Dongle"])].copy()
    except Exception:
        # ne pas faire échouer l'application si quelque chose d'inattendu survient
        pass

    for df_tmp in (df_sans_final, df_avec_final):
        df_tmp["Total TTC"] = df_tmp["Prix Unit. TTC"] * df_tmp["Quantité"]

    total_ttc_sans = float(df_sans_final["Total TTC"].sum())
    total_ttc_avec = float(df_avec_final["Total TTC"].sum())

    st.markdown("### Récapitulatif devis")
    c1, c2 = st.columns(2)
    c1.metric("Total TTC scénario SANS batterie", f"{total_ttc_sans:,.2f} DH")
    c2.metric("Total TTC scénario AVEC batterie", f"{total_ttc_avec:,.2f} DH")

    battery_capacity_re = re.compile(r"(\d+(?:[.,]\d+)?)\s*[kK][wW][hH]")
    battery_capacity_kwh = 0.0
    mask_battery = df_avec_final["Désignation"] == "Batterie"
    for _, row in df_avec_final[mask_battery].iterrows():
        qty = float(row.get("Quantité", 0) or 0)
        brand_text = str(row.get("Marque", "") or "")
        match = battery_capacity_re.search(brand_text)
        if match and qty > 0:
            try:
                cap_value = float(match.group(1).replace(",", "."))
            except Exception:
                cap_value = 0.0
            battery_capacity_kwh += qty * max(0.0, cap_value)

    battery_monthly_usages = [battery_capacity_kwh * 0.9 * days for days in DAYS_IN_MONTH]

    # ROI
    kwh_mensuels = [f / KWH_PRICE if KWH_PRICE > 0 else 0 for f in factures_roi]
    prod_pv = [GHI[i] * puissance_kwp * EFFICIENCY for i in range(12)]

    self_consumed_sans = []
    self_consumed_avec = []
    battery_usage_per_month = []

    for i, pv_kwh in enumerate(prod_pv):
        ratio_sans = day_usage_ratio
        ratio_avec = day_usage_ratio  # placeholder until the battery-specific strategy is defined
        sc_sans = pv_kwh * ratio_sans
        sc_avec = pv_kwh * ratio_avec
        # Cap by available consumption if known
        conso_month = kwh_mensuels[i] if i < len(kwh_mensuels) else sc_sans + sc_avec
        sc_sans = min(sc_sans, conso_month)
        sc_avec = min(sc_avec, conso_month)
        battery_energy = battery_monthly_usages[i] if i < len(battery_monthly_usages) else 0.0
        battery_usage_per_month.append(battery_energy)
        self_consumed_sans.append(sc_sans)
        self_consumed_avec.append(sc_avec)

    eco_mens_sans = [x * KWH_PRICE for x in self_consumed_sans]
    eco_mens_avec = [
        (pv_kwh + battery_kwh) * KWH_PRICE
        for pv_kwh, battery_kwh in zip(self_consumed_avec, battery_usage_per_month)
    ]

    eco_ann_sans = sum(eco_mens_sans)
    eco_ann_avec = sum(eco_mens_avec)

    payback_sans = total_ttc_sans / eco_ann_sans if eco_ann_sans > 0 and total_ttc_sans > 0 else None
    payback_avec = total_ttc_avec / eco_ann_avec if eco_ann_avec > 0 and total_ttc_avec > 0 else None

    st.subheader("📈 ROI (Retour sur investissement)")

    st.write(f"**Production PV annuelle estimée :** {sum(prod_pv):,.0f} kWh/an")

    col_roi1, col_roi2 = st.columns(2)
    with col_roi1:
        st.markdown("### 🔋 Scénario SANS batterie")
        st.write(f"**Coût système SANS batterie :** {total_ttc_sans:,.0f} MAD")
        st.write(f"**Économie annuelle estimée :** {eco_ann_sans:,.0f} MAD/an")
        if payback_sans:
            st.write(f"**Temps de retour estimé :** {payback_sans:.1f} ans")
        else:
            st.write("Temps de retour non calculable (économie annuelle nulle).")

    with col_roi2:
        st.markdown("### 🔋 Scénario AVEC batterie")
        st.write(f"**Coût système AVEC batterie :** {total_ttc_avec:,.0f} MAD")
        st.write(f"**Économie annuelle estimée :** {eco_ann_avec:,.0f} MAD/an")
        if payback_avec:
            st.write(f"**Temps de retour estimé :** {payback_avec:.1f} ans")
        else:
            st.write("Temps de retour non calculable (économie annuelle nulle).")

    df_roi = pd.DataFrame({
        "Mois": MOIS,
        "Facture (MAD)": factures_roi,
        "Production PV (kWh)": prod_pv,
        "PV utilisée SANS batt (kWh)": self_consumed_sans,
        "PV utilisée AVEC batt (kWh)": self_consumed_avec,
        "Batterie (kWh)": battery_usage_per_month,
        "Économie SANS batt (MAD)": eco_mens_sans,
        "Économie AVEC batt (MAD)": eco_mens_avec,
    })
    st.markdown("#### Détail mensuel ROI")
    st.dataframe(df_roi, use_container_width=True)

    fig_roi = build_roi_figure(MOIS, factures_roi, eco_mens_sans, eco_mens_avec)
    st.pyplot(fig_roi)
    roi_fig_all_buf = roi_figure_buffer(MOIS, factures_roi, eco_mens_sans, eco_mens_avec)

    # Graphique cumulatif 25 ans
    years_25 = list(range(0, 26))
    cumulative_sans_25 = [-total_ttc_sans + eco_ann_sans * n for n in years_25] if eco_ann_sans is not None else []
    has_battery_option = eco_ann_avec is not None and eco_ann_avec > 0 and total_ttc_avec is not None and total_ttc_avec > 0
    cumulative_avec_25 = [-total_ttc_avec + eco_ann_avec * n for n in years_25] if has_battery_option else None
    roi_fig_cumul_buf = None
    if cumulative_sans_25:
        roi_fig_cumul_buf = roi_cumulative_buffer(years_25, cumulative_sans_25, cumulative_avec_25 if has_battery_option else None)

    # ROIs résumé pour PDF
    roi_summary_sans = {
        "prod_annuelle": sum(prod_pv),
        "eco_annuelle": eco_ann_sans,
        "cout_systeme": total_ttc_sans,
        "payback": payback_sans,
    }
    roi_summary_avec = {
        "prod_annuelle": sum(prod_pv),
        "eco_annuelle": eco_ann_avec,
        "cout_systeme": total_ttc_avec,
        "payback": payback_avec,
    }

    if st.button("Générer le devis complet en PDF"):
        cat_now = load_catalog()
        learn_from_df(pd.concat([df_sans_final, df_avec_final], ignore_index=True), cat_now)

        # Sauvegarde des nouveaux templates
        templates = load_custom_templates()
        existing_labels = {t["label"] for t in templates if "label" in t}
        for l in (st.session_state.custom_lines_sans + st.session_state.custom_lines_avec):
            label = (l.get("desc") or "").strip()
            photo = (l.get("photo") or "").strip()
            if label and label not in existing_labels:
                templates.append(
                    {
                        "label": label,
                        "default_tva": int(l.get("tva", 20)),
                        "default_photo": photo,
                    }
                )
                existing_labels.add(label)
        save_custom_templates(templates)

        # Selon le choix de scénarios
        df_sans_used = df_sans_final if scenario_choice in ("Sans batterie uniquement", "Les deux (Sans + Avec)") else df_sans_final.iloc[0:0]
        df_avec_used = df_avec_final if scenario_choice in ("Avec batterie uniquement", "Les deux (Sans + Avec)") else df_avec_final.iloc[0:0]

        pdf_path = generate_double_devis_pdf(
            df_sans=df_sans_used,
            df_avec=df_avec_used,
            notes_sans=st.session_state.notes_sans,
            notes_avec=st.session_state.notes_avec,
            client_name=client_name,
            client_address=client_address,
            client_phone=client_phone,
            doc_type=doc_type,
            doc_number=doc_number,
            roi_summary_sans=roi_summary_sans if scenario_choice != "Avec batterie uniquement" else None,
            roi_summary_avec=roi_summary_avec if scenario_choice != "Sans batterie uniquement" else None,
            roi_fig_all_buf=roi_fig_all_buf,
            roi_fig_cumul_buf=roi_fig_cumul_buf,
            scenario_choice=scenario_choice,
            recommended_option=recommended_option,
            installation_type=installation_type,
            type_label=type_label,
            type_phrase=type_phrase,
        )
        target_dir = DEVIS_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        final_path = target_dir / pdf_path.name
        if pdf_path != final_path:
            shutil.copy(str(pdf_path), str(final_path))
            pdf_path = final_path

        st.success(f"Devis généré ✅ → {pdf_path}")
        with open(pdf_path, "rb") as f:
            st.download_button(
                "⬇️ Télécharger le PDF du devis",
                f,
                file_name=pdf_path.name,
                mime="application/pdf",
            )

        # On stocke comme référence la version AVEC (ou SANS, peu importe, il en faut une pour la facture)
        config["devis_counter"] = int(doc_number) + 1
        devis_history[str(int(doc_number))] = {
            "client_name": client_name,
            "client_address": client_address,
            "client_phone": client_phone,
            "df": df_avec_final.to_dict(),
            "total_ttc": float(total_ttc_avec),
            "notes": st.session_state.notes_avec,
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        with open(DEVIS_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(devis_history, f, ensure_ascii=False, indent=2)

# ---------- MODE FACTURE ----------
else:
    if not devis_history:
        st.warning("Aucun devis trouvé.")
    else:
        st.subheader("Transformer un Devis en Facture")

        devis_nums = sorted(devis_history.keys(), key=lambda x: int(x))
        selected_devis = st.selectbox(
            "Choisir le devis à facturer :",
            devis_nums,
            format_func=lambda x: f"Devis {x} — {devis_history[x].get('client_name','')}",
        )

        default_fact_num = config["facture_counter"]
        fact_number = st.number_input("Numéro Facture", value=int(default_fact_num), step=1)

        if st.button("Générer la Facture en PDF"):
            data = devis_history[selected_devis]
            client_name = data.get("client_name", "")
            client_address = data.get("client_address", "")
            client_phone = data.get("client_phone", "")
            df_saved = pd.DataFrame(data.get("df", {}))
            notes_saved = data.get("notes", [])

            doc_type = "Facture"
            pdf_path, file_name = generate_single_pdf(
                df_saved,
                client_name,
                client_address,
                client_phone,
                doc_type,
                int(fact_number),
                notes_saved,
            )

            st.success(f"{doc_type} {int(fact_number)} générée ✅ → {pdf_path}")
            with open(pdf_path, "rb") as f:
                st.download_button(
                    "⬇️ Télécharger la Facture PDF",
                    f,
                    file_name=file_name,
                    mime="application/pdf",
                )

            config["facture_counter"] = int(fact_number) + 1
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
