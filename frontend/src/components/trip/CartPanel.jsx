import { ShoppingBag, X } from "lucide-react";
import { useStore } from "../../store";
import { rub } from "../../lib/format";

export default function CartPanel() {
  const cart = useStore((s) => s.trip.cart);
  const issues = useStore((s) => s.trip.validation?.issues);
  const loading = useStore((s) => s.loading);
  const send = useStore((s) => s.send);
  const openCheckout = useStore((s) => s.openCheckout);

  const items = cart?.items ?? [];
  const hasErrors = (issues ?? []).some((i) => i.severity === "error");

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4">
      <h2 className="mb-3 flex items-center gap-2 font-semibold"><ShoppingBag size={18} /> Корзина</h2>
      {items.length === 0 ? (
        <p className="text-sm text-slate-500">Пока пусто. Выберите варианты в чате — они появятся здесь.</p>
      ) : (
        <>
          <ul className="space-y-2">
            {items.map((it) => (
              <li key={it.ref_id} className="flex items-start justify-between gap-2 text-sm">
                <span>{it.title}</span>
                <span className="flex items-center gap-1 whitespace-nowrap font-medium">
                  {rub(it.price)}
                  <button disabled={loading} aria-label="Убрать"
                    onClick={() => send({ action: { type: "remove_from_cart", payload: { ref_id: it.ref_id } }, echo: `Убрать: ${it.title}` })}
                    className="text-slate-400 hover:text-red-600"><X size={14} /></button>
                </span>
              </li>
            ))}
          </ul>
          <div className="mt-3 flex justify-between border-t border-slate-100 pt-3 font-bold">
            <span>Итого</span><span>{rub(cart.total)}</span>
          </div>
          {hasErrors && <p className="mt-2 text-xs text-red-600">Есть нестыковки — сперва исправим их в чате.</p>}
          <button onClick={openCheckout} disabled={hasErrors || loading}
            className="mt-3 w-full rounded-xl bg-indigo-600 py-2.5 font-medium text-white disabled:opacity-40">
            Оформить
          </button>
        </>
      )}
    </section>
  );
}