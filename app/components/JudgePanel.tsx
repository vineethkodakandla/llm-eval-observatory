import type { HistoryRecord, JudgeModel, Snapshot } from "../lib/types";
import { colorFor, kappaLabel, pct, signed } from "../lib/format";
import { seriesFor } from "../lib/data";
import { Meter, Rank, Section } from "./ui";
import TrendChart from "./charts/TrendChart";

export default function JudgePanel({
  track,
  history,
  mock,
}: {
  track: NonNullable<Snapshot["tracks"]["judge"]>;
  history: HistoryRecord[];
  mock: boolean;
}) {
  const judges = track.per_judge;
  const colors: Record<string, string> = {};
  const labels: Record<string, string> = {};
  judges.forEach((m, i) => {
    colors[m.model] = colorFor(i);
    labels[m.model] = m.label;
  });
  const { x, series } = seriesFor(history, "judge", "agreement", mock);
  const fk = track.inter_rater.fleiss_kappa;

  return (
    <Section
      id="judge"
      eyebrow="Track 3"
      title="LLM-as-judge bias & reliability"
      blurb={`Judges are themselves unreliable, so this track quantifies how. Each model judges ${track.n_items} pairwise items against held-out human labels, in both presentation orders. We measure agreement with the human, position bias (how often the verdict flips when we swap order — an unbiased judge never flips), and verbosity bias (tendency to pick the longer answer; the set is length-balanced so 0 is neutral).`}
    >
      <div className="grid gap-4 lg:grid-cols-5">
        <div className="card overflow-hidden lg:col-span-3">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-ink-700 text-left text-[11px] uppercase tracking-wider text-slate-500">
                <th className="px-4 py-2.5 font-medium">#</th>
                <th className="px-2 py-2.5 font-medium">Judge</th>
                <th className="px-2 py-2.5 font-medium">Agree w/ human</th>
                <th className="px-2 py-2.5 text-right font-medium" title="Lower is better — verdict flips when order is swapped">
                  Order flip
                </th>
                <th className="px-4 py-2.5 text-right font-medium" title="Tendency to pick the longer answer; 0 is neutral">
                  Verbosity
                </th>
              </tr>
            </thead>
            <tbody>
              {judges.map((m, i) => (
                <Row key={m.model} m={m} i={i} color={colors[m.model]} />
              ))}
            </tbody>
          </table>
        </div>

        <div className="card space-y-2 p-4 lg:col-span-2">
          <div className="text-xs font-medium uppercase tracking-wider text-slate-500">
            Agreement with human over time
          </div>
          <TrendChart x={x} series={series} labels={labels} colors={colors} />
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-5">
        <div className="card flex flex-col justify-center gap-1 p-5 md:col-span-2">
          <div className="text-xs font-medium uppercase tracking-wider text-slate-500">
            Inter-rater agreement
          </div>
          <div className="flex items-baseline gap-3">
            <span className="stat-num text-4xl font-bold text-white">
              {fk === null ? "—" : fk.toFixed(2)}
            </span>
            <span className="text-sm text-slate-400">Fleiss&apos; κ · {kappaLabel(fk)}</span>
          </div>
          <p className="text-xs leading-relaxed text-slate-500">
            How much the judges agree with each other beyond chance. Low κ means
            &quot;which model is right?&quot; depends a lot on which judge you ask —
            the core reason a single LLM judge can&apos;t be trusted blindly.
          </p>
        </div>

        <div className="card space-y-2 p-5 md:col-span-3">
          <div className="text-xs font-medium uppercase tracking-wider text-slate-500">
            Pairwise judge agreement (Cohen&apos;s κ)
          </div>
          <div className="flex flex-wrap gap-2">
            {track.inter_rater.pairwise.map((p) => (
              <span key={`${p.a}-${p.b}`} className="chip text-slate-300">
                {labels[p.a] ?? p.a} ↔ {labels[p.b] ?? p.b}:
                <span className="stat-num ml-1 text-slate-100">
                  {p.cohen_kappa === null ? "—" : p.cohen_kappa.toFixed(2)}
                </span>
              </span>
            ))}
          </div>
          <p className="text-xs leading-relaxed text-slate-500">{track.balance_note}</p>
        </div>
      </div>
    </Section>
  );
}

function Row({ m, i, color }: { m: JudgeModel; i: number; color: string }) {
  const flip = m.position_bias.flip_rate;
  const verb = m.verbosity_bias.bias ?? 0;
  const flipTone =
    flip <= 0.1 ? "text-accent-green" : flip <= 0.3 ? "text-amber-300" : "text-accent-red";
  const verbTone = Math.abs(verb) <= 0.05 ? "text-slate-300" : "text-amber-300";
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
          <div className="w-28">
            <Meter ci={m.agreement_ci95} color={color} />
          </div>
          <span className="stat-num text-slate-100">{pct(m.agreement_with_human, 1)}</span>
        </div>
      </td>
      <td className="px-2 py-3 text-right">
        <span className={`stat-num ${flipTone}`} title={`primacy: picks Response 1 ${pct(m.position_bias.position_1_rate)} of the time`}>
          {pct(flip)}
        </span>
      </td>
      <td className="px-4 py-3 text-right">
        <span className={`stat-num ${verbTone}`} title="positive = favors longer answers">
          {signed(verb)}
        </span>
      </td>
    </tr>
  );
}
