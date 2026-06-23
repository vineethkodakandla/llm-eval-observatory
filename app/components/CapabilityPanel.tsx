import type { CapModel, HistoryRecord, Snapshot } from "../lib/types";
import { colorFor, pct } from "../lib/format";
import { seriesFor } from "../lib/data";
import { CategoryBars, DriftBadge, Meter, Rank, Section } from "./ui";
import TrendChart from "./charts/TrendChart";

export default function CapabilityPanel({
  track,
  history,
  mock,
}: {
  track: NonNullable<Snapshot["tracks"]["capability"]>;
  history: HistoryRecord[];
  mock: boolean;
}) {
  const models = track.per_model;
  const colors: Record<string, string> = {};
  const labels: Record<string, string> = {};
  models.forEach((m, i) => {
    colors[m.model] = colorFor(i);
    labels[m.model] = m.label;
  });
  const { x, series } = seriesFor(history, "capability", "accuracy", mock);

  return (
    <Section
      id="capability"
      eyebrow="Track 1"
      title="Capability & drift"
      blurb={`Accuracy on a fixed ${track.n_items}-item auto-graded suite (math, logic, instruction-following, factual recall). Bars show the point estimate; the faint band behind each is the bootstrapped 95% CI. A drift badge appears only when a model's score moves more than 5 points AND its CI no longer overlaps the previous run's — noise stays quiet.`}
    >
      <div className="grid gap-4 lg:grid-cols-5">
        <div className="card overflow-hidden lg:col-span-3">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-ink-700 text-left text-[11px] uppercase tracking-wider text-slate-500">
                <th className="px-4 py-2.5 font-medium">#</th>
                <th className="px-2 py-2.5 font-medium">Model</th>
                <th className="px-2 py-2.5 font-medium">Accuracy (95% CI)</th>
                <th className="px-4 py-2.5 text-right font-medium">vs last</th>
              </tr>
            </thead>
            <tbody>
              {models.map((m, i) => (
                <Row key={m.model} m={m} i={i} color={colors[m.model]} />
              ))}
            </tbody>
          </table>
        </div>

        <div className="card space-y-2 p-4 lg:col-span-2">
          <div className="text-xs font-medium uppercase tracking-wider text-slate-500">
            Accuracy over time
          </div>
          <TrendChart x={x} series={series} labels={labels} colors={colors} />
        </div>
      </div>

      <div className="card space-y-4 p-4">
        <div className="text-xs font-medium uppercase tracking-wider text-slate-500">
          Accuracy by category
        </div>
        <div className="grid gap-x-8 gap-y-4 md:grid-cols-2">
          {models.map((m, i) => (
            <div key={m.model} className="space-y-2">
              <div className="flex items-center gap-2 text-sm">
                <span className="h-2.5 w-2.5 rounded-sm" style={{ background: colorFor(i) }} />
                <span className="font-medium text-slate-200">{m.label}</span>
              </div>
              <CategoryBars data={m.by_category} color={colorFor(i)} />
            </div>
          ))}
        </div>
      </div>
    </Section>
  );
}

function Row({ m, i, color }: { m: CapModel; i: number; color: string }) {
  return (
    <tr className="border-b border-ink-800/60 last:border-0">
      <td className="px-4 py-3">
        <Rank i={i} />
      </td>
      <td className="px-2 py-3">
        <div className="font-medium text-slate-100">{m.label}</div>
        <div className="text-[11px] text-slate-500">{m.family}</div>
      </td>
      <td className="px-2 py-3">
        <div className="flex items-center gap-3">
          <div className="w-40">
            <Meter ci={m.ci95} color={color} />
          </div>
          <div className="stat-num text-right">
            <span className="text-slate-100">{pct(m.accuracy, 1)}</span>
            <span className="ml-2 text-[11px] text-slate-500">
              [{pct(m.ci95[1])}–{pct(m.ci95[2])}]
            </span>
          </div>
        </div>
      </td>
      <td className="px-4 py-3 text-right">
        <DriftBadge drift={m.drift} />
      </td>
    </tr>
  );
}
