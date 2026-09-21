import { computed, shallowRef } from "vue";
import { onPullDownRefresh, onShow } from "@dcloudio/uni-app";
import { api } from "./api";
import {
  goLogin,
  onSessionChange,
  session,
  sessionGeneration,
} from "./session";
import type { Subject, Workspace } from "./types";
import { errorText, fallbackToday } from "./utils";

export const workspace = shallowRef<Workspace | null>(null);
export const loading = shallowRef(false);
export const syncError = shallowRef("");
export const lastSynced = shallowRef<number | null>(null);
export const studyDate = computed(
  () => workspace.value?.overview.date || fallbackToday(),
);
export const subjects = computed(() => workspace.value?.subjects || []);
let pending: Promise<boolean> | null = null;

onSessionChange(() => {
  workspace.value = null;
  syncError.value = "";
  lastSynced.value = null;
  loading.value = false;
  pending = null;
});

export function refreshWorkspace(): Promise<boolean> {
  if (!session.value) return Promise.resolve(false);
  if (pending) return pending;
  const generation = sessionGeneration();
  loading.value = true;
  const task = (async () => {
    try {
      const result = await api.workspace();
      if (
        generation !== sessionGeneration() ||
        result.auth.account?.id !== session.value?.account.id
      )
        return false;
      workspace.value = result;
      lastSynced.value = Date.now();
      syncError.value = "";
      return true;
    } catch (error) {
      if (generation === sessionGeneration())
        syncError.value = errorText(error);
      return false;
    } finally {
      if (generation === sessionGeneration()) {
        loading.value = false;
        pending = null;
      }
    }
  })();
  pending = task;
  return task;
}

export function useWorkspacePage() {
  onShow(() => {
    if (!session.value) goLogin();
    else void refreshWorkspace();
  });
  onPullDownRefresh(async () => {
    try {
      await refreshWorkspace();
    } finally {
      uni.stopPullDownRefresh();
    }
  });
}

export function subjectFor(id: string): Subject | undefined {
  return subjects.value.find((subject) => subject.id === id);
}
