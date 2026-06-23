export default function EmptyState() {
  return (
    <div className="card space-y-4 p-8">
      <h2 className="text-lg font-bold text-white">No runs yet</h2>
      <p className="max-w-2xl text-sm leading-relaxed text-slate-400">
        The eval engine hasn&apos;t produced a snapshot. Generate one — every number
        on this dashboard comes from a real run, so there are no placeholder
        figures here by design.
      </p>
      <div className="space-y-3">
        <Step n={1} text="Get a free Groq API key">
          <a href="https://console.groq.com/keys" target="_blank" rel="noreferrer"
             className="text-accent-cyan hover:underline">
            console.groq.com/keys
          </a>
        </Step>
        <Step n={2} text="Run the suite (about 5 minutes, free)">
          <code className="block rounded bg-ink-850 px-3 py-2 font-mono text-xs text-slate-300">
            pip install -r eval/requirements.txt
            <br />
            GROQ_API_KEY=… python eval/run_eval.py
          </code>
        </Step>
        <Step n={3} text="Or preview the UI with synthetic data">
          <code className="block rounded bg-ink-850 px-3 py-2 font-mono text-xs text-slate-300">
            python eval/run_eval.py --mock
          </code>
        </Step>
        <Step n={4} text="Push — the nightly Action takes over from there" />
      </div>
    </div>
  );
}

function Step({ n, text, children }: { n: number; text: string; children?: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-ink-600 text-xs font-bold text-accent-cyan">
        {n}
      </span>
      <div className="space-y-1.5">
        <div className="text-sm text-slate-200">{text}</div>
        {children}
      </div>
    </div>
  );
}
