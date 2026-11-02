import { useStore } from "../../store";

export default function ErrorBanner() {
  const error = useStore((s) => s.error);
  const retry = useStore((s) => s.retry);
  const init = useStore((s) => s.init);
  const sessionId = useStore((s) => s.sessionId);
  if (!error) return null;
  return (
    <div className="flex items-center justify-center gap-3 bg-red-50 px-4 py-2 text-sm text-red-700">
      {error}
      <button onClick={sessionId ? retry : init} className="rounded-md bg-red-600 px-3 py-1 text-white">
        Повторить
      </button>
    </div>
  );
}