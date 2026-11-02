import csv
import math
from functools import lru_cache
from pathlib import Path

from agent.state import Transfer
from tools.cache import cached_get

OSRM = "https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
MAX_KM = 400                 # дальше — значит, в координатах ошибка
AIRPORTS_CSV = Path(__file__).parent.parent / "data" / "airports.csv"


@lru_cache
def airports() -> dict[str, tuple[float, float]]:
    with open(AIRPORTS_CSV, encoding="utf-8") as f:
        return {r["code"]: (float(r["lat"]), float(r["lon"])) for r in csv.DictReader(f)}


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(a))


def route(lat1, lon1, lat2, lon2) -> tuple[float, float, bool]:
    """(км, минуты в пути, это_реальные_данные_OSRM)."""
    try:
        data = cached_get(OSRM.format(lat1=lat1, lon1=lon1, lat2=lat2, lon2=lon2),
                          params={"overview": "false"})
        r = data["routes"][0]
        return r["distance"] / 1000, r["duration"] / 60, True
    except Exception:
        km = _haversine_km(lat1, lon1, lat2, lon2) * 1.3      # дороги не прямые
        return km, km / 50 * 60, False                        # 50 км/ч в среднем


def _round5(x: float) -> int:
    return int(5 * round(x / 5))


def estimate_transfer(airport_code: str, hotel_lat: float, hotel_lon: float,
                      passengers: int) -> list[Transfer]:
    ap = airports().get(airport_code)
    if ap is None:
        return []
    if abs(hotel_lat) < 0.01 and abs(hotel_lon) < 0.01:
        return []                     # у отеля нет координат — трансфер не посчитать
    km, minutes, _ = route(ap[0], ap[1], hotel_lat, hotel_lon)
    if km > MAX_KM:
        return []                     # отель «за 1000 км от аэропорта» — ошибка в данных
    key = f"{airport_code}_{hotel_lat:.3f}_{hotel_lon:.3f}"
    result = []

    # Такси: подача + время в пути; 5+ человек — минивэн дороже
    taxi_price = max(1200, 300 + 35 * km) * (1.5 if passengers > 4 else 1.0)
    result.append(Transfer(id=f"tr_{key}_taxi", kind="taxi",
                           duration_min=_round5(minutes + 10), price=int(round(taxi_price, -2))))

    # Шаттл: дешевле на человека, но с заездами в другие отели
    if km <= 250:
        result.append(Transfer(id=f"tr_{key}_shuttle", kind="shuttle",
                               duration_min=_round5(minutes * 1.4 + 20),
                               price=int(round(max(600, 8 * km) * passengers, -2))))

    # Общественный транспорт: только если недалеко
    if km <= 60:
        result.append(Transfer(id=f"tr_{key}_public", kind="public",
                               duration_min=_round5(minutes * 2 + 15),
                               price=int(round(max(100, 2 * km) * passengers, -1))))
    return result