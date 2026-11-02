import { Plane, TrainFront, Luggage } from "lucide-react";
import Badge from "../ui/Badge";
import CardActions from "./CardActions";
import { rub, timeHM, dateShort } from "../../lib/format";

// По backend/api/schemas.py: depart/arrive — ISO-строки,
// duration — готовая строка «4 ч 10 мин», baggage — true/false
export default function FlightCard({ card }) {
  const Icon = card.type === "train" ? TrainFront : Plane;
  const stops = card.stops ? `Пересадок: ${card.stops}` : "Без пересадок";
  // бэк кладёт направление в payload кнопки: "out" — туда, "back" — обратно
  const direction = card.actions?.[0]?.payload?.direction;
  const dirLabel = direction === "out" ? "Туда" : direction === "back" ? "Обратно" : null;
  return (
    <article className="flex h-full flex-col rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Icon size={16} /> {card.airline}
        {dirLabel && <span className="ml-auto"><Badge>{dirLabel}</Badge></span>}
      </div>
      <div className="mt-3 flex items-center justify-between">
        <div>
          <p className="text-xl font-bold">{timeHM(card.depart)}</p>
          <p className="text-xs text-slate-500">{dateShort(card.depart)}</p>
        </div>
        <div className="flex-1 px-3 text-center text-xs text-slate-500">
          {card.duration}<div className="my-1 h-px bg-slate-300" />{stops}
        </div>
        <div className="text-right">
          <p className="text-xl font-bold">{timeHM(card.arrive)}</p>
          <p className="text-xs text-slate-500">{dateShort(card.arrive)}</p>
        </div>
      </div>
      <p className="mt-3 flex items-center gap-2 font-bold">
        {rub(card.price)}
        <span className="flex items-center gap-1 text-xs font-normal text-slate-500">
          <Luggage size={14} /> {card.baggage ? "багаж включён" : "без багажа"}
        </span>
      </p>
      <div className="mt-auto">
        <CardActions actions={card.actions} subject={`${dirLabel ? dirLabel + ", " : ""}${card.airline} ${timeHM(card.depart)}`} />
      </div>
    </article>
  );
}