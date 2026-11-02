import sqlite3
from pathlib import Path
from typing import Optional

from agent.state import TripState

DB_PATH = Path(__file__).parent / "app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS destinations (
    id TEXT PRIMARY KEY, name TEXT, country TEXT, airport_code TEXT,
    lat REAL, lon REAL, tags TEXT, avg_hotel_price INTEGER,
    flight_hours_from_msk REAL, description TEXT, image_url TEXT
);
CREATE TABLE IF NOT EXISTS climate (
    destination_id TEXT, month INTEGER, air_temp REAL, water_temp REAL, rain_days INTEGER,
    PRIMARY KEY (destination_id, month)
);
CREATE TABLE IF NOT EXISTS hotels (
    id TEXT PRIMARY KEY, destination_id TEXT, name TEXT, lat REAL, lon REAL,
    stars INTEGER, rating REAL, price_per_night INTEGER, meal_plan TEXT,
    cancel_policy TEXT, checkin_time TEXT, checkout_time TEXT,
    pet_friendly INTEGER, kids_club INTEGER, beach_distance_m INTEGER,
    reviews_json TEXT, image_url TEXT
);
CREATE TABLE IF NOT EXISTS rooms (
    id TEXT PRIMARY KEY, hotel_id TEXT, name TEXT,
    capacity_adults INTEGER, capacity_children INTEGER, price_multiplier REAL
);
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY, state_json TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT,
    content TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY, session_id TEXT, items_json TEXT,
    total INTEGER, status TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS api_cache (
    key TEXT PRIMARY KEY, response_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def save_state(state: TripState):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sessions (session_id, state_json, updated_at) "
            "VALUES (?, ?, CURRENT_TIMESTAMP)",
            (state.session_id, state.model_dump_json()),
        )


def load_state(session_id: str) -> Optional[TripState]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT state_json FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
    return TripState.model_validate_json(row["state_json"]) if row else None


def save_message(session_id: str, role: str, content: str):
    with get_conn() as conn:
        conn.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                     (session_id, role, content))


def load_messages(session_id: str, limit: int = 20) -> list[dict]:
    """Последние limit сообщений в хронологическом порядке: [{"role", "content"}]."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit)).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def clear_messages(session_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))