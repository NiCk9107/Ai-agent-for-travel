import React from "react";
import DestinationCard from "./DestinationCard";
import HotelCard from "./HotelCard";
import FlightCard from "./FlightCard";
import TransferCard from "./TransferCard";
import OrderCard from "./OrderCard";

// card.type -> какой компонент рисовать. Типа нет в списке — карточку просто не рисуем.
const REGISTRY = {
  destination: DestinationCard,
  hotel: HotelCard,
  flight: FlightCard,
  train: FlightCard,
  transfer: TransferCard,
  order: OrderCard,
};

// Если одна карточка упадёт из-за кривых данных, остальное приложение продолжит работать
class CardBoundary extends React.Component {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(err) { console.error("Карточка упала:", err); }
  render() { return this.state.failed ? null : this.props.children; }
}

export default function CardRenderer({ card }) {
  const Card = REGISTRY[card?.type];
  if (!Card) {
    console.warn("Неизвестный тип карточки:", card?.type);
    return null;
  }
  return <CardBoundary><Card card={card} /></CardBoundary>;
}