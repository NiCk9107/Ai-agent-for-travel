"""
Контракт API (раздел 3.2 плана) в виде Pydantic-моделей.
Это договор с C (фронт) и B (эндпоинты).

"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ───────────── Действия (кнопки на карточках) ─────────────

ActionType = Literal[
    "choose_destination", "select_hotel", "select_flight", "select_transfer",
    "compare", "quick_reply", "confirm_checkout", "remove_from_cart",
]


class Action(BaseModel):
    type: ActionType
    payload: dict[str, Any] = Field(default_factory=dict)


class CardAction(Action):
    label: str  # текст на кнопке, например «Выбрать»


# ───────────── Карточки ─────────────
# Фронт выбирает компонент по полю type. Неизвестный type просто не рисуется.

CardType = Literal["destination", "hotel", "flight", "train", "transfer",
                   "comparison", "itinerary", "order", "changes"]


class Card(BaseModel):
    type: CardType
    id: str
    actions: list[CardAction] = Field(default_factory=list)


class DestinationCard(Card):
    type: Literal["destination"] = "destination"
    title: str
    image_url: Optional[str] = None
    badges: list[str] = Field(default_factory=list)   # ["+22° воздух", "4 ч полёта"]
    price_from: Optional[int] = None
    price_note: Optional[str] = None
    why: Optional[str] = None
    tradeoffs: Optional[str] = None
    risks: Optional[str] = None


class HotelCard(Card):
    type: Literal["hotel"] = "hotel"
    name: str
    stars: int
    rating: Optional[float] = None
    price_total: int
    meal_plan: str
    cancel_policy: str
    beach_distance: Optional[int] = None
    image_url: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    pros: list[str] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class FlightCard(Card):
    type: Literal["flight"] = "flight"
    airline: str
    depart: str          # ISO-строка
    arrive: str
    duration: str        # «4 ч 10 мин»
    stops: int
    price: int
    baggage: bool


class TransferCard(Card):
    type: Literal["transfer"] = "transfer"
    kind: Literal["taxi", "shuttle", "public"]
    duration_min: int
    price: int


class ComparisonCard(Card):
    type: Literal["comparison"] = "comparison"
    title: str
    columns: list[dict[str, Any]]   # [{"id": "antalya_h1", "name": "Sea Breeze", "actions": [...]}]
    rows: list[dict[str, Any]]      # [{"label": "Цена за 7 ноч.", "values": ["63 000 ₽", ...], "best": 1}]

class ChangesCard(Card):
    """Плашка «Что изменилось» после пересборки плана."""
    type: Literal["changes"] = "changes"
    title: str
    items: list[dict[str, str]]                 # [{"kind": "kept|replaced|removed|changed|price|note", "text": ...}]
    total_before: int
    total_after: int
    delta: int
# ───────────── Запросы и ответы ─────────────

class SessionResponse(BaseModel):
    session_id: str


class ChatRequest(BaseModel):
    session_id: str
    message: Optional[str] = None
    action: Optional[Action] = None


class Reply(BaseModel):
    text: str
    cards: list[dict[str, Any]] = Field(default_factory=list)  # Card.model_dump()
    quick_replies: list[str] = Field(default_factory=list)


class CartView(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    currency: str = "RUB"


class TripView(BaseModel):
    stage: str
    assumptions: list[str] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    cart: CartView = Field(default_factory=CartView)
    validation: dict[str, Any] = Field(default_factory=lambda: {"ok": None, "issues": []})


class ChatResponse(BaseModel):
    reply: Reply
    trip: TripView


class Payer(BaseModel):
    name: str
    email: str


class CheckoutRequest(BaseModel):
    session_id: str
    payer: Payer


class CheckoutResponse(BaseModel):
    order_id: str
    status: Literal["paid"] = "paid"
    total: int