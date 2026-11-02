"""Тесты scoring.py. Запуск из папки backend:  python -m pytest tests -v"""
from agent.state import Child, Hotel, Pet, Requirements
from logic.scoring import build_weights, passes_must_have, score_hotels


def make_hotel(hid, price, rating=8.0, beach=300, meal="BB", cancel="non_refundable",
               kids=False, pets=False):
    return Hotel(id=hid, destination_id="test", name=hid, lat=0, lon=0, stars=4,
                 rating=rating, price_per_night=price, meal_plan=meal,
                 cancel_policy=cancel, kids_club=kids, beach_distance_m=beach, pet_friendly=pets)


CHEAP = make_hotel("cheap", 3000, rating=7.5, beach=900)
FAMILY = make_hotel("family", 7000, rating=8.7, beach=300, meal="AI", cancel="free_cancel_3d", kids=True)
LUXURY = make_hotel("luxury", 15000, rating=9.3, beach=50, meal="AI", cancel="free_cancel_7d", kids=True)
ALL = [CHEAP, FAMILY, LUXURY]


def ids(scores):
    return [s.hotel_id for s in scores]


def test_cheap_profile_moves_cheap_up_and_luxury_down():
    base = ids(score_hotels(ALL, Requirements(adults=2), nights=7))
    cheap = ids(score_hotels(ALL, Requirements(adults=2, mood=["недорого"]), nights=7))
    assert cheap.index("cheap") < base.index("cheap")   # дешёвый поднялся
    assert cheap[-1] == "luxury"                        # дорогой — последний


def test_family_profile_prefers_family_hotel():
    req = Requirements(adults=2, children=[Child(age=5)])
    top = ids(score_hotels(ALL, req, nights=7))
    assert top[0] in ("family", "luxury")
    assert top[-1] == "cheap"


def test_weights_change_with_profile():
    base = build_weights(Requirements(adults=2))
    cheap = build_weights(Requirements(adults=2, mood=["недорого"]))
    kids = build_weights(Requirements(adults=2, children=[Child(age=4)]))
    assert cheap["price"] == base["price"] * 2
    assert kids["kids"] > base["kids"]


def test_must_have_free_cancel_filters_out():
    req = Requirements(adults=2, must_have=["бесплатная отмена"])
    assert "cheap" not in ids(score_hotels(ALL, req, nights=7))


def test_pets_require_pet_friendly():
    req = Requirements(adults=2, pets=[Pet(kind="собака")])
    assert not passes_must_have(FAMILY, req)
    assert passes_must_have(make_hotel("dogs", 5000, pets=True), req)


def test_nothing_passes_returns_empty():
    req = Requirements(adults=2, pets=[Pet(kind="кошка")])
    assert score_hotels(ALL, req, nights=7) == []


def test_explanations():
    req = Requirements(adults=2, children=[Child(age=5)], budget_total_rub=150000)
    by_id = {s.hotel_id: s for s in score_hotels(ALL, req, nights=7)}

    assert "самый дешёвый из подходящих" in by_id["cheap"].pros
    assert "нет детского клуба" in by_id["cheap"].tradeoffs
    assert any("невозвратная" in r for r in by_id["cheap"].risks)

    assert "детский клуб" in by_id["family"].pros
    assert "бесплатная отмена за 3 дн." in by_id["family"].pros
    assert any("дороже самого дешёвого" in t for t in by_id["family"].tradeoffs)

    # 15000 × 7 = 105 000 = 70% бюджета
    assert any("70% бюджета" in r for r in by_id["luxury"].risks)


def test_price_total_uses_nights():
    req = Requirements(adults=2)
    by_id = {s.hotel_id: s for s in score_hotels(ALL, req, nights=5)}
    assert by_id["cheap"].price_total == 15000


def test_scores_between_0_and_1_and_sorted():
    scores = score_hotels(ALL, Requirements(adults=2), nights=7)
    assert all(0 <= s.score <= 1 for s in scores)
    assert [s.score for s in scores] == sorted([s.score for s in scores], reverse=True)


def test_budget_pushes_down_hotel_that_eats_budget():
    # С бюджетом 150 000 отель за 105 000 (70%) не должен быть первым
    req = Requirements(adults=2, children=[Child(age=5)], budget_total_rub=150000)
    assert ids(score_hotels(ALL, req, nights=7))[0] == "family"