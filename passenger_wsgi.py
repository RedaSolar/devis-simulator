import sys
import os

# Absolute path to the app on the cPanel server
APP_DIR = "/home/taqinorm/taqinor_app"

sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

from a2wsgi import ASGIMiddleware
from main import app

# Passenger requires the WSGI callable to be named 'application'
application = ASGIMiddleware(app)
