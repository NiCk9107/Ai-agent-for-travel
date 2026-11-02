"""
Цикл агента: модель → инструмент → результат → снова модель… пока модель не ответит текстом.
"""
from __future__ import annotations

from typing import Awaitable, Callable, Optional

from agent import llm
from agent.cards import build_cards, build_quick_replies
from agent.prompts import SYSTEM_PROMPT, state_context
from agent.state import TripState
from agent.tool_registry import STATUS_TEXT, TOOLS, dispatch, run_validation, trip_timeline
from db import database as db

MAX_STEPS = 8          # защита от зацикливания
HISTORY_LIMIT = 20     # сколько последних реплик помнит агент


# ───────────── Хранение (база B: db/database.py) ─────────────

def load_state(session_id: str) -> TripState:
    return db.load_state(session_id) or TripState(session_id=session_id)


def save_state(state: TripState) -> None:
    db.save_state(state)


def load_history(session_id: str) -> list[dict]:
    return db.load_messages(session_id, HISTORY_LIMIT)


def save_history(session_id: str, user_text: str, reply_text: str) -> None:
    db.save_message(session_id, "user", user_text)
    db.save_message(session_id, "assistant", reply_text)


# ───────────── Кнопки → текст для агента ─────────────

# тип кнопки → (вид выбора для select_option, поле payload с id)
BUTTON_KINDS = {
    "choose_destination": ("destination", "destination_id"),
    "select_hotel": ("hotel", "hotel_id"),
    "select_flight": ("outbound_flight", "flight_id"),     # направление уточняется по direction
    "select_transfer": ("transfer", "transfer_id"),
}

def action_to_text(action: dict) -> str:
    t, p = action.get("type"), action.get("payload", {})
    if t == "choose_destination":
        return f"[Кнопка] Пользователь выбрал направление {p.get('destination_id')}"
    if t == "select_hotel":
        return f"[Кнопка] Пользователь выбрал отель {p.get('hotel_id')}"
    if t == "select_flight":
        kind = "туда" if p.get("direction") == "out" else "обратно"
        return f"[Кнопка] Пользователь выбрал рейс {kind}: {p.get('flight_id')}"
    if t == "select_transfer":
        return f"[Кнопка] Пользователь выбрал трансфер {p.get('transfer_id')}"
    if t == "compare":
        return f"[Кнопка] Сравни варианты: {p.get('ids')}"
    if t == "confirm_checkout":
        return "[Кнопка] Пользователь подтвердил оплату"
    if t == "quick_reply":
        return str(p.get("text", ""))
    return f"[Кнопка] {t}: {p}"


# ───────────── Главная функция ─────────────

async def run_agent(session_id: str, user_text: Optional[str] = None, action: Optional[dict] = None,
                    emit: Optional[Callable[[str, dict], Awaitable[None]]] = None) -> dict:
    """Возвращает dict в формате ChatResponse из api/schemas.py."""
    state = load_state(session_id)
    text = user_text or (action_to_text(action) if action else "")
    # Кнопки «Выбрать» обрабатывает КОД, а не модель: выбор точный и не зацикливается
    if action and action.get("type") in BUTTON_KINDS:
        kind, field = BUTTON_KINDS[action["type"]]
        p = action.get("payload", {})
        if action["type"] == "select_flight":
            kind = "outbound_flight" if p.get("direction") == "out" else "return_flight"
        res = dispatch("select_option", {"kind": kind, "id": p.get(field, "")}, state)
        text = (f"{text}. Выбор УЖЕ сохранён кодом — select_option НЕ вызывай, "
                f"сразу сделай следующий шаг по порядку работы."
                if "error" not in res else f"{text}. Не удалось: {res['error']}")
    # Крестик в корзине: удаляет КОД сразу, модель только комментирует
    if action and action.get("type") == "remove_from_cart":
        res = dispatch("remove_from_cart", {"ref_id": action.get("payload", {}).get("ref_id", "")}, state)
        text = (f"[Кнопка] Пользователь убрал из корзины: {res['removed']}. Это уже сделано — "
                f"коротко подтверди и подскажи, что выбрать взамен, если нужно."
                if "removed" in res else f"[Кнопка] Не удалось убрать из корзины: {res.get('error')}")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": state_context(state)},
        *load_history(session_id),
        {"role": "user", "content": text},
    ]

    reply_text = ""
    extra_cards = []                  # карточки, которые вернули сами инструменты (сравнение)
    try:
        for _ in range(MAX_STEPS):
            resp = await llm.chat(messages, tools=TOOLS)
            if not resp.tool_calls:
                reply_text = resp.text
                break
            messages.append(resp.as_message())
            for call in resp.tool_calls:
                print(f"   🔧 {call.name}({call.args})")
                if emit:
                    await emit("status", {"text": STATUS_TEXT.get(call.name, "Думаю…")})
                try:
                    result = dispatch(call.name, call.args, state)
                except Exception as e:  # модель увидит ошибку и попробует обойти
                    result = {"error": str(e)}
                if isinstance(result, dict) and "card" in result:
                    extra_cards.append(result.pop("card"))   # пользователю — карточка, модели — сводка
                messages.append(llm.tool_result(call.id, result))
    except RuntimeError:
        reply_text = ("Сервис подбора сейчас перегружен. Попробуйте отправить сообщение "
                      "ещё раз через минуту — всё, что вы уже выбрали, сохранено.")
    if not reply_text:
        reply_text = "Я немного запутался. Давайте уточним: что важнее всего в этой поездке?"

    # Состыковки проверяет код после КАЖДОГО хода — таймлайн всегда актуален
    if state.selected.hotel_id or state.selected.outbound_flight_id:
        run_validation(state)

    save_state(state)
    save_history(session_id, text, reply_text)

    trip = state.public_view()
    trip["timeline"] = trip_timeline(state)
    return {
        "reply": {
            "text": reply_text,
            "cards": extra_cards + build_cards(state),
            "quick_replies": build_quick_replies(state),
        },
        "trip": trip,
    }