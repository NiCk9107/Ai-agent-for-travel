import { useStore } from "../../store";
import MessageList from "./MessageList";
import StatusLine from "./StatusLine";
import QuickReplies from "./QuickReplies";
import ChatInput from "./ChatInput";

export default function ChatPanel() {
  const messages = useStore((s) => s.messages);
  const last = messages.at(-1);
  return (
    <div className="flex h-full flex-col rounded-2xl border border-slate-200 bg-white">
      <MessageList />
      <StatusLine />
      {last?.role === "assistant" && <QuickReplies items={last.quick_replies ?? []} />}
      <ChatInput />
    </div>
  );
}