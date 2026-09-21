import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { MiniSession } from "./types";

vi.mock("./config", () => ({
  storageScope: "https%3A%2F%2Fstudy.example.com",
  requestOrigin: "https://study.example.com",
  isWeChat: true,
}));

const login = (owner: string): MiniSession => ({
  account: { id: owner, username: owner },
  access_token: owner.repeat(48),
  token_type: "Bearer",
  expires_at: "2026-10-01T00:00:00Z",
  wechat_bound: false,
});
let storage: Map<string, unknown>;

beforeEach(() => {
  vi.resetModules();
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-09-16T00:00:00Z"));
  storage = new Map();
  vi.stubGlobal("uni", {
    getStorageSync: vi.fn((key: string) => storage.get(key)),
    setStorageSync: vi.fn((key: string, value: unknown) =>
      storage.set(key, structuredClone(value)),
    ),
    removeStorageSync: vi.fn((key: string) => storage.delete(key)),
  });
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("mobile timer recovery", () => {
  it("recovers elapsed time after the application is suspended, excluding pauses", async () => {
    const timer = await import("./focus");
    const { setSession } = await import("./session");
    setSession(login("alice"));
    timer.startFocus({
      title: "资料分析",
      subject_id: "data",
      plan_id: null,
      study_date: "2026-09-16",
    });
    vi.setSystemTime(new Date("2026-09-16T00:45:00Z"));
    timer.tickFocus();
    expect(timer.focusElapsed.value).toBe(2700);
    timer.pauseFocus();
    vi.setSystemTime(new Date("2026-09-16T01:00:00Z"));
    timer.resumeFocus();
    vi.setSystemTime(new Date("2026-09-16T01:05:00Z"));
    timer.tickFocus();
    expect(timer.focusElapsed.value).toBe(3000);
  });

  it("pauses the outgoing account and never shows its timer to another account", async () => {
    const timer = await import("./focus");
    const { setSession } = await import("./session");
    setSession(login("alice"));
    timer.startFocus({
      title: "Alice 的专注",
      subject_id: "data",
      plan_id: null,
      study_date: "2026-09-16",
    });
    vi.setSystemTime(new Date("2026-09-16T00:25:00Z"));
    setSession(login("bob"));
    expect(timer.focus.value).toBeNull();
    timer.startFocus({
      title: "Bob 的专注",
      subject_id: "math",
      plan_id: null,
      study_date: "2026-09-16",
    });
    vi.setSystemTime(new Date("2026-09-16T00:30:00Z"));
    setSession(null);
    vi.setSystemTime(new Date("2026-09-16T01:00:00Z"));
    setSession(login("alice"));
    expect(timer.focus.value?.title).toBe("Alice 的专注");
    expect(timer.focus.value?.started_at).toBeNull();
    expect(timer.focusElapsed.value).toBe(1500);
    setSession(login("bob"));
    expect(timer.focusElapsed.value).toBe(300);
    expect(
      [...storage.keys()].some((key) =>
        key.includes("https%3A%2F%2Fstudy.example.com:alice"),
      ),
    ).toBe(true);
  });

  it("restores a running timer after process restart and caps it at 24 hours", async () => {
    const timer = await import("./focus");
    const auth = await import("./session");
    auth.setSession(login("alice"));
    timer.startFocus({
      title: "未保存的专注",
      subject_id: "data",
      plan_id: null,
      study_date: "2026-09-16",
    });
    const id = timer.focus.value?.id;
    vi.resetModules();
    vi.setSystemTime(new Date("2026-09-18T00:00:00Z"));
    const restored = await import("./focus");
    const restoredAuth = await import("./session");
    restoredAuth.restoreSession();
    expect(restored.focus.value?.id).toBe(id);
    expect(restored.focusElapsed.value).toBe(86400);
    expect(restored.focus.value?.started_at).toBeNull();
    restored.resumeFocus();
    expect(restored.focus.value?.started_at).toBeNull();
  });

  it("keeps an active timer during same-account token rotation", async () => {
    const timer = await import("./focus");
    const { setSession } = await import("./session");
    setSession(login("alice"));
    timer.startFocus({
      title: "继续学习",
      subject_id: "data",
      plan_id: null,
      study_date: "2026-09-16",
    });
    const id = timer.focus.value?.id;
    setSession({ ...login("alice"), access_token: "rotated-token".repeat(4) });
    expect(timer.focus.value?.id).toBe(id);
    expect(timer.focus.value?.started_at).not.toBeNull();
  });

  it("reports storage failure while keeping the current timer available to save", async () => {
    const timer = await import("./focus");
    const { setSession } = await import("./session");
    setSession(login("alice"));
    vi.mocked(uni.setStorageSync).mockImplementation(() => {
      throw new Error("quota");
    });
    timer.startFocus({
      title: "需要及时保存",
      subject_id: "data",
      plan_id: null,
      study_date: "2026-09-16",
    });
    expect(timer.focus.value?.title).toBe("需要及时保存");
    expect(timer.focusStorageError.value).toContain("无法保存");
    setSession(login("bob"));
    expect(timer.focus.value).toBeNull();
  });
});

describe("stored login validation", () => {
  it("discards expired and malformed stored sessions", async () => {
    const { validSession } = await import("./session");
    expect(validSession(login("alice"))).toBe(true);
    expect(
      validSession({ ...login("alice"), expires_at: "2026-09-15T00:00:00Z" }),
    ).toBe(false);
    expect(validSession({ ...login("alice"), access_token: "short" })).toBe(
      false,
    );
    expect(validSession({ ...login("alice"), account: null })).toBe(false);
  });
});
