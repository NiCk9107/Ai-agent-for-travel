// Этапы поездки, которые присылает бэкенд в trip.stage
export const STAGES = [
  { key: "clarifying",          label: "Запрос" },
  { key: "inspiration",         label: "Идеи" },
  { key: "destination_choice",  label: "Направление" },
  { key: "hotel_selection",     label: "Отель" },
  { key: "transport_selection", label: "Дорога" },
  { key: "trip_review",         label: "Проверка" },
  { key: "checkout",            label: "Оплата" },
  { key: "purchased",           label: "Готово" },
];

// stage -> «Шаг N из 6»
export function stepOf(stage) {
  const i = STAGES.findIndex((s) => s.key === stage);
  if (i < 0) return { n: 1, total: 6, label: "Запрос" };
  const n = Math.min(Math.max(i, 1), 6);
  return { n, total: 6, label: STAGES[i].label };
}