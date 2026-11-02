"""Загрузка направлений из CSV в БД. Запуск из папки backend: python -m scripts.load_destinations"""
import csv
from pathlib import Path

from db.database import get_conn, init_db

CSV_PATH = Path(__file__).parent.parent / "data" / "destinations.csv"

init_db()
with open(CSV_PATH, encoding="utf-8") as f, get_conn() as conn:
    rows = list(csv.DictReader(f))
    for r in rows:
        conn.execute(
            "INSERT OR REPLACE INTO destinations "
            "(id, name, country, airport_code, lat, lon, tags, avg_hotel_price, flight_hours_from_msk) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (r["id"], r["name"], r["country"], r["airport_code"],
             float(r["lat"]), float(r["lon"]), r["tags"],
             int(r["avg_hotel_price"]) if r.get("avg_hotel_price") else None,
             float(r["flight_hours_from_msk"])),
        )
print(f"Загружено направлений: {len(rows)}")