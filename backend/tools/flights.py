"""
Генератор рейсов. Аргументы — те же, что у заглушки A в agent/stubs.py.
Фиксированный seed от (откуда, куда, дата, направление): один и тот же запрос
всегда даёт одинаковые рейсы — важно для отладки и повторяемости демо.
Правдоподобие: ночные и ранние рейсы дешевле, выходные дороже, длинные — с пересадкой.
"""
import hashlib
import random
from datetime import date, datetime, timedelta

from agent.state import Flight
from tools.destinations import get_destination

ORIGIN_AIRPORTS = {
    "москва": "MOW", "санкт-петербург": "LED", "питер": "LED", "спб": "LED",
    "казань": "KZN", "екатеринбург": "SVX", "новосибирск": "OVB",
}
AIRLINES = ["Аэрофлот", "S7", "Победа", "Уральские авиалинии", "Red Wings", "Turkish Airlines"]


def _seed(*parts) -> int:
    key = "|".join(str(p) for p in parts)
    return int(hashlib.md5(key.encode()).hexdigest()[:8], 16)  # hash() не годится: меняется при перезапуске


def search_flights(origin: str, destination_id: str, day: date, passengers: int,
                   direction: str) -> list[Flight]:
    """direction: 'out' — туда, 'back' — обратно."""
    dest = get_destination(destination_id)
    if dest is None:
        return []
    home = ORIGIN_AIRPORTS.get((origin or "москва").strip().lower(), "MOW")
    frm, to = (home, dest.airport_code) if direction == "out" else (dest.airport_code, home)

    rnd = random.Random(_seed(frm, to, day.isoformat(), direction))
    base_hours = dest.flight_hours_from_msk or 4
    weekend = day.weekday() >= 4  # пт, сб, вс

    count = rnd.randint(3, 5)
    airlines = rnd.sample(AIRLINES, count)  # у каждого рейса своя авиакомпания
    flights = []
    for i in range(1, count + 1):
        hour = rnd.choice([1, 6, 8, 10, 13, 16, 19, 22])
        stops = 1 if base_hours > 8 and rnd.random() < 0.5 else 0
        duration = base_hours + (rnd.uniform(2, 5) if stops else rnd.uniform(-0.3, 0.3))

        price = 5000 + 3500 * base_hours
        price *= rnd.uniform(0.85, 1.2)
        if hour in (1, 6, 22):
            price *= 0.8            # неудобное время — дешевле
        if weekend:
            price *= 1.15
        if stops:
            price *= 0.85
        airline = airlines[i - 1]

        depart = datetime.combine(day, datetime.min.time()) + timedelta(hours=hour, minutes=rnd.choice([0, 15, 30, 45]))
        flights.append(Flight(
            id=f"{direction}_{destination_id}_{day:%m%d}_{i}", airline=airline,
            origin_airport=frm, dest_airport=to,
            depart=depart, arrive=depart + timedelta(hours=round(duration * 4) / 4),
            stops=stops, price_per_person=int(round(price, -2)),
            baggage=airline != "Победа", pets_allowed=airline in ("Аэрофлот", "S7"),
        ))
    return sorted(flights, key=lambda f: f.depart)