import Badge from "../ui/Badge";
import CardImage from "./CardImage";
import WhyBlock from "./WhyBlock";
import CardActions from "./CardActions";
import { rub, toList } from "../../lib/format";

export default function DestinationCard({ card }) {
  return (
    <article className="flex h-full flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <CardImage src={card.image_url} alt={card.title} />
      <div className="flex flex-1 flex-col p-4">
        <h3 className="font-semibold">{card.title}</h3>
        <div className="mt-2 flex flex-wrap gap-1">
          {toList(card.badges).map((b) => <Badge key={b}>{b}</Badge>)}
        </div>
        {card.price_from != null && (
          <p className="mt-3 text-lg font-bold">
            от {rub(card.price_from)}{" "}
            <span className="text-xs font-normal text-slate-500">{card.price_note}</span>
          </p>
        )}
        <WhyBlock why={card.why} tradeoffs={card.tradeoffs} risks={card.risks} />
        <div className="mt-auto"><CardActions actions={card.actions} subject={card.title} /></div>
      </div>
    </article>
  );
}