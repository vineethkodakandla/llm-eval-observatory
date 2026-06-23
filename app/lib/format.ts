// Small pure formatting helpers shared by server and client components.

export const pct = (x: number | null | undefined, digits = 0): string =>
  x === null || x === undefined ? "—" : `${(x * 100).toFixed(digits)}%`;

export const signed = (x: number | null | undefined, digits = 2): string =>
  x === null || x === undefined ? "—" : `${x >= 0 ? "+" : ""}${x.toFixed(digits)}`;

// A stable, readable palette keyed by model index.
const PALETTE = ["#22d3ee", "#a78bfa", "#34d399", "#fbbf24", "#f87171", "#60a5fa"];
export const colorFor = (i: number): string => PALETTE[i % PALETTE.length];

export function relativeTime(iso: string, now = new Date()): string {
  if (!iso) return "never";
  const then = new Date(iso).getTime();
  const s = Math.max(0, Math.round((now.getTime() - then) / 1000));
  if (s < 90) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 90) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 36) return `${h}h ago`;
  const d = Math.round(h / 24);
  return `${d}d ago`;
}

// Landis & Koch interpretation bands for kappa — labelled so a reader (and an
// interviewer) sees what the number means without looking it up.
export function kappaLabel(k: number | null | undefined): string {
  if (k === null || k === undefined) return "n/a";
  if (k < 0) return "worse than chance";
  if (k < 0.2) return "slight";
  if (k < 0.4) return "fair";
  if (k < 0.6) return "moderate";
  if (k < 0.8) return "substantial";
  return "almost perfect";
}

export interface RepoLinks {
  repo: string | null;
  commit: string | null;
  actions: string | null;
  badge: string | null;
}

export function repoLinks(gitRepo: string, gitSha: string): RepoLinks {
  const isReal = gitRepo && !gitRepo.startsWith("local/") && gitRepo.includes("/");
  if (!isReal) return { repo: null, commit: null, actions: null, badge: null };
  const base = `https://github.com/${gitRepo}`;
  return {
    repo: base,
    commit: gitSha && gitSha !== "local" ? `${base}/commit/${gitSha}` : base,
    actions: `${base}/actions/workflows/nightly-eval.yml`,
    badge: `${base}/actions/workflows/nightly-eval.yml/badge.svg`,
  };
}

export const shortSha = (sha: string): string =>
  sha && sha !== "local" ? sha.slice(0, 7) : "local";
