"""
Каталог найденных объектов: id → Destination / Hotel / Flight.
В TripState хранятся только id, а карточкам нужны полные данные — берём их отсюда.
Пока в памяти; позже B может заменить get() на чтение из БД.
"""
from pydantic import BaseModel

_items: dict[str, BaseModel] = {}


def remember(objs: list) -> list:
    for o in objs:
        _items[o.id] = o
    return objs


def get(item_id: str):
    return _items.get(item_id)



# Доп. данные к объекту, которых нет в модели: например, оценка scoring
# (pros / tradeoffs / risks) для отеля. Ключ — id объекта.
_meta: dict[str, dict] = {}


def set_meta(item_id: str, data: dict) -> None:
    _meta[item_id] = data


def get_meta(item_id: str) -> dict:
    return _meta.get(item_id, {})