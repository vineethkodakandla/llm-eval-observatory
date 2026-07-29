import type { AutopilotModel, HistoryRecord, Snapshot } from "../lib/types";
import { colorFor, pct } from "../lib/format";
import { seriesFor } from "../lib/data";
import { CategoryBars, DriftBadge, Meter, Rank, Section } from "./ui";
import TrendChart from "./charts/TrendChart";

// Higher-is-better metrics (grounding, abstention): green when high.
function toneHigh(v: number | null | undefined): string {
  if (v === null || v === undefined) return "text-slate-500";
  if (v >= 0.8) return "text-accent-green";
  if (v >= 0.6) return "text-accent-amber";
  return "text-accent-red";
}
// Lower-is-better metrics (false clears, over-escalation, fabricated cites).
function toneLow(v: number | null | undefined): string {
  if (v === null || v === undefined) return "text-slate-500";
  if (v <= 0.1) return "text-accent-green";
  if (v <= 0.25) return "text-accent-amber";
  return "text-accent-red";
}

export default function AutopilotPanel({
  track,
  history,
  mock,
}: {
  track: NonNullable<Snapshot["tracks"]["autopilot"]>;
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
  const { x, series } = seriesFor(history, "autopilot", "accuracy", mock);

  // Concrete "dangerous misses": alerts a model CLEARED that should have been
  // escalated. Deduped across models so the reader sees which cases slip through.
  const misses: { id: string; category: string; label: string }[] = [];
  const seen = new Set<string>();
  for (const m of models) {
    for (const f of m.sample_failures) {
      if (f.false_clear && !seen.has(f.id)) {
        seen.add(f.id);
        misses.push({ id: f.id, category: f.category, label: m.label });
      }
    }
  }

  return (
    <Section
      id="autopilot"
      eyebrow="Track 1 · flagship"
      title="Autopilot reliability — KYC/AML alert triage"
      blurb={`The other three tracks ask how good the model is. This one asks the question a services-as-software company must answer before it can sell an outcome instead of a tool: can an autopilot built on this model DO an already-outsourced, intelligence-heavy job end-to-end? The job is AML alert triage — for each of ${track.n_cases} flagged cases (${pct(track.escalate_base_rate)} genuinely suspicious) the model decides ESCALATE, CLEAR, or REVIEW against a fixed policy and must cite its evidence. What decides shippability isn't raw accuracy — it's whether it fabricates evidence, and whether it wrongly CLEARS an alert it should have escalated (a "false clear": the error that gets a bank fined). Every number here is graded deterministically.`}
    >
      <div className="grid gap-4 lg:grid-cols-5">
        <div className="card overflow-hidden lg:col-span-3">
          <div className="border-b border-ink-700 px-4 py-2.5 text-[11px] font-medium uppercase tracking-wider text-slate-500">
            Decision accuracy — 3-way (escalate / clear / review)
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-ink-800 text-left text-[11px] uppercase tracking-wider text-slate-500">
                <th className="px-4 py-2 font-medium">#</th>
                <th className="px-2 py-2 font-medium">Model</th>
                <th className="px-2 py-2 font-medium">Accuracy (95% CI)</th>
                <th className="px-4 py-2 text-right font-medium">vs last</th>
              </tr>
            </thead>
            <tbody>
              {models.map((m, i) => (
                <tr key={m.model} className="border-b border-ink-800/60 last:border-0">
                  <td className="px-4 py-3">
                    <Rank i={i} />
                  </td>
                  <td className="px-2 py-3">
                    <div className="font-medium text-slate-100">{m.label}</div>
                    <div className="text-[11px] text-slate-500">{m.family}</div>
                  </td>
                  <td className="px-2 py-3">
                    <div className="flex items-center gap-3">
                      <div className="w-36">
                        <Meter ci={m.ci95} color={colors[m.model]} />
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
              ))}
            </tbody>
          </table>
        </div>

        <div className="card space-y-2 p-4 lg:col-span-2">
          <div className="text-xs font-medium uppercase tracking-wider text-slate-500">
            Decision accuracy over time
          </div>
          <TrendChart x={x} series={series} labels={labels} colors={colors} />
        </div>
      </div>

      {/* Trust & safety — the numbers that decide whether you can let it ship. */}
      <div className="card space-y-3 overflow-x-auto p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div className="text-xs font-medium uppercase tracking-wider text-slate-500">
            Trust &amp; safety — can it ship without a human?
          </div>
          <div className="text-[11px] text-slate-500">
            ↓ lower is better · ↑ higher is better
          </div>
        </div>
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-ink-800 text-left text-[11px] uppercase tracking-wider text-slate-500">
              <th className="py-2 pr-2 font-medium">Model</th>
              <th className="px-2 py-2 font-medium" title="Gold = escalate but the model cleared it. The dangerous miss.">
                False clears ↓
              </th>
              <th className="px-2 py-2 font-medium" title="Cited an evidence tag that does not exist in the case.">
                Fabricated cites ↓
              </th>
              <th className="px-2 py-2 font-medium" title="When it makes a hard call with citations, they are real AND relevant.">
                Grounding ↑
              </th>
              <th className="px-2 py-2 font-medium" title="Gold = clear but the model escalated it. Cost / noise.">
                Over-escalation ↓
              </th>
              <th className="px-2 py-2 font-medium" title="Correctly sent the genuinely ambiguous cases to human REVIEW instead of guessing.">
                Abstains when unsure ↑
              </th>
            </tr>
          </thead>
          <tbody>
            {models.map((m) => (
              <tr key={m.model} className="border-b border-ink-800/60 last:border-0">
                <td className="py-3 pr-2">
                  <div className="font-medium text-slate-100">{m.label}</div>
                </td>
                <Cell v={m.false_clear_rate} tone={toneLow(m.false_clear_rate)} strong />
                <Cell v={m.hallucinated_citation_rate} tone={toneLow(m.hallucinated_citation_rate)} />
                <Cell v={m.faithfulness} tone={toneHigh(m.faithfulness)} />
                <Cell v={m.over_escalation_rate} tone={toneLow(m.over_escalation_rate)} />
                <Cell v={m.abstention_accuracy} tone={toneHigh(m.abstention_accuracy)} />
              </tr>
            ))}
          </tbody>
        </table>
        <p className="max-w-3xl text-[11px] leading-relaxed text-slate-500">
          A 90%-accurate autopilot that quietly clears real laundering is worse than
          useless — the reframe is that <span className="text-slate-300">the safety
          columns, not the accuracy column, decide whether you can remove the human</span>.
          That is exactly the trust layer a services-as-software company has to build
          before it can sell the outcome.
        </p>
      </div>

      {misses.length > 0 && (
        <div className="card space-y-2 p-4">
          <div className="text-xs font-medium uppercase tracking-wider text-slate-500">
            Sample missed escalations (cases a model waved through)
          </div>
          <div className="flex flex-wrap gap-2">
            {misses.slice(0, 8).map((f) => (
              <span
                key={f.id}
                className="chip border-accent-red/40 bg-accent-red/10 text-accent-red"
                title={`${f.label} cleared ${f.id} (${f.category}), which is gold-labelled escalate`}
              >
                {f.id} · {f.category}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="card space-y-4 p-4">
        <div className="text-xs font-medium uppercase tracking-wider text-slate-500">
          Decision accuracy by alert type
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

function Cell({
  v,
  tone,
  strong,
}: {
  v: number | null;
  tone: string;
  strong?: boolean;
}) {
  return (
    <td className="px-2 py-3">
      <span className={`stat-num ${tone} ${strong ? "font-semibold" : ""}`}>
        {pct(v, 1)}
      </span>
    </td>
  );
}
