// ЕДИНСТВЕННОЕ место, где фронт ходит на сервер.
// VITE_USE_MOCKS=true в .env -> вместо сервера отвечают моки.
import { mockApi } from "./mocks/mockServer";

const API_URL = import.meta.env.VITE_API_URL ?? "";
const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === "true";
const TIMEOUT_MS = 120000; // агент может думать долго (несколько вызовов LLM), но не вечно

// Ошибка с кодом ответа сервера (0 = сервер не ответил вовремя)
export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function request(path, options = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${API_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      signal: ctrl.signal,
      ...options,
    });
    if (!res.ok) {
      let detail = "";
      try { detail = JSON.stringify((await res.json()).detail ?? ""); } catch { /* ответ не JSON */ }
      throw new ApiError(res.status, `API ${res.status} ${detail}`);
    }
    return res.json();
  } catch (e) {
    if (e.name === "AbortError") throw new ApiError(0, "timeout");
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

const post = (path, body) =>
  request(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });

const realApi = {
  health: () => request("/api/health"),
  createSession: () => post("/api/session"),
  chat: (body) => post("/api/chat", body),
  getState: (id) => request(`/api/state/${id}`),
  checkout: (body) => post("/api/checkout", body),
  reset: (id) => post("/api/reset", { session_id: id }),
};

export const api = USE_MOCKS ? mockApi : realApi;