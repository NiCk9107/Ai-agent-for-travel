"""
Пересборка плана при изменении условий (раздел 2.4 плана).
Пользователь пишет «а если на два дня позже?» → агент вызывает update_requirements →
этот код по графу зависимостей сбрасывает ТОЛЬКО зависимые части, подбирает замену
(тот же отель, похожий рейс на новые даты) и считает разницу в цене.
Модели остаётся только объяснить готовый diff: «отель тот же, перелёт +3 200 ₽».
"""
from __future__ import annotations

from datetime import date

from agent import catalog
from agent.state import CartItem, ChangeLogEntry, Stage, TripState
from logic.scoring import passes_must_have, score_hotels

# Изменилось поле → что затронуто (раздел 2.4)
DEPENDENCIES: dict[str, list[str]] = {
    "date_from": ["flights", "hotel_nights"],
    "date_to": ["flights", "hotel_nights"],
    "nights": ["flights", "hotel_nights"],
    "month": ["flights", "hotel_nights"],
    "origin": ["flights"],
    "adults": ["rooms", "flight_prices", "transfers"],
    "children": ["rooms", "flight_prices", "transfers"],
    "pets": ["hotel_rules", "flight_rules"],
    "must_have": ["hotel_rules", "flight_rules", "rerank"],
    "budget_total_rub": ["rerank"],
    "mood": ["rerank"],
    "nice_to_have": ["rerank"],
}

TRANSFER_NAMES = {"taxi": "Такси", "shuttle": "Шаттл", "public": "Общественный транспорт"}
NO_STOPS_WORDS = ("без пересад", "прям")


def rub(x: int) -> str:
    return f"{x:,} ₽".replace(",", " ")


def passengers(state: TripState) -> int:
    r = state.requirements
    return (r.adults or 1) + len(r.children)


# ───────────── Цены выбранного ─────────────

def trip_parts(state: TripState) -> dict[str, int]:
    """Стоимость выбранного по частям (даже если ещё не в корзине)."""
    s, r, n = state.selected, state.requirements, passengers(state)
    parts = {"hotel": 0, "flights": 0, "transfer": 0}
    hotel = catalog.get(s.hotel_id) if s.hotel_id else None
    if hotel and r.nights:
        parts["hotel"] = hotel.price_per_night * r.nights
    for fid in (s.outbound_flight_id, s.return_flight_id):
        f = catalog.get(fid) if fid else None
        if f:
            parts["flights"] += f.price_per_person * n
    for tid in s.transfer_ids:
        t = catalog.get(tid)
        if t:
            parts["transfer"] += t.price * 2
    return parts


def build_cart(state: TripState) -> list[CartItem]:
    s, r, n = state.selected, state.requirements, passengers(state)
    hotel = catalog.get(s.hotel_id)
    out, back = catalog.get(s.outbound_flight_id), catalog.get(s.return_flight_id)
    room = next((rm for rm in hotel.rooms if rm.id == s.room_id), None)
    cart = [
        CartItem(kind="hotel", ref_id=hotel.id,
                 title=f"{hotel.name}, {room.name + ', ' if room else ''}{r.nights} ночей",
                 price=hotel.price_per_night * r.nights),
        CartItem(kind="flight", ref_id=out.id, title=f"{out.airline} {out.origin_airport}→{out.dest_airport}",
                 price=out.price_per_person * n),
        CartItem(kind="flight", ref_id=back.id, title=f"{back.airline} {back.origin_airport}→{back.dest_airport}",
                 price=back.price_per_person * n),
    ]
    for tid in s.transfer_ids:
        t = catalog.get(tid)
        if t:
            cart.append(CartItem(kind="transfer", ref_id=t.id,
                                 title=f"{TRANSFER_NAMES.get(t.kind, t.kind)} аэропорт ↔ отель, туда и обратно",
                                 price=t.price * 2))
    return cart


# ───────────── Правила для рейсов ─────────────

def flight_ok(f, req) -> bool:
    """Подходит ли рейс под обязательные условия (питомец, без пересадок)."""
    if req.pets and not f.pets_allowed:
        return False
    must = " ".join(req.must_have).lower()
    if any(w in must for w in NO_STOPS_WORDS) and f.stops > 0:
        return False
    return True


def pick_equivalent(old, candidates: list):
    """Самая похожая замена: та же авиакомпания, ближайшее время вылета."""
    if not candidates:
        return None
    def closeness(f):
        same_airline = 0 if f.airline == old.airline else 1
        minutes = abs((f.depart.hour * 60 + f.depart.minute) - (old.depart.hour * 60 + old.depart.minute))
        return (same_airline, minutes)
    return min(candidates, key=closeness)


# ───────────── Снимок «до» и описание изменений ─────────────

def snapshot(state: TripState) -> dict:
    parts = trip_parts(state)
    s = state.selected
    # Копии объектов рейсов: новый поиск может перезаписать каталог теми же id
    flights = {attr: catalog.get(getattr(s, attr)).model_copy()
               for attr in ("outbound_flight_id", "return_flight_id")
               if getattr(s, attr) and catalog.get(getattr(s, attr))}
    return {"hotel_id": s.hotel_id, "room_id": s.room_id, "flights": flights,
            "out_id": s.outbound_flight_id, "back_id": s.return_flight_id,
            "transfer_id": s.transfer_ids[0] if s.transfer_ids else None,
            "parts": parts, "total": sum(parts.values()), "cart_nonempty": bool(state.cart),
            "had_hotels": bool(state.shortlist.hotels)}


def _fmt_value(field: str, v) -> str:
    if v is None or v == []:
        return "—"
    if isinstance(v, date):
        return v.strftime("%d.%m")
    if field == "budget_total_rub":
        return rub(v)
    if isinstance(v, list):
        return ", ".join(str(x.get("kind", x.get("age", x)) if isinstance(x, dict) else x) for x in v)
    return str(v)


FIELD_NAMES = {"date_from": "заезд", "date_to": "выезд", "nights": "ночей", "month": "месяц",
               "origin": "вылет из", "adults": "взрослых", "children": "дети (возраст)",
               "pets": "питомцы", "budget_total_rub": "бюджет", "must_have": "обязательно",
               "mood": "пожелания", "nice_to_have": "желательно"}


def describe(changes: list[tuple[str, object, object]]) -> list[str]:
    return [f"{FIELD_NAMES.get(f, f)}: {_fmt_value(f, old)} → {_fmt_value(f, new)}" for f, old, new in changes]


# ───────────── Главная функция ─────────────

def apply_changes(state: TripState, changes: list[tuple[str, object, object]], before: dict) -> dict | None:
    """Пересобирает план после изменения требований. Возвращает diff или None."""
    from agent import tool_registry as tr   # импорт здесь — чтобы не было циклического импорта

    effects = {e for f, _, _ in changes for e in DEPENDENCIES.get(f, [])}
    nothing_chosen = not (before["hotel_id"] or before["out_id"] or before["had_hotels"])
    if not effects or nothing_chosen:
        return None

    s, r, n = state.selected, state.requirements, passengers(state)
    diff = {"changed": describe(changes), "kept": [], "replaced": [], "removed": [], "notes": []}
    if r.date_from or r.month:
        tr._ensure_dates(state)

    # 1. Отель: вместимость, питомец, обязательные условия
    hotel = catalog.get(s.hotel_id) if s.hotel_id else None
    if hotel and effects & {"rooms", "hotel_rules"}:
        fresh = {h.id: h for h in catalog.remember(
            tr.search_hotels_impl(r.destination_id, r.adults or 1, len(r.children)))}
        new_h = fresh.get(hotel.id)
        old_room = next((rm.name for rm in hotel.rooms if rm.id == s.room_id), None)
        if new_h is None:
            diff["removed"].append(f"отель {hotel.name}: нет номера на {n} гостей")
            s.hotel_id = s.room_id = None
        elif not passes_must_have(new_h, r):
            reason = "не принимает животных" if r.pets and not new_h.pet_friendly else "не подходит под обязательные условия"
            diff["removed"].append(f"отель {hotel.name}: {reason}")
            s.hotel_id = s.room_id = None
        else:
            s.room_id = new_h.rooms[0].id
            if old_room and new_h.rooms[0].name != old_room:
                diff["replaced"].append(f"номер: {old_room} → {new_h.rooms[0].name}")
            diff["kept"].append(f"отель {new_h.name}")
    elif hotel:
        diff["kept"].append(f"отель {hotel.name}")

    # 2. Отель сброшен или ещё не выбран — заново подбираем и ранжируем
    if not s.hotel_id and r.destination_id and (before["had_hotels"] or before["hotel_id"]) \
            and (effects & {"rooms", "hotel_rules", "rerank", "hotel_nights"}):
        hotels = catalog.remember(tr.search_hotels_impl(r.destination_id, r.adults or 1, len(r.children)))
        scores = score_hotels(hotels, r, r.nights or 7)[:3]
        for sc in scores:
            catalog.set_meta(sc.hotel_id, {"score": sc.score, "pros": sc.pros,
                                           "tradeoffs": sc.tradeoffs, "risks": sc.risks})
        state.shortlist.hotels = [sc.hotel_id for sc in scores]
        diff["notes"].append("подобрал отели заново под новые условия" if scores
                             else "ни один отель не подходит — нужно ослабить условия")

    # 3. Рейсы: новые даты / город вылета / питомец / без пересадок
    had_flights = before["out_id"] or before["back_id"] or state.shortlist.outbound_flights
    if had_flights and r.destination_id and effects & {"flights", "flight_rules"}:
        out_all = catalog.remember(tr.search_flights_impl(r.origin, r.destination_id, r.date_from, n, "out"))
        back_all = catalog.remember(tr.search_flights_impl(r.origin, r.destination_id, r.date_to, n, "back"))
        out_ok = [f for f in out_all if flight_ok(f, r)]
        back_ok = [f for f in back_all if flight_ok(f, r)]
        state.shortlist.outbound_flights = [f.id for f in (out_ok or out_all)]
        state.shortlist.return_flights = [f.id for f in (back_ok or back_all)]
        for attr, label, ok, all_, day in (
                ("outbound_flight_id", "рейс туда", out_ok, out_all, r.date_from),
                ("return_flight_id", "рейс обратно", back_ok, back_all, r.date_to)):
            old = before["flights"].get(attr) if getattr(s, attr) else None
            if not old:
                continue
            route_changed = bool(all_) and (old.origin_airport, old.dest_airport) != \
                (all_[0].origin_airport, all_[0].dest_airport)
            must_replace = old.depart.date() != day or route_changed or not flight_ok(old, r)
            if not must_replace:
                diff["kept"].append(f"{label} {old.airline} {old.depart:%d.%m %H:%M}")
                continue
            new = pick_equivalent(old, ok)
            if new:
                setattr(s, attr, new.id)
                diff["replaced"].append(f"{label}: {old.airline} {old.origin_airport}→{old.dest_airport} "
                                        f"{old.depart:%d.%m %H:%M} → {new.airline} "
                                        f"{new.origin_airport}→{new.dest_airport} {new.depart:%d.%m %H:%M}")
            else:
                setattr(s, attr, None)
                diff["removed"].append(f"{label}: нет подходящих рейсов, нужно выбрать вручную")
    elif before["out_id"] and "flight_prices" in effects:
        diff["notes"].append(f"билеты пересчитаны на {n} пассажиров")

    # 4. Трансфер: зависит от отеля и числа пассажиров
    if s.transfer_ids:
        old_t = catalog.get(s.transfer_ids[0])
        hotel = catalog.get(s.hotel_id) if s.hotel_id else None
        dest = tr._destination(state)
        if not hotel or not dest:
            s.transfer_ids, state.shortlist.transfers = [], []
            diff["removed"].append("трансфер: сначала нужно выбрать отель")
        elif "transfers" in effects or (before["hotel_id"] != s.hotel_id):
            ts = catalog.remember(tr.estimate_transfer_impl(dest.airport_code, hotel.lat, hotel.lon, n))
            state.shortlist.transfers = [t.id for t in ts]
            same = next((t for t in ts if old_t and t.kind == old_t.kind), None)
            s.transfer_ids = [same.id] if same else []
            if not same:
                diff["removed"].append("трансфер: нужно выбрать заново")

    # 5. Итоги, корзина, этап, проверка
    after_parts = trip_parts(state)
    total_after = sum(after_parts.values())
    price_changes = []
    for key, label in (("hotel", "отель"), ("flights", "перелёт"), ("transfer", "трансфер")):
        delta = after_parts[key] - before["parts"][key]
        if delta and before["parts"][key] and after_parts[key]:   # выпавшее — не «подешевело»
            price_changes.append({"item": label, "delta": delta,
                                  "text": f"{label} {'+' if delta > 0 else '−'}{rub(abs(delta))}"})

    complete = s.hotel_id and s.outbound_flight_id and s.return_flight_id
    if before["cart_nonempty"]:
        if complete:
            state.cart = build_cart(state)
        else:
            state.cart = []
            diff["notes"].append("корзина очищена: нужно заново выбрать то, что выпало")
    recompute_stage(state)
    tr.run_validation(state)

    diff.update({"price_changes": price_changes, "total_before": before["total"],
                 "total_after": total_after, "delta": total_after - before["total"],
                 "budget": r.budget_total_rub,
                 "over_budget_by": max(0, total_after - r.budget_total_rub) if r.budget_total_rub else 0})
    state.change_log.append(ChangeLogEntry(field=", ".join(f for f, _, _ in changes),
                                           reset=diff["removed"] + diff["replaced"]))
    return diff


def recompute_stage(state: TripState) -> None:
    """Этап по тому, что сейчас выбрано (после сброса можно откатиться назад)."""
    s = state.selected
    if state.stage == Stage.purchased:
        return
    if not state.requirements.destination_id:
        return
    if not s.hotel_id:
        state.stage = Stage.hotel_selection
    elif not (s.outbound_flight_id and s.return_flight_id):
        state.stage = Stage.transport_selection
    else:
        state.stage = Stage.trip_review     # всё выбрано — проверка и подтверждение


def changes_card(diff: dict, n: int) -> dict:
    """Карточка «Что изменилось» для фронта (плашка в чате)."""
    items = ([{"kind": "changed", "text": t} for t in diff["changed"]]
             + [{"kind": "kept", "text": t} for t in diff["kept"]]
             + [{"kind": "replaced", "text": t} for t in diff["replaced"]]
             + [{"kind": "removed", "text": t} for t in diff["removed"]]
             + [{"kind": "price", "text": p["text"]} for p in diff["price_changes"]]
             + [{"kind": "note", "text": t} for t in diff["notes"]])
    return {"type": "changes", "id": f"chg_{n}", "title": "Что изменилось", "items": items,
            "total_before": diff["total_before"], "total_after": diff["total_after"],
            "delta": diff["delta"], "actions": []}