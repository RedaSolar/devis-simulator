import sys, os
APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)
import db
from auth_utils import hash_password
db.init_db()
if not db.get_user_by_username("admin"):
    db.create_user("admin", hash_password("admin123"), role="admin")
    print("OK: admin user created")
else:
    print("OK: admin user already exists")
if not db.get_user_by_username("moumna"):
    db.create_user("moumna", hash_password("sisayed"), role="user")
    print("OK: user moumna created")
else:
    print("OK: user moumna already exists")
