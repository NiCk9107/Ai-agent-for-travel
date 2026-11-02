import { Loader2 } from "lucide-react";
import { useStore } from "../../store";

export default function StatusLine() {
  const status = useStore((s) => s.status);
  if (!status) return null;
  return (
    <div className="flex items-center gap-2 px-4 pb-2 text-sm text-slate-500">
      <Loader2 size={16} className="animate-spin" /> {status}
    </div>
  );
}