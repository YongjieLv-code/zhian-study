import type { TimerState } from "./types";

export const timerKey = (owner: string) => `zhian.focus.v2:${owner}`;
const legacyKey = "zhian.focus.v1";

export function parseTimer(raw: string | null): TimerState | null {
  if (!raw) return null;
  try {
    const data = JSON.parse(raw) as TimerState;
    if (
      typeof data.id !== "string" ||
      typeof data.title !== "string" ||
      typeof data.subject_id !== "string" ||
      typeof data.study_date !== "string" ||
      (data.plan_id !== null && typeof data.plan_id !== "string") ||
      !Number.isFinite(data.elapsed) ||
      data.elapsed < 0 ||
      (data.started_at !== null && !Number.isFinite(data.started_at))
    )
      return null;
    return data;
  } catch {
    return null;
  }
}

export function readTimer(
  storage: Pick<Storage, "getItem" | "setItem" | "removeItem">,
  owner: string,
): TimerState | null {
  const key = timerKey(owner);
  const saved = storage.getItem(key);
  if (saved !== null) return parseTimer(saved);
  if (owner === "local") {
    const legacy = storage.getItem(legacyKey);
    const timer = parseTimer(legacy);
    if (timer && legacy) {
      storage.setItem(key, legacy);
      storage.removeItem(legacyKey);
    }
    return timer;
  }
  return null;
}
