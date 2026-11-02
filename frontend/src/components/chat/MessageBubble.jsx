import CardRenderer from "../cards/CardRenderer";

// Модель иногда пишет **жирный** текст (markdown). Показываем его жирным, а не со звёздочками.
function renderText(text) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") && part.length > 4
      ? <b key={i}>{part.slice(2, -2)}</b>
      : part
  );
}

// isLast = это последнее сообщение в чате. Кнопки работают только на карточках последнего ответа,
// чтобы нельзя было случайно нажать «Выбрать» на старой карточке и откатить выбор.
export default function MessageBubble({ message, isLast }) {
  // сообщение пользователя — фиолетовый пузырь справа
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-indigo-600 px-4 py-2 text-white">
          {message.text}
        </div>
      </div>
    );
  }
  // сообщение агента — серый пузырь слева и карточки под ним
  return (
    <div className="flex flex-col items-start gap-3">
      {message.text && (
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-bl-sm bg-slate-100 px-4 py-2">
          {renderText(message.text)}
        </div>
      )}
      {message.cards?.length > 0 && (
        <div className={`grid w-full gap-3 sm:grid-cols-2 xl:grid-cols-3 ${isLast ? "" : "pointer-events-none opacity-60"}`}>
          {message.cards.map((c, i) => (
            <CardRenderer key={`${c.type}-${c.id ?? i}`} card={c} />
          ))}
        </div>
      )}
    </div>
  );
}