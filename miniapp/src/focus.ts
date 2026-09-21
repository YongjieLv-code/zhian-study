import { computed, shallowRef } from "vue";
import { storageScope } from "./config";
import { onSessionChange, session } from "./session";
import type { TimerState } from "./types";
import { createId } from "./utils";

export const focus = shallowRef<TimerState | null>(null);
export const clockNow = shallowRef(Date.now());
export const focusStorageError = shallowRef("");
const key = (owner: string) => `zhian.mini.focus.v1:${storageScope}:${owner}`;

export function elapsedSeconds(
  timer: TimerState | null,
  at = Date.now(),
): number {
  if (!timer) return 0;
  const running =
    timer.started_at === null ? 0 : Math.max(0, (at - timer.started_at) / 1000);
  return Math.min(86400, Math.floor(timer.elapsed + running));
}

export const focusElapsed = computed(() =>
  elapsedSeconds(focus.value, clockNow.value),
);

export function parseFocus(value: unknown): TimerState | null {
  if (!value || typeof value !== "object") return null;
  const candidate = value as TimerState;
  if (
    typeof candidate.id !== "string" ||
    !/^[0-9a-f-]{36}$/i.test(candidate.id) ||
    typeof candidate.title !== "string" ||
    typeof candidate.subject_id !== "string" ||
    !/^\d{4}-\d{2}-\d{2}$/.test(candidate.study_date) ||
    (candidate.plan_id !== null && typeof candidate.plan_id !== "string") ||
    !Number.isFinite(candidate.elapsed) ||
    candidate.elapsed < 0 ||
    candidate.elapsed > 86400 ||
    (candidate.started_at !== null &&
      (!Number.isFinite(candidate.started_at) || candidate.started_at < 0))
  )
    return null;
  return candidate;
}

function persistFor(owner: string, value: TimerState | null) {
  try {
    if (value) uni.setStorageSync(key(owner), value);
    else uni.removeStorageSync(key(owner));
    focusStorageError.value = "";
  } catch {
    focusStorageError.value = "手机暂时无法保存计时状态，请及时保存学习记录。";
  }
}

export function persistFocus() {
  if (session.value) persistFor(session.value.account.id, focus.value);
}

onSessionChange((previous, next) => {
  if (previous?.account.id === next?.account.id) return;
  if (previous && focus.value)
    persistFor(previous.account.id, {
      ...focus.value,
      elapsed: elapsedSeconds(focus.value),
      started_at: null,
    });
  focus.value = null;
  if (next) {
    try {
      focus.value = parseFocus(uni.getStorageSync(key(next.account.id)));
    } catch {
      focusStorageError.value = "暂时无法读取未保存的计时，请核对学习记录。";
    }
  }
  tickFocus();
});

export function tickFocus() {
  clockNow.value = Date.now();
  if (focus.value?.started_at !== null && focusElapsed.value >= 86400)
    pauseFocus();
}

export function startFocus(
  data: Pick<TimerState, "title" | "subject_id" | "plan_id" | "study_date">,
) {
  if (!session.value || focus.value) return;
  focus.value = { ...data, id: createId(), elapsed: 0, started_at: Date.now() };
  tickFocus();
  persistFocus();
}

export function pauseFocus() {
  if (!focus.value) return;
  focus.value = {
    ...focus.value,
    elapsed: elapsedSeconds(focus.value),
    started_at: null,
  };
  clockNow.value = Date.now();
  persistFocus();
}

export function resumeFocus() {
  if (
    !focus.value ||
    focus.value.started_at !== null ||
    focus.value.elapsed >= 86400
  )
    return;
  focus.value = { ...focus.value, started_at: Date.now() };
  tickFocus();
  persistFocus();
}

export function clearFocus() {
  focus.value = null;
  persistFocus();
}
