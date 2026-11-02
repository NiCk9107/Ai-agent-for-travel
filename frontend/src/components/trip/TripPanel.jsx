import { useStore } from "../../store";
import AssumptionsNote from "../chat/AssumptionsNote";
import TripTimeline from "./TripTimeline";
import CartPanel from "./CartPanel";

export default function TripPanel() {
  const timeline = useStore((s) => s.trip.timeline);
  const issues = useStore((s) => s.trip.validation?.issues);
  return (
    <div className="space-y-4">
      <AssumptionsNote />
      {timeline?.length > 0 && (
        <section className="rounded-2xl border border-slate-200 bg-white p-4">
          <h2 className="mb-3 font-semibold">План поездки</h2>
          <TripTimeline steps={timeline} issues={issues ?? []} />
        </section>
      )}
      <CartPanel />
    </div>
  );
}