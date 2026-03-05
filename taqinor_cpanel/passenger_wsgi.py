import sys
import os

# Dynamically resolve the app directory — works wherever the zip is extracted
APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

from a2wsgi import ASGIMiddleware
from main import app

# Passenger requires the WSGI callable to be named 'application'
application = ASGIMiddleware(app)
