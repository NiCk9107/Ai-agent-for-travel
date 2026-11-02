import { useStore } from "../../store";

// Кнопки из card.actions. Нажатие уходит на сервер как action,
// а в чате показываем «Выбрать: Анталья».
export default function CardActions({ actions = [], subject }) {
  const send = useStore((s) => s.send);
  const loading = useStore((s) => s.loading);
  if (!actions.length) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {actions.map((a, i) => (
        <button
          key={`${a.type}-${i}`}
          disabled={loading}
          onClick={() => send({
            action: { type: a.type, payload: a.payload ?? {} },
            echo: subject ? `${a.label}: ${subject}` : a.label,
          })}
          className={i === 0
            ? "rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-40"
            : "rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-40"}
        >
          {a.label}
        </button>
      ))}
    </div>
  );
}