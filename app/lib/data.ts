import { promises as fs } from "fs";
import path from "path";
import type { HistoryRecord, Snapshot } from "./types";

const DATA_DIR = path.join(process.cwd(), "public", "data");

const EMPTY: Snapshot = {
  schema_version: 1,
  status: "awaiting_first_run",
  mock: false,
  generated_at: "",
  run_id: "",
  date: "",
  git_sha: "",
  git_repo: process.env.NEXT_PUBLIC_REPO ?? "",
  provider: "groq",
  models: [],
  duration_sec: 0,
  totals: { api_calls: 0, prompt_tokens: 0, completion_tokens: 0 },
  tracks: {},
};

export async function getSnapshot(): Promise<Snapshot> {
  try {
    const raw = await fs.readFile(path.join(DATA_DIR, "latest.json"), "utf-8");
    const parsed = JSON.parse(raw) as Snapshot;
    if (!parsed.status) parsed.status = "ok";
    return parsed;
  } catch {
    return EMPTY;
  }
}

export async function getHistory(): Promise<HistoryRecord[]> {
  try {
    const raw = await fs.readFile(path.join(DATA_DIR, "history.jsonl"), "utf-8");
    return raw
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean)
      .map((l) => JSON.parse(l) as HistoryRecord);
  } catch {
    return [];
  }
}

/** Build a per-model time series for one metric from the run history. */
export function seriesFor(
  history: HistoryRecord[],
  track: "autopilot" | "capability" | "robustness" | "judge",
  metric: string,
  mock: boolean
): { x: string[]; series: Record<string, (number | null)[]> } {
  const rows = history.filter((h) => h.mock === mock && h[track]);
  const x = rows.map((r) => r.date);
  const models = new Set<string>();
  rows.forEach((r) => Object.keys(r[track] ?? {}).forEach((m) => models.add(m)));

  const series: Record<string, (number | null)[]> = {};
  for (const m of models) {
    series[m] = rows.map((r) => {
      const cell = (r[track] as Record<string, Record<string, number>> | undefined)?.[m];
      const v = cell?.[metric];
      return typeof v === "number" ? v : null;
    });
  }
  return { x, series };
}
