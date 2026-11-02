import { useEffect, useRef } from "react";
import { useStore } from "../../store";
import MessageBubble from "./MessageBubble";

const EXAMPLES = [
  "Хочу к тёплому морю в ноябре, недорого, с ребёнком 5 лет",
  "Сочи, 10–15 декабря, двое взрослых, до 60 тысяч",
  "Хочу тишины и гор, без людей",
];

export default function MessageList() {
  const messages = useStore((s) => s.messages);
  const send = useStore((s) => s.send);
  const endRef = useRef(null);

  // при новом сообщении прокручиваем вниз
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length]);

  return (
    <div className="flex-1 space-y-4 overflow-y-auto p-4">
      {messages.length === 0 && (
        <div className="mx-auto mt-10 max-w-md text-center">
          <p className="text-xl font-semibold">Куда поедем?</p>
          <p className="mt-1 text-slate-500">Опишите поездку своими словами — я подберу и соберу всё.</p>
          <div className="mt-6 flex flex-col gap-2">
            {EXAMPLES.map((e) => (
              <button key={e} onClick={() => send({ text: e })}
                className="rounded-xl border border-slate-200 px-4 py-2 text-left text-sm hover:bg-slate-50">
                {e}
              </button>
            ))}
          </div>
        </div>
      )}
      {messages.map((m, i) => <MessageBubble key={i} message={m} isLast={i === messages.length - 1} />)}
      <div ref={endRef} />
    </div>
  );
}