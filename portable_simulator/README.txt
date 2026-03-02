TAQINOR Solar Quote Simulator
==============================

REQUIREMENTS
------------
- Windows 10/11
- Python 3.9 or newer  (https://www.python.org/downloads/)
  (tick "Add Python to PATH" during install)
- Internet access for first-time font download (cached after that)


FIRST-TIME SETUP (run once)
----------------------------
Double-click  install.bat
This installs all Python packages and the Chromium browser used for PDF generation.


DAILY USE
---------
Double-click  start.bat
Your browser will open automatically at http://localhost:8000

Default login:
  Username: admin
  Password: admin123
Change the password after first login from the user settings.


GENERATED PDFs
--------------
All quote PDFs are saved in the  devis_client/  folder.


TROUBLESHOOTING
---------------
- "python not found": reinstall Python and tick "Add Python to PATH"
- "pip not found": same as above
- PDF generation fails: run install.bat again to reinstall Playwright
- Port 8000 in use: restart your computer or change the port in start.bat
