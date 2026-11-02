import { useState } from "react";
import { Send } from "lucide-react";
import { useStore } from "../../store";

export default function ChatInput() {
  const [text, setText] = useState("");
  const send = useStore((s) => s.send);
  const loading = useStore((s) => s.loading);

  const submit = () => {
    const t = text.trim();
    if (!t || loading) return;
    send({ text: t });
    setText("");
  };

  return (
    <div className="flex items-end gap-2 border-t border-slate-200 p-3">
      <textarea
        rows={1}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
        placeholder="Например: море в ноябре, двое взрослых и ребёнок"
        className="max-h-40 flex-1 resize-none rounded-xl border border-slate-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
      />
      <button onClick={submit} disabled={loading || !text.trim()} aria-label="Отправить"
        className="rounded-xl bg-indigo-600 p-3 text-white disabled:opacity-40">
        <Send size={18} />
      </button>
    </div>
  );
}