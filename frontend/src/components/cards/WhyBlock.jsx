import { Check, Scale, AlertTriangle } from "lucide-react";
import { toList } from "../../lib/format";

// Три строки: ✓ почему подходит, ⚖ чем жертвуем, ⚠ риски
export default function WhyBlock({ why, pros, tradeoffs, risks }) {
  const rows = [
    ...[...toList(why), ...toList(pros)].map((t) => ({ t, Icon: Check, cls: "text-emerald-700" })),
    ...toList(tradeoffs).map((t) => ({ t, Icon: Scale, cls: "text-slate-600" })),
    ...toList(risks).map((t) => ({ t, Icon: AlertTriangle, cls: "text-amber-700" })),
  ];
  return (
    <ul className="mt-3 space-y-1 text-sm">
      {rows.map(({ t, Icon, cls }, i) => (
        <li key={i} className={`flex gap-1.5 ${cls}`}>
          <Icon size={14} className="mt-0.5 shrink-0" />{t}
        </li>
      ))}
    </ul>
  );
}