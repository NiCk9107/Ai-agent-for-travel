import { CheckCircle2 } from "lucide-react";
import { rub } from "../../lib/format";

export default function OrderCard({ card }) {
  return (
    <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4">
      <div className="flex items-center gap-2 font-semibold text-emerald-800">
        <CheckCircle2 size={18} /> Заказ {card.order_id ?? card.id}
      </div>
      <ul className="mt-2 text-sm">
        {(card.items ?? []).map((it) => <li key={it.ref_id}>{it.title} — {rub(it.price)}</li>)}
      </ul>
      <p className="mt-2 font-bold">Итого {rub(card.total)}</p>
    </div>
  );
}