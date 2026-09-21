import { shallowRef } from "vue";
import { storageScope } from "./config";
import type { MiniSession } from "./types";

const key = `zhian.mini.session.v1:${storageScope}`;
export const session = shallowRef<MiniSession | null>(null);
export const sessionStorageError = shallowRef("");
let generation = 0;
const listeners = new Set<
  (previous: MiniSession | null, next: MiniSession | null) => void
>();

export const sessionGeneration = () => generation;
export const onSessionChange = (
  listener: (previous: MiniSession | null, next: MiniSession | null) => void,
) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

export function validSession(value: unknown): value is MiniSession {
  if (!value || typeof value !== "object") return false;
  const candidate = value as MiniSession;
  return (
    candidate.token_type === "Bearer" &&
    typeof candidate.access_token === "string" &&
    candidate.access_token.length >= 32 &&
    candidate.access_token.length <= 256 &&
    typeof candidate.account?.id === "string" &&
    typeof candidate.account?.username === "string" &&
    Number.isFinite(Date.parse(candidate.expires_at)) &&
    Date.parse(candidate.expires_at) > Date.now()
  );
}

export function setSession(value: MiniSession | null) {
  const previous = session.value;
  try {
    if (value) uni.setStorageSync(key, value);
    else uni.removeStorageSync(key);
    sessionStorageError.value = "";
  } catch {
    sessionStorageError.value = "无法保存登录状态，关闭小程序后需要重新登录。";
  }
  const changed =
    previous?.access_token !== value?.access_token ||
    previous?.account.id !== value?.account.id;
  if (changed) generation++;
  session.value = value;
  if (changed) listeners.forEach((listener) => listener(previous, value));
}

export function restoreSession() {
  try {
    const value: unknown = uni.getStorageSync(key);
    setSession(validSession(value) ? value : null);
  } catch {
    setSession(null);
  }
}

let navigating = false;
export function goLogin() {
  const pages = getCurrentPages();
  if (navigating || pages[pages.length - 1]?.route === "pages/login/index")
    return;
  navigating = true;
  uni.reLaunch({
    url: "/pages/login/index",
    complete: () => {
      navigating = false;
    },
  });
}
