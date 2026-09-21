import { describe, expect, it, vi } from "vitest";
import type { TimerState } from "./types";
import {
  addDays,
  clockText,
  elapsedSeconds,
  monday,
  percentage,
  studyToday,
} from "./utils";

describe("study calendar boundaries", () => {
  it("uses the configured study timezone across midnight", () => {
    vi.useFakeTimers();
    try {
      vi.setSystemTime(new Date("2026-09-14T17:00:00Z"));
      expect(studyToday("Asia/Shanghai")).toBe("2026-09-15");
      expect(studyToday("UTC")).toBe("2026-09-14");
    } finally {
      vi.useRealTimers();
    }
  });
  it("moves across months, leap days and years without UTC date shifts", () => {
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
    expect(addDays("2024-03-01", -1)).toBe("2024-02-29");
    expect(addDays("2026-03-01", -1)).toBe("2026-02-28");
    expect(monday("2026-09-20")).toBe("2026-09-14");
    expect(monday("2026-09-14")).toBe("2026-09-14");
  });
  it("does not report zero-question practice as a 0% score", () => {
    expect(percentage(0, 0)).toBeNull();
    expect(percentage(16, 20)).toBe(80);
  });
});

describe("persistent focus timing", () => {
  const timer: TimerState = {
    id: "test",
    title: "学习",
    subject_id: "data",
    plan_id: null,
    study_date: "2026-09-15",
    elapsed: 90,
    started_at: 100000,
  };
  it("includes already elapsed time when restored after a refresh", () => {
    expect(elapsedSeconds(timer, 160000)).toBe(150);
    expect(clockText(elapsedSeconds(timer, 160000))).toBe("00:02:30");
  });
  it("does not accumulate paused time or run backwards after a clock adjustment", () => {
    expect(elapsedSeconds({ ...timer, started_at: null }, 200000)).toBe(90);
    expect(elapsedSeconds(timer, 90000)).toBe(90);
  });
  it("caps forgotten timers at 24 hours", () => {
    expect(elapsedSeconds(timer, 100000 + 48 * 3600000)).toBe(86400);
    expect(clockText(86400)).toBe("24:00:00");
  });
});
