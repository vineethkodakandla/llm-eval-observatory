import type { Snapshot } from "../lib/types";
import { relativeTime, repoLinks, shortSha } from "../lib/format";

export default function Header({ snap }: { snap: Snapshot }) {
  const links = repoLinks(snap.git_repo, snap.git_sha);
  const live = snap.status === "ok";
  const dot = !live
    ? "bg-slate-500"
    : snap.mock
      ? "bg-accent-amber"
      : "bg-accent-green";

  return (
    <header className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-widest text-accent-cyan/80">
            <span className="h-1.5 w-1.5 rounded-full bg-accent-cyan" />
            Open-source LLM measurement · Groq free tier
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
            LLM Eval Observatory
          </h1>
          <p className="max-w-2xl text-sm leading-relaxed text-slate-400">
            A living dashboard that measures open-source models every night —
            capability drift, prompt-injection robustness, and LLM-as-judge bias.
            Every number is computed by a scheduled GitHub Action and committed to
            this repo, not hand-typed. The data below is the evidence.
          </p>
        </div>
        {links.badge && (
          <a href={links.actions ?? "#"} target="_blank" rel="noreferrer"
             className="shrink-0">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={links.badge} alt="nightly eval status" className="h-5" />
          </a>
        )}
      </div>

      {snap.mock && (
        <div className="card border-accent-amber/40 bg-accent-amber/5 px-4 py-3 text-sm text-amber-200">
          <span className="font-semibold">Demo data.</span> This snapshot was
          generated in <code className="font-mono">--mock</code> mode with
          synthetic responses — it exercises the full pipeline and charts but is{" "}
          <span className="font-semibold">not a real model run</span>. The nightly
          Action (or a live run with a Groq key) replaces it with real numbers.
        </div>
      )}

      <div className="card flex flex-wrap items-center gap-x-6 gap-y-3 px-5 py-3 text-sm">
        <Field label="Status">
          <span className="inline-flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${dot}`} />
            {live ? (snap.mock ? "demo run" : "live") : "awaiting first run"}
          </span>
        </Field>
        <Field label="Last run">
          {snap.generated_at ? (
            <span title={`${snap.generated_at} (UTC)`} className="stat-num">
              {relativeTime(snap.generated_at)}
            </span>
          ) : (
            "—"
          )}
        </Field>
        <Field label="Commit">
          {links.commit ? (
            <a href={links.commit} target="_blank" rel="noreferrer"
               className="stat-num text-accent-cyan hover:underline">
              {shortSha(snap.git_sha)}
            </a>
          ) : (
            <span className="stat-num text-slate-400">{shortSha(snap.git_sha)}</span>
          )}
        </Field>
        <Field label="Models">
          <span className="stat-num">{snap.models.length}</span>
        </Field>
        <Field label="API calls">
          <span className="stat-num">{snap.totals.api_calls.toLocaleString()}</span>
        </Field>
        <Field label="Duration">
          <span className="stat-num">{snap.duration_sec}s</span>
        </Field>
        <a
          href="/data/latest.json"
          target="_blank"
          rel="noreferrer"
          className="ml-auto chip border-ink-600 text-slate-300 hover:border-accent-cyan hover:text-accent-cyan"
        >
          raw JSON ↗
        </a>
      </div>
    </header>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col">
      <span className="text-[10px] uppercase tracking-wider text-slate-500">
        {label}
      </span>
      <span className="text-slate-200">{children}</span>
    </div>
  );
}
