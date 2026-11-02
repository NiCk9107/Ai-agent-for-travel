import { useState } from "react";
import { Star } from "lucide-react";
import Badge from "../ui/Badge";
import CardImage from "./CardImage";
import WhyBlock from "./WhyBlock";
import CardActions from "./CardActions";
import { rub, label, MEAL, cancelLabel } from "../../lib/format";

export default function HotelCard({ card }) {
  const [showReviews, setShowReviews] = useState(false);
  const freeCancel = card.cancel_policy && card.cancel_policy !== "non_refundable";
  const reviews = card.reviews ?? [];
  return (
    <article className="flex h-full flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <CardImage src={card.image_url} alt={card.name} />
      <div className="flex flex-1 flex-col p-4">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-semibold">{card.name}</h3>
          {card.rating != null && (
            <span className="rounded-md bg-indigo-600 px-1.5 text-sm font-bold text-white">{card.rating}</span>
          )}
        </div>
        <div className="mt-1 flex">
          {Array.from({ length: card.stars ?? 0 }, (_, i) => (
            <Star key={i} size={14} className="fill-amber-400 text-amber-400" />
          ))}
        </div>
        <div className="mt-2 flex flex-wrap gap-1">
          {card.meal_plan && <Badge>{label(MEAL, card.meal_plan)}</Badge>}
          {card.beach_distance != null && <Badge>{card.beach_distance} м до пляжа</Badge>}
          {card.cancel_policy && (
            <Badge tone={freeCancel ? "green" : "amber"}>{cancelLabel(card.cancel_policy)}</Badge>
          )}
        </div>
        <p className="mt-3 text-lg font-bold">
          {rub(card.price_total)}{" "}
          {card.price_note && <span className="text-xs font-normal text-slate-500">{card.price_note}</span>}
        </p>
        <WhyBlock pros={card.pros} tradeoffs={card.tradeoffs} risks={card.risks} />
        {reviews.length > 0 && (
          <button onClick={() => setShowReviews((v) => !v)} className="mt-2 self-start text-sm text-indigo-600">
            {showReviews ? "Скрыть отзывы" : `Отзывы (${reviews.length})`}
          </button>
        )}
        {showReviews && (
          <ul className="mt-2 space-y-2 text-sm">
            {reviews.map((r, i) => (
              <li key={i} className="rounded-lg bg-slate-50 p-2">
                {/* бэк присылает отзыв как {author, score, plus, minus}; на всякий случай понимаем и {rating, text} */}
                <b>{r.author}</b>{(r.score ?? r.rating) != null && ` · ${r.score ?? r.rating}/10`}
                {r.text && <div>{r.text}</div>}
                {r.plus && <div className="text-emerald-700">+ {r.plus}</div>}
                {r.minus && <div className="text-slate-600">− {r.minus}</div>}
              </li>
            ))}
          </ul>
        )}
        <div className="mt-auto"><CardActions actions={card.actions} subject={card.name} /></div>
      </div>
    </article>
  );
}