import hashlib
import json
import math
import random
import sys
import time

from db.database import get_conn, init_db
from tools.cache import cached_post

OVERPASS = "https://overpass-api.de/api/interpreter"
RADIUS_HOTELS = 15000      # м вокруг центра направления
RADIUS_BEACHES = 20000
MAX_HOTELS = 20            # на направление
MIN_HOTELS = 8             # если в OSM меньше — добавляем синтетические

SYNTH_NAMES = ["Sunrise", "Blue Lagoon", "Panorama", "Garden Inn", "Royal Park",
               "Central", "Family Club", "Sea View", "Palm Resort", "Comfort",
               "Mountain Lodge", "Old Town", "Green Valley", "Grand", "Harmony"]

REVIEW_PLUS = {
    "beach": "До пляжа пара минут пешком.", "ai": "Еда разнообразная, всё включено без доплат.",
    "kids": "Детям было чем заняться, аниматоры хорошие.", "cheap": "За эти деньги — отличный вариант.",
    "rating": "Чисто, вежливый персонал.", "cancel": "Удобно, что можно бесплатно отменить.",
}
REVIEW_MINUS = {
    "far": "До моря далековато, приходилось ездить.", "old": "Ремонт уже не первой свежести.",
    "noise": "Вечером бывает шумно.", "food": "Завтраки однообразные.",
    "wifi": "Wi-Fi в номере слабый.",
}


def seed_of(*parts) -> int:
    return int(hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def overpass(query: str) -> list[dict]:
    return cached_post(OVERPASS, query).get("elements", [])


def fetch_osm_hotels(lat: float, lon: float) -> list[dict]:
    q = f"""[out:json][timeout:60];
(
  node["tourism"~"^(hotel|resort)$"]["name"](around:{RADIUS_HOTELS},{lat},{lon});
  way["tourism"~"^(hotel|resort)$"]["name"](around:{RADIUS_HOTELS},{lat},{lon});
);
out center 80;"""
    result = []
    for el in overpass(q):
        c = el if el["type"] == "node" else el.get("center", {})
        if "lat" not in c:
            continue
        tags = el.get("tags", {})
        result.append({"osm_id": f"{el['type'][0]}{el['id']}",
                       "name": tags.get("name:ru") or tags.get("name"),
                       "lat": c["lat"], "lon": c["lon"], "stars": tags.get("stars")})
    return result


def fetch_beaches(lat: float, lon: float) -> list[tuple[float, float]]:
    q = f"""[out:json][timeout:60];
(
  node["natural"="beach"](around:{RADIUS_BEACHES},{lat},{lon});
  way["natural"="beach"](around:{RADIUS_BEACHES},{lat},{lon});
);
out center 300;"""
    points = []
    for el in overpass(q):
        c = el if el["type"] == "node" else el.get("center", {})
        if "lat" in c:
            points.append((c["lat"], c["lon"]))
    return points


def synth_hotel(raw: dict, dest, beaches, rnd: random.Random) -> dict:
    """Дополняем реальный отель правдоподобной синтетикой."""
    tag_stars = str(raw.get("stars") or "").strip()[:1]
    stars = int(tag_stars) if tag_stars.isdigit() and 1 <= int(tag_stars) <= 5 \
        else rnd.choices([3, 4, 5], weights=[4, 4, 2])[0]

    beach = None
    if beaches:
        d = min(haversine_m(raw["lat"], raw["lon"], b[0], b[1]) for b in beaches)
        beach = max(30, int(round(d, -1)))
        if beach > 5000:
            beach = None                      # пляж слишком далеко — не пляжный отель

    is_sea = beach is not None
    rating = round(min(9.8, 6.8 + stars * 0.4 + rnd.uniform(-0.4, 0.6)), 1)

    # Цена: средняя по направлению × звёзды × близость к морю × разброс
    base = dest["avg_hotel_price"] or 6000
    k = {1: 0.4, 2: 0.5, 3: 0.65, 4: 1.0, 5: 1.8}[stars]
    if beach is not None:
        k *= 1.3 if beach < 200 else 1.1 if beach < 500 else 0.9 if beach > 1500 else 1.0
    price = int(round(base * k * rnd.uniform(0.85, 1.15), -2))

    if is_sea and stars == 5:
        meal = rnd.choices(["AI", "HB", "BB"], weights=[7, 2, 1])[0]
    elif is_sea and stars == 4:
        meal = rnd.choices(["AI", "HB", "BB"], weights=[4, 2, 4])[0]
    else:
        meal = rnd.choices(["BB", "RO", "HB"], weights=[6, 2, 2])[0]

    cancel = rnd.choices(["free_cancel_7d", "free_cancel_3d", "non_refundable"],
                         weights=[3, 4, 3] if stars >= 4 else [1, 3, 6])[0]
    kids = rnd.random() < (0.6 if is_sea and stars >= 4 else 0.15)
    pets = rnd.random() < 0.15
    checkin = rnd.choice(["14:00", "14:00", "15:00"])
    checkout = rnd.choice(["12:00", "12:00", "11:00"])

    # Отзывы из шаблонов — согласованы с характеристиками отеля
    plus = [REVIEW_PLUS["rating"]]
    if beach is not None and beach <= 400:
        plus.append(REVIEW_PLUS["beach"])
    if meal == "AI":
        plus.append(REVIEW_PLUS["ai"])
    if kids:
        plus.append(REVIEW_PLUS["kids"])
    if stars <= 3:
        plus.append(REVIEW_PLUS["cheap"])
    minus = []
    if beach is not None and beach > 1000:
        minus.append(REVIEW_MINUS["far"])
    if stars <= 3:
        minus.append(REVIEW_MINUS["old"])
    minus.append(rnd.choice([REVIEW_MINUS["noise"], REVIEW_MINUS["food"], REVIEW_MINUS["wifi"]]))
    reviews = [{"author": rnd.choice(["Анна", "Игорь", "Мария", "Дмитрий", "Ольга", "Сергей"]),
                "score": round(min(10, rating + rnd.uniform(-0.8, 0.5)), 1),
                "plus": p, "minus": m} for p, m in zip(plus, minus + minus)][:3]

    return {"stars": stars, "rating": rating, "price": price, "meal": meal, "cancel": cancel,
            "kids": kids, "pets": pets, "beach": beach, "checkin": checkin,
            "checkout": checkout, "reviews": reviews}


def make_rooms(hotel_id: str, stars: int, rnd: random.Random) -> list[tuple]:
    rooms = [(f"{hotel_id}_std", hotel_id, "Стандарт", 2, 1, 1.0)]
    if stars >= 3:
        rooms.append((f"{hotel_id}_fam", hotel_id, "Семейный", 2, 2, round(rnd.uniform(1.25, 1.4), 2)))
    if stars >= 4:
        rooms.append((f"{hotel_id}_suite", hotel_id, "Люкс", 3, 1, round(rnd.uniform(1.7, 2.0), 2)))
    if stars >= 3 and rnd.random() < 0.5:
        rooms.append((f"{hotel_id}_apt", hotel_id, "Апартаменты", 4, 1, round(rnd.uniform(2.0, 2.3), 2)))
    if rnd.random() < 0.4:
        rooms.append((f"{hotel_id}_single", hotel_id, "Одноместный", 1, 0, 0.75))
    return rooms


def load_destination(dest) -> tuple[int, int]:
    lat, lon = dest["lat"], dest["lon"]
    try:
        raw = fetch_osm_hotels(lat, lon)
        time.sleep(1)
        beaches = fetch_beaches(lat, lon) if "море" in (dest["tags"] or "") else []
    except Exception as e:
        print(f"   ⚠️ Overpass недоступен ({e}), только синтетика")
        raw, beaches = [], []

    # Уникальные имена, ближе к центру — первыми
    seen, hotels = set(), []
    for h in sorted(raw, key=lambda h: haversine_m(lat, lon, h["lat"], h["lon"])):
        if h["name"] and h["name"] not in seen:
            seen.add(h["name"])
            hotels.append(h)
    hotels = hotels[:MAX_HOTELS]

    # Мало реальных — добиваем синтетическими (честно: id начинается с _s)
    rnd_s = random.Random(seed_of(dest["id"], "synth"))
    i = 0
    while len(hotels) < MIN_HOTELS:
        name = f"{SYNTH_NAMES[i % len(SYNTH_NAMES)]} {dest['name']}"
        hotels.append({"osm_id": f"s{i}", "name": name, "stars": None,
                       "lat": lat + rnd_s.uniform(-0.03, 0.03), "lon": lon + rnd_s.uniform(-0.03, 0.03)})
        i += 1

    with get_conn() as conn:
        old = [r["id"] for r in conn.execute("SELECT id FROM hotels WHERE destination_id = ?", (dest["id"],))]
        conn.executemany("DELETE FROM rooms WHERE hotel_id = ?", [(h,) for h in old])
        conn.execute("DELETE FROM hotels WHERE destination_id = ?", (dest["id"],))

        for h in hotels:
            hid = f"{dest['id']}_{h['osm_id']}"
            rnd = random.Random(seed_of(hid))
            s = synth_hotel(h, dest, beaches, rnd)
            conn.execute(
                "INSERT INTO hotels (id, destination_id, name, lat, lon, stars, rating, price_per_night, "
                "meal_plan, cancel_policy, checkin_time, checkout_time, pet_friendly, kids_club, "
                "beach_distance_m, reviews_json, image_url) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (hid, dest["id"], h["name"], h["lat"], h["lon"], s["stars"], s["rating"], s["price"],
                 s["meal"], s["cancel"], s["checkin"], s["checkout"], int(s["pets"]), int(s["kids"]),
                 s["beach"], json.dumps(s["reviews"], ensure_ascii=False), None))
            conn.executemany("INSERT INTO rooms VALUES (?,?,?,?,?,?)", make_rooms(hid, s["stars"], rnd))
    real = sum(1 for h in hotels if not h["osm_id"].startswith("s"))
    return real, len(hotels) - real


def main():
    init_db()
    only = sys.argv[1] if len(sys.argv) > 1 else None
    with get_conn() as conn:
        dests = conn.execute("SELECT * FROM destinations" + (" WHERE id = ?" if only else ""),
                             (only,) if only else ()).fetchall()
    if not dests:
        print("Направления не найдены. Сначала: python -m scripts.load_destinations")
        return
    for d in dests:
        real, synth = load_destination(d)
        print(f"✅ {d['name']}: {real} из OSM + {synth} синтетических")
        time.sleep(1)  # не перегружаем бесплатный Overpass


if __name__ == "__main__":
    main()