# Copilot Instructions for Solar Panels Simulator

## Project Overview
- This is a Streamlit-based application for managing solar panel installation quotes ("devis") and invoices ("factures").
- Main entry point: `app.py` (over 2800 lines, contains UI, business logic, and PDF/report generation).
- Data is stored in JSON files: `brand_catalog.json` (product catalog), `config.json` (counters), `devis_history.json` (history), and `custom_line_templates.json` (custom line items).
- Output PDFs are saved in `devis_client/` (quotes) and `factures_client/` (invoices).

## Key Components
- **Catalog Management:**
  - Catalog normalization and updates are handled by `normalize_catalog.py` and `update_catalog.py`.
  - Catalog structure uses nested dictionaries with keys for brands, powers, and phases (see `brand_catalog.json`).
- **Custom Lines:**
  - Custom line templates are managed via `custom_line_templates.json` and session state in Streamlit.
- **PDF Generation:**
  - Uses `reportlab` for PDF creation and `matplotlib` for ROI figures.
  - Images for products are loaded from the `pictures/` directory using naming conventions (see `img_candidates`).

## Developer Workflows
- **Run the App:**
  - Use `run_devis.bat` to launch the Streamlit app (`streamlit run app.py`).
- **Update Catalog:**
  - Run `normalize_catalog.py` or `update_catalog.py` to update/normalize the product catalog.
- **Add Functions:**
  - Utility functions for catalog access are in `add_functions.py`.
- **Replace UI Components:**
  - Use `replace_line_editor.py` to update the `line_editor` function in `app.py`.

## Project Conventions
- All persistent data is stored as JSON in the project root.
- Product images must be placed in `pictures/` and named according to the conventions in `img_candidates`.
- All PDF outputs are saved in `devis_client/` or `factures_client/`.
- Streamlit session state is used for UI state and temporary data.

## External Dependencies
- `streamlit`, `pandas`, `reportlab`, `matplotlib` (install via pip if missing).

## Examples
- To add a new panel brand, update `brand_catalog.json` and run `normalize_catalog.py`.
- To generate a new quote, use the Streamlit UI and check `devis_client/` for the output PDF.

---
For questions about catalog structure or PDF generation, see the relevant functions in `app.py` and the helper scripts in the project root.