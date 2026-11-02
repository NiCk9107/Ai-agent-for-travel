import json
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from agent.cards import build_cards, build_quick_replies


from agent.state import Stage, TripState
from api.schemas import CheckoutRequest, CheckoutResponse
from db.database import clear_messages, get_conn, load_messages, load_state, save_state

router = APIRouter()


class ResetRequest(BaseModel):
    session_id: str


@router.get("/state/{session_id}")
def get_state(session_id: str):
    """Восстановить экран после перезагрузки страницы."""
    state = load_state(session_id)
    if not state:
        raise HTTPException(404, "Сессия не найдена")
    return {"trip": state.public_view(), "messages": load_messages(session_id, limit=100),
            "cards": build_cards(state), "quick_replies": build_quick_replies(state)}



@router.get("/cart/{session_id}")
def get_cart(session_id: str):
    """Корзина: позиции, итог и сравнение с бюджетом (для CartPanel)."""
    state = load_state(session_id)
    if not state:
        raise HTTPException(404, "Сессия не найдена")
    cart = state.public_view()["cart"]
    budget = state.requirements.budget_total_rub
    total = cart["total"]
    cart["budget"] = budget
    cart["over_budget_by"] = max(0, total - budget) if budget else 0
    cart["budget_left"] = max(0, budget - total) if budget else None
    cart["by_kind"] = {k: sum(i["price"] for i in cart["items"] if i["kind"] == k)
                       for k in ("hotel", "flight", "train", "transfer")}
    return cart


@router.post("/checkout", response_model=CheckoutResponse)
def checkout(req: CheckoutRequest):
    """Имитация оплаты из модалки CheckoutModal. Деньги не списываются."""
    state = load_state(req.session_id)
    if not state:
        raise HTTPException(404, "Сессия не найдена")
    if not state.cart:
        raise HTTPException(400, "Корзина пуста")

    order_id = state.order_id or "ORD-" + uuid.uuid4().hex[:6].upper()
    total = state.cart_total()
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO orders (order_id, session_id, items_json, total, status) "
            "VALUES (?, ?, ?, ?, 'paid')",
            (order_id, req.session_id,
             json.dumps({"payer": req.payer.model_dump(),
                         "items": [i.model_dump() for i in state.cart]}, ensure_ascii=False),
             total))

    state.order_id = order_id
    state.stage = Stage.purchased
    save_state(state)
    return CheckoutResponse(order_id=order_id, total=total)


@router.post("/reset")
def reset(req: ResetRequest):
    """Кнопка «Новая поездка»: чистое состояние, та же сессия."""
    save_state(TripState(session_id=req.session_id))
    clear_messages(req.session_id)
    return {"ok": True}