import { Car, Bus, TramFront } from "lucide-react";
import CardActions from "./CardActions";
import { rub, duration, label, TRANSFER_KIND } from "../../lib/format";

const ICON = { taxi: Car, shuttle: Bus, public: TramFront };

export default function TransferCard({ card }) {
  const Icon = ICON[card.kind] ?? Car;
  const name = label(TRANSFER_KIND, card.kind);
  return (
    <article className="flex h-full flex-col rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2 font-semibold"><Icon size={18} /> {name}</div>
      <p className="text-sm text-slate-500">Аэропорт → отель · {duration(card.duration_min)}</p>
      <p className="mt-2 font-bold">{rub(card.price)}</p>
      <div className="mt-auto"><CardActions actions={card.actions} subject={name} /></div>
    </article>
  );
}