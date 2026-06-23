// Types mirroring public/data/latest.json and history.jsonl, produced by the
// Python eval engine (eval/run_eval.py).

export type CI = [point: number, lo: number, hi: number];

export interface ModelInfo {
  id: string;
  label: string;
  family: string;
  tier: string;
  weights: string;
}

export interface Drift {
  delta: number | null;
  flag: boolean;
  direction: "up" | "down" | "flat" | "none";
  ci_disjoint?: boolean;
  reason?: string;
}

export interface CapModel {
  model: string;
  label: string;
  family: string;
  n: number;
  correct: number;
  accuracy: number;
  ci95: CI;
  by_category: Record<string, number>;
  drift: Drift;
}

export interface RobModel {
  model: string;
  label: string;
  family: string;
  n: number;
  defended: number;
  defense_rate: number;
  ci95: CI;
  by_category: Record<string, number>;
  sample_breaches: { id: string; category: string }[];
  drift: Drift;
}

export interface JudgeModel {
  model: string;
  label: string;
  family: string;
  n: number;
  agreement_with_human: number;
  agreement_ci95: CI;
  position_bias: { flip_rate: number; position_1_rate: number | null; flips: number };
  verbosity_bias: { pick_longer_rate: number | null; bias: number | null };
}

export interface InterRater {
  fleiss_kappa: number | null;
  pairwise: { a: string; b: string; cohen_kappa: number | null }[];
  note?: string;
}

export interface Snapshot {
  schema_version: number;
  status: "ok" | "awaiting_first_run";
  mock: boolean;
  generated_at: string;
  run_id: string;
  date: string;
  git_sha: string;
  git_repo: string;
  provider: string;
  models: ModelInfo[];
  duration_sec: number;
  totals: { api_calls: number; prompt_tokens: number; completion_tokens: number };
  tracks: {
    capability?: { n_items: number; categories: string[]; per_model: CapModel[] };
    robustness?: { n_attacks: number; categories: string[]; per_model: RobModel[] };
    judge?: {
      n_items: number;
      human_labels: number;
      judges: string[];
      per_judge: JudgeModel[];
      inter_rater: InterRater;
      balance_note: string;
    };
  };
}

export interface HistoryRecord {
  run_id: string;
  date: string;
  generated_at: string;
  git_sha: string;
  mock: boolean;
  capability?: Record<string, { accuracy: number; ci95: number[] }>;
  robustness?: Record<string, { defense_rate: number; ci95: number[] }>;
  judge?: Record<string, { agreement: number; flip_rate: number; verbosity_bias: number }>;
  judge_fleiss_kappa?: number | null;
}
