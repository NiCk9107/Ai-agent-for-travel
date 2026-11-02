import { useEffect, useState } from "react";
import { useStore } from "./store";
import { rub } from "./lib/format";
import Header from "./components/layout/Header";
import ErrorBanner from "./components/layout/ErrorBanner";
import ChatPanel from "./components/chat/ChatPanel";
import TripPanel from "./components/trip/TripPanel";
import CheckoutModal from "./components/trip/CheckoutModal";
import OrderSuccess from "./components/trip/OrderSuccess";

export default function App() {
  const init = useStore((s) => s.init);
  const total = useStore((s) => s.trip.cart?.total ?? 0);
  const [sheetOpen, setSheetOpen] = useState(false); // выдвижная панель на телефоне
  // при открытии страницы один раз создаём или восстанавливаем сессию
  useEffect(() => { init(); }, [init]);

  return (
    <div className="flex h-full flex-col">
      <Header />
      <ErrorBanner />
      <main className="mx-auto flex w-full max-w-7xl flex-1 gap-4 overflow-hidden p-2 md:p-4">
        {/* слева чат */}
        <section className="flex min-w-0 flex-1 flex-col">
          <ChatPanel />
        </section>
        {/* справа план и корзина — только на широком экране */}
        <aside className="hidden w-96 shrink-0 overflow-y-auto lg:block">
          <TripPanel />
        </aside>
      </main>

      {/* на узком экране: кнопка внизу открывает ту же панель снизу */}
      <button onClick={() => setSheetOpen(true)}
        className="fixed bottom-20 right-4 z-40 rounded-full bg-indigo-600 px-4 py-2 text-sm text-white shadow-lg lg:hidden">
        Поездка · {rub(total)}
      </button>
      {sheetOpen && (
        <div className="fixed inset-0 z-40 bg-black/40 lg:hidden" onClick={() => setSheetOpen(false)}>
          <div onClick={(e) => e.stopPropagation()}
            className="absolute inset-x-0 bottom-0 max-h-[80vh] overflow-y-auto rounded-t-2xl bg-slate-50 p-4">
            <TripPanel />
          </div>
        </div>
      )}

      <CheckoutModal />
      <OrderSuccess />
    </div>
  );
}