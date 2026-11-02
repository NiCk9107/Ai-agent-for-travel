import dayjs from "dayjs";
import "dayjs/locale/ru";
dayjs.locale("ru");

// 98000 -> «98 000 ₽»
export const rub = (n) => (n == null ? "" : `${Math.round(n).toLocaleString("ru-RU")} ₽`);
// "2026-11-12T06:40" -> «12 нояб., чт»
export const dateShort = (iso) => dayjs(iso).format("D MMM, dd");
// "2026-11-12T06:40" -> «06:40»
export const timeHM = (iso) => dayjs(iso).format("HH:mm");
// 35 -> «35 мин», 230 -> «3 ч 50 мин»
export const duration = (min) => {
  const h = Math.floor(min / 60), m = min % 60;
  return h ? `${h} ч${m ? ` ${m} мин` : ""}` : `${m} мин`;
};
// строку превращает в массив из одного элемента, массив оставляет как есть
export const toList = (v) => (Array.isArray(v) ? v : v ? [v] : []);

// Коды из бэкенда -> понятные подписи. Неизвестный код показываем как есть.
export const MEAL = { RO: "Без питания", BB: "Завтрак", HB: "Полупансион", FB: "Полный пансион", AI: "Всё включено" };
export const TRANSFER_KIND = { taxi: "Такси", shuttle: "Шаттл", public: "Общественный транспорт" };
export const label = (map, code) => map[code] ?? code;

// Условия отмены: non_refundable -> «Невозвратный тариф», free_cancel_3d -> «Бесплатная отмена за 3 дн.»
export const cancelLabel = (code) => {
  if (!code) return "";
  if (code === "non_refundable") return "Невозвратный тариф";
  const m = /^free_cancel_(\d+)d$/.exec(code);
  return m ? `Бесплатная отмена за ${m[1]} дн.` : code;
};