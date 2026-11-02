"""
Климат по месяцам из архива Open-Meteo (бесплатно, без ключа).
Для каждого направления берём 3 года дневных данных и считаем средние по месяцам.
"""
import time
from collections import defaultdict

import httpx

from db.database import get_conn, init_db

URL = "https://archive-api.open-meteo.com/v1/archive"
START, END = "2022-01-01", "2024-12-31"
YEARS = 3


def fetch(lat: float, lon: float) -> dict:
    params = {
        "latitude": lat, "longitude": lon, "start_date": START, "end_date": END,
        "daily": "temperature_2m_mean,precipitation_sum", "timezone": "auto",
    }
    resp = httpx.get(URL, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()["daily"]


def monthly(daily: dict) -> dict[int, tuple[float, int]]:
    """{месяц: (средняя t° воздуха, дней с дождём в среднем за месяц)}"""
    temps, rain = defaultdict(list), defaultdict(int)
    for day, t, p in zip(daily["time"], daily["temperature_2m_mean"], daily["precipitation_sum"]):
        m = int(day[5:7])
        if t is not None:
            temps[m].append(t)
        if p is not None and p >= 1.0:  
            rain[m] += 1
    return {m: (round(sum(v) / len(v), 1), round(rain[m] / YEARS)) for m, v in temps.items()}


def main():
    init_db()
    with get_conn() as conn:
        dests = conn.execute("SELECT id, name, lat, lon FROM destinations").fetchall()

    for d in dests:
        try:
            stats = monthly(fetch(d["lat"], d["lon"]))
        except Exception as e:
            print(f"❌ {d['name']}: {e}")
            continue
        with get_conn() as conn:
            for m, (air, rain_days) in stats.items():
                conn.execute(
                    "INSERT OR REPLACE INTO climate (destination_id, month, air_temp, water_temp, rain_days) "
                    "VALUES (?, ?, ?, NULL, ?)", (d["id"], m, air, rain_days))
        print(f"✅ {d['name']}: январь {stats[1][0]}°, июль {stats[7][0]}°")
        time.sleep(0.5)  


if __name__ == "__main__":
    main()