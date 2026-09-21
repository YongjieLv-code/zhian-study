import { computed, onBeforeUnmount, ref } from "vue";
import type { TimerState } from "./types";
import { elapsedSeconds } from "./utils";
import { parseTimer, readTimer, timerKey } from "./timerStorage";

export function useTimer() {
  const timer = ref<TimerState | null>(null);
  const timestamp = ref(Date.now());
  const storageAvailable = ref(true);
  let owner: string | null = null;
  function selectWorkspace(value: string | null) {
    if (owner === value) return;
    owner = value;
    timer.value = null;
    timestamp.value = Date.now();
    if (!owner) return;
    try {
      timer.value = readTimer(localStorage, owner);
    } catch {
      storageAvailable.value = false;
    }
  }
  function persist() {
    if (!owner) return;
    try {
      if (timer.value)
        localStorage.setItem(timerKey(owner), JSON.stringify(timer.value));
      else localStorage.removeItem(timerKey(owner));
    } catch {
      storageAvailable.value = false;
    }
  }
  const elapsed = computed(() => elapsedSeconds(timer.value, timestamp.value));
  function start(
    data: Pick<TimerState, "title" | "subject_id" | "plan_id" | "study_date">,
  ) {
    if (!owner) return;
    timer.value = {
      ...data,
      id: crypto.randomUUID(),
      elapsed: 0,
      started_at: Date.now(),
    };
    timestamp.value = Date.now();
    persist();
  }
  function pause() {
    if (!timer.value) return;
    timer.value = {
      ...timer.value,
      elapsed: elapsedSeconds(timer.value, Date.now()),
      started_at: null,
    };
    timestamp.value = Date.now();
    persist();
  }
  function resume() {
    if (!timer.value || timer.value.started_at !== null) return;
    timer.value = { ...timer.value, started_at: Date.now() };
    timestamp.value = Date.now();
    persist();
  }
  function reset() {
    timer.value = null;
    persist();
  }
  function sync(event: StorageEvent) {
    if (owner && event.key === timerKey(owner))
      timer.value = parseTimer(event.newValue);
  }
  const interval = window.setInterval(() => {
    timestamp.value = Date.now();
    if (timer.value?.started_at !== null && elapsed.value >= 86400) pause();
  }, 1000);
  window.addEventListener("storage", sync);
  onBeforeUnmount(() => {
    clearInterval(interval);
    window.removeEventListener("storage", sync);
  });
  return {
    timer,
    elapsed,
    storageAvailable,
    start,
    pause,
    resume,
    reset,
    selectWorkspace,
  };
}
