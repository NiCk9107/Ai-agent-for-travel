import json
from typing import Optional

from agent.state import Hotel, Room
from db.database import get_conn


def _rooms(conn, hotel_id: str) -> list[Room]:
    rows = conn.execute("SELECT * FROM rooms WHERE hotel_id = ? ORDER BY price_multiplier",
                        (hotel_id,)).fetchall()
    return [Room(id=r["id"], hotel_id=r["hotel_id"], name=r["name"],
                 capacity_adults=r["capacity_adults"], capacity_children=r["capacity_children"],
                 price_multiplier=r["price_multiplier"]) for r in rows]


def _fits(room: Room, adults: int, children: int) -> bool:
    return room.capacity_adults >= adults and \
        room.capacity_adults + room.capacity_children >= adults + children


def _to_hotel(row, rooms: list[Room], price_per_night: int) -> Hotel:
    return Hotel(
        id=row["id"], destination_id=row["destination_id"], name=row["name"],
        lat=row["lat"], lon=row["lon"], stars=row["stars"], rating=row["rating"],
        price_per_night=price_per_night, meal_plan=row["meal_plan"],
        cancel_policy=row["cancel_policy"], checkin_time=row["checkin_time"],
        checkout_time=row["checkout_time"], pet_friendly=bool(row["pet_friendly"]),
        kids_club=bool(row["kids_club"]), beach_distance_m=row["beach_distance_m"],
        image_url=row["image_url"], rooms=rooms,
    )


def search_hotels(destination_id: str, adults: int, children: int) -> list[Hotel]:
    """Отели, где есть номер на adults взрослых + children детей."""
    result = []
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM hotels WHERE destination_id = ?", (destination_id,)).fetchall()
        for row in rows:
            fitting = [r for r in _rooms(conn, row["id"]) if _fits(r, adults, children)]
            if not fitting:
                continue
            price = int(round(row["price_per_night"] * fitting[0].price_multiplier, -2))
            result.append(_to_hotel(row, fitting, price))

        # Пустая выдача (например, 6 человек): не молчим, а отдаём ближайшее —
        # самый вместительный номер каждого отеля. validator у A пометит ROOM_CAPACITY,
        # и агент честно скажет: «номера на всех нет, вот самые большие / можно взять два».
        if not result:
            for row in rows:
                rooms = sorted(_rooms(conn, row["id"]),
                               key=lambda r: r.capacity_adults + r.capacity_children, reverse=True)
                if rooms:
                    price = int(round(row["price_per_night"] * rooms[0].price_multiplier, -2))
                    result.append(_to_hotel(row, rooms[:1], price))
    return result


def get_hotel_details(hotel_id: str) -> Optional[dict]:
    """Номера, правила и отзывы — для вопроса «расскажи подробнее про отель»."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM hotels WHERE id = ?", (hotel_id,)).fetchone()
        if not row:
            return None
        rooms = _rooms(conn, hotel_id)
    hotel = _to_hotel(row, rooms, row["price_per_night"])
    return {
        **hotel.model_dump(exclude={"rooms"}),
        "rooms": [{"name": r.name, "adults": r.capacity_adults, "children": r.capacity_children,
                   "price_per_night": int(round(row["price_per_night"] * r.price_multiplier, -2))}
                  for r in rooms],
        "reviews": json.loads(row["reviews_json"] or "[]"),
        "source": "синтетика" if hotel_id.startswith(f"{row['destination_id']}_s")
                  else "название и координаты — OpenStreetMap, остальное — синтетика",
    }