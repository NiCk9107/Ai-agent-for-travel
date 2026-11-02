import { useStore } from "../../store";
import { stepOf } from "../../lib/stages";

export default function StageProgress() {
  const stage = useStore((s) => s.trip.stage);
  const { n, total, label } = stepOf(stage);
  return (
    <div className="hidden items-center gap-2 text-sm text-slate-600 sm:flex">
      <div className="flex gap-1">
        {Array.from({ length: total }, (_, i) => (
          <span key={i} className={`h-1.5 w-6 rounded-full ${i < n ? "bg-indigo-600" : "bg-slate-200"}`} />
        ))}
      </div>
      Шаг {n} из {total} · {label}
    </div>
  );
}