"""
Инструменты-ЗАГЛУШКИ дня 2. Возвращают выдуманные, но правдоподобные данные
в формате из state.py. Когда B сделает настоящие функции с теми же именами
и аргументами, просто меняем импорт в tool_registry.py.
"""
from datetime import date, datetime, timedelta
from tools.destinations import get_destination
from agent.state import Destination, Flight, Hotel, Room, Transfer

_DESTINATIONS = [
    Destination(id="antalya", name="Анталья", country="Турция", airport_code="AYT",
                lat=36.8969, lon=30.7133, tags=["море", "пляж", "семья"],
                avg_hotel_price=9000, flight_hours_from_msk=4,
                description="Семейные отели «всё включено», короткий перелёт"),
    Destination(id="sharm", name="Шарм-эш-Шейх", country="Египет", airport_code="SSH",
                lat=27.9158, lon=34.33, tags=["море", "пляж", "дайвинг"],
                avg_hotel_price=7000, flight_hours_from_msk=5,
                description="Тёплое море круглый год, коралловые рифы"),
    Destination(id="sochi", name="Сочи", country="Россия", airport_code="AER",
                lat=43.5855, lon=39.7231, tags=["море", "горы", "без визы"],
                avg_hotel_price=8000, flight_hours_from_msk=2.5,
                description="Море и горы рядом, без визы и обмена валюты"),
]

_AIRPORTS = {"москва": "MOW", "санкт-петербург": "LED", "питер": "LED", "казань": "KZN"}


def suggest_destinations(month: str | None, tags: list[str], max_flight_hours: float | None) -> list[Destination]:
    result = [d for d in _DESTINATIONS
              if max_flight_hours is None or (d.flight_hours_from_msk or 0) <= max_flight_hours]
    return result[:3] or _DESTINATIONS[:3]


def search_hotels(destination_id: str, adults: int, children: int) -> list[Hotel]:
    dest = get_destination(destination_id)
    base = (dest.avg_hotel_price if dest else None) or 8000
    variants = [
        ("Sea Breeze Family", 4, 8.7, 1.0, "AI", "free_cancel_3d", True, 300),
        ("Sunny Budget", 3, 7.9, 0.6, "BB", "non_refundable", False, 900),
        ("Royal Palace", 5, 9.2, 1.8, "AI", "free_cancel_7d", True, 50),
    ]
    hotels = []
    for i, (name, stars, rating, k, meal, cancel, kids, beach) in enumerate(variants, 1):
        hid = f"{destination_id}_h{i}"
        hotels.append(Hotel(
            id=hid, destination_id=destination_id, name=name, lat=0, lon=0,
            stars=stars, rating=rating, price_per_night=int(base * k), meal_plan=meal,
            cancel_policy=cancel, kids_club=kids, beach_distance_m=beach,
            rooms=[Room(id=f"{hid}_r1", hotel_id=hid, name="Семейный номер",
                        capacity_adults=max(2, adults), capacity_children=max(1, children))],
        ))
    return hotels


def search_flights(origin: str, destination_id: str, day: date, passengers: int,
                   direction: str) -> list[Flight]:
    dest = next((d for d in _DESTINATIONS if d.id == destination_id), _DESTINATIONS[0])
    home = _AIRPORTS.get((origin or "москва").lower(), "MOW")
    frm, to = (home, dest.airport_code) if direction == "out" else (dest.airport_code, home)
    hours = dest.flight_hours_from_msk or 4
    options = [("Аэрофлот", 9, 1.0), ("Победа", 6, 0.7), ("S7", 19, 0.85)]
    flights = []
    for i, (airline, hour, k) in enumerate(options, 1):
        dep = datetime.combine(day, datetime.min.time()) + timedelta(hours=hour)
        flights.append(Flight(
            id=f"{direction}_{destination_id}_{day:%m%d}_{i}", airline=airline,
            origin_airport=frm, dest_airport=to, depart=dep, arrive=dep + timedelta(hours=hours),
            price_per_person=int(15000 * k), baggage=airline != "Победа",
        ))
    return flights



def estimate_transfer(airport_code: str, hotel_lat: float, hotel_lon: float,
                      passengers: int) -> list[Transfer]:
    """Заглушка: B заменит на OSRM (реальное время в пути) + формулу цены."""
    key = f"{airport_code}_{hotel_lat:.3f}_{hotel_lon:.3f}"
    return [
        Transfer(id=f"tr_{key}_taxi", kind="taxi", duration_min=40, price=2500 + 300 * max(0, passengers - 3)),
        Transfer(id=f"tr_{key}_shuttle", kind="shuttle", duration_min=70, price=700 * passengers),
        Transfer(id=f"tr_{key}_public", kind="public", duration_min=95, price=150 * passengers),
    ]