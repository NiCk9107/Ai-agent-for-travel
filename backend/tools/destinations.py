"""
Настоящий suggest_destinations. Аргументы — те же, что у заглушки A в agent/stubs.py.
Логика: отсекаем по времени перелёта и погоде, ранжируем по совпадению тегов.
"""
from typing import Optional

from agent.state import Destination
from db.database import get_conn
from tools.climate import get_climate

WARM_TAGS = {"море", "пляж", "тепло", "тёплое море", "загар"}
SNOW_TAGS = {"лыжи", "сноуборд", "горнолыжный"}
# Порог для СРЕДНЕСУТОЧНОЙ температуры (с учётом ночи): днём обычно на 4–6° теплее
WARM_MIN = 20
# Лыжи проверяем по сезону, а не по температуре: склоны выше посёлка и там холоднее
SKI_MONTHS = {12, 1, 2, 3}


def _row_to_destination(row) -> Destination:
    return Destination(
        id=row["id"], name=row["name"], country=row["country"], airport_code=row["airport_code"],
        lat=row["lat"], lon=row["lon"], tags=(row["tags"] or "").split(";"),
        avg_hotel_price=row["avg_hotel_price"], flight_hours_from_msk=row["flight_hours_from_msk"],
        description=row["description"], image_url=row["image_url"],
    )


def get_destination(destination_id: str) -> Optional[Destination]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM destinations WHERE id = ?", (destination_id,)).fetchone()
    return _row_to_destination(row) if row else None


def suggest_destinations(month: Optional[str], tags: list[str],
                         max_flight_hours: Optional[float], limit: int = 3) -> list[Destination]:
    """month — строка 'YYYY-MM' (как в Requirements), tags — пожелания («море», «горы»).
    Если по погоде ничего не подошло — возвращаем лучшие варианты без фильтра погоды,
    чтобы агенту всегда было что показать (и честно сказать про погоду)."""
    result = _search(month, tags, max_flight_hours, limit, check_weather=True)
    return result or _search(month, tags, max_flight_hours, limit, check_weather=False)


def _search(month, tags, max_flight_hours, limit, check_weather: bool) -> list[Destination]:
    m = int(month[5:7]) if month else None
    wanted = {t.lower() for t in tags}

    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM destinations").fetchall()

    scored = []
    for row in rows:
        hours = row["flight_hours_from_msk"] or 99
        if max_flight_hours and hours > max_flight_hours:
            continue

        d = _row_to_destination(row)
        climate = get_climate(d.id, m) if m else None
        air = climate["air_temp"] if climate else None

        # Погода: просят море — нужно тепло; просят лыжи — нужен сезон
        if air is not None and check_weather:
            if wanted & WARM_TAGS and air < WARM_MIN:
                continue

        if check_weather and wanted & SNOW_TAGS and m and m not in SKI_MONTHS:
            continue

        matched = len(wanted & {t.lower() for t in d.tags})
        if wanted and not matched:
            continue                                              # ни один тег не совпал — не предлагаем
        score = matched * 10                                      # совпадение тегов — главное
        score -= hours                                            # ближе — лучше
        if climate and climate["rain_days"] is not None:
            score -= climate["rain_days"] * 0.3                   # меньше дождей — лучше

        if air is not None:
            weather = f"средняя температура {air:+.0f}°"
            if climate["rain_days"]:
                weather += f", дождливых дней ~{climate['rain_days']}"
            d.description = (d.description + ". " if d.description else "") + f"Погода в этом месяце: {weather}"
        scored.append((score, d))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in scored[:limit]]