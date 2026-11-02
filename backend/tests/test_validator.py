"""Тесты validator.py. Запуск из папки backend:  python -m pytest tests -v"""
from datetime import date, datetime

from agent.state import Child, Flight, Hotel, Pet, Requirements, Room
from logic.validator import Trip, build_timeline, validate


def req(**kw):
    base = dict(adults=2, date_from=date(2026, 11, 10), date_to=date(2026, 11, 17), nights=7)
    base.update(kw)
    return Requirements(**base)


def flight(fid, dep, arr, frm="MOW", to="AYT", airline="Аэрофлот", pets=True):
    return Flight(id=fid, airline=airline, origin_airport=frm, dest_airport=to,
                  depart=dep, arrive=arr, price_per_person=15000, pets_allowed=pets)


HOTEL = Hotel(id="h1", destination_id="antalya", name="Sea Breeze", lat=0, lon=0, stars=4,
              price_per_night=9000, checkin_time="14:00", checkout_time="12:00", pet_friendly=False)
ROOM = Room(id="r1", hotel_id="h1", name="Стандарт", capacity_adults=2, capacity_children=1)

GOOD_OUT = flight("out", datetime(2026, 11, 10, 9, 0), datetime(2026, 11, 10, 13, 0))
GOOD_BACK = flight("back", datetime(2026, 11, 17, 18, 0), datetime(2026, 11, 17, 22, 0), "AYT", "MOW")


def codes(t):
    return [i.code for i in validate(t)]


def good_trip(**kw):
    t = Trip(req=req(), hotel=HOTEL, room=ROOM, outbound=GOOD_OUT, back=GOOD_BACK,
             transfer_min=40, total=140000)
    for k, v in kw.items():
        setattr(t, k, v)
    return t


def test_good_trip_has_no_issues():
    assert codes(good_trip()) == []


def test_early_arrival_gives_checkin_wait():
    # Прилёт 06:30 + 40 мин трансфер = 07:10, заселение с 14:00 → ждать ~7 ч
    early = flight("out", datetime(2026, 11, 10, 2, 30), datetime(2026, 11, 10, 6, 30))
    issues = validate(good_trip(outbound=early))
    wait = [i for i in issues if i.code == "CHECKIN_WAIT"]
    assert wait and wait[0].severity == "warning"
    assert "07:10" in wait[0].message and wait[0].fix_suggestion


def test_night_arrival_after_midnight_is_ok_date():
    night = flight("out", datetime(2026, 11, 10, 22, 0), datetime(2026, 11, 11, 2, 0))
    assert "ARRIVAL_DATE_MISMATCH" not in codes(good_trip(outbound=night))


def test_wrong_arrival_date_is_error():
    wrong = flight("out", datetime(2026, 11, 12, 9, 0), datetime(2026, 11, 12, 13, 0))
    assert "ARRIVAL_DATE_MISMATCH" in codes(good_trip(outbound=wrong))


def test_return_on_wrong_date_is_error():
    wrong = flight("back", datetime(2026, 11, 18, 18, 0), datetime(2026, 11, 18, 22, 0), "AYT", "MOW")
    assert "RETURN_DATE_MISMATCH" in codes(good_trip(back=wrong))


def test_very_early_return_loses_night():
    # Вылет 02:00 (межд., буфер 3 ч + 40 мин) → выезжать накануне в 22:20
    early = flight("back", datetime(2026, 11, 17, 2, 0), datetime(2026, 11, 17, 6, 0), "AYT", "MOW")
    issues = validate(good_trip(back=early))
    lost = [i for i in issues if i.code == "RETURN_NIGHT_LOST"]
    assert lost and "22:20" in lost[0].message


def test_late_return_gives_long_wait():
    late = flight("back", datetime(2026, 11, 17, 23, 30), datetime(2026, 11, 18, 3, 30), "AYT", "MOW")
    assert "LONG_WAIT_AFTER_CHECKOUT" in codes(good_trip(back=late))


def test_domestic_flight_uses_2h_buffer():
    # Сочи: внутренний рейс, буфер 2 ч. Вылет 15:00 - 2 ч - 40 мин = 12:20 → ожидание 20 мин, без проблем
    sochi = flight("back", datetime(2026, 11, 17, 15, 0), datetime(2026, 11, 17, 17, 30), "AER", "MOW")
    assert codes(good_trip(back=sochi)) == []


def test_nights_mismatch():
    t = good_trip()
    t.req = req(nights=6)
    assert "NIGHTS_MISMATCH" in codes(t)


def test_room_too_small():
    t = good_trip()
    t.req = req(adults=2, children=[Child(age=5), Child(age=8)])
    assert "ROOM_CAPACITY" in codes(t)


def test_pets_hotel_and_flight():
    t = good_trip(back=flight("back", datetime(2026, 11, 17, 18, 0), datetime(2026, 11, 17, 22, 0),
                              "AYT", "MOW", airline="Победа", pets=False))
    t.req = req(pets=[Pet(kind="собака")])
    c = codes(t)
    assert "PET_HOTEL" in c and "PET_FLIGHT" in c


def test_over_budget_is_warning_with_amount():
    t = good_trip(total=163200)
    t.req = req(budget_total_rub=150000)
    over = [i for i in validate(t) if i.code == "OVER_BUDGET"][0]
    assert over.severity == "warning" and "13 200" in over.message

def test_timeline_marks_problem_steps():
    early = flight("out", datetime(2026, 11, 10, 2, 30), datetime(2026, 11, 10, 6, 30))
    t = good_trip(outbound=early)
    steps = build_timeline(t, validate(t))
    assert [s["kind"] for s in steps] == ["flight", "arrive", "transfer", "checkin",
                                          "checkout", "transfer", "flight"]
    checkin = [s for s in steps if s["kind"] == "checkin"][0]
    assert checkin["issue_code"] == "CHECKIN_WAIT" and checkin["severity"] == "warning"
    assert len(checkin["at"]) == 16            # "2026-11-10T14:00" — без секунд и пояса