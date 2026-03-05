import sys
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

from a2wsgi import ASGIMiddleware
from main import app

application = ASGIMiddleware(app)
