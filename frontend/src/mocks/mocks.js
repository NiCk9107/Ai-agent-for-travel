// Фальшивые ответы сервера. Формат — как у настоящего бэка (backend/agent/cards.py).
const trip = (stage, extra = {}) => ({
  stage,
  assumptions: ["Вылет из Москвы — взят по умолчанию", "7 ночей — стандартная длительность"],
  timeline: [],
  cart: { items: [], total: 0, currency: "RUB" },
  validation: { ok: null, issues: [] },
  ...extra,
});

const dest = (id, title, badges, why) => ({
  type: "destination", id, title, image_url: null, badges,
  price_from: null, price_note: null, why, tradeoffs: null, risks: null,
  actions: [{ type: "choose_destination", label: "Выбрать", payload: { destination_id: id } }],
});

const hotel = (id, name, stars, rating, price_total, meal_plan, cancel_policy, beach_distance) => ({
  type: "hotel", id, name, stars, rating, price_total, meal_plan, cancel_policy, beach_distance,
  image_url: null, lat: 0, lon: 0, pros: [], tradeoffs: [], risks: [],
  actions: [{ type: "select_hotel", label: "Выбрать", payload: { hotel_id: id } }],
});

const flight = (id, direction, airline, depart, arrive, duration, price, baggage) => ({
  type: "flight", id, airline, depart, arrive, duration, stops: 0, price, baggage,
  actions: [{ type: "select_flight", label: "Выбрать", payload: { flight_id: id, direction } }],
});

const CART = {
  items: [
    { kind: "hotel", ref_id: "antalya_h1", title: "Sea Breeze Family, 7 ночей", price: 63000 },
    { kind: "flight", ref_id: "out_1", title: "Аэрофлот MOW→AYT", price: 45000 },
    { kind: "flight", ref_id: "back_2", title: "S7 AYT→MOW", price: 38250 },
  ],
  total: 146250,
  currency: "RUB",
};

export const MOCK_REPLIES = {
  destinations: {
    reply: {
      text: "Нашёл три направления, где в ноябре тепло и лететь до 5 часов.",
      cards: [
        dest("antalya", "Анталья, Турция", ["4 ч полёта"], "Семейные отели «всё включено». Погода в этом месяце: средняя температура +19°"),
        dest("sharm", "Шарм-эш-Шейх, Египет", ["5 ч полёта"], "Тёплое море круглый год. Погода в этом месяце: средняя температура +25°"),
        dest("sochi", "Сочи, Россия", ["2.5 ч полёта"], "Море и горы рядом, без визы"),
      ],
      quick_replies: ["Покажи подешевле", "Хочу теплее", "Без долгих перелётов"],
    },
    trip: trip("destination_choice"),
  },

  hotels: {
    reply: {
      text: "В Анталье подобрал три отеля на 7 ночей.",
      cards: [
        {
          ...hotel("antalya_h1", "Sea Breeze Family", 4, 8.7, 63000, "Всё включено", "free_cancel_3d", 300),
          pros: ["300 м до пляжа", "бесплатная отмена за 3 дн.", "детский клуб"],
          tradeoffs: ["на 66% дороже самого дешёвого из подходящих"],
          risks: [],
          reviews: [
            { author: "Анна", score: 9.1, plus: "Детям было чем заняться, аниматоры хорошие.", minus: "Вечером бывает шумно." },
            { author: "Сергей", score: 8.4, plus: "До пляжа пара минут пешком.", minus: "Завтраки однообразные." },
          ],
        },
        hotel("antalya_h2", "Sunny Budget", 3, 7.9, 37800, "Завтраки", "non_refundable", 900),
        hotel("antalya_h3", "Royal Palace", 5, 9.2, 113400, "Всё включено", "free_cancel_7d", 50),
      ],
      quick_replies: ["Подешевле", "Ближе к морю", "Только с бесплатной отменой"],
    },
    trip: trip("hotel_selection"),
  },

  flightsOut: {
    reply: {
      text: "Теперь рейс туда.",
      cards: [
        flight("out_1", "out", "Аэрофлот", "2026-11-10T09:00:00", "2026-11-10T13:00:00", "4 ч 00 мин", 45000, true),
        flight("out_2", "out", "Победа", "2026-11-10T06:15:00", "2026-11-10T10:15:00", "4 ч 00 мин", 31500, false),
      ],
      quick_replies: ["Без пересадок", "Самый дешёвый", "Удобное время"],
    },
    trip: trip("transport_selection"),
  },

  flightsBack: {
    reply: {
      text: "И рейс обратно.",
      cards: [
        flight("back_1", "back", "Turkish Airlines", "2026-11-17T13:30:00", "2026-11-17T17:30:00", "4 ч 00 мин", 42000, true),
        flight("back_2", "back", "S7", "2026-11-17T19:00:00", "2026-11-17T23:00:00", "4 ч 00 мин", 38250, true),
      ],
      quick_replies: ["Без пересадок", "Самый дешёвый", "Удобное время"],
    },
    trip: trip("transport_selection"),
  },

  review: {
    reply: {
      text: "Поездка собрана: 146 250 ₽, укладываемся в бюджет. Оформляем?",
      cards: [],
      quick_replies: ["Подтверждаю, оформляй", "Поменять даты"],
    },
    trip: trip("checkout", { cart: CART }),
  },

  purchased: {
    reply: {
      text: "Готово! Заказ оформлен.",
      cards: [{ type: "order", id: "ORD-MOCK01", items: CART.items, total: CART.total }],
      quick_replies: ["Новая поездка"],
    },
    trip: trip("purchased", { cart: CART }),
  },
};