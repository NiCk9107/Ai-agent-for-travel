// Притворяется сервером: по нажатой кнопке или тексту выбирает следующий ответ из mocks.js
import { MOCK_REPLIES } from "./mocks";

const delay = (ms) => new Promise((r) => setTimeout(r, ms));
let paid = false; // оплачено ли через окно оплаты — как stage "purchased" на сервере

function pickReply(body) {
  const a = body.action;
  if (a?.type === "choose_destination") return MOCK_REPLIES.hotels;
  if (a?.type === "select_hotel") return MOCK_REPLIES.flightsOut;
  if (a?.type === "select_flight") return a.payload?.direction === "out" ? MOCK_REPLIES.flightsBack : MOCK_REPLIES.review;
  if (/оформляй|подтверждаю/i.test(body.message ?? "")) return MOCK_REPLIES.purchased;
  return MOCK_REPLIES.destinations;
}

export const mockApi = {
  health: async () => ({ ok: true }),
  createSession: async () => ({ session_id: "s_mock" }),
  chat: async (body) => { await delay(700); return structuredClone(pickReply(body)); },
  getState: async () => ({
    trip: paid ? MOCK_REPLIES.purchased.trip : { ...MOCK_REPLIES.destinations.trip, stage: "clarifying", assumptions: [] },
    messages: [],
  }),
  checkout: async () => { await delay(600); paid = true; return { order_id: "ORD-MOCK01", status: "paid", total: 146250 }; },
  reset: async () => { paid = false; return { ok: true }; },
};