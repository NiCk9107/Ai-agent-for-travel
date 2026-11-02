import { RotateCcw } from "lucide-react";
import { useStore } from "../../store";
import StageProgress from "./StageProgress";

export default function Header() {
  const reset = useStore((s) => s.reset);
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3">
        <h1 className="text-lg font-bold">О!дин запрос</h1>
        <StageProgress />
        <button onClick={reset} className="ml-auto flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900">
          <RotateCcw size={16} /> Новая поездка
        </button>
      </div>
    </header>
  );
}