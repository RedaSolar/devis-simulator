// =========================================================
// TAQINOR Solar Quote Simulator — Application Logic
// =========================================================

const MONTHS_FR = ["Jan","Fév","Mar","Avr","Mai","Juin","Juil","Août","Sep","Oct","Nov","Déc"];

let roiChart = null;
let monthlyChart = null;
let currentProductLines = [];
let currentRoiResult = null;
let currentTotals = { sans: 0, avec: 0 };
let _roiDebounce = null;
let onduleurOptionsCache = {};  // cache: "{type}_{brand}" → [{power, phase, sell_ttc, buy_ttc}]
let _catalogCache = null;       // full catalog fetched once on load

// ---- Special product line type detection ----
function _getSpecialType(designation) {
    const d = (designation || '').toLowerCase().trim();
    if (d === 'onduleur réseau') return 'onduleur_reseau';
    if (d === 'onduleur hybride') return 'onduleur_hybride';
    if (d === 'panneaux') return 'panneaux';
    if (d === 'batterie') return 'batterie';
    return null;
}

function _catKeyForStype(stype) {
    if (stype === 'onduleur_reseau') return 'Onduleur Injection';
    if (stype === 'onduleur_hybride') return 'Onduleur Hybride';
    if (stype === 'panneaux') return 'Panneaux';
    if (stype === 'batterie') return 'Batterie';
    return null;
}

// Build <option> tags for power/phase dropdown from catalog entry
function _buildPowerOptsHtml(catEntry, brand, isOnduleur, unit, selPower, selPhase) {
    if (!catEntry || !brand || !catEntry[brand]) return '';
    const brandData = catEntry[brand];
    const powers = Object.keys(brandData)
        .filter(k => !isNaN(parseFloat(k)))
        .sort((a, b) => parseFloat(a) - parseFloat(b));
    let opts = '';
    if (isOnduleur) {
        for (const power of powers) {
            const pd = brandData[power];
            if (!pd?.variants) continue;
            const phases = Object.keys(pd.variants).sort();
            for (const phase of phases) {
                const vd = pd.variants[phase];
                if (!vd) continue;
                const label = `${power}kW — ${phase}`;
                const val = JSON.stringify({ power: parseFloat(power), phase, sell_ttc: vd.sell_ttc, buy_ttc: vd.buy_ttc });
                const isSel = selPower !== undefined &&
                    Math.abs(parseFloat(power) - parseFloat(selPower || 0)) < 0.01 &&
                    (!selPhase || phase === selPhase);
                opts += `<option value="${escHtml(val)}" ${isSel ? 'selected' : ''}>${escHtml(label)}</option>`;
            }
        }
    } else {
        for (const power of powers) {
            const pd = brandData[power];
            if (!pd) continue;
            const label = `${power} ${unit}`;
            const val = JSON.stringify({ power: parseFloat(power), sell_ttc: pd.sell_ttc, buy_ttc: pd.buy_ttc });
            const isSel = selPower !== undefined &&
                Math.abs(parseFloat(power) - parseFloat(selPower || 0)) < 0.01;
            opts += `<option value="${escHtml(val)}" ${isSel ? 'selected' : ''}>${escHtml(label)}</option>`;
        }
    }
    return opts;
}

// Build the <td> with brand + power cascading dropdowns for special rows
function _buildSpecialDropdownsTd(line, i) {
    const stype = _getSpecialType(line.designation);
    if (!stype || !_catalogCache) {
        return `<td>
            <input type="text" class="table-input" data-field="marque" data-idx="${i}"
                   value="${escHtml(line.marque || '')}" placeholder="Marque">
        </td>`;
    }
    const catKey = _catKeyForStype(stype);
    const catEntry = _catalogCache[catKey];
    if (!catEntry) {
        return `<td>
            <input type="text" class="table-input" data-field="marque" data-idx="${i}"
                   value="${escHtml(line.marque || '')}" placeholder="Marque">
        </td>`;
    }
    const isOnduleur = stype.startsWith('onduleur');
    const unit = stype === 'panneaux' ? 'W' : 'kWh';
    const brands = Object.keys(catEntry).filter(k => k !== '__default__');
    const selBrand = line._specBrand || line.marque || (brands[0] || '');
    const brandOpts = brands.map(b =>
        `<option value="${escHtml(b)}" ${b === selBrand ? 'selected' : ''}>${escHtml(b)}</option>`
    ).join('');
    const powerOpts = _buildPowerOptsHtml(catEntry, selBrand, isOnduleur, unit, line._specPower, line._specPhase);
    return `<td>
        <select class="table-input spec-brand" data-idx="${i}" data-stype="${escHtml(stype)}" style="margin-bottom:3px;width:100%;">
            ${brandOpts || '<option value="">— aucune marque —</option>'}
        </select>
        <select class="table-input spec-power" data-idx="${i}" data-stype="${escHtml(stype)}" style="width:100%;">
            ${powerOpts || '<option value="">— sélectionner puissance —</option>'}
        </select>
    </td>`;
}

// ---- Default lines suppression (admin, stored in localStorage) ----
const _HIDDEN_LINES_KEY = 'taqinor_hidden_lines';

function _getHiddenLines() {
    try { return JSON.parse(localStorage.getItem(_HIDDEN_LINES_KEY) || '[]'); } catch { return []; }
}
function _setHiddenLines(arr) {
    localStorage.setItem(_HIDDEN_LINES_KEY, JSON.stringify(arr));
}
function resetDefaultLines() {
    _setHiddenLines([]);
    renderDefaultLinesList();
    showToast('Table par défaut réinitialisée', 'success');
}
function renderDefaultLinesList() {
    const container = document.getElementById('default-lines-list');
    if (!container) return;
    const allLines = _allDefaultProductLines();
    const hidden = _getHiddenLines();
    container.innerHTML = allLines.map(des => {
        const isSuppressed = hidden.includes(des);
        return `<label style="display:flex;align-items:center;gap:8px;padding:4px 0;cursor:pointer;">
            <input type="checkbox" ${isSuppressed ? 'checked' : ''} onchange="toggleDefaultLine('${escHtml(des)}', this.checked)">
            <span style="${isSuppressed ? 'text-decoration:line-through;color:#aaa;' : ''}">${escHtml(des)}</span>
        </label>`;
    }).join('');
}
function toggleDefaultLine(designation, suppress) {
    const hidden = _getHiddenLines();
    if (suppress && !hidden.includes(designation)) {
        hidden.push(designation);
    } else if (!suppress) {
        const idx = hidden.indexOf(designation);
        if (idx !== -1) hidden.splice(idx, 1);
    }
    _setHiddenLines(hidden);
    renderDefaultLinesList();
}

// ---- Toast Notifications ----
function showToast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const icons = { success: '✓', danger: '✕', warning: '⚠', info: 'ℹ' };
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || 'ℹ'}</span>
        <span class="toast-msg">${message}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">×</button>
    `;
    container.appendChild(toast);
    if (duration > 0) {
        setTimeout(() => toast.remove(), duration);
    }
}

// ---- Tab Navigation ----
function showTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-link[data-tab]').forEach(el => el.classList.remove('active'));
    const tabEl = document.getElementById(`tab-${tabName}`);
    if (tabEl) tabEl.classList.add('active');
    const navEl = document.querySelector(`.nav-link[data-tab="${tabName}"]`);
    if (navEl) navEl.classList.add('active');

    // Load data for specific tabs
    if (tabName === 'history') loadHistory();
    if (tabName === 'catalog') loadCatalog();
    if (tabName === 'admin') { loadUsers(); renderDefaultLinesList(); }
}

// ---- Autoconsumption default by installation type ----
const DAY_USAGE_DEFAULTS = {
    'Résidentielle': 60,
    'Commerciale':   80,
    'Industrielle':  80,
    'Agricole':      100,
};

function updateDayUsageForType() {
    const type = document.getElementById('install-type')?.value || 'Résidentielle';
    const pct  = DAY_USAGE_DEFAULTS[type] ?? 50;
    const slider   = document.getElementById('day-usage');
    const sliderVal = document.getElementById('day-usage-val');
    if (slider)    { slider.value = pct; }
    if (sliderVal) { sliderVal.textContent = pct + '%'; }
    scheduleROI();
}

// ---- Initialize App ----
async function initApp() {
    if (!requireAuth()) return;
    const user = getUser();

    // Update UI with user info
    const userInfoEl = document.getElementById('user-info');
    if (userInfoEl && user) {
        userInfoEl.innerHTML = `
            <span class="user-badge">
                ${user.username}
                <span class="role">${user.role}</span>
            </span>
        `;
    }

    // Show/hide admin tab
    const adminTabBtn = document.getElementById('nav-admin');
    if (adminTabBtn) {
        adminTabBtn.style.display = (user && user.role === 'admin') ? 'inline-flex' : 'none';
    }

    // Apply role-based visibility (buy prices hidden for non-admins)
    applyRoleVisibility(user);

    // Set default doc number
    try {
        const res = await authFetch('/api/devis');
        if (res && res.ok) {
            const history = await res.json();
            const maxNum = history.reduce((m, d) => Math.max(m, parseInt(d.doc_number) || 0), 0);
            const docNumEl = document.getElementById('doc-number');
            if (docNumEl && docNumEl.value <= 0) {
                docNumEl.value = maxNum + 1;
            }
        }
    } catch (e) { /* non-critical */ }

    // Initialize monthly bills
    renderMonthlyInputs([500, 450, 400, 380, 360, 500, 700, 680, 580, 480, 430, 480]);

    // Show first tab
    showTab('devis');

    // Compute kWp from nb-panneaux × puissance-panneau — wire both events
    // so spinners (change) and keyboard (input) both trigger recalculation
    ['nb-panneaux', 'puissance-panneau'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input',  updateKwp);
            el.addEventListener('change', updateKwp);
            // Also schedule ROI auto-refresh when these change
            el.addEventListener('change', scheduleROI);
        }
    });
    updateKwp();

    // Auto-refresh ROI when day-usage slider changes
    document.getElementById('day-usage')?.addEventListener('change', scheduleROI);

    // Slider display
    const slider = document.getElementById('day-usage');
    if (slider) {
        const sliderVal = document.getElementById('day-usage-val');
        if (sliderVal) sliderVal.textContent = slider.value + '%';
        slider.addEventListener('input', () => {
            if (sliderVal) sliderVal.textContent = slider.value + '%';
        });
    }

    // Pre-fetch catalog so price auto-fill is instant on first edit
    _ensureCatalog();

    // Set autoconsumption default for initial type, then update on change
    updateDayUsageForType();
    document.getElementById('install-type')?.addEventListener('change', updateDayUsageForType);

    // Re-render simulation when scenario/recommended changes (no new API call needed)
    document.getElementById('scenario-choice')?.addEventListener('change', () => {
        const { v } = getScenario();
        const recEl = document.getElementById('recommended-option');
        const recVal = recEl?.value;
        // Auto-reset incompatible manual selections
        if (recVal !== 'Auto' && recVal !== 'Aucune recommandation') {
            if ((v === 'Sans batterie' && recVal === 'Avec batterie') ||
                (v === 'Avec batterie' && recVal === 'Sans batterie')) {
                if (recEl) recEl.value = 'Auto';
                showToast('Option recommandée réinitialisée en Auto (incompatible avec le scénario)', 'warning', 3000);
            }
        }
        updateTotals();
        if (currentRoiResult) {
            renderROISummary(currentRoiResult, currentTotals.sans, currentTotals.avec);
            renderMonthlyChart(currentRoiResult);
        }
    });

    document.getElementById('recommended-option')?.addEventListener('change', () => {
        const { v } = getScenario();
        const rec = document.getElementById('recommended-option')?.value;
        if ((v === 'Sans batterie' && rec === 'Avec batterie') ||
            (v === 'Avec batterie' && rec === 'Sans batterie')) {
            showToast('Attention : option recommandée incompatible avec le scénario sélectionné', 'warning', 4000);
        }
        updateTotals();
        if (currentRoiResult) {
            renderROISummary(currentRoiResult, currentTotals.sans, currentTotals.avec);
            renderMonthlyChart(currentRoiResult);
        }
    });

    // Default product lines table — render once now, then re-render after catalog loads
    // so that Onduleur/Panneaux/Batterie rows show brand+power dropdowns
    renderProductLines(getDefaultProductLines());
    _ensureCatalog().then(() => {
        renderProductLines(currentProductLines); // shows special dropdowns now that cache is ready
        currentProductLines.forEach((_, i) => autofillRowPrice(i));
    });
}

function isAdmin() { return getUser()?.role === 'admin'; }
function isCommercial() { return getUser()?.role === 'commercial'; }

function getScenario() {
    const v = document.getElementById('scenario-choice')?.value || 'Les deux (Sans + Avec)';
    return { v, showSans: v !== 'Avec batterie', showAvec: v !== 'Sans batterie' };
}
function getRecommended() {
    const val = document.getElementById('recommended-option')?.value || 'Auto';
    if (val !== 'Auto') return val;
    // Auto: resolve based on scenario and ROI data
    const { v } = getScenario();
    if (v === 'Sans batterie') return 'Sans batterie';
    if (v === 'Avec batterie') return 'Avec batterie';
    // Both options: pick the one with lower payback (shorter ROI = better)
    if (currentRoiResult) {
        const ps = currentRoiResult.payback_sans ?? 0;
        const pa = currentRoiResult.payback_avec ?? 0;
        if (ps <= 0 && pa <= 0) return 'Aucune recommandation';
        if (ps <= 0) return 'Avec batterie';
        if (pa <= 0) return 'Sans batterie';
        return ps <= pa ? 'Sans batterie' : 'Avec batterie';
    }
    return 'Aucune recommandation';
}

function applyRoleVisibility(user) {
    const admin = user?.role === 'admin';
    const commercial = user?.role === 'commercial';
    // Hide .admin-only elements (buy-price inputs in catalog add-forms)
    document.querySelectorAll('.admin-only').forEach(el => {
        el.style.display = admin ? '' : 'none';
    });
    // Hide buy-price column header in product lines table
    const thAchat = document.getElementById('th-prix-achat');
    if (thAchat) thAchat.style.display = admin ? '' : 'none';

    // Commercial role: simplified devis view
    const navCatalog = document.getElementById('nav-catalog');
    if (navCatalog) navCatalog.style.display = commercial ? 'none' : '';

    const navHistory = document.getElementById('nav-history');
    if (navHistory) navHistory.style.display = commercial ? 'none' : '';

    const hiddenForCommercial = ['section-product-lines', 'section-custom-lines', 'section-notes', 'tech-params-advanced', 'tech-struct-group'];
    hiddenForCommercial.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = commercial ? 'none' : '';
    });

    const btnAutofill = document.getElementById('btn-autofill');
    if (btnAutofill) btnAutofill.style.display = commercial ? 'none' : '';

    const btnPrepare = document.getElementById('btn-prepare-devis');
    if (btnPrepare) btnPrepare.style.display = commercial ? '' : 'none';

    const btnCalcRoi = document.getElementById('btn-calc-roi');
    if (btnCalcRoi) btnCalcRoi.style.display = commercial ? 'none' : '';
}

function _allDefaultProductLines() {
    return [
        "Onduleur réseau",
        "Onduleur hybride",
        "Smart Meter",
        "Wifi Dongle",
        "Panneaux",
        "Batterie",
        "Batterie",
        "Structures acier",
        "Structures aluminium",
        "Socles",
        "Accessoires",
        "Tableau De Protection AC/DC",
        "Installation",
        "Transport",
        "Suivi journalier, maintenance chaque 12 mois pendent 2 ans",
    ];
}

function getDefaultProductLines() {
    const hidden = _getHiddenLines();
    const all = [
        { designation: "Onduleur réseau",   marque: "", quantite: 1, prix_achat_ttc: 0, prix_unit_ttc: 0, tva: 20 },
        { designation: "Onduleur hybride",  marque: "", quantite: 1, prix_achat_ttc: 0, prix_unit_ttc: 0, tva: 20 },
        { designation: "Smart Meter",       marque: "", quantite: 0, prix_achat_ttc: 0, prix_unit_ttc: 0, tva: 20 },
        { designation: "Wifi Dongle",       marque: "", quantite: 0, prix_achat_ttc: 0, prix_unit_ttc: 0, tva: 20 },
        { designation: "Panneaux",          marque: "", quantite: 0, prix_achat_ttc: 0, prix_unit_ttc: 0, tva: 20 },
        { designation: "Batterie",          marque: "", quantite: 1, prix_achat_ttc: 0, prix_unit_ttc: 0, tva: 20 },
        { designation: "Batterie",          marque: "", quantite: 0, prix_achat_ttc: 0, prix_unit_ttc: 0, tva: 20 },
        { designation: "Structures acier",  marque: "", quantite: 0, prix_achat_ttc: 0, prix_unit_ttc: 0, tva: 20 },
        { designation: "Structures aluminium", marque: "", quantite: 0, prix_achat_ttc: 0, prix_unit_ttc: 0, tva: 20 },
        { designation: "Socles",            marque: "", quantite: 0, prix_achat_ttc: 0, prix_unit_ttc: 0, tva: 20 },
        { designation: "Accessoires",       marque: "", quantite: 1, prix_achat_ttc: 0, prix_unit_ttc: 0, tva: 20 },
        { designation: "Tableau De Protection AC/DC", marque: "", quantite: 1, prix_achat_ttc: 0, prix_unit_ttc: 0, tva: 20 },
        { designation: "Installation",      marque: "", quantite: 1, prix_achat_ttc: 0, prix_unit_ttc: 0, tva: 20 },
        { designation: "Transport",         marque: "", quantite: 1, prix_achat_ttc: 0, prix_unit_ttc: 0, tva: 20 },
        { designation: "Suivi journalier, maintenance chaque 12 mois pendent 2 ans", marque: "", quantite: 1, prix_achat_ttc: 0, prix_unit_ttc: 0, tva: 20 },
    ];
    if (!hidden.length) return all;
    // Filter hidden lines (track count for duplicate designations like "Batterie")
    const hiddenCount = {};
    return all.filter(line => {
        const des = line.designation;
        if (!hidden.includes(des)) return true;
        // For duplicates, suppress only the first occurrence that matches
        hiddenCount[des] = (hiddenCount[des] || 0) + 1;
        return false; // suppress all matching
    });
}

// ---- Monthly Inputs ----
function renderMonthlyInputs(values) {
    const grid = document.getElementById('monthly-grid');
    if (!grid) return;
    grid.innerHTML = '';
    MONTHS_FR.forEach((month, i) => {
        const val = (values && values[i] !== undefined) ? values[i] : 500;
        const wrapper = document.createElement('div');
        wrapper.className = 'month-input-wrapper';
        wrapper.innerHTML = `
            <span class="month-label">${month}</span>
            <input type="number" class="form-control month-input" id="month-${i}"
                   value="${Math.round(val)}" min="0" step="10" placeholder="0">
        `;
        grid.appendChild(wrapper);
        // Auto-refresh simulation when user edits a bill directly
        wrapper.querySelector('input').addEventListener('change', scheduleROI);
    });
}

function getMonthlyValues() {
    return MONTHS_FR.map((_, i) => {
        const el = document.getElementById(`month-${i}`);
        return el ? parseFloat(el.value) || 0 : 0;
    });
}

// ---- Estimate Months ----
async function estimateMonths() {
    const fHiver = parseFloat(document.getElementById('f-hiver')?.value) || 0;
    const fEte = parseFloat(document.getElementById('f-ete')?.value) || 0;
    if (fHiver <= 0 && fEte <= 0) {
        showToast('Entrez au moins une facture (hiver ou été)', 'warning');
        return;
    }
    const btn = document.getElementById('btn-estimate-months');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Calcul...'; }
    try {
        const res = await authFetch('/api/roi/estimate-months', {
            method: 'POST',
            body: JSON.stringify({ f_hiver: fHiver, f_ete: fEte }),
        });
        if (!res) return;
        if (!res.ok) {
            const err = await res.json();
            showToast('Erreur: ' + (err.detail || 'Inconnue'), 'danger');
            return;
        }
        const data = await res.json();
        renderMonthlyInputs(data.monthly);
        scheduleROI();
        showToast('Factures mensuelles estimées!', 'success');
    } catch (e) {
        showToast('Erreur réseau: ' + e.message, 'danger');
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '📊 Estimer 12 mois'; }
    }
}

// ---- Bill Estimator Sync (client-side interpolation, mirrors Python interpoler_factures) ----
function interpolerFactures(hiver, ete) {
    if (ete <= 0) return Array(12).fill(hiver);
    const premiere = Array.from({length: 7}, (_, i) => hiver + (ete - hiver) / 6 * i);
    const seconde  = Array.from({length: 5}, (_, i) => ete  - (ete - hiver) / 4 * i);
    return [...premiere, ...seconde];
}

function syncBillEstimator() {
    const fHiver = parseFloat(document.getElementById('f-hiver')?.value) || 0;
    const fEte   = parseFloat(document.getElementById('f-ete')?.value)   || 0;
    if (fHiver <= 0) return;

    // Estimate panel count: 8 panels per 900 MAD of winter bill
    const suggested = Math.floor(fHiver / 900) * 8;
    if (suggested > 0) {
        const nbEl = document.getElementById('nb-panneaux');
        if (nbEl) { nbEl.value = suggested; updateKwp(); }
    }

    renderMonthlyInputs(interpolerFactures(fHiver, fEte > 0 ? fEte : fHiver));
    scheduleROI();
}

// ---- Computed kWp ----
function updateKwp() {
    const nb  = parseInt(document.getElementById('nb-panneaux')?.value) || 0;
    const w   = parseFloat(document.getElementById('puissance-panneau')?.value) || 0;
    const kwp = nb * w / 1000;
    const hidden = document.getElementById('puissance-kwp');
    if (hidden) hidden.value = kwp > 0 ? kwp.toFixed(3) : '';
    const disp = document.getElementById('kwp-display');
    if (disp) disp.textContent = kwp > 0 ? kwp.toFixed(2) + ' kWp' : '—';
}

// ---- Auto-fill ----
async function autoFill() {
    const kwp = parseFloat(document.getElementById('puissance-kwp')?.value) || 0;
    const panW = parseInt(document.getElementById('puissance-panneau')?.value) || 710;
    if (kwp <= 0) {
        showToast('Entrez le nombre de panneaux', 'warning');
        return;
    }
    const btn = document.getElementById('btn-autofill');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Remplissage...'; }
    try {
        const res = await authFetch('/api/autofill', {
            method: 'POST',
            body: JSON.stringify({ puissance_kwp: kwp, puissance_panneau_w: panW }),
        });
        if (!res) return;
        if (!res.ok) {
            const err = await res.json();
            showToast('Erreur autofill: ' + (err.detail || 'Inconnue'), 'danger');
            return;
        }
        const data = await res.json();
        const lines = Array.isArray(data) ? data : (data.rows || []);
        const onduleurMeta = Array.isArray(data) ? {} : (data.onduleur_options || {});
        // Sync spec selections from autofill metadata into line data
        lines.forEach(line => {
            const stype = _getSpecialType(line.designation);
            if (stype === 'onduleur_reseau' && onduleurMeta.reseau) {
                line._specBrand = onduleurMeta.reseau.brand || line.marque;
                line._specPower = onduleurMeta.reseau.power;
                line._specPhase = onduleurMeta.reseau.phase;
            } else if (stype === 'onduleur_hybride' && onduleurMeta.hybride) {
                line._specBrand = onduleurMeta.hybride.brand || line.marque;
                line._specPower = onduleurMeta.hybride.power;
                line._specPhase = onduleurMeta.hybride.phase;
            } else if (line.marque) {
                line._specBrand = line.marque;
            }
        });
        currentProductLines = lines;
        // Sync autofilled onduleur power/phase into the Section 3 fields
        _syncOnduleurSection3(onduleurMeta);
        renderProductLines(lines, onduleurMeta);
        updateTotals();
        scheduleROI();
        showToast('Produits auto-remplis depuis le catalogue!', 'success');
    } catch (e) {
        showToast('Erreur réseau: ' + e.message, 'danger');
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '⚡ Auto-remplir'; }
    }
}

// ---- Préparer le devis (commercial shortcut: autofill + ROI) ----
async function prepareDevis() {
    const kwp = parseFloat(document.getElementById('puissance-kwp')?.value) || 0;
    if (kwp <= 0) {
        showToast('Entrez le nombre de panneaux', 'warning');
        return;
    }
    const btn = document.getElementById('btn-prepare-devis');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Préparation...'; }
    try {
        await autoFill();
        await calculateROI();
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '⚡ Préparer le devis'; }
    }
}


// ---- Onduleur catalog helpers ----
async function fetchOnduleurOptions(type, brand) {
    const key = `${type}_${brand}`;
    if (onduleurOptionsCache[key]) return onduleurOptionsCache[key];
    try {
        const res = await authFetch(`/api/autofill/onduleur-options?type=${encodeURIComponent(type)}&brand=${encodeURIComponent(brand)}`);
        if (!res || !res.ok) return [];
        const data = await res.json();
        onduleurOptionsCache[key] = data;
        return data;
    } catch (e) {
        console.error('Failed to fetch onduleur options:', e);
        return [];
    }
}

function _syncOnduleurSection3(onduleurMeta) {
    // Sync autofill-selected onduleur into the Section 3 kW/phase fields
    const meta = onduleurMeta.reseau || onduleurMeta.hybride;
    if (!meta) return;
    const kwInput = document.getElementById('onduleur-kw');
    if (kwInput && meta.power) kwInput.value = meta.power;
    const phaseVal = (meta.phase || 'Monophasé').toLowerCase().includes('tri') ? 'Triphasé' : 'Monophasé';
    const phaseRadio = document.querySelector(`input[name="onduleur-phase"][value="${phaseVal}"]`);
    if (phaseRadio) phaseRadio.checked = true;
}

// ---- Product Lines Table ----
// ---- Catalog price auto-fill ----
async function _ensureCatalog() {
    if (_catalogCache) return _catalogCache;
    try {
        const res = await authFetch('/api/catalog');
        if (res && res.ok) _catalogCache = await res.json();
    } catch (_) {}
    return _catalogCache;
}

function _catalogKeyFor(designation) {
    const d = (designation || '').toLowerCase().trim();
    if (!d) return null;
    if (d.includes('onduleur') || d === 'panneaux' || d.startsWith('panneau') || d === 'batterie') return null;
    if (d.startsWith('structures')) return 'Structures';
    // Match canonical names case-insensitively
    const canonicals = ['Smart Meter','Wifi Dongle','Socles','Accessoires',
        'Tableau De Protection AC/DC','Installation','Transport',
        'Suivi journalier, maintenance chaque 12 mois pendent 2 ans'];
    for (const c of canonicals) {
        if (d === c.toLowerCase()) return c;
    }
    return designation; // fallback: try as-is
}

async function autofillRowPrice(idx) {
    const line = currentProductLines[idx];
    if (!line) return;
    if (line.prix_unit_ttc && line.prix_unit_ttc > 0) return; // already has a price
    const catKey = _catalogKeyFor(line.designation);
    if (!catKey) return; // onduleur/panneaux/batterie — needs brand+power, skip
    const catalog = await _ensureCatalog();
    if (!catalog) return;
    const entry = catalog[catKey]?.['__default__'];
    if (!entry || !entry.sell_ttc) return;

    // Write price into model
    line.prix_unit_ttc  = entry.sell_ttc;
    if (entry.buy_ttc != null) line.prix_achat_ttc = entry.buy_ttc;

    // Update UI inputs on the same row
    const tr = document.querySelector(`tr[data-idx="${idx}"]`);
    const puIn = tr?.querySelector('[data-field="prix_unit_ttc"]');
    const paIn = tr?.querySelector('[data-field="prix_achat_ttc"]');
    if (puIn) puIn.value = entry.sell_ttc;
    if (paIn && entry.buy_ttc != null) paIn.value = entry.buy_ttc;

    // Recompute row total display
    const total = (line.prix_unit_ttc || 0) * (line.quantite || 0);
    const totalEl = document.querySelector(`.row-total[data-idx="${idx}"]`);
    if (totalEl) totalEl.textContent = formatMoney(total);

    updateTotals();
    scheduleROI();
}

function renderProductLines(lines, onduleurMeta) {
    onduleurMeta = onduleurMeta || {};
    currentProductLines = lines || [];
    const tbody = document.getElementById('product-lines-tbody');
    if (!tbody) return;
    const showBuy = isAdmin();
    tbody.innerHTML = '';
    lines.forEach((line, i) => {
        const tr = document.createElement('tr');
        tr.dataset.idx = i;
        const des = line.designation || '';
        const stype = _getSpecialType(des);

        // Build marque cell — cascading brand+power dropdowns for special types
        const marqueTd = stype ? _buildSpecialDropdownsTd(line, i) : `<td>
            <input type="text" class="table-input" data-field="marque" data-idx="${i}"
                   value="${escHtml(line.marque || '')}" placeholder="Marque">
        </td>`;

        tr.innerHTML = `
            <td>
                <input type="text" class="table-input table-input-wide" data-field="designation" data-idx="${i}"
                       value="${escHtml(des)}" placeholder="Désignation">
            </td>
            ${marqueTd}
            <td>
                <input type="number" class="table-input table-input-num" data-field="quantite" data-idx="${i}"
                       value="${line.quantite || 0}" min="0" step="1">
            </td>
            <td>
                <input type="number" class="table-input table-input-num" data-field="prix_unit_ttc" data-idx="${i}"
                       value="${line.prix_unit_ttc || 0}" min="0" step="100">
            </td>
            ${showBuy ? `<td>
                <input type="number" class="table-input table-input-num" data-field="prix_achat_ttc" data-idx="${i}"
                       value="${line.prix_achat_ttc || 0}" min="0" step="100">
            </td>` : ''}
            <td>
                <select class="table-input" data-field="tva" data-idx="${i}">
                    ${[0,7,10,14,20].map(v => `<option value="${v}" ${v === (line.tva || 20) ? 'selected' : ''}>${v}%</option>`).join('')}
                </select>
            </td>
            <td class="text-right">
                <span class="row-total" data-idx="${i}">${formatMoney(line.prix_unit_ttc * line.quantite)}</span>
            </td>
            <td>
                <button class="btn btn-danger btn-sm" onclick="removeProductLine(${i})" title="Supprimer">×</button>
            </td>
        `;
        tbody.appendChild(tr);
    });

    // Attach change listeners to all data-field inputs/selects
    tbody.querySelectorAll('[data-field]').forEach(el => {
        el.addEventListener('input', onProductLineChange);
        el.addEventListener('change', onProductLineChange);
    });

    // spec-brand: rebuild power dropdown when brand changes
    tbody.querySelectorAll('.spec-brand').forEach(sel => {
        sel.addEventListener('change', () => {
            const idx = parseInt(sel.dataset.idx);
            const stype = sel.dataset.stype;
            const brand = sel.value;
            currentProductLines[idx]._specBrand = brand;
            currentProductLines[idx].marque = brand;
            currentProductLines[idx]._specPower = undefined;
            currentProductLines[idx].prix_unit_ttc = 0;
            currentProductLines[idx].prix_achat_ttc = 0;
            const tr = sel.closest('tr');
            const powerSel = tr?.querySelector('.spec-power');
            if (powerSel && _catalogCache) {
                const catKey = _catKeyForStype(stype);
                const catEntry = _catalogCache[catKey];
                const isOnd = stype.startsWith('onduleur');
                const unit = stype === 'panneaux' ? 'W' : 'kWh';
                powerSel.innerHTML = _buildPowerOptsHtml(catEntry, brand, isOnd, unit) ||
                    '<option value="">— sélectionner puissance —</option>';
            }
            updateTotals();
        });
    });

    // spec-power: fill price and sync Section 3 for onduleurs
    tbody.querySelectorAll('.spec-power').forEach(sel => {
        sel.addEventListener('change', _applySpecPower);
        // Auto-apply first option price on load if price is 0
        if (sel.options.length && sel.value) {
            const idx = parseInt(sel.dataset.idx);
            const line = currentProductLines[idx];
            if (line && !(line.prix_unit_ttc > 0)) {
                _applySpecPower({ target: sel });
            }
        }
    });

    updateTotals();
}

function _applySpecPower(e) {
    const sel = e.target;
    const idx = parseInt(sel.dataset.idx);
    const stype = sel.dataset.stype;
    if (!sel.value) return;
    try {
        const opt = JSON.parse(sel.value);
        const line = currentProductLines[idx];
        if (!line) return;
        line.prix_unit_ttc = opt.sell_ttc || 0;
        line.prix_achat_ttc = opt.buy_ttc || 0;
        line._specPower = opt.power;
        if (opt.phase) line._specPhase = opt.phase;
        // Sync brand from the sibling brand select
        const tr = sel.closest('tr');
        const brandSel = tr?.querySelector('.spec-brand');
        if (brandSel) { line._specBrand = brandSel.value; line.marque = brandSel.value; }
        // Update visible price inputs
        const puIn = tr?.querySelector('[data-field="prix_unit_ttc"]');
        const paIn = tr?.querySelector('[data-field="prix_achat_ttc"]');
        if (puIn) puIn.value = opt.sell_ttc || 0;
        if (paIn) paIn.value = opt.buy_ttc || 0;
        // Sync Section 3 for onduleurs
        if (stype && stype.startsWith('onduleur')) {
            if (opt.power) {
                const kwInput = document.getElementById('onduleur-kw');
                if (kwInput) kwInput.value = opt.power;
            }
            if (opt.phase) {
                const phaseVal = opt.phase.toLowerCase().includes('tri') ? 'Triphasé' : 'Monophasé';
                const phaseRadio = document.querySelector(`input[name="onduleur-phase"][value="${phaseVal}"]`);
                if (phaseRadio) phaseRadio.checked = true;
            }
        }
        const total = (opt.sell_ttc || 0) * (line.quantite || 0);
        const totalEl = document.querySelector(`.row-total[data-idx="${idx}"]`);
        if (totalEl) totalEl.textContent = formatMoney(total);
        updateTotals();
        scheduleROI();
    } catch (_) {}
}

function onProductLineChange(e) {
    const el = e.target;
    const idx = parseInt(el.dataset.idx);
    const field = el.dataset.field;
    if (idx < 0 || idx >= currentProductLines.length) return;

    if (field === 'onduleur_power_phase') {
        // Power/phase dropdown changed — update prices and sync Section 3
        try {
            const opt = JSON.parse(el.value);
            if (opt.sell_ttc != null) {
                currentProductLines[idx].prix_unit_ttc = opt.sell_ttc;
                currentProductLines[idx].prix_achat_ttc = opt.buy_ttc || 0;
                const tr = el.closest('tr');
                const puIn = tr?.querySelector('[data-field="prix_unit_ttc"]');
                const paIn = tr?.querySelector('[data-field="prix_achat_ttc"]');
                if (puIn) puIn.value = opt.sell_ttc;
                if (paIn) paIn.value = opt.buy_ttc || 0;
            }
            // Sync Section 3 onduleur kW/phase fields
            if (opt.power) {
                const kwInput = document.getElementById('onduleur-kw');
                if (kwInput) kwInput.value = opt.power;
            }
            if (opt.phase) {
                const phaseVal = opt.phase.toLowerCase().includes('tri') ? 'Triphasé' : 'Monophasé';
                const phaseRadio = document.querySelector(`input[name="onduleur-phase"][value="${phaseVal}"]`);
                if (phaseRadio) phaseRadio.checked = true;
            }
        } catch (_) { /* ignore JSON parse errors */ }
    } else {
        const val = (field === 'designation' || field === 'marque') ? el.value : parseFloat(el.value) || 0;
        currentProductLines[idx][field] = val;
        // Auto-fill price from catalog when designation changes or qty becomes non-zero
        if (field === 'designation') {
            currentProductLines[idx].prix_unit_ttc = 0;
            if (_getSpecialType(val) && _catalogCache) {
                // Special type: re-render to show brand+power dropdowns
                renderProductLines(currentProductLines);
                return;
            }
            autofillRowPrice(idx);
        } else if (field === 'quantite' && val > 0) {
            autofillRowPrice(idx);
        }
    }

    // Update row total
    const line = currentProductLines[idx];
    const total = (line.prix_unit_ttc || 0) * (line.quantite || 0);
    const totalEl = document.querySelector(`.row-total[data-idx="${idx}"]`);
    if (totalEl) totalEl.textContent = formatMoney(total);

    updateTotals();
    scheduleROI();
}

function addProductLine() {
    currentProductLines.push({ designation: "", marque: "", quantite: 0, prix_achat_ttc: 0, prix_unit_ttc: 0, tva: 20 });
    renderProductLines(currentProductLines);
}

function removeProductLine(idx) {
    currentProductLines.splice(idx, 1);
    renderProductLines(currentProductLines);
}

function applyDiscount() {
    updateTotals();
    scheduleROI();
}

function updateTotals() {
    const lines = getCurrentProductLines();
    const { showSans, showAvec } = getScenario();
    const recommended = getRecommended();

    // SANS: exclude Batterie and Onduleur hybride
    const sanLines = lines.filter(l => !['Batterie', 'Onduleur hybride'].includes(l.designation));
    // AVEC: exclude Onduleur réseau
    const avecLines = lines.filter(l => l.designation !== 'Onduleur réseau');

    const totalSans = sanLines.reduce((s, l) => s + (l.prix_unit_ttc * l.quantite), 0);
    const totalAvec = avecLines.reduce((s, l) => s + (l.prix_unit_ttc * l.quantite), 0);

    // Apply discount
    const pct = parseFloat(document.getElementById('discount-pct')?.value) || 0;
    const discSans = pct > 0 ? Math.round(totalSans * (1 - pct / 100)) : totalSans;
    const discAvec = pct > 0 ? Math.round(totalAvec * (1 - pct / 100)) : totalAvec;

    const elSans = document.getElementById('total-sans');
    const elAvec = document.getElementById('total-avec');
    if (elSans) elSans.textContent = formatMoney(totalSans);
    if (elAvec) elAvec.textContent = formatMoney(totalAvec);

    // Show/hide discount final totals
    const elSansFinal = document.getElementById('total-sans-final');
    const elAvecFinal = document.getElementById('total-avec-final');
    const tiSansFinal = document.getElementById('total-item-sans-final');
    const tiAvecFinal = document.getElementById('total-item-avec-final');
    if (elSansFinal) elSansFinal.textContent = formatMoney(discSans);
    if (elAvecFinal) elAvecFinal.textContent = formatMoney(discAvec);
    if (tiSansFinal) tiSansFinal.style.display = (pct > 0 && showSans) ? '' : 'none';
    if (tiAvecFinal) tiAvecFinal.style.display = (pct > 0 && showAvec) ? '' : 'none';

    // Show/hide total rows and mark recommended
    const tiSans = document.getElementById('total-item-sans');
    const tiAvec = document.getElementById('total-item-avec');
    if (tiSans) {
        tiSans.style.display = showSans ? '' : 'none';
        tiSans.querySelector('.total-label').textContent =
            'Total SANS batterie' + (recommended === 'Sans batterie' ? ' ⭐' : '');
    }
    if (tiAvec) {
        tiAvec.style.display = showAvec ? '' : 'none';
        tiAvec.querySelector('.total-label').textContent =
            'Total AVEC batterie' + (recommended === 'Avec batterie' ? ' ⭐' : '');
    }

    return { totalSans: discSans, totalAvec: discAvec };
}

function getCurrentProductLines() {
    // Read directly from DOM inputs so changes are always fresh
    const tbody = document.getElementById('product-lines-tbody');
    if (!tbody) return currentProductLines;
    const result = [];
    tbody.querySelectorAll('tr[data-idx]').forEach(tr => {
        const idx = parseInt(tr.dataset.idx);
        if (isNaN(idx) || idx < 0 || idx >= currentProductLines.length) return;
        const base = currentProductLines[idx];
        const g = (field) => tr.querySelector(`[data-field="${field}"]`);
        result.push({
            ...base,
            designation:   g('designation')?.value   ?? base.designation,
            marque:        g('marque')?.value         ?? base.marque,
            quantite:      parseFloat(g('quantite')?.value   ?? base.quantite)   || 0,
            prix_unit_ttc: parseFloat(g('prix_unit_ttc')?.value ?? base.prix_unit_ttc) || 0,
            prix_achat_ttc:parseFloat(g('prix_achat_ttc')?.value ?? base.prix_achat_ttc) || 0,
            tva:           parseFloat(g('tva')?.value ?? base.tva) || 20,
        });
    });
    return result.length ? result : currentProductLines;
}

// ---- Custom Lines ----
function addCustomLine(scenario) {
    const tbody = document.getElementById(`custom-${scenario}-tbody`);
    if (!tbody) return;
    const idx = tbody.children.length;
    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td><input type="text" class="table-input table-input-wide" placeholder="Désignation" name="custom_des_${scenario}_${idx}"></td>
        <td><input type="text" class="table-input" placeholder="Marque" name="custom_marque_${scenario}_${idx}"></td>
        <td><input type="number" class="table-input table-input-num" placeholder="0" min="0" step="1" name="custom_qty_${scenario}_${idx}" value="1"></td>
        <td><input type="number" class="table-input table-input-num" placeholder="0" min="0" name="custom_pu_${scenario}_${idx}" value="0"></td>
        <td><input type="number" class="table-input table-input-num" placeholder="0" min="0" name="custom_pa_${scenario}_${idx}" value="0"></td>
        <td>
            <select class="table-input" name="custom_tva_${scenario}_${idx}">
                ${[0,7,10,14,20].map(v => `<option value="${v}" ${v===20?'selected':''}>${v}%</option>`).join('')}
            </select>
        </td>
        <td><button class="btn btn-danger btn-sm" onclick="this.closest('tr').remove()">×</button></td>
    `;
    tbody.appendChild(tr);
}

function getCustomLines(scenario) {
    const tbody = document.getElementById(`custom-${scenario}-tbody`);
    if (!tbody) return [];
    const lines = [];
    tbody.querySelectorAll('tr').forEach((tr, i) => {
        const des = tr.querySelector(`[name^="custom_des_${scenario}"]`)?.value || '';
        if (!des.trim()) return;
        lines.push({
            designation: des.trim(),
            marque: tr.querySelector(`[name^="custom_marque_${scenario}"]`)?.value || '',
            quantite: parseFloat(tr.querySelector(`[name^="custom_qty_${scenario}"]`)?.value) || 0,
            prix_unit_ttc: parseFloat(tr.querySelector(`[name^="custom_pu_${scenario}"]`)?.value) || 0,
            prix_achat_ttc: parseFloat(tr.querySelector(`[name^="custom_pa_${scenario}"]`)?.value) || 0,
            tva: parseFloat(tr.querySelector(`[name^="custom_tva_${scenario}"]`)?.value) || 20,
        });
    });
    return lines;
}

// ---- Notes ----
function addNote(scenario) {
    const container = document.getElementById(`notes-${scenario}`);
    if (!container) return;
    const row = document.createElement('div');
    row.className = 'note-row';
    row.innerHTML = `
        <textarea placeholder="Texte de la note..." rows="1"></textarea>
        <button class="btn btn-danger btn-sm" onclick="this.closest('.note-row').remove()">×</button>
    `;
    container.appendChild(row);
}

function getNotes(scenario) {
    const container = document.getElementById(`notes-${scenario}`);
    if (!container) return [];
    return Array.from(container.querySelectorAll('textarea'))
        .map(el => el.value.trim())
        .filter(Boolean);
}

// ---- Calculate ROI ----
// silent=true: skip toasts (used for auto-refresh on field change)
async function calculateROI(silent = false) {
    const kwp = parseFloat(document.getElementById('puissance-kwp')?.value) || 0;
    if (kwp <= 0) { if (!silent) showToast('Entrez le nombre de panneaux', 'warning'); return; }

    const factures = getMonthlyValues();
    if (!factures.some(v => v > 0)) { if (!silent) showToast('Entrez vos factures mensuelles', 'warning'); return; }

    const dayPct = parseInt(document.getElementById('day-usage')?.value) || 50;
    const { totalSans, totalAvec } = updateTotals();

    // Compute total battery kWh from product table (same logic as devis_router.py)
    let batteryKwh = 0;
    getCurrentProductLines().forEach(line => {
        const des = (line.designation || '').toLowerCase();
        if (!des.includes('batterie')) return;
        const qty = line.quantite ?? 0;
        const searchStr = des + ' ' + (line.marque || '').toLowerCase();
        const m = searchStr.match(/(\d+(?:\.\d+)?)\s*kwh/);
        batteryKwh += qty * (m ? parseFloat(m[1]) : 5.0);
    });

    const btn = document.getElementById('btn-calc-roi');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Calcul...'; }

    try {
        const res = await authFetch('/api/roi/calculate', {
            method: 'POST',
            body: JSON.stringify({
                puissance_kwp: kwp,
                factures_mensuelles: factures,
                day_usage_percent: dayPct,
                total_cost_sans: totalSans,
                total_cost_avec: totalAvec,
                battery_capacity_kwh: batteryKwh,
            }),
        });
        if (!res) return;
        if (!res.ok) {
            if (!silent) { const err = await res.json(); showToast('Erreur ROI: ' + (err.detail || 'Inconnue'), 'danger'); }
            return;
        }
        const data = await res.json();
        currentRoiResult = data;
        currentTotals = { sans: totalSans, avec: totalAvec };
        updateTotals();  // refresh ⭐ labels now that Auto recommendation is resolved
        renderROISummary(data, totalSans, totalAvec);
        renderMonthlyChart(data);
        if (!silent) showToast('Simulation actualisée', 'success', 2000);
    } catch (e) {
        if (!silent) showToast('Erreur réseau: ' + e.message, 'danger');
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '🔄 Actualiser'; }
    }
}

// ---- Monthly savings chart ----
function renderMonthlyChart(data) {
    const ctx = document.getElementById('roi-monthly-chart');
    if (!ctx) return;
    if (monthlyChart) { monthlyChart.destroy(); }
    const months = ['Jan','Fév','Mar','Avr','Mai','Jun','Jul','Aoû','Sep','Oct','Nov','Déc'];
    const { showSans, showAvec } = getScenario();
    const recommended = getRecommended();
    const sansRec = recommended === 'Sans batterie';
    const avecRec = recommended === 'Avec batterie';

    const datasets = [
        {
            label: 'Facture ONEE (MAD)',
            data: data.monthly_detail.map(d => d.facture),
            backgroundColor: 'rgba(181,192,206,0.55)',
            borderColor: 'rgba(181,192,206,0.8)',
            borderWidth: 1,
            borderRadius: 3,
            order: 2,
        },
    ];
    if (showSans) {
        datasets.push({
            label: 'Option 1 – Sans batterie' + (sansRec ? ' ⭐' : ''),
            data: data.eco_sans_monthly,
            type: 'line',
            borderColor: '#1A2B4A',
            backgroundColor: 'transparent',
            borderWidth: sansRec ? 3.5 : 2.2,
            pointRadius: sansRec ? 5 : 4,
            tension: 0.3,
            order: 1,
        });
    }
    if (showAvec) {
        datasets.push({
            label: 'Option 2 – Avec batterie' + (avecRec ? ' ⭐' : ''),
            data: data.eco_avec_monthly,
            type: 'line',
            borderColor: '#F5A623',
            backgroundColor: 'transparent',
            borderWidth: avecRec ? 3.5 : 2.2,
            pointRadius: avecRec ? 5 : 4,
            tension: 0.3,
            order: 0,
        });
    }

    monthlyChart = new Chart(ctx, {
        type: 'bar',
        data: { labels: months, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { position: 'top', labels: { font: { size: 11 } } },
                tooltip: { callbacks: { label: c => `${c.dataset.label}: ${Math.round(c.parsed.y).toLocaleString('fr-MA')} MAD` } },
            },
            scales: {
                x: { grid: { display: false } },
                y: {
                    title: { display: true, text: 'MAD / mois' },
                    grid: { color: 'rgba(0,0,0,0.05)' },
                    ticks: { callback: v => v.toLocaleString('fr-MA') },
                },
            },
        },
    });
    const wrapper = document.getElementById('roi-monthly-wrapper');
    if (wrapper) wrapper.style.display = '';
}

// ---- Auto-refresh scheduler (debounced) ----
function scheduleROI() {
    clearTimeout(_roiDebounce);
    _roiDebounce = setTimeout(() => calculateROI(true), 900);
}

function renderROISummary(data, totalSans, totalAvec) {
    const el = document.getElementById('roi-metrics');
    if (!el) return;
    const { showSans, showAvec } = getScenario();
    const recommended = getRecommended();
    const fmtNum = v => v !== null && v !== undefined ? v.toLocaleString('fr-MA') : 'N/A';

    const recBadge = '<span style="font-size:0.6rem;background:#F5A623;color:#0F1E35;border-radius:3px;padding:1px 5px;font-weight:700;margin-left:5px;vertical-align:middle;">★ Recommandé</span>';

    function card(label, value, unit, show, isRec, baseClass = '') {
        if (!show) return '';
        const border = isRec ? 'box-shadow:0 0 0 2px #F5A623;' : '';
        return `<div class="metric-card ${baseClass}" style="${border}">
            <div class="metric-label">${label}${isRec ? recBadge : ''}</div>
            <div class="metric-value">${value}</div>
            <div class="metric-unit">${unit}</div>
        </div>`;
    }

    const sansRec = recommended === 'Sans batterie';
    const avecRec = recommended === 'Avec batterie';

    el.innerHTML =
        card('Production annuelle', fmtNum(Math.round(data.production_annuelle_kwh)), 'kWh / an', true, false, 'highlight') +
        card('Éco. Option 1 – Sans batterie', fmtNum(Math.round(data.eco_annuelle_sans)), 'MAD / an', showSans, sansRec) +
        card('Éco. Option 2 – Avec batterie', fmtNum(Math.round(data.eco_annuelle_avec)), 'MAD / an', showAvec, avecRec) +
        card('ROI Sans batterie', data.payback_sans !== null ? data.payback_sans + ' ans' : 'N/A', 'retour sur invest.', showSans, sansRec, 'highlight-orange') +
        card('ROI Avec batterie', data.payback_avec !== null ? data.payback_avec + ' ans' : 'N/A', 'retour sur invest.', showAvec, avecRec, 'highlight-orange') +
        card('Coût Option 1 – Sans', fmtNum(Math.round(totalSans)), 'MAD TTC', showSans, sansRec) +
        card('Coût Option 2 – Avec', fmtNum(Math.round(totalAvec)), 'MAD TTC', showAvec, avecRec);
}

function renderROIChart(data) {
    const ctx = document.getElementById('roi-chart');
    if (!ctx) return;
    if (roiChart) { roiChart.destroy(); }
    const cumul = data.cumulative_25;
    roiChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: cumul.years,
            datasets: [
                {
                    label: 'Sans batterie (MAD)',
                    data: cumul.sans,
                    borderColor: '#0A5275',
                    backgroundColor: 'rgba(10,82,117,0.08)',
                    borderWidth: 2.5,
                    pointRadius: 3,
                    fill: true,
                    tension: 0.3,
                },
                {
                    label: 'Avec batterie (MAD)',
                    data: cumul.avec,
                    borderColor: '#F28E2B',
                    backgroundColor: 'rgba(242,142,43,0.06)',
                    borderWidth: 2,
                    borderDash: [5,3],
                    pointRadius: 3,
                    fill: true,
                    tension: 0.3,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { position: 'top', labels: { font: { size: 12 } } },
                tooltip: {
                    callbacks: {
                        label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y.toLocaleString('fr-MA')} MAD`,
                    },
                },
            },
            scales: {
                x: {
                    title: { display: true, text: 'Années' },
                    grid: { display: false },
                },
                y: {
                    title: { display: true, text: 'Gain cumulé (MAD)' },
                    grid: { color: 'rgba(0,0,0,0.06)' },
                    ticks: {
                        callback: v => v.toLocaleString('fr-MA'),
                    },
                },
            },
        },
    });
}

// ---- Collect Form Data ----
function collectFormData() {
    const docNumber = parseInt(document.getElementById('doc-number')?.value) || 1;
    const installType = document.getElementById('install-type')?.value || 'Résidentielle';
    const clientName = document.getElementById('client-name')?.value || '';
    const clientAddress = document.getElementById('client-address')?.value || '';
    const clientPhone = document.getElementById('client-phone')?.value || '';
    const clientIce = document.getElementById('client-ice')?.value || '';
    const scenario = document.getElementById('scenario-choice')?.value || 'Les deux (Sans + Avec)';
    const recommended = getRecommended();  // resolves "Auto" to actual value
    const kwp = parseFloat(document.getElementById('puissance-kwp')?.value) || 0;
    const panW = parseInt(document.getElementById('puissance-panneau')?.value) || 710;
    const dayUsage = parseInt(document.getElementById('day-usage')?.value) || 50;
    const structType = document.querySelector('input[name="structure-type"]:checked')?.value || 'acier';
    const onduleurKw = parseFloat(document.getElementById('onduleur-kw')?.value) || null;
    const onduleurPhase = document.querySelector('input[name="onduleur-phase"]:checked')?.value || 'Monophasé';

    const factures = getMonthlyValues();
    const lines = getCurrentProductLines();
    const customSans = getCustomLines('sans');
    const customAvec = getCustomLines('avec');
    const notesSans = getNotes('sans');
    const notesAvec = getNotes('avec');
    const discountPct = parseFloat(document.getElementById('discount-pct')?.value) || 0;
    const onepageMode = document.getElementById('onepage-mode')?.checked;

    return {
        doc_number: docNumber,
        installation_type: installType,
        client_name: clientName,
        client_address: clientAddress,
        client_phone: clientPhone,
        client_ice: clientIce,
        scenario_choice: scenario,
        recommended_option: recommended,
        discount_percent: discountPct,
        puissance_kwp: kwp,
        puissance_panneau_w: panW,
        roi_data: {
            factures_mensuelles: factures,
            day_usage_percent: dayUsage,
        },
        product_lines: lines,
        custom_lines_sans: customSans,
        custom_lines_avec: customAvec,
        notes_sans: notesSans,
        notes_avec: notesAvec,
        structure_type: structType,
        onduleur_kw: onduleurKw,
        onduleur_phase: onduleurPhase,
        pdf_mode: onepageMode ? 'onepage' : 'full',
    };
}

// ---- Generate PDF ----
async function generatePDF() {
    const data = collectFormData();
    if (!data.client_name) { showToast('Entrez le nom du client', 'warning'); return; }
    if (data.puissance_kwp <= 0) { showToast('Entrez le nombre de panneaux', 'warning'); return; }
    if (!data.product_lines.length) { showToast('Ajoutez au moins une ligne produit', 'warning'); return; }

    const btn = document.getElementById('btn-generate-pdf');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Génération PDF...'; }

    try {
        const res = await authFetch('/api/devis/generate', {
            method: 'POST',
            body: JSON.stringify(data),
        });
        if (!res) return;
        if (!res.ok) {
            const err = await res.json();
            showToast('Erreur PDF: ' + (err.detail || 'Inconnue'), 'danger');
            return;
        }
        const result = await res.json();
        showDownloadBanner(result);
        showToast('Devis PDF généré avec succès!', 'success', 6000);

        // Update doc counter
        const docNumEl = document.getElementById('doc-number');
        if (docNumEl) docNumEl.value = parseInt(data.doc_number) + 1;
    } catch (e) {
        showToast('Erreur réseau: ' + e.message, 'danger');
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '📄 Générer PDF'; }
    }
}

function showDownloadBanner(result) {
    const container = document.getElementById('download-area');
    if (!container) return;
    container.innerHTML = `
        <div class="download-banner">
            <span class="download-icon">📄</span>
            <div>
                <strong>Devis généré avec succès!</strong><br>
                <small>${result.pdf_filename}</small><br>
                <small>SANS: ${formatMoney(result.total_sans)} | AVEC: ${formatMoney(result.total_avec)}</small>
            </div>
            <button class="btn btn-primary btn-sm"
                    onclick="downloadPDF('${result.devis_id}', '${result.pdf_filename}')">
                ⬇ Télécharger PDF
            </button>
        </div>
    `;
    container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ---- History Tab ----
async function loadHistory() {
    const tbody = document.getElementById('history-tbody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:1rem;"><span class="spinner spinner-dark"></span> Chargement...</td></tr>';
    try {
        const res = await authFetch('/api/devis');
        if (!res) return;
        if (!res.ok) { tbody.innerHTML = '<tr><td colspan="6">Erreur chargement</td></tr>'; return; }
        const history = await res.json();
        if (!history.length) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#888;padding:1rem;">Aucun devis dans l\'historique</td></tr>';
            return;
        }
        tbody.innerHTML = history.map(d => `
            <tr>
                <td><strong>${d.doc_number || d.devis_id}</strong></td>
                <td>${escHtml(d.client_name || '—')}</td>
                <td>${d.created_at || '—'}</td>
                <td>${formatMoney(d.total_ttc)}</td>
                <td>${escHtml(d.scenario_choice || '—')}</td>
                <td>
                    <div class="btn-group">
                        <button class="btn btn-primary btn-sm"
                                onclick="downloadPDF('${d.devis_id}')" title="Télécharger PDF">
                           ⬇ PDF
                        </button>
                        <button class="btn btn-danger btn-sm"
                                onclick="deleteDevis('${d.devis_id}')" title="Supprimer">× Suppr.</button>
                    </div>
                </td>
            </tr>
        `).join('');
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="6" style="color:red;">Erreur: ${e.message}</td></tr>`;
    }
}

async function downloadPDF(devisId, filename) {
    try {
        const res = await authFetch(`/api/devis/${devisId}/pdf`);
        if (!res || !res.ok) { showToast('Erreur téléchargement PDF', 'danger'); return; }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename || `Devis_${devisId}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (e) {
        showToast('Erreur réseau: ' + e.message, 'danger');
    }
}

async function deleteDevis(devisId) {
    if (!confirm(`Supprimer le devis ${devisId}? Cette action est irréversible.`)) return;
    try {
        const res = await authFetch(`/api/devis/${devisId}`, { method: 'DELETE' });
        if (!res) return;
        if (res.status === 204 || res.ok) {
            showToast('Devis supprimé', 'success');
            loadHistory();
        } else {
            const err = await res.json();
            showToast('Erreur: ' + (err.detail || 'Inconnue'), 'danger');
        }
    } catch (e) {
        showToast('Erreur réseau: ' + e.message, 'danger');
    }
}

// ---- Catalog Tab ----
async function loadCatalog() {
    const container = document.getElementById('catalog-display');
    if (!container) return;
    container.innerHTML = '<p><span class="spinner spinner-dark"></span> Chargement catalogue...</p>';
    try {
        const res = await authFetch('/api/catalog');
        if (!res) return;
        if (!res.ok) { container.innerHTML = '<p class="alert alert-danger">Erreur chargement catalogue</p>'; return; }
        const catalog = await res.json();
        renderCatalogDisplay(catalog, container);
    } catch (e) {
        container.innerHTML = `<p class="alert alert-danger">Erreur: ${e.message}</p>`;
    }
}

window._catPriceRows = [];

function renderCatalogDisplay(catalog, container) {
    window._catPriceRows = [];
    const admin = isAdmin();
    const ONDULEUR = ['Onduleur Injection', 'Onduleur Hybride'];
    const PANEL_BAT = ['Panneaux', 'Batterie'];
    const sections = [];

    for (const [category, items] of Object.entries(catalog)) {
        if (typeof items !== 'object' || !items) continue;
        let rows = '';
        let thead = '';

        if (ONDULEUR.includes(category)) {
            thead = `<tr><th>Marque</th><th>Puissance</th><th>Phase</th><th>Prix Vente TTC</th>${admin ? '<th>Prix Achat TTC</th>' : ''}<th></th></tr>`;
            let hasRow = false;
            for (const [brand, bd] of Object.entries(items)) {
                if (brand === '__default__' || typeof bd !== 'object') continue;
                const powers = Object.keys(bd).filter(k => !isNaN(parseFloat(k))).sort((a, b) => parseFloat(a) - parseFloat(b));
                for (const power of powers) {
                    const pd = bd[power];
                    if (typeof pd !== 'object' || !pd.variants) continue;
                    const phases = Object.keys(pd.variants).sort();
                    for (const phase of phases) {
                        const vd = pd.variants[phase];
                        if (typeof vd !== 'object') continue;
                        const i = window._catPriceRows.length;
                        window._catPriceRows.push({ category, brand, power, phase });
                        rows += `<tr>
                            <td>${escHtml(brand)}</td>
                            <td>${power} kW</td>
                            <td>${escHtml(phase)}</td>
                            <td><input type="number" class="form-control form-control-sm" id="cps${i}" value="${vd.sell_ttc || 0}" style="width:110px"></td>
                            ${admin ? `<td><input type="number" class="form-control form-control-sm" id="cpb${i}" value="${vd.buy_ttc || 0}" style="width:110px"></td>` : ''}
                            <td style="white-space:nowrap;">
                                <button class="btn btn-primary btn-sm" onclick="saveCatalogPrice(${i})">💾</button>
                                ${admin ? `<button class="btn btn-danger btn-sm" onclick="deleteCatalogEntry(${i})" title="Supprimer">🗑️</button>` : ''}
                            </td>
                        </tr>`;
                        hasRow = true;
                    }
                }
            }
            if (!hasRow) continue;

        } else if (PANEL_BAT.includes(category)) {
            const unit = category === 'Panneaux' ? 'W' : 'kWh';
            thead = `<tr><th>Marque</th><th>Capacité (${unit})</th><th>Prix Vente TTC</th>${admin ? '<th>Prix Achat TTC</th>' : ''}<th></th></tr>`;
            let hasRow = false;
            for (const [brand, bd] of Object.entries(items)) {
                if (brand === '__default__' || typeof bd !== 'object') continue;
                const powers = Object.keys(bd).filter(k => !isNaN(parseFloat(k))).sort((a, b) => parseFloat(a) - parseFloat(b));
                for (const power of powers) {
                    const pd = bd[power];
                    if (typeof pd !== 'object') continue;
                    const i = window._catPriceRows.length;
                    window._catPriceRows.push({ category, brand, power, phase: '' });
                    rows += `<tr>
                        <td>${escHtml(brand)}</td>
                        <td>${power} ${unit}</td>
                        <td><input type="number" class="form-control form-control-sm" id="cps${i}" value="${pd.sell_ttc || 0}" style="width:110px"></td>
                        ${admin ? `<td><input type="number" class="form-control form-control-sm" id="cpb${i}" value="${pd.buy_ttc || 0}" style="width:110px"></td>` : ''}
                        <td style="white-space:nowrap;">
                            <button class="btn btn-primary btn-sm" onclick="saveCatalogPrice(${i})">💾</button>
                            ${admin ? `<button class="btn btn-danger btn-sm" onclick="deleteCatalogEntry(${i})" title="Supprimer">🗑️</button>` : ''}
                        </td>
                    </tr>`;
                    hasRow = true;
                }
            }
            if (!hasRow) continue;

        } else {
            // Simple category: just __default__ row
            const def = items['__default__'];
            if (!def || typeof def !== 'object') continue;
            thead = `<tr><th>Prix Vente TTC</th>${admin ? '<th>Prix Achat TTC</th>' : ''}<th></th></tr>`;
            const i = window._catPriceRows.length;
            window._catPriceRows.push({ category, brand: '__default__', power: '', phase: '' });
            rows = `<tr>
                <td><input type="number" class="form-control form-control-sm" id="cps${i}" value="${def.sell_ttc || 0}" style="width:110px"></td>
                ${admin ? `<td><input type="number" class="form-control form-control-sm" id="cpb${i}" value="${def.buy_ttc || 0}" style="width:110px"></td>` : ''}
                <td><button class="btn btn-primary btn-sm" onclick="saveCatalogPrice(${i})">💾</button></td>
            </tr>`;
        }

        sections.push(`<div class="card" style="margin-bottom:1rem;">
            <div class="card-header"><h3>${escHtml(category)}</h3></div>
            <div class="table-wrapper">
                <table><thead>${thead}</thead><tbody>${rows}</tbody></table>
            </div>
        </div>`);
    }
    container.innerHTML = sections.join('') || '<p class="alert alert-info">Catalogue vide</p>';
}

async function saveCatalogPrice(i) {
    const row = window._catPriceRows[i];
    if (!row) return;
    const sell = parseFloat(document.getElementById(`cps${i}`)?.value) || 0;
    const payload = {
        category: row.category,
        brand:    row.brand,
        power:    row.power,
        phase:    row.phase,
        sell_ttc: sell,
    };
    if (isAdmin()) {
        payload.buy_ttc = parseFloat(document.getElementById(`cpb${i}`)?.value) || 0;
    }
    try {
        const res = await authFetch('/api/catalog/price', {
            method: 'PATCH',
            body: JSON.stringify(payload),
        });
        if (!res) return;
        const data = await res.json();
        showToast(data.message || 'Prix mis à jour', 'success');
        // Clear onduleur options cache so updated prices appear on next autofill
        onduleurOptionsCache = {};
    } catch (e) {
        showToast('Erreur: ' + e.message, 'danger');
    }
}

async function deleteCatalogEntry(i) {
    const row = window._catPriceRows[i];
    if (!row) return;
    const label = row.phase ? `${row.brand} ${row.power}kW ${row.phase}` : `${row.brand} ${row.power}`;
    if (!confirm(`Supprimer "${label}" du catalogue?`)) return;
    try {
        const res = await authFetch('/api/catalog/entry', {
            method: 'DELETE',
            body: JSON.stringify({ category: row.category, brand: row.brand, power: row.power, phase: row.phase }),
        });
        if (!res) return;
        const data = await res.json();
        showToast(data.message || 'Entrée supprimée', 'success');
        _catalogCache = null; // invalidate local cache
        loadCatalog();
    } catch (e) { showToast('Erreur: ' + e.message, 'danger'); }
}

async function addCatalogInverter() {
    const ondType = document.getElementById('inv-type')?.value;
    const brand = document.getElementById('inv-brand')?.value?.trim();
    const power = parseFloat(document.getElementById('inv-power')?.value) || 0;
    const phase = document.getElementById('inv-phase')?.value || 'Monophase';
    const sell = parseFloat(document.getElementById('inv-sell')?.value) || 0;
    const buy = parseFloat(document.getElementById('inv-buy')?.value) || 0;
    if (!brand || power <= 0) { showToast('Remplissez tous les champs requis', 'warning'); return; }
    try {
        const res = await authFetch('/api/catalog/inverter', {
            method: 'POST',
            body: JSON.stringify({ onduleur_type: ondType, brand, power_kw: power, phase, sell_ttc: sell, buy_ttc: buy }),
        });
        if (!res) return;
        const data = await res.json();
        showToast(data.message || 'Onduleur ajouté!', 'success');
        loadCatalog();
    } catch (e) { showToast('Erreur: ' + e.message, 'danger'); }
}

async function addCatalogPanel() {
    const brand = document.getElementById('pan-brand')?.value?.trim();
    const power = parseInt(document.getElementById('pan-power')?.value) || 0;
    const sell = parseFloat(document.getElementById('pan-sell')?.value) || 0;
    const buy = parseFloat(document.getElementById('pan-buy')?.value) || 0;
    if (!brand || power <= 0) { showToast('Remplissez tous les champs requis', 'warning'); return; }
    try {
        const res = await authFetch('/api/catalog/panel', {
            method: 'POST',
            body: JSON.stringify({ brand, power_w: power, sell_ttc: sell, buy_ttc: buy }),
        });
        if (!res) return;
        const data = await res.json();
        showToast(data.message || 'Panneau ajouté!', 'success');
        loadCatalog();
    } catch (e) { showToast('Erreur: ' + e.message, 'danger'); }
}

async function addCatalogBattery() {
    const brand = document.getElementById('bat-brand')?.value?.trim();
    const cap = parseFloat(document.getElementById('bat-cap')?.value) || 0;
    const sell = parseFloat(document.getElementById('bat-sell')?.value) || 0;
    const buy = parseFloat(document.getElementById('bat-buy')?.value) || 0;
    if (!brand || cap <= 0) { showToast('Remplissez tous les champs requis', 'warning'); return; }
    try {
        const res = await authFetch('/api/catalog/battery', {
            method: 'POST',
            body: JSON.stringify({ brand, capacity_kwh: cap, sell_ttc: sell, buy_ttc: buy }),
        });
        if (!res) return;
        const data = await res.json();
        showToast(data.message || 'Batterie ajoutée!', 'success');
        loadCatalog();
    } catch (e) { showToast('Erreur: ' + e.message, 'danger'); }
}

// ---- Admin Tab ----
async function loadUsers() {
    const tbody = document.getElementById('users-tbody');
    if (!tbody) return;
    const user = getUser();
    if (!user || user.role !== 'admin') return;
    tbody.innerHTML = '<tr><td colspan="4"><span class="spinner spinner-dark"></span> Chargement...</td></tr>';
    try {
        const res = await authFetch('/api/auth/users');
        if (!res) return;
        if (!res.ok) { tbody.innerHTML = '<tr><td colspan="4">Erreur</td></tr>'; return; }
        const users = await res.json();
        tbody.innerHTML = users.map(u => `
            <tr>
                <td>${u.id}</td>
                <td><strong>${escHtml(u.username)}</strong></td>
                <td><span class="badge badge-${u.role}">${u.role}</span></td>
                <td>
                    ${u.username !== 'admin' ? `
                    <button class="btn btn-danger btn-sm" onclick="deleteUser(${u.id}, '${escHtml(u.username)}')">
                        × Supprimer
                    </button>` : '<em style="color:#aaa">protégé</em>'}
                </td>
            </tr>
        `).join('');
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="4" style="color:red;">Erreur: ${e.message}</td></tr>`;
    }
}

async function addUser() {
    const username = document.getElementById('new-username')?.value?.trim();
    const password = document.getElementById('new-password')?.value;
    const role = document.getElementById('new-role')?.value || 'user';
    if (!username || !password) { showToast('Remplissez username et password', 'warning'); return; }
    try {
        const res = await authFetch('/api/auth/register', {
            method: 'POST',
            body: JSON.stringify({ username, password, role }),
        });
        if (!res) return;
        if (!res.ok) {
            const err = await res.json();
            showToast('Erreur: ' + (err.detail || 'Inconnue'), 'danger');
            return;
        }
        showToast(`Utilisateur "${username}" créé!`, 'success');
        document.getElementById('new-username').value = '';
        document.getElementById('new-password').value = '';
        loadUsers();
    } catch (e) { showToast('Erreur: ' + e.message, 'danger'); }
}

async function deleteUser(userId, username) {
    if (!confirm(`Supprimer l'utilisateur "${username}"?`)) return;
    try {
        const res = await authFetch(`/api/auth/users/${userId}`, { method: 'DELETE' });
        if (!res) return;
        if (res.status === 204 || res.ok) {
            showToast(`Utilisateur "${username}" supprimé`, 'success');
            loadUsers();
        } else {
            const err = await res.json();
            showToast('Erreur: ' + (err.detail || 'Inconnue'), 'danger');
        }
    } catch (e) { showToast('Erreur: ' + e.message, 'danger'); }
}

// ---- Helpers ----
function formatMoney(val) {
    if (val === null || val === undefined || isNaN(val)) return '0 MAD';
    return Math.round(val).toLocaleString('fr-MA') + ' MAD';
}

function escHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// ---- Start app on DOM ready ----
document.addEventListener('DOMContentLoaded', initApp);
