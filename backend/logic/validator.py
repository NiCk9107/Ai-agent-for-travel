"""
Проверка состыковок поездки — чистые функции, БЕЗ LLM (раздел 2.7 плана).
LLM путается в датах и времени, поэтому «успеваем ли на заселение» считает код.
Каждая проблема: Issue(severity="error"|"warning", code, message, fix_suggestion).
error — поездка не состыкуется, в корзину нельзя; warning — можно, но предупредить.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional

from agent.state import Flight, Hotel, Issue, Requirements, Room

AIRPORT_BUFFER_DOMESTIC = timedelta(hours=2)
AIRPORT_BUFFER_INTERNATIONAL = timedelta(hours=3)
MAX_CHECKIN_WAIT = timedelta(hours=3)        # ждать заселения дольше — предупреждение
MAX_AIRPORT_WAIT = timedelta(hours=6)        # от выезда до вылета дольше — предупреждение
DEFAULT_TRANSFER = timedelta(minutes=60)     # если трансфер ещё не выбран

RUSSIAN_AIRPORTS = {"MOW", "SVO", "DME", "VKO", "LED", "KZN", "AER", "KGD", "MRV", "NAL",
                    "MCX", "NOZ", "RGK", "IKT", "PKC", "MMK", "SVX", "OVB"}


@dataclass
class Trip:
    """Всё, что нужно для проверки. Собирается из TripState в tool_registry."""
    req: Requirements
    hotel: Optional[Hotel] = None
    room: Optional[Room] = None
    outbound: Optional[Flight] = None
    back: Optional[Flight] = None
    transfer_min: Optional[int] = None      # длительность выбранного трансфера
    total: int = 0                          # итог корзины


def _t(hhmm: str) -> time:
    h, m = hhmm.split(":")
    return time(int(h), int(m))


def _fmt(dt: datetime) -> str:
    return dt.strftime("%d.%m %H:%M")


def _hours(td: timedelta) -> str:
    h = td.total_seconds() / 3600
    return f"{h:.1f}".rstrip("0").rstrip(".").replace(".", ",") + " ч"


def is_international(f: Flight) -> bool:
    return not ({f.origin_airport, f.dest_airport} <= RUSSIAN_AIRPORTS)


# ───────────── Отдельные проверки ─────────────

def check_nights(t: Trip) -> list[Issue]:
    r = t.req
    if r.date_from and r.date_to and r.nights is not None:
        real = (r.date_to - r.date_from).days
        if real != r.nights:
            return [Issue(severity="error", code="NIGHTS_MISMATCH",
                          message=f"Ночей в брони {r.nights}, а по датам {real}.",
                          fix_suggestion=f"Пересчитать отель на {real} ночей.")]
    return []


def check_arrival_date(t: Trip) -> list[Issue]:
    """Дата заезда = дата прилёта (или накануне, если прилёт ночью до 06:00)."""
    if not (t.outbound and t.req.date_from):
        return []
    arr = t.outbound.arrive.date()
    if arr == t.req.date_from:
        return []
    if arr == t.req.date_from + timedelta(days=1) and t.outbound.arrive.time() < time(6):
        return []  # ночной прилёт: номер с вечера накануне — это нормально
    return [Issue(severity="error", code="ARRIVAL_DATE_MISMATCH",
                  message=f"Рейс прилетает {_fmt(t.outbound.arrive)}, а заезд в отель {t.req.date_from:%d.%m}.",
                  fix_suggestion="Выбрать рейс на дату заезда или сдвинуть даты отеля.")]


def check_checkin_wait(t: Trip) -> list[Issue]:
    """Прилёт + трансфер не должен быть сильно раньше времени заселения."""
    if not (t.outbound and t.hotel):
        return []
    transfer = timedelta(minutes=t.transfer_min) if t.transfer_min else DEFAULT_TRANSFER
    at_hotel = t.outbound.arrive + transfer
    checkin = datetime.combine(at_hotel.date(), _t(t.hotel.checkin_time))
    wait = checkin - at_hotel
    if wait > MAX_CHECKIN_WAIT:
        return [Issue(severity="warning", code="CHECKIN_WAIT",
                      message=f"В отеле будете в {at_hotel:%H:%M}, заселение с {t.hotel.checkin_time} — "
                              f"ожидание около {_hours(wait)}.",
                      fix_suggestion="Запросить ранний заезд, оставить вещи в камере хранения "
                                     "или выбрать рейс попозже.")]
    return []


def check_return(t: Trip) -> list[Issue]:
    """Выезд + трансфер + время в аэропорту должны уложиться до обратного вылета."""
    if not (t.back and t.req.date_to):
        return []
    issues = []
    dep = t.back.depart
    if dep.date() != t.req.date_to:
        issues.append(Issue(severity="error", code="RETURN_DATE_MISMATCH",
                            message=f"Обратный рейс {_fmt(dep)}, а выезд из отеля {t.req.date_to:%d.%m}.",
                            fix_suggestion="Выбрать обратный рейс на дату выезда или сдвинуть даты."))
        return issues

    transfer = timedelta(minutes=t.transfer_min) if t.transfer_min else DEFAULT_TRANSFER
    buffer = AIRPORT_BUFFER_INTERNATIONAL if is_international(t.back) else AIRPORT_BUFFER_DOMESTIC
    leave_by = dep - buffer - transfer                         # когда выехать из отеля
    checkout = datetime.combine(t.req.date_to, _t(t.hotel.checkout_time)) if t.hotel else None

    if leave_by.date() < t.req.date_to:
        issues.append(Issue(severity="warning", code="RETURN_NIGHT_LOST",
                            message=f"Вылет в {dep:%H:%M}: из отеля придётся выехать накануне в "
                                    f"{leave_by:%H:%M}, последняя ночь пропадает.",
                            fix_suggestion="Выбрать дневной обратный рейс или сократить отель на ночь."))
    elif checkout and leave_by - checkout > MAX_AIRPORT_WAIT:
        issues.append(Issue(severity="warning", code="LONG_WAIT_AFTER_CHECKOUT",
                            message=f"Выезд из отеля в {t.hotel.checkout_time}, а ехать в аэропорт только в "
                                    f"{leave_by:%H:%M} — свободных {_hours(leave_by - checkout)} без номера.",
                            fix_suggestion="Попросить поздний выезд или выбрать рейс пораньше."))
    return issues


def check_order(t: Trip) -> list[Issue]:
    if t.outbound and t.back and t.back.depart <= t.outbound.arrive:
        return [Issue(severity="error", code="FLIGHTS_ORDER",
                      message="Обратный рейс вылетает раньше, чем прилетает рейс туда.",
                      fix_suggestion="Выбрать рейсы заново.")]
    return []


def check_capacity(t: Trip) -> list[Issue]:
    if not t.room:
        return []
    adults, kids = t.req.adults or 1, len(t.req.children)
    if t.room.capacity_adults < adults or t.room.capacity_adults + t.room.capacity_children < adults + kids:
        return [Issue(severity="error", code="ROOM_CAPACITY",
                      message=f"Номер «{t.room.name}» рассчитан на {t.room.capacity_adults}+"
                              f"{t.room.capacity_children}, а едут {adults}+{kids}.",
                      fix_suggestion="Выбрать номер побольше или второй номер.")]
    return []


def check_pets(t: Trip) -> list[Issue]:
    if not t.req.pets:
        return []
    issues = []
    if t.hotel and not t.hotel.pet_friendly:
        issues.append(Issue(severity="error", code="PET_HOTEL",
                            message=f"Отель {t.hotel.name} не принимает животных.",
                            fix_suggestion="Выбрать отель с отметкой «можно с животными»."))
    for f, label in ((t.outbound, "туда"), (t.back, "обратно")):
        if f and not f.pets_allowed:
            issues.append(Issue(severity="error", code="PET_FLIGHT",
                                message=f"{f.airline} (рейс {label}) не перевозит животных.",
                                fix_suggestion="Выбрать перевозчика, который берёт животных."))
    return issues


def check_budget(t: Trip) -> list[Issue]:
    budget = t.req.budget_total_rub
    if budget and t.total > budget:
        over = t.total - budget
        return [Issue(severity="warning", code="OVER_BUDGET",
                      message=f"Итог {t.total:,} ₽ — превышаем бюджет на {over:,} ₽.".replace(",", " "),
                      fix_suggestion="Отель попроще, более дешёвые рейсы (ночные, без багажа) "
                                     "или другие даты.")]
    return []


CHECKS = [check_nights, check_arrival_date, check_checkin_wait, check_return,
          check_order, check_capacity, check_pets, check_budget]


def validate(t: Trip) -> list[Issue]:
    issues = []
    for check in CHECKS:
        issues += check(t)
    return issues


# ───────────── Таймлайн для фронта (TripTimeline) ─────────────

def build_timeline(t: Trip, issues: list[Issue]) -> list[dict]:
    """Шаги поездки по порядку. issue_code — какую проблему подсветить на шаге."""
    by_code = {i.code: i for i in issues}
    transfer = timedelta(minutes=t.transfer_min) if t.transfer_min else DEFAULT_TRANSFER
    steps = []

    def add(kind, at, title, codes=()):
        found = [c for c in codes if c in by_code]
        step = {"at": at.strftime("%Y-%m-%dT%H:%M") if at else None, "kind": kind, "title": title,
                "severity": "error" if any(by_code[c].severity == "error" for c in found)
                else "warning" if found else None}
        if found:
            step["issue_code"] = found[0]       # фронт красит шаг по коду проблемы
        steps.append(step)

    if t.outbound:
        f = t.outbound
        add("flight", f.depart, f"Вылет {f.origin_airport} → {f.dest_airport}, {f.airline}")
        add("arrive", f.arrive, f"Прилёт в {f.dest_airport}", ["ARRIVAL_DATE_MISMATCH"])
        add("transfer", f.arrive, f"Трансфер в отель (~{int(transfer.total_seconds() // 60)} мин)")
    if t.hotel and t.req.date_from:
        add("checkin", datetime.combine(t.req.date_from, _t(t.hotel.checkin_time)),
            f"Заселение в {t.hotel.name}", ["CHECKIN_WAIT", "PET_HOTEL", "ROOM_CAPACITY"])
    if t.hotel and t.req.date_to:
        add("checkout", datetime.combine(t.req.date_to, _t(t.hotel.checkout_time)),
            f"Выезд из отеля ({t.req.nights} ноч.)", ["LONG_WAIT_AFTER_CHECKOUT", "NIGHTS_MISMATCH"])
    if t.back:
        f = t.back
        add("transfer", f.depart - transfer - (AIRPORT_BUFFER_INTERNATIONAL if is_international(f)
                                               else AIRPORT_BUFFER_DOMESTIC), "Трансфер в аэропорт")
        add("flight", f.depart, f"Вылет {f.origin_airport} → {f.dest_airport}, {f.airline}",
            ["RETURN_DATE_MISMATCH", "RETURN_NIGHT_LOST", "PET_FLIGHT"])
    return steps