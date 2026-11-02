"""
TripState и все модели данных проекта.
Это «сердце» агента: всё, что известно о поездке, лежит здесь.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field




class Stage(str, Enum):
    clarifying = "clarifying"                    # уточняем требования
    inspiration = "inspiration"                  # подбираем направления
    destination_choice = "destination_choice"    # пользователь выбирает направление
    hotel_selection = "hotel_selection"          # выбор отеля
    transport_selection = "transport_selection"  # перелёт / поезд / трансфер
    trip_review = "trip_review"                  # обзор и проверка состыковок
    checkout = "checkout"                        # подтверждение оплаты
    purchased = "purchased"                      # заказ оформлен




class Child(BaseModel):
    age: int = Field(ge=0, le=17)


class Pet(BaseModel):
    kind: str = Field(description="Например: собака, кошка")
    weight_kg: Optional[float] = None


class Requirements(BaseModel):
    origin: Optional[str] = Field(None, description="Город вылета, например «Москва»")
    destination_id: Optional[str] = Field(None, description="id направления из БД, например antalya")
    month: Optional[str] = Field(None, description="Месяц поездки в формате YYYY-MM")
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    nights: Optional[int] = Field(None, ge=1)
    adults: Optional[int] = Field(None, ge=1)
    children: list[Child] = Field(default_factory=list)
    pets: list[Pet] = Field(default_factory=list)
    budget_total_rub: Optional[int] = Field(None, ge=0)
    max_travel_hours: Optional[float] = None
    mood: list[str] = Field(default_factory=list, description="Настроение: «тёплое море», «спокойно»")
    must_have: list[str] = Field(default_factory=list, description="Обязательно: «бесплатная отмена»")
    nice_to_have: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list, description="Допущения, показанные пользователю")




class Destination(BaseModel):
    id: str
    name: str
    country: str
    airport_code: str
    lat: float
    lon: float
    tags: list[str] = Field(default_factory=list)
    avg_hotel_price: Optional[int] = None
    flight_hours_from_msk: Optional[float] = None
    description: Optional[str] = None
    image_url: Optional[str] = None


class Room(BaseModel):
    id: str
    hotel_id: str
    name: str
    capacity_adults: int
    capacity_children: int = 0
    price_multiplier: float = 1.0


class Hotel(BaseModel):
    id: str
    destination_id: str
    name: str
    lat: float
    lon: float
    stars: int = Field(ge=1, le=5)
    rating: Optional[float] = Field(None, ge=0, le=10)
    price_per_night: int
    meal_plan: Literal["RO", "BB", "HB", "FB", "AI"] = "BB"  # без питания / завтрак / ... / всё включено
    cancel_policy: str = "non_refundable"
    checkin_time: str = "14:00"
    checkout_time: str = "12:00"
    pet_friendly: bool = False
    kids_club: bool = False
    beach_distance_m: Optional[int] = None
    image_url: Optional[str] = None
    rooms: list[Room] = Field(default_factory=list)


class Flight(BaseModel):
    id: str
    airline: str
    origin_airport: str
    dest_airport: str
    depart: datetime
    arrive: datetime
    stops: int = 0
    price_per_person: int
    baggage: bool = True
    pets_allowed: bool = False

    @property
    def duration_hours(self) -> float:
        return round((self.arrive - self.depart).total_seconds() / 3600, 1)


class Transfer(BaseModel):
    id: str
    kind: Literal["taxi", "shuttle", "public"]
    duration_min: int
    price: int




class Shortlist(BaseModel):
    destinations: list[str] = Field(default_factory=list)
    hotels: list[str] = Field(default_factory=list)
    outbound_flights: list[str] = Field(default_factory=list)
    return_flights: list[str] = Field(default_factory=list)
    transfers: list[str] = Field(default_factory=list)


class Selected(BaseModel):
    hotel_id: Optional[str] = None
    room_id: Optional[str] = None
    outbound_flight_id: Optional[str] = None
    return_flight_id: Optional[str] = None
    transfer_ids: list[str] = Field(default_factory=list)


class CartItem(BaseModel):
    kind: Literal["hotel", "flight", "train", "transfer"]
    ref_id: str
    title: str
    price: int


class Issue(BaseModel):
    severity: Literal["error", "warning"]
    code: str                     
    message: str
    fix_suggestion: Optional[str] = None


class Validation(BaseModel):
    ok: Optional[bool] = None
    issues: list[Issue] = Field(default_factory=list)


class ChangeLogEntry(BaseModel):
    at: datetime = Field(default_factory=datetime.now)
    field: str
    old: Any = None
    new: Any = None
    reset: list[str] = Field(default_factory=list, description="Что сбросили из-за изменения")


class TripState(BaseModel):
    session_id: str
    stage: Stage = Stage.clarifying
    requirements: Requirements = Field(default_factory=Requirements)
    shortlist: Shortlist = Field(default_factory=Shortlist)
    selected: Selected = Field(default_factory=Selected)
    cart: list[CartItem] = Field(default_factory=list)
    validation: Validation = Field(default_factory=Validation)
    change_log: list[ChangeLogEntry] = Field(default_factory=list)
    order_id: Optional[str] = None

    def cart_total(self) -> int:
        return sum(i.price for i in self.cart)

    def public_view(self) -> dict:
        """Кусок состояния, который уходит на фронт (поле trip в ответе /api/chat)."""
        return {
            "stage": self.stage.value,
            "assumptions": self.requirements.assumptions,
            "timeline": [],  # заполним на день 4 (TripTimeline)
            "cart": {
                "items": [i.model_dump() for i in self.cart],
                "total": self.cart_total(),
                "currency": "RUB",
            },
            "validation": self.validation.model_dump(),
        }



def missing_required(state: TripState) -> list[str]:
    """Чего не хватает, чтобы начать поиск. Агент получает этот список в контексте."""
    r = state.requirements
    missing = []
    if not r.origin:
        missing.append("origin")
    if not (r.month or r.date_from):
        missing.append("period")
    if not r.adults:
        missing.append("adults")
    return missing