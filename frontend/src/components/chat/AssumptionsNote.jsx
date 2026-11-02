import { Info } from "lucide-react";
import { useStore } from "../../store";

export default function AssumptionsNote() {
  const items = useStore((s) => s.trip.assumptions);
  if (!items?.length) return null;
  return (
    <div className="rounded-xl bg-amber-50 p-3 text-sm text-amber-800">
      <div className="mb-1 flex items-center gap-1 font-medium"><Info size={14} /> Я допустил</div>
      <ul className="list-disc pl-5">{items.map((a) => <li key={a}>{a}</li>)}</ul>
      <p className="mt-1 text-xs">Напишите в чат, если что-то не так.</p>
    </div>
  );
}