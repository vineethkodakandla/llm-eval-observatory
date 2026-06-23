import Header from "./components/Header";
import EmptyState from "./components/EmptyState";
import CapabilityPanel from "./components/CapabilityPanel";
import RobustnessPanel from "./components/RobustnessPanel";
import JudgePanel from "./components/JudgePanel";
import { getHistory, getSnapshot } from "./lib/data";

// Re-render hourly. In practice each nightly Action commit triggers a fresh
// Vercel deploy, so the page is rebuilt with new data on every run; this just
// bounds staleness if a deploy is skipped.
export const revalidate = 3600;

export default async function Page() {
  const snap = await getSnapshot();
  const history = await getHistory();
  const empty = snap.status === "awaiting_first_run";

  return (
    <main className="mx-auto max-w-6xl space-y-10 px-4 py-8 sm:px-6 sm:py-12">
      <Header snap={snap} />

      {empty ? (
        <EmptyState />
      ) : (
        <div className="space-y-12">
          {snap.tracks.capability && (
            <CapabilityPanel track={snap.tracks.capability} history={history} mock={snap.mock} />
          )}
          {snap.tracks.robustness && (
            <RobustnessPanel track={snap.tracks.robustness} history={history} mock={snap.mock} />
          )}
          {snap.tracks.judge && (
            <JudgePanel track={snap.tracks.judge} history={history} mock={snap.mock} />
          )}
        </div>
      )}

      <Footer
        models={snap.models}
        runs={history.length}
        repo={snap.git_repo}
        provider={snap.provider}
      />
    </main>
  );
}

function Footer({
  models,
  runs,
  repo,
  provider,
}: {
  models: { id: string; label: string; family: string; weights: string; tier: string }[];
  runs: number;
  repo: string;
  provider: string;
}) {
  return (
    <footer className="space-y-6 border-t border-ink-800 pt-8 text-sm text-slate-400">
      <div className="grid gap-6 md:grid-cols-3">
        <div className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            How it works
          </h3>
          <p className="text-xs leading-relaxed">
            A scheduled GitHub Action runs the eval suite nightly against {provider}&apos;s
            free tier, computes the statistics, and commits the results JSON to this repo.
            This site reads that file — so the dashboard is the artifact, not a screenshot
            of one. {runs > 0 && <>It has captured <span className="stat-num text-slate-300">{runs}</span> run{runs === 1 ? "" : "s"} so far.</>}
          </p>
        </div>
        <div className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Models (all open weights)
          </h3>
          <ul className="space-y-1 text-xs">
            {models.map((m) => (
              <li key={m.id} className="flex items-center justify-between gap-2">
                <span className="text-slate-300">{m.label}</span>
                <span className="text-slate-600">
                  {m.family} · {m.tier}
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Honesty notes
          </h3>
          <ul className="list-disc space-y-1 pl-4 text-xs leading-relaxed">
            <li>All grading is deterministic except the judge track, whose reliability we measure explicitly.</li>
            <li>CIs are 5,000-sample seeded bootstraps — reproducible from the raw answers.</li>
            <li>Human judge labels are seed labels meant to be reviewed and owned.</li>
          </ul>
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-600">
        <span>LLM Eval Observatory · built by Vineeth Kodakandla</span>
        {repo && !repo.startsWith("local/") && (
          <a
            href={`https://github.com/${repo}`}
            target="_blank"
            rel="noreferrer"
            className="hover:text-accent-cyan"
          >
            {repo} ↗
          </a>
        )}
      </div>
    </footer>
  );
}
