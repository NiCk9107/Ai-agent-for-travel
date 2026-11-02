const TONES = {
  slate: "bg-slate-100 text-slate-700",
  green: "bg-emerald-50 text-emerald-700",
  amber: "bg-amber-50 text-amber-800",
};

export default function Badge({ children, tone = "slate" }) {
  return <span className={`rounded-full px-2 py-0.5 text-xs ${TONES[tone]}`}>{children}</span>;
}