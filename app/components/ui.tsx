import type { CI, Drift } from "../lib/types";
import { pct } from "../lib/format";

export function Section({
  id,
  eyebrow,
  title,
  blurb,
  children,
}: {
  id: string;
  eyebrow: string;
  title: string;
  blurb: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="space-y-4 scroll-mt-6">
      <div className="space-y-1">
        <div className="text-xs font-semibold uppercase tracking-widest text-accent-cyan/80">
          {eyebrow}
        </div>
        <h2 className="text-xl font-bold text-white">{title}</h2>
        <p className="max-w-3xl text-sm leading-relaxed text-slate-400">{blurb}</p>
      </div>
      {children}
    </section>
  );
}

/** Horizontal meter with the 95% CI drawn as a translucent band behind the fill. */
export function Meter({ ci, color }: { ci: CI; color: string }) {
  const [point, lo, hi] = ci;
  return (
    <div className="relative meter" title={`95% CI: ${pct(lo, 1)} – ${pct(hi, 1)}`}>
      <div
        className="absolute inset-y-0 rounded-full opacity-25"
        style={{ left: `${lo * 100}%`, width: `${(hi - lo) * 100}%`, background: color }}
      />
      <div
        className="absolute inset-y-0 left-0 rounded-full"
        style={{ width: `${point * 100}%`, background: color }}
      />
      <div
        className="absolute -top-0.5 h-3 w-[2px] bg-white/80"
        style={{ left: `calc(${point * 100}% - 1px)` }}
      />
    </div>
  );
}

export function DriftBadge({ drift }: { drift: Drift }) {
  if (!drift || drift.delta === null) {
    return <span className="text-[11px] text-slate-600">baseline</span>;
  }
  if (!drift.flag) {
    return (
      <span className="text-[11px] text-slate-500">
        {drift.delta >= 0 ? "+" : ""}
        {(drift.delta * 100).toFixed(1)}pp
      </span>
    );
  }
  const up = drift.direction === "up";
  return (
    <span
      className={`chip ${
        up
          ? "border-accent-green/40 bg-accent-green/10 text-accent-green"
          : "border-accent-red/40 bg-accent-red/10 text-accent-red"
      }`}
      title="Flagged: point moved >5pp AND the 95% CIs do not overlap"
    >
      {up ? "▲" : "▼"} {drift.delta >= 0 ? "+" : ""}
      {(drift.delta * 100).toFixed(1)}pp drift
    </span>
  );
}

export function CategoryBars({
  data,
  color,
}: {
  data: Record<string, number>;
  color: string;
}) {
  const entries = Object.entries(data);
  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
      {entries.map(([cat, v]) => (
        <div key={cat} className="flex items-center gap-2">
          <span className="w-24 shrink-0 truncate text-[11px] text-slate-400" title={cat}>
            {cat}
          </span>
          <div className="meter h-1.5 flex-1">
            <div
              className="h-full rounded-full"
              style={{ width: `${v * 100}%`, background: color }}
            />
          </div>
          <span className="stat-num w-9 shrink-0 text-right text-[11px] text-slate-400">
            {pct(v)}
          </span>
        </div>
      ))}
    </div>
  );
}

export function Rank({ i }: { i: number }) {
  const medal = ["text-amber-300", "text-slate-300", "text-amber-600"][i] ?? "text-slate-600";
  return <span className={`stat-num text-sm font-bold ${medal}`}>{i + 1}</span>;
}
