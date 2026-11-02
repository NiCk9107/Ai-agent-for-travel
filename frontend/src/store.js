// Общая память приложения (Zustand). Компоненты читают отсюда данные и вызывают функции.
import { create } from "zustand";
import { api } from "./api";

const SESSION_KEY = "odin_session_id";
export const EMPTY_TRIP = {
  stage: "clarifying",
  assumptions: [],
  timeline: [],
  cart: { items: [], total: 0, currency: "RUB" },
  validation: { ok: null, issues: [] },
};

// localStorage может быть недоступен (режим инкогнито) — поэтому try/catch
const readSession = () => { try { return localStorage.getItem(SESSION_KEY); } catch { return null; } };
const writeSession = (id) => { try { localStorage.setItem(SESSION_KEY, id); } catch { /* ничего */ } };

// Понятный текст ошибки для красной плашки
const errorText = (e) => {
  if (e?.status === 0) return "Агент думает слишком долго. Попробуйте ещё раз";
  if (e?.status) return `Сервер ответил ошибкой ${e.status}. Попробуйте ещё раз`;
  return "Нет связи с сервером";
};

export const useStore = create((set, get) => ({
  sessionId: null,
  initStarted: false,
  messages: [],        // {role: "user" | "assistant", text, cards?, quick_replies?}
  trip: EMPTY_TRIP,
  status: null,        // «Агент думает…»
  loading: false,
  error: null,         // текст для красной плашки
  lastRequest: null,   // для кнопки «Повторить»
  checkoutOpen: false,
  order: null,

  // 1. При открытии сайта: восстановить сессию или создать новую
  init: async () => {
    if (get().initStarted) return;
    set({ initStarted: true });
    const saved = readSession();
    if (saved) {
      try {
        const data = await api.getState(saved);
        const messages = (data.messages ?? [])
          // служебные строки «[Кнопка] …» бэк пишет для агента — пользователю их не показываем
          .filter((m) => !(m.role === "user" && (m.content ?? "").startsWith("[Кнопка]")))
          .map((m) => ({ ...m, text: m.text ?? m.content }));
        // бэк хранит только тексты, а карточки текущего шага отдаёт отдельно — вешаем их на последний ответ агента
        const last = messages.length - 1;
        if (last >= 0 && messages[last].role === "assistant") {
          messages[last] = { ...messages[last], cards: data.cards ?? [], quick_replies: data.quick_replies ?? [] };
        }
        set({ sessionId: saved, trip: data.trip ?? EMPTY_TRIP, messages });
        return;
      } catch { /* сессия устарела — создадим новую */ }
    }
    try {
      const { session_id } = await api.createSession();
      writeSession(session_id);
      set({ sessionId: session_id, error: null });
    } catch (e) {
      console.error("init:", e);
      set({ error: errorText(e), initStarted: false });
    }
  },

  // 2. Отправить текст ИЛИ нажатие кнопки. echo — что показать в чате вместо текста
  send: async ({ text = null, action = null, echo = null }) => {
    const { sessionId, loading } = get();
    if (loading || !sessionId) return;
    const shown = text ?? echo;
    if (shown) set((s) => ({ messages: [...s.messages, { role: "user", text: shown }] }));
    await get()._request({ session_id: sessionId, message: text, action });
  },

  _request: async (body) => {
    set({ loading: true, status: "Агент думает…", error: null, lastRequest: body });
    try {
      const data = await api.chat(body);
      get().applyReply(data);
    } catch (e) {
      console.error("chat:", e);
      set({ loading: false, status: null, error: errorText(e) });
    }
  },

  retry: () => { const b = get().lastRequest; if (b) get()._request(b); },

  applyReply: (data) =>
    set((s) => ({
      messages: [...s.messages, { role: "assistant", ...data.reply }],
      trip: data.trip ?? s.trip,
      loading: false,
      status: null,
      lastRequest: null,
    })),

  // 3. Оплата
  openCheckout: () => set({ checkoutOpen: true }),
  closeCheckout: () => set({ checkoutOpen: false }),
  checkout: async (payer) => {
    const { sessionId } = get();
    const order = await api.checkout({ session_id: sessionId, payer });
    set({ order, checkoutOpen: false });
  },

  // 4. Кнопка «Новая поездка»
  reset: async () => {
    try { await api.reset(get().sessionId); } catch { /* ничего */ }
    set({ messages: [], trip: EMPTY_TRIP, order: null, error: null, status: null, lastRequest: null });
  },
}));