"""
Карточки для фронта строит КОД из TripState, а не модель.
Поэтому цены и названия в карточках всегда точные.
"""
from agent import catalog
from agent.state import Stage, TripState
from api.schemas import CardAction, DestinationCard, FlightCard, HotelCard, TransferCard

MEAL = {"RO": "Без питания", "BB": "Завтраки", "HB": "Полупансион",
        "FB": "Полный пансион", "AI": "Всё включено"}


def _duration(f) -> str:
    mins = int((f.arrive - f.depart).total_seconds() // 60)
    return f"{mins // 60} ч {mins % 60:02d} мин"


def _flight_card(f, n: int, kind: str) -> dict:
    return FlightCard(
        id=f.id, airline=f.airline, depart=f.depart.isoformat(), arrive=f.arrive.isoformat(),
        duration=_duration(f), stops=f.stops, price=f.price_per_person * n, baggage=f.baggage,
        actions=[CardAction(type="select_flight", label="Выбрать",
                            payload={"flight_id": f.id, "direction": kind})],
    ).model_dump()


def build_cards(state: TripState) -> list[dict]:
    r, s, sl = state.requirements, state.selected, state.shortlist
    n = (r.adults or 1) + len(r.children)

    if state.stage == Stage.destination_choice:
        cards = []
        for d in filter(None, map(catalog.get, sl.destinations)):
            cards.append(DestinationCard(
                id=d.id, title=f"{d.name}, {d.country}", image_url=d.image_url,
                badges=[f"{d.flight_hours_from_msk:g} ч полёта"] if d.flight_hours_from_msk else [],
                why=d.description,
                actions=[CardAction(type="choose_destination", label="Выбрать",
                                    payload={"destination_id": d.id})],
            ).model_dump())
        return cards

    if state.stage == Stage.hotel_selection:
        return [HotelCard(
            id=h.id, name=h.name, stars=h.stars, rating=h.rating,
            price_total=h.price_per_night * (r.nights or 1), meal_plan=MEAL.get(h.meal_plan, h.meal_plan),
            cancel_policy=h.cancel_policy, beach_distance=h.beach_distance_m, image_url=h.image_url,
            lat=h.lat, lon=h.lon,
            pros=catalog.get_meta(h.id).get("pros", []),
            tradeoffs=catalog.get_meta(h.id).get("tradeoffs", []),
            risks=catalog.get_meta(h.id).get("risks", []),
            actions=[CardAction(type="select_hotel", label="Выбрать", payload={"hotel_id": h.id})],
        ).model_dump() for h in filter(None, map(catalog.get, sl.hotels))]

    if state.stage == Stage.transport_selection:
        if not s.outbound_flight_id:
            return [_flight_card(f, n, "out") for f in filter(None, map(catalog.get, sl.outbound_flights))]
        if not s.return_flight_id:
            return [_flight_card(f, n, "back") for f in filter(None, map(catalog.get, sl.return_flights))]
        # Оба рейса выбраны, трансферы подобраны, но не выбран — показываем трансферы
    if state.stage == Stage.trip_review and sl.transfers and not s.transfer_ids:
        return [TransferCard(
            id=t.id, kind=t.kind, duration_min=t.duration_min, price=t.price,
            actions=[CardAction(type="select_transfer", label="Выбрать", payload={"transfer_id": t.id})],
        ).model_dump() for t in filter(None, map(catalog.get, sl.transfers))]
    
    if state.stage == Stage.purchased and state.order_id:
        return [{"type": "order", "id": state.order_id,
                 "items": [i.model_dump() for i in state.cart], "total": state.cart_total()}]

    return []


def build_quick_replies(state: TripState) -> list[str]:
    return {
        Stage.clarifying: ["Из Москвы", "Вдвоём", "В ноябре"],
        Stage.destination_choice: ["Покажи подешевле", "Хочу теплее", "Без долгих перелётов"],
        Stage.hotel_selection: ["Подешевле", "Ближе к морю", "Только с бесплатной отменой"],
        Stage.transport_selection: ["Без пересадок", "Самый дешёвый", "Удобное время"],
        Stage.trip_review: ["Подтверждаю, оформляй", "Поменять даты", "Поменять отель"],
        Stage.purchased: ["Новая поездка"],
    }.get(state.stage, [])
