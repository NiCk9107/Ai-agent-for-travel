import { useStore } from "../../store";

export default function QuickReplies({ items }) {
  const send = useStore((s) => s.send);
  const loading = useStore((s) => s.loading);
  const reset = useStore((s) => s.reset);
  if (!items.length || loading) return null;
  return (
    <div className="flex flex-wrap gap-2 px-4 pb-2">
      {items.map((q) => (
        <button key={q} onClick={() => (q === "Новая поездка" ? reset() : send({ text: q }))}
          className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-sm text-indigo-700 hover:bg-indigo-100">
          {q}
        </button>
      ))}
    </div>
  );
}