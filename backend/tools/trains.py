"""
Генератор поездов (открытого API нет — честно говорим, что это синтетика).
Только для направлений внутри России/Беларуси, куда ходят поезда из Москвы и Питера.
Seed от (откуда, куда, дата, направление) — одинаковый запрос даёт одинаковые поезда.
Агенту пока не подключён: A добавит инструмент search_trains, когда будет время (доп. задача).
"""
import hashlib
import random
from datetime import date, datetime, timedelta

from pydantic import BaseModel

# часы в пути из Москвы (MOW) и Санкт-Петербурга (LED)
TRAIN_HOURS = {
    ("MOW", "spb"): 4, ("MOW", "kazan"): 12, ("MOW", "sochi"): 24, ("MOW", "kislovodsk"): 26,
    ("MOW", "minsk"): 8, ("MOW", "kaliningrad"): 21, ("MOW", "murmansk"): 35, ("MOW", "dagestan"): 37,
    ("LED", "kazan"): 25, ("LED", "sochi"): 40, ("LED", "minsk"): 12,
}
CITY = {"москва": "MOW", "санкт-петербург": "LED", "питер": "LED", "спб": "LED"}
CLASSES = [("Плацкарт", 1.0), ("Купе", 2.2), ("СВ", 4.5)]


class Train(BaseModel):
    id: str
    number: str
    name: str
    depart: datetime
    arrive: datetime
    car_class: str
    price_per_person: int
    pets_allowed: bool = True   # в купе РЖД можно с животными, если выкупить купе


def _seed(*parts) -> int:
    return int(hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


def search_trains(origin: str, destination_id: str, day: date, passengers: int,
                  direction: str) -> list[Train]:
    home = CITY.get((origin or "москва").strip().lower(), "MOW")
    hours = TRAIN_HOURS.get((home, destination_id))
    if hours is None:
        return []
    rnd = random.Random(_seed(home, destination_id, day.isoformat(), direction))
    trains = []
    for i in range(rnd.randint(2, 3)):
        dep = datetime.combine(day, datetime.min.time()) + timedelta(
            hours=rnd.choice([7, 12, 16, 19, 21, 23]), minutes=rnd.choice([0, 10, 25, 40, 55]))
        dur = timedelta(hours=hours * rnd.uniform(0.9, 1.1))
        base = 900 + 95 * hours
        number = f"{rnd.randint(1, 199):03d}{rnd.choice('АСМЧ')}"
        for cls, k in CLASSES:
            trains.append(Train(
                id=f"train_{direction}_{destination_id}_{day:%m%d}_{i}_{cls[:3]}",
                number=number, name=rnd.choice(["Фирменный", "Скорый", "Ласточка" if hours <= 5 else "Скорый"]),
                depart=dep, arrive=dep + dur, car_class=cls,
                price_per_person=int(round(base * k * rnd.uniform(0.9, 1.15), -1))))
    return sorted(trains, key=lambda t: (t.depart, t.price_per_person))