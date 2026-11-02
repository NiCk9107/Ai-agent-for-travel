import { Plane, PlaneLanding, Car, BedDouble, DoorOpen, Circle } from "lucide-react";
import { dateShort, timeHM } from "../../lib/format";

const ICONS = { flight: Plane, arrive: PlaneLanding, transfer: Car, checkin: BedDouble, checkout: DoorOpen };
const TONE = {
  error: "border-red-300 bg-red-50 text-red-700",
  warning: "border-amber-300 bg-amber-50 text-amber-800",
};

export default function TripTimeline({ steps, issues = [] }) {
  const byCode = Object.fromEntries(issues.map((i) => [i.code, i]));
  return (
    <ol className="relative space-y-4 border-l border-slate-200 pl-5">
      {steps.map((s, i) => {
        const Icon = ICONS[s.kind] ?? Circle;
        const issue = s.issue_code ? byCode[s.issue_code] : null;
        return (
          <li key={i} className="relative">
            <span className="absolute -left-[31px] flex h-6 w-6 items-center justify-center rounded-full border border-slate-200 bg-white">
              <Icon size={13} />
            </span>
            <p className="text-xs text-slate-500">{dateShort(s.at)} · {timeHM(s.at)}</p>
            <p className="text-sm font-medium">{s.title}</p>
            {issue && (
              <div className={`mt-1 rounded-lg border p-2 text-xs ${TONE[issue.severity] ?? TONE.warning}`}>
                {issue.message}
                {issue.fix_suggestion && <div className="mt-0.5 opacity-80">Совет: {issue.fix_suggestion}</div>}
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}