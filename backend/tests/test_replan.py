"""
Сценарии пересборки плана из раздела 2.4 / дня 5. Без LLM и без базы:
инструменты вызываются напрямую, данные — из заглушек agent/stubs.py.
Запуск из папки backend:  python -m pytest tests -v
"""
import pytest

from agent import stubs
from agent import tool_registry as tr
from agent.state import Stage, TripState


@pytest.fixture(autouse=True)
def use_stubs(monkeypatch):
    """Тесты не зависят от базы и интернета — подставляем заглушки."""
    monkeypatch.setattr(tr, "suggest_destinations_impl", stubs.suggest_destinations)
    monkeypatch.setattr(tr, "search_hotels_impl", stubs.search_hotels)
    monkeypatch.setattr(tr, "search_flights_impl", stubs.search_flights)
    monkeypatch.setattr(tr, "estimate_transfer_impl", stubs.estimate_transfer)


def full_trip() -> TripState:
    """Собранная поездка в корзине: Анталья, 10–17.11, 2+1, бюджет 200 000."""
    st = TripState(session_id="t")
    call = lambda name, **a: tr.dispatch(name, a, st)
    call("update_requirements", origin="Москва", month="2026-11", adults=2,
         children_ages=[5], budget_total_rub=200000)
    call("suggest_destinations", tags=["море"])
    call("select_option", kind="destination", id="antalya")
    call("search_hotels")
    call("select_option", kind="hotel", id="antalya_h1")
    call("search_flights")
    call("select_option", kind="outbound_flight", id=st.shortlist.outbound_flights[0])
    call("select_option", kind="return_flight", id=st.shortlist.return_flights[0])
    call("estimate_transfer")
    call("select_option", kind="transfer", id=st.shortlist.transfers[0])
    assert "total" in call("add_to_cart")
    return st


def change(st, **args):
    return tr.dispatch("update_requirements", args, st)


def test_two_days_later_keeps_hotel_and_moves_flights():
    st = full_trip()
    res = change(st, date_from="2026-11-12")
    d = res["replan"]
    assert str(st.requirements.date_to) == "2026-11-19" and st.requirements.nights == 7
    assert any("Sea Breeze" in k for k in d["kept"])
    assert len(d["replaced"]) == 2                       # оба рейса на новые даты
    assert st.cart and st.stage == Stage.trip_review     # корзина пересобрана
    assert res["card"]["type"] == "changes"


def test_longer_stay_changes_only_return_flight_and_hotel_price():
    st = full_trip()
    d = change(st, nights=10)["replan"]
    assert any("рейс туда" in k for k in d["kept"])
    assert [r for r in d["replaced"] if r.startswith("рейс обратно")]
    assert any(p["item"] == "отель" and p["delta"] > 0 for p in d["price_changes"])


def test_budget_change_does_not_reset_anything():
    st = full_trip()
    before = st.selected.model_dump()
    d = change(st, budget_total_rub=120000)["replan"]
    assert st.selected.model_dump() == before
    assert d["over_budget_by"] > 0                        # агент скажет, на сколько превышаем


def test_dog_removes_hotel_and_flights_that_do_not_allow_pets():
    st = full_trip()
    d = change(st, pets=["собака"])["replan"]
    assert any("не принимает животных" in r for r in d["removed"])
    assert st.selected.hotel_id is None and not st.cart
    assert st.stage == Stage.hotel_selection


def test_extra_child_recalculates_prices_without_reset():
    st = full_trip()
    hotel = st.selected.hotel_id
    d = change(st, children_ages=[5, 9])["replan"]
    assert st.selected.hotel_id == hotel
    assert any(p["item"] == "перелёт" and p["delta"] > 0 for p in d["price_changes"])


def test_new_origin_replaces_flights_with_new_route():
    st = full_trip()
    d = change(st, origin="Санкт-Петербург")["replan"]
    assert len(d["replaced"]) == 2 and all("LED" in r for r in d["replaced"])


def test_new_destination_resets_everything():
    st = full_trip()
    tr.dispatch("select_option", {"kind": "destination", "id": "sochi"}, st)
    assert st.selected.hotel_id is None and not st.cart and st.stage == Stage.hotel_selection


def test_no_replan_before_anything_chosen():
    st = TripState(session_id="t")
    res = change(st, origin="Москва", month="2026-11", adults=2)
    assert "replan" not in res and "card" not in res

