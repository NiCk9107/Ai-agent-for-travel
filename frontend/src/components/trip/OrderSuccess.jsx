import { CheckCircle2 } from "lucide-react";
import { useStore } from "../../store";
import { rub } from "../../lib/format";

export default function OrderSuccess() {
  const order = useStore((s) => s.order);
  const reset = useStore((s) => s.reset);
  if (!order) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-sm rounded-2xl bg-white p-6 text-center">
        <CheckCircle2 size={48} className="mx-auto text-emerald-500" />
        <h2 className="mt-3 text-xl font-semibold">Заказ оформлен</h2>
        <p className="mt-1 text-slate-600">№ {order.order_id} · {rub(order.total)}</p>
        <button onClick={reset} className="mt-5 w-full rounded-xl bg-indigo-600 py-2.5 text-white">Новая поездка</button>
      </div>
    </div>
  );
}