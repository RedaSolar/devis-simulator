import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(".")
DB_PATH = BASE_DIR / "users.db"


def _get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


def _row_to_dict(row, include_password=True):
    if row is None:
        return None
    d = dict(row)
    if not include_password:
        d.pop("password_hash", None)
    return d


def create_user(username: str, password_hash: str, role: str = "user") -> dict:
    conn = _get_conn()
    try:
        created_at = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (username, password_hash, role, created_at),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return _row_to_dict(row)
    except sqlite3.IntegrityError:
        raise ValueError(f"User '{username}' already exists")
    finally:
        conn.close()


def get_user_by_username(username: str) -> dict | None:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> dict | None:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_all_users() -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT id, username, role, created_at FROM users ORDER BY id").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def delete_user(user_id: int) -> bool:
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def update_user_role(user_id: int, role: str) -> dict | None:
    conn = _get_conn()
    try:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
        conn.commit()
        row = conn.execute("SELECT id, username, role, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
