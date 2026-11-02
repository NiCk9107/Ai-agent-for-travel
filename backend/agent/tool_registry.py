"""
Инструменты агента: схемы для модели + функции-обработчики + dispatch.
Описание инструмента говорит модели, КОГДА его вызывать.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Literal, Optional

from pydantic import BaseModel, Field

from agent import catalog, replan, stubs
from agent.llm import make_tool
from logic.scoring import score_hotels
from logic.validator import Trip, build_timeline, validate
from agent.state import ChangeLogEntry, Child, Pet, Stage, TripState, missing_required

# Настоящие функции B (направления, рейсы, отели, трансферы)
from tools.destinations import suggest_destinations as suggest_destinations_impl
from tools.flights import search_flights as search_flights_impl
from tools.hotels import search_hotels as search_hotels_impl
from tools.transfers import estimate_transfer as estimate_transfer_impl


# ───────────── Аргументы инструментов ─────────────

class UpdateRequirementsArgs(BaseModel):
    origin: Optional[str] = Field(None, description="Город вылета")
    month: Optional[str] = Field(None, description="Месяц поездки YYYY-MM")
    date_from: Optional[date] = Field(None, description="Дата заезда YYYY-MM-DD, если названа")
    date_to: Optional[date] = Field(None, description="Дата выезда YYYY-MM-DD, если названа")
    nights: Optional[int] = None
    adults: Optional[int] = None
    children_ages: Optional[list[int]] = Field(None, description="Возрасты детей")
    budget_total_rub: Optional[int] = None
    max_travel_hours: Optional[float] = None
    mood: Optional[list[str]] = Field(None, description="Настроение: «тёплое море», «спокойно»")
    must_have: Optional[list[str]] = Field(None, description="Обязательные условия: «бесплатная отмена», «без пересадок»")
    nice_to_have: Optional[list[str]] = None
    pets: Optional[list[str]] = Field(None, description="Питомцы, напр. [«собака»]; [] — без питомцев")
    assumptions: Optional[list[str]] = Field(
        None, description="Допущения, которые ты сделал сам, напр. «Вылет из Москвы»")


class SuggestDestinationsArgs(BaseModel):
    tags: list[str] = Field(default_factory=list, description="Теги: море, горы, город...")


class SelectOptionArgs(BaseModel):
    kind: Literal["destination", "hotel", "outbound_flight", "return_flight", "transfer"]
    id: str


class Empty(BaseModel):
    pass


class CompareArgs(BaseModel):
    kind: Literal["hotel", "outbound_flight", "return_flight", "transfer"]
    ids: list[str] = Field(description="id 2–4 вариантов из показанных")


class RemoveArgs(BaseModel):
    ref_id: str = Field(description="ref_id позиции корзины")


class CheckoutArgs(BaseModel):
    confirmed: bool = Field(description="true только если пользователь явно подтвердил оплату")


TOOLS = [
    make_tool("update_requirements",
              "Вызывай КАЖДЫЙ раз, когда пользователь сообщает что-то о поездке "
              "(откуда, когда, кто едет, бюджет, пожелания) или меняет условия. "
              "Передавай только новые/изменённые поля. Сюда же записывай свои допущения.",
              UpdateRequirementsArgs),
    make_tool("suggest_destinations",
              "Подобрать 3 направления. Вызывай, когда обязательные поля известны, "
              "а направление пользователь ещё не выбрал.", SuggestDestinationsArgs),
    make_tool("select_option",
              "Зафиксировать выбор пользователя: направление, отель, рейс туда или обратно. "
              "Вызывай, когда пользователь выбрал вариант (словами или кнопкой).", SelectOptionArgs),
    make_tool("search_hotels",
              "Подобрать отели в выбранном направлении. Вызывай сразу после выбора направления.", Empty),
    make_tool("search_flights",
              "Подобрать рейсы туда и обратно. Вызывай после выбора отеля.", Empty),
    make_tool("estimate_transfer",
              "Подобрать трансфер аэропорт ↔ отель (такси, шаттл, общественный транспорт). "
              "Вызывай после выбора обоих рейсов.", Empty),
    make_tool("validate_trip",
              "Проверить состыковки: даты, прилёт → трансфер → заселение, выезд → вылет, "
              "вместимость номера, животные, бюджет. ОБЯЗАТЕЛЬНО вызывай перед add_to_cart "
              "и после любого изменения выбора.", Empty),
    make_tool("compare_options",
              "Таблица сравнения 2–4 вариантов одного типа. Вызывай, когда пользователь "
              "просит сравнить или сомневается между вариантами.", CompareArgs),
    make_tool("add_to_cart",
              "Положить выбранные отель, рейсы и трансфер в корзину и посчитать итог. "
              "Вызывай после validate_trip без ошибок (error).", Empty),
    make_tool("remove_from_cart",
              "Убрать позицию из корзины (отель, рейс или трансфер). Вызывай, когда пользователь "
              "просит что-то убрать словами.", RemoveArgs),
    make_tool("checkout",
              "Оформить заказ. Вызывай ТОЛЬКО после того, как показал итог и сумму "
              "и пользователь явно подтвердил.", CheckoutArgs),
]


# ───────────── Вспомогательное ─────────────

def _passengers(state: TripState) -> int:
    r = state.requirements
    return (r.adults or 1) + len(r.children)


def _ensure_dates(state: TripState) -> tuple[date, date]:
    """Если точных дат нет — берём допущение: с 10-го числа месяца, 7 ночей."""
    r = state.requirements
    if not r.date_from:
        if not r.month:
            raise ValueError("Неизвестен период поездки — спроси пользователя")
        y, m = map(int, r.month.split("-"))
        r.date_from = date(y, m, 10)
        r.assumptions.append(f"Даты: с {r.date_from:%d.%m}, поправьте, если нужно другие")
    if not r.date_to:
        r.date_to = r.date_from + timedelta(days=r.nights or 7)
        if not r.nights:
            r.assumptions.append("7 ночей — стандартная длительность")
    r.nights = (r.date_to - r.date_from).days
    return r.date_from, r.date_to


def _destination(state: TripState):
    d = catalog.get(state.requirements.destination_id or "")
    if d is None:
        try:  # после перезапуска сервера каталог пуст — берём из базы B
            from tools.destinations import get_destination
            d = get_destination(state.requirements.destination_id)
        except ImportError:
            d = None
    return d


def _build_trip(state: TripState) -> Trip:
    """Собирает всё выбранное в объект для validator.py."""
    s = state.selected
    hotel = catalog.get(s.hotel_id) if s.hotel_id else None
    room = next((r for r in hotel.rooms if r.id == s.room_id), None) if hotel else None
    transfer = catalog.get(s.transfer_ids[0]) if s.transfer_ids else None
    return Trip(req=state.requirements, hotel=hotel, room=room,
                outbound=catalog.get(s.outbound_flight_id) if s.outbound_flight_id else None,
                back=catalog.get(s.return_flight_id) if s.return_flight_id else None,
                transfer_min=transfer.duration_min if transfer else None,
                total=state.cart_total())


def run_validation(state: TripState) -> list:
    issues = validate(_build_trip(state))
    state.validation.issues = issues
    state.validation.ok = not any(i.severity == "error" for i in issues)
    return issues


def trip_timeline(state: TripState) -> list[dict]:
    """Таймлайн для фронта (trip.timeline): шаги поездки + подсветка проблем."""
    t = _build_trip(state)
    return build_timeline(t, state.validation.issues)


# ───────────── Обработчики ─────────────

def update_requirements(args: UpdateRequirementsArgs, state: TripState) -> dict:
    r = state.requirements
    data = args.model_dump(exclude_none=True)
    before = replan.snapshot(state)          # что было выбрано и сколько стоило ДО изменения
    changes: list[tuple[str, object, object]] = []

    # Даты: «на два дня позже» = сдвигаем заезд и выезд, длительность сохраняем
    if "date_from" in data and "date_to" not in data and r.date_from and r.date_to:
        data["date_to"] = data["date_from"] + timedelta(days=(r.date_to - r.date_from).days)
    if "nights" in data and "date_to" not in data and (data.get("date_from") or r.date_from):
        data["date_to"] = (data.get("date_from") or r.date_from) + timedelta(days=data["nights"])
    if "month" in data and data["month"] != r.month and "date_from" not in data:
        r.date_from = r.date_to = None        # новый месяц — даты пересчитаются в _ensure_dates

    if "children_ages" in data:
        ages = data.pop("children_ages")
        old_ages = [c.age for c in r.children]
        if sorted(ages) != sorted(old_ages):
            r.children = [Child(age=a) for a in ages]
            changes.append(("children", old_ages, ages))
    if "pets" in data:
        kinds = data.pop("pets")
        old_kinds = [p.kind for p in r.pets]
        if kinds != old_kinds:
            r.pets = [Pet(kind=k) for k in kinds]
            changes.append(("pets", old_kinds, kinds))
    if "assumptions" in data:
        for a in data.pop("assumptions"):
            if a not in r.assumptions:
                r.assumptions.append(a)

    for field, new in data.items():
        old = getattr(r, field)
        if old != new:
            setattr(r, field, new)
            changes.append((field, old, new))
    if r.date_from and r.date_to:
        r.nights = (r.date_to - r.date_from).days

    for field, old, new in changes:
        state.change_log.append(ChangeLogEntry(field=field, old=old, new=new))

    missing = missing_required(state)
    if missing:
        state.stage = Stage.clarifying
    elif state.stage == Stage.clarifying:
        state.stage = Stage.inspiration

    result = {"requirements": r.model_dump(mode="json", exclude_none=True), "missing": missing}

    # Пересборка плана: сбрасываем только зависимое, подбираем замену, считаем разницу
    diff = replan.apply_changes(state, changes, before)
    if diff:
        result["replan"] = diff
        result["card"] = replan.changes_card(diff, len(state.change_log))
    return result


def suggest_destinations(args: SuggestDestinationsArgs, state: TripState) -> dict:
    if missing_required(state):
        return {"error": f"Сначала уточни: {missing_required(state)}"}
    r = state.requirements
    dests = catalog.remember(suggest_destinations_impl(r.month, args.tags, r.max_travel_hours))
    state.shortlist.destinations = [d.id for d in dests]
    state.stage = Stage.destination_choice
    return {"destinations": [d.model_dump(mode="json") for d in dests]}


def select_option(args: SelectOptionArgs, state: TripState) -> dict:
    obj = catalog.get(args.id)
    if obj is None:
        return {"error": f"Вариант {args.id} не найден среди показанных"}
    # Рейс «туда» нельзя записать в «обратно» и наоборот — иначе диалог зацикливается
    if args.kind == "outbound_flight" and args.id not in state.shortlist.outbound_flights:
        return {"error": f"{args.id} — не рейс туда. Рейсы туда: {state.shortlist.outbound_flights}"}
    if args.kind == "return_flight" and args.id not in state.shortlist.return_flights:
        return {"error": f"{args.id} — не рейс обратно. Рейсы обратно: {state.shortlist.return_flights}"}
    s = state.selected
    if args.kind == "destination":
        state.requirements.destination_id = args.id
        s.hotel_id = s.room_id = s.outbound_flight_id = s.return_flight_id = None
        s.transfer_ids, state.shortlist.transfers = [], []
        state.shortlist.hotels, state.shortlist.outbound_flights, state.shortlist.return_flights = [], [], []
        state.cart = []                                          # новое направление — всё заново
        state.validation.issues, state.validation.ok = [], None
        state.stage = Stage.hotel_selection
    elif args.kind == "hotel":
        s.hotel_id = args.id
        s.room_id = obj.rooms[0].id if obj.rooms else None
        s.transfer_ids, state.shortlist.transfers = [], []   # трансфер зависит от адреса отеля
        state.stage = Stage.transport_selection
    elif args.kind == "outbound_flight":
        s.outbound_flight_id = args.id
    elif args.kind == "return_flight":
        s.return_flight_id = args.id
    elif args.kind == "transfer":
        s.transfer_ids = [args.id]
    if s.hotel_id and s.outbound_flight_id and s.return_flight_id:
        state.stage = Stage.trip_review
    return {"selected": s.model_dump(), "stage": state.stage.value}


def search_hotels(args: Empty, state: TripState) -> dict:
    r = state.requirements
    if not r.destination_id:
        return {"error": "Сначала нужно выбрать направление"}
    _ensure_dates(state)
    hotels = catalog.remember(search_hotels_impl(r.destination_id, r.adults or 1, len(r.children)))

    # Ранжирует и объясняет КОД (logic/scoring.py), модель только пересказывает
    scores = score_hotels(hotels, r, r.nights)[:3]
    if not scores:
        return {"error": "Ни один отель не подходит под обязательные условия "
                         f"({', '.join(r.must_have) or 'питомец'}). Предложи ослабить условия."}
    for sc in scores:
        catalog.set_meta(sc.hotel_id, {"score": sc.score, "pros": sc.pros,
                                       "tradeoffs": sc.tradeoffs, "risks": sc.risks})
    state.shortlist.hotels = [sc.hotel_id for sc in scores]
    state.stage = Stage.hotel_selection

    return {"nights": r.nights, "hotels": [
        {"id": sc.hotel_id, "name": catalog.get(sc.hotel_id).name, "score": sc.score,
         "price_total": sc.price_total, "pros": sc.pros, "tradeoffs": sc.tradeoffs, "risks": sc.risks}
        for sc in scores]}


def search_flights(args: Empty, state: TripState) -> dict:
    r = state.requirements
    if not r.destination_id:
        return {"error": "Сначала нужно выбрать направление"}
    d_from, d_to = _ensure_dates(state)
    n = _passengers(state)
    out_all = catalog.remember(search_flights_impl(r.origin, r.destination_id, d_from, n, "out"))
    back_all = catalog.remember(search_flights_impl(r.origin, r.destination_id, d_to, n, "back"))
    # Питомец / «без пересадок» — отсекаем неподходящие (если не осталось ничего — показываем все)
    out = [f for f in out_all if replan.flight_ok(f, r)] or out_all
    back = [f for f in back_all if replan.flight_ok(f, r)] or back_all
    state.shortlist.outbound_flights = [f.id for f in out]
    state.shortlist.return_flights = [f.id for f in back]
    state.stage = Stage.transport_selection
    fmt = lambda f: {**f.model_dump(mode="json"), "price_total": f.price_per_person * n}
    return {"passengers": n, "outbound": [fmt(f) for f in out], "return": [fmt(f) for f in back]}


def estimate_transfer(args: Empty, state: TripState) -> dict:
    s = state.selected
    hotel = catalog.get(s.hotel_id) if s.hotel_id else None
    dest = _destination(state)
    if not (hotel and dest):
        return {"error": "Сначала нужно выбрать направление и отель"}
    transfers = catalog.remember(
        estimate_transfer_impl(dest.airport_code, hotel.lat, hotel.lon, _passengers(state)))
    state.shortlist.transfers = [t.id for t in transfers]
    return {"transfers": [t.model_dump() for t in transfers]}


def validate_trip(args: Empty, state: TripState) -> dict:
    issues = run_validation(state)
    return {"ok": state.validation.ok,
            "issues": [i.model_dump() for i in issues],
            "note": "error — исправить до корзины; warning — сказать пользователю и предложить fix_suggestion"}


KIND_TITLES = {"hotel": "Сравнение отелей", "outbound_flight": "Сравнение рейсов туда",
               "return_flight": "Сравнение рейсов обратно", "transfer": "Сравнение трансферов"}
TRANSFER_NAMES = replan.TRANSFER_NAMES


def _rub(x: int) -> str:
    return f"{x:,} ₽".replace(",", " ")


def _row(label: str, raw: list, shown: list, best: str | None) -> dict:
    """best: 'min' / 'max' / None — какую колонку подсветить как лучшую (считает код)."""
    winner = None
    if best and len(set(raw)) > 1:
        target = min(raw) if best == "min" else max(raw)
        winner = raw.index(target)
    return {"label": label, "values": shown, "best": winner}


def _column(kind: str, item) -> dict:
    """Колонка таблицы: название + кнопка «Выбрать» прямо в сравнении."""
    if kind == "hotel":
        name, action = item.name, {"type": "select_hotel", "payload": {"hotel_id": item.id}}
    elif kind in ("outbound_flight", "return_flight"):
        name = f"{item.airline} {item.depart:%H:%M}"
        action = {"type": "select_flight",
                  "payload": {"flight_id": item.id, "direction": "out" if kind == "outbound_flight" else "back"}}
    else:
        name, action = TRANSFER_NAMES.get(item.kind, item.kind), \
            {"type": "select_transfer", "payload": {"transfer_id": item.id}}
    return {"id": item.id, "name": name, "actions": [{**action, "label": "Выбрать"}]}


def compare_options(args: CompareArgs, state: TripState) -> dict:
    items = [catalog.get(i) for i in args.ids]
    items = [x for x in items if x is not None]
    if len(items) < 2:
        return {"error": "Для сравнения нужно минимум 2 варианта из показанных"}
    r, n = state.requirements, _passengers(state)
    rows = []

    if args.kind == "hotel":
        nights = r.nights or 1
        rows.append(_row(f"Цена за {nights} ноч.", [h.price_per_night * nights for h in items],
                         [_rub(h.price_per_night * nights) for h in items], "min"))
        rows.append(_row("Звёзды", [h.stars for h in items], ["★" * h.stars for h in items], "max"))
        rows.append(_row("Рейтинг", [h.rating or 0 for h in items], [str(h.rating or "—") for h in items], "max"))
        rows.append(_row("До пляжа", [h.beach_distance_m or 99999 for h in items],
                         [f"{h.beach_distance_m} м" if h.beach_distance_m else "—" for h in items], "min"))
        rows.append(_row("Питание", [h.meal_plan == "AI" for h in items],
                         [{"AI": "Всё включено", "HB": "Полупансион", "FB": "Полный пансион",
                           "BB": "Завтраки", "RO": "Без питания"}.get(h.meal_plan, h.meal_plan) for h in items], "max"))
        rows.append(_row("Бесплатная отмена", [h.cancel_policy.startswith("free_cancel") for h in items],
                         ["да" if h.cancel_policy.startswith("free_cancel") else "нет" for h in items], "max"))
        rows.append(_row("Детский клуб", [h.kids_club for h in items],
                         ["да" if h.kids_club else "нет" for h in items], "max" if r.children else None))
    elif args.kind in ("outbound_flight", "return_flight"):
        rows.append(_row("Цена на всех", [f.price_per_person * n for f in items],
                         [_rub(f.price_per_person * n) for f in items], "min"))
        dur = [(f.arrive - f.depart).total_seconds() / 60 for f in items]
        rows.append(_row("В пути", dur, [f"{int(d // 60)} ч {int(d % 60):02d} мин" for d in dur], "min"))
        rows.append(_row("Пересадки", [f.stops for f in items], [str(f.stops) for f in items], "min"))
        rows.append(_row("Багаж", [f.baggage for f in items], ["включён" if f.baggage else "нет" for f in items], "max"))
        rows.append(_row("Вылет → прилёт", [0] * len(items),
                         [f"{f.depart:%d.%m %H:%M} → {f.arrive:%H:%M}" for f in items], None))
    else:
        rows.append(_row("Цена", [t.price for t in items], [_rub(t.price) for t in items], "min"))
        rows.append(_row("В пути", [t.duration_min for t in items], [f"{t.duration_min} мин" for t in items], "min"))

    columns = [_column(args.kind, x) for x in items]
    card = {"type": "comparison", "id": "cmp_" + "_".join(args.ids)[:60], "title": KIND_TITLES[args.kind],
            "columns": columns, "rows": rows, "actions": []}
    names = [c["name"] for c in columns]
    # "card" core.py покажет пользователю; модели отдаём только сводку
    return {"card": card, "summary": {row["label"]: {"values": dict(zip(names, row["values"])),
                                                     "best": names[row["best"]] if row["best"] is not None else None}
                                      for row in rows}}


def add_to_cart(args: Empty, state: TripState) -> dict:
    s, r = state.selected, state.requirements
    if not (s.hotel_id and s.outbound_flight_id and s.return_flight_id):
        return {"error": "Нужно выбрать отель и оба рейса"}
    cart = replan.build_cart(state)

    old_cart, state.cart = state.cart, cart
    issues = run_validation(state)            # проверка состыковок — обязательна, делает код
    errors = [i for i in issues if i.severity == "error"]
    if errors:
        state.cart = old_cart                 # с ошибками в корзину не кладём
        return {"error": "Поездка не состыкуется — в корзину не добавлено",
                "issues": [i.model_dump() for i in errors]}

    state.stage = Stage.trip_review          # «Шаг 5 из 6 · Проверка» — ждём подтверждения
    total = state.cart_total()
    budget = r.budget_total_rub
    return {"cart": [i.model_dump() for i in state.cart], "total": total,
            "over_budget_by": max(0, total - budget) if budget else None,
            "warnings": [i.model_dump() for i in issues]}


def remove_from_cart(args: RemoveArgs, state: TripState) -> dict:
    item = next((i for i in state.cart if i.ref_id == args.ref_id), None)
    if item is None:
        return {"error": "Такой позиции нет в корзине"}
    s = state.selected
    state.cart = [i for i in state.cart if i.ref_id != args.ref_id]
    if item.kind == "hotel":
        s.hotel_id = s.room_id = None
        s.transfer_ids, state.shortlist.transfers = [], []          # трансфер зависит от отеля
        state.cart = [i for i in state.cart if i.kind != "transfer"]
    elif item.kind == "flight":
        if s.outbound_flight_id == args.ref_id:
            s.outbound_flight_id = None
        if s.return_flight_id == args.ref_id:
            s.return_flight_id = None
    elif item.kind == "transfer":
        s.transfer_ids = []
    replan.recompute_stage(state)
    run_validation(state)
    return {"removed": item.title, "cart": [i.model_dump() for i in state.cart],
            "total": state.cart_total(), "stage": state.stage.value}


def checkout(args: CheckoutArgs, state: TripState) -> dict:
    if not args.confirmed:
        return {"error": "Пользователь не подтвердил оплату — спроси подтверждение"}
    if not state.cart:
        return {"error": "Корзина пуста"}
    state.order_id = "ORD-" + uuid.uuid4().hex[:6].upper()
    state.stage = Stage.purchased
    return {"order_id": state.order_id, "total": state.cart_total(), "status": "paid"}


# ───────────── Диспетчер ─────────────

HANDLERS = {
    "update_requirements": (update_requirements, UpdateRequirementsArgs),
    "suggest_destinations": (suggest_destinations, SuggestDestinationsArgs),
    "select_option": (select_option, SelectOptionArgs),
    "search_hotels": (search_hotels, Empty),
    "search_flights": (search_flights, Empty),
    "estimate_transfer": (estimate_transfer, Empty),
    "validate_trip": (validate_trip, Empty),
    "compare_options": (compare_options, CompareArgs),
    "add_to_cart": (add_to_cart, Empty),
    "remove_from_cart": (remove_from_cart, RemoveArgs),
    "checkout": (checkout, CheckoutArgs),
}

STATUS_TEXT = {
    "update_requirements": "Разбираю запрос…",
    "suggest_destinations": "Подбираю направления…",
    "select_option": "Запоминаю выбор…",
    "search_hotels": "Ищу отели…",
    "search_flights": "Ищу рейсы…",
    "estimate_transfer": "Считаю трансфер…",
    "validate_trip": "Проверяю состыковки…",
    "compare_options": "Сравниваю варианты…",
    "add_to_cart": "Собираю корзину…",
    "remove_from_cart": "Убираю из корзины…",
    "checkout": "Оформляю заказ…",
}


def dispatch(name: str, args: dict, state: TripState) -> dict:
    if name not in HANDLERS:
        return {"error": f"Нет инструмента {name}"}
    func, model = HANDLERS[name]
    return func(model(**args), state)