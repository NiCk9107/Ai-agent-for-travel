import { useState } from "react";
import { useStore } from "../../store";
import { rub } from "../../lib/format";

export default function CheckoutModal() {
  const open = useStore((s) => s.checkoutOpen);
  const close = useStore((s) => s.closeCheckout);
  const checkout = useStore((s) => s.checkout);
  const cart = useStore((s) => s.trip.cart);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  if (!open) return null;
  const valid = name.trim() && /\S+@\S+\.\S+/.test(email) && agree;

  const pay = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try { await checkout({ name: name.trim(), email: email.trim() }); }
    catch { setErr("Не удалось оформить. Попробуйте ещё раз."); }
    finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center sm:p-4" onClick={close}>
      <form onSubmit={pay} onClick={(e) => e.stopPropagation()}
        className="max-h-[90vh] w-full max-w-md overflow-y-auto rounded-t-2xl bg-white p-6 sm:rounded-2xl">
        <h2 className="text-lg font-semibold">Подтвердите заказ</h2>
        <ul className="mt-3 space-y-1 text-sm">
          {(cart?.items ?? []).map((it) => (
            <li key={it.ref_id} className="flex justify-between gap-2"><span>{it.title}</span><span>{rub(it.price)}</span></li>
          ))}
        </ul>
        <div className="mt-2 flex justify-between border-t pt-2 text-lg font-bold">
          <span>Итого</span><span>{rub(cart?.total)}</span>
        </div>
        <label className="mt-4 block text-sm">Имя
          <input value={name} onChange={(e) => setName(e.target.value)} className="mt-1 w-full rounded-lg border px-3 py-2" />
        </label>
        <label className="mt-3 block text-sm">Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1 w-full rounded-lg border px-3 py-2" />
        </label>
        <label className="mt-3 flex items-center gap-2 text-sm">
          <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
          Проверил(а) состав и сумму
        </label>
        {err && <p className="mt-2 text-sm text-red-600">{err}</p>}
        <button disabled={!valid || busy} className="mt-4 w-full rounded-xl bg-indigo-600 py-3 font-medium text-white disabled:opacity-40">
          {busy ? "Оформляем…" : `Оплатить ${rub(cart?.total)}`}
        </button>
        <p className="mt-2 text-center text-xs text-slate-400">Демо: оплата имитируется, деньги не списываются.</p>
      </form>
    </div>
  );
}