# TAQINOR Simulator — cPanel Deployment Guide

## Prerequisites
- cPanel with **Python App** support (Passenger/WSGI)
- Python 3.10 or 3.11 recommended
- SSH or Terminal access (to install dependencies and Playwright)

---

## Step 1 — Upload & Extract

1. Upload `taqinor_cpanel.zip` via **cPanel File Manager** to your home directory.
2. Extract it into a dedicated folder, e.g. `simulator_app/`
   - Final path: `/home/<your_username>/simulator_app/`

---

## Step 2 — Create a Python App in cPanel

1. Go to **cPanel → Setup Python App**
2. Click **Create Application**
3. Fill in:
   | Field | Value |
   |---|---|
   | Python version | 3.10 or 3.11 |
   | Application root | `simulator_app` |
   | Application URL | your domain or subdomain (e.g. `simulator.yourdomain.com`) |
   | Application startup file | `passenger_wsgi.py` |
   | Application Entry point | `application` |
4. Click **Create**

---

## Step 3 — Install Dependencies

In the **cPanel Python App** panel, click **Enter to the virtual environment** to open an SSH terminal with the venv activated, then run:

```bash
pip install -r requirements.txt
playwright install chromium
playwright install-deps chromium
```

> If `playwright install-deps` fails (shared hosting), contact your host to install Chromium system libraries, or switch to a VPS plan.

---

## Step 4 — Configure the App URL (if not at domain root)

If your app is served under a sub-path (e.g. `yourdomain.com/simulator`), edit `main.py` line 23:

```python
# Change:
app = FastAPI(..., root_path="/simulator")
# To match your actual sub-path, or leave as "" if at domain root:
app = FastAPI(..., root_path="")
```

---

## Step 5 — Restart & Test

1. In **Setup Python App**, click **Restart**
2. Visit your domain — you should see the login page
3. Default credentials: **admin / admin123** (change immediately in Admin tab)

---

## Writable Directories

The app creates these automatically on first run:
- `devis_client/` — generated PDFs
- `factures_client/` — generated invoices

Ensure the app folder has write permissions (`chmod 755` on the folder).

---

## Troubleshooting

- **500 errors**: Check `stderr.log` in your app directory or cPanel error logs
- **Chrome not found**: Run `playwright install chromium` again inside the venv
- **Static files 404**: Make sure Application URL is set correctly in cPanel
- **Login fails**: Delete `users.db` and restart — it will recreate with default admin
