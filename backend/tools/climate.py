"""Погода в направлении на месяц — из таблицы climate (заполняется scripts/load_climate.py)."""
from typing import Optional

from db.database import get_conn


def get_climate(destination_id: str, month: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT air_temp, water_temp, rain_days FROM climate WHERE destination_id = ? AND month = ?",
            (destination_id, month)).fetchone()
    return dict(row) if row else None