"""
Оценка и сравнение отелей — обычный код, БЕЗ LLM.
score = Σ вес_критерия × нормализованное_значение (0..1)
Веса зависят от профиля поездки. Кроме балла возвращаем готовые факты:
pros (почему подходит), tradeoffs (чем жертвуем), risks (риски).
LLM потом только превращает эти факты в текст.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from agent.state import Hotel, Requirements

FREE_CANCEL = "free_cancel"          # cancel_policy вида free_cancel_3d, free_cancel_7d
CHEAP_WORDS = {"недорого", "дёшево", "дешево", "бюджетно", "эконом"}
CALM_WORDS = {"спокойно", "тихо", "тишина", "без людей", "уединённо"}


@dataclass
class HotelScore:
    hotel_id: str
    score: float
    price_total: int
    pros: list[str] = field(default_factory=list)
    tradeoffs: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


# ───────────── Профиль → веса ─────────────

def build_weights(req: Requirements) -> dict[str, float]:
    """Базовые веса + поправки по профилю (раздел 2.6 плана)."""
    w = {"price": 1.0, "rating": 1.0, "beach": 1.0, "cancel": 0.5, "meal": 0.5, "kids": 0.0,
         "budget": 1.5 if req.budget_total_rub else 0.0}
    words = {s.lower() for s in req.mood + req.nice_to_have + req.must_have}

    if words & CHEAP_WORDS:
        w["price"] *= 2                       # «недорого» → цена ×2,
        for k in ("rating", "beach", "meal"):
            w[k] *= 0.5                       # а «комфорт» вдвое менее важен
    if req.children:
        w["kids"] = 1.0 * 1.5                 # с ребёнком → детская инфраструктура ×1.5
        w["meal"] *= 1.5                      # «всё включено» с детьми удобнее
        if any(c.age < 7 for c in req.children):
            w["beach"] *= 1.5                 # с маленьким — ближе к морю
    if words & CALM_WORDS:
        w["rating"] *= 1.5                    # спокойный отдых — важнее качество
    return w


def _norm(value: float, lo: float, hi: float, invert: bool = False) -> float:
    """Нормализация в 0..1 среди кандидатов. invert=True: меньше — лучше."""
    if hi == lo:
        return 1.0
    x = (value - lo) / (hi - lo)
    return 1 - x if invert else x


def _budget_fit(price: int, budget: int | None) -> float:
    """Отель до 40% бюджета — отлично (1.0), от 80% и выше — плохо (0.0): на перелёт не хватит."""
    if not budget:
        return 1.0
    share = price / budget
    return max(0.0, min(1.0, (0.8 - share) / 0.4))


def _is_free_cancel(h: Hotel) -> bool:
    return h.cancel_policy.startswith(FREE_CANCEL)


# ───────────── Обязательные условия ─────────────

def passes_must_have(h: Hotel, req: Requirements) -> bool:
    """Если must_have не выполнено — вариант отсекается."""
    must = {s.lower() for s in req.must_have}
    if req.pets and not h.pet_friendly:
        return False
    if any("отмен" in m for m in must) and not _is_free_cancel(h):
        return False
    if any("всё включено" in m or "все включено" in m for m in must) and h.meal_plan != "AI":
        return False
    if any("детск" in m for m in must) and not h.kids_club:
        return False
    return True


# ───────────── Главная функция ─────────────

def score_hotels(hotels: list[Hotel], req: Requirements, nights: int) -> list[HotelScore]:
    """Отсекает неподходящие, считает баллы, сортирует от лучшего к худшему."""
    candidates = [h for h in hotels if passes_must_have(h, req)]
    if not candidates:
        return []

    w = build_weights(req)
    prices = [h.price_per_night * nights for h in candidates]
    p_lo, p_hi = min(prices), max(prices)
    ratings = [h.rating or 7.0 for h in candidates]
    beaches = [h.beach_distance_m if h.beach_distance_m is not None else 2000 for h in candidates]
    total_w = sum(w.values())

    result = []
    for h, price in zip(candidates, prices):
        rating = h.rating or 7.0
        beach = h.beach_distance_m if h.beach_distance_m is not None else 2000

        raw = (
            w["price"] * _norm(price, p_lo, p_hi, invert=True)
            + w["rating"] * _norm(rating, min(ratings), max(ratings))
            + w["beach"] * _norm(beach, min(beaches), max(beaches), invert=True)
            + w["cancel"] * (1.0 if _is_free_cancel(h) else 0.0)
            + w["meal"] * {"AI": 1.0, "FB": 0.8, "HB": 0.6, "BB": 0.3, "RO": 0.0}.get(h.meal_plan, 0.3)
            + w["kids"] * (1.0 if h.kids_club else 0.0)
            + w["budget"] * _budget_fit(price, req.budget_total_rub)
        )
        s = HotelScore(hotel_id=h.id, score=round(raw / total_w, 2), price_total=price)
        _explain(s, h, req, price, p_lo, beach)
        result.append(s)

    result.sort(key=lambda x: x.score, reverse=True)
    return result


def _explain(s: HotelScore, h: Hotel, req: Requirements, price: int, cheapest: int, beach: int):
    """Готовые факты для карточки и для объяснения агентом."""
    # Почему подходит
    if beach <= 300:
        s.pros.append(f"{beach} м до пляжа")
    if _is_free_cancel(h):
        days = h.cancel_policy.replace(FREE_CANCEL, "").strip("_").rstrip("d")
        s.pros.append(f"бесплатная отмена за {days} дн." if days.isdigit() else "бесплатная отмена")
    if h.meal_plan == "AI":
        s.pros.append("всё включено")
    if h.kids_club and req.children:
        s.pros.append("детский клуб")
    if h.rating and h.rating >= 9:
        s.pros.append(f"рейтинг {h.rating}")
    if price == cheapest:
        s.pros.append("самый дешёвый из подходящих")

    # Чем жертвуем
    if price > cheapest:
        ratio = price / cheapest
        if ratio >= 2:
            times = f"{ratio:.1f}".rstrip("0").rstrip(".").replace(".", ",")
            s.tradeoffs.append(f"в {times} раза дороже самого дешёвого из подходящих")
        else:
            s.tradeoffs.append(f"на {round((ratio - 1) * 100)}% дороже самого дешёвого из подходящих")
    if beach >= 800:
        s.tradeoffs.append(f"до пляжа {beach} м")
    if h.meal_plan in ("RO", "BB"):
        s.tradeoffs.append("только завтраки" if h.meal_plan == "BB" else "без питания")
    if req.children and not h.kids_club:
        s.tradeoffs.append("нет детского клуба")

    # Риски
    if not _is_free_cancel(h):
        s.risks.append("невозвратная бронь: при отмене деньги не вернут")
    if req.budget_total_rub:
        share = price / req.budget_total_rub
        if share > 1:
            s.risks.append(f"один отель дороже всего бюджета на {price - req.budget_total_rub:,} ₽".replace(",", " "))
        elif share > 0.6:
            s.risks.append(f"отель — {round(share * 100)}% бюджета, на перелёт останется мало")