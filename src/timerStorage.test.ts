import { describe, expect, it } from "vitest";
import { readTimer, timerKey } from "./timerStorage";

function memoryStorage() {
  const data = new Map<string, string>();
  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => {
      data.set(key, value);
    },
    removeItem: (key: string) => {
      data.delete(key);
    },
  };
}
const timer = {
  id: "test",
  title: "资料分析",
  subject_id: "data",
  study_date: "2026-09-15",
  plan_id: null,
  elapsed: 60,
  started_at: null,
};

describe("account-scoped focus recovery", () => {
  it("migrates an existing timer only into the local workspace", () => {
    const storage = memoryStorage();
    storage.setItem("zhian.focus.v1", JSON.stringify(timer));
    expect(readTimer(storage, "bob")).toBeNull();
    expect(readTimer(storage, "local")).toEqual(timer);
    expect(storage.getItem("zhian.focus.v1")).toBeNull();
    expect(readTimer(storage, "local")).toEqual(timer);
  });
  it("switching accounts cannot expose or overwrite another timer", () => {
    const storage = memoryStorage();
    storage.setItem(timerKey("alice"), JSON.stringify(timer));
    expect(readTimer(storage, "bob")).toBeNull();
    storage.setItem(
      timerKey("bob"),
      JSON.stringify({ ...timer, title: "申论" }),
    );
    expect(readTimer(storage, "alice")?.title).toBe("资料分析");
    expect(readTimer(storage, "bob")?.title).toBe("申论");
  });
  it("discards malformed timer state instead of showing stale content", () => {
    const storage = memoryStorage();
    storage.setItem(
      timerKey("alice"),
      JSON.stringify({ ...timer, elapsed: -1 }),
    );
    expect(readTimer(storage, "alice")).toBeNull();
    storage.setItem(timerKey("alice"), "invalid json");
    expect(readTimer(storage, "alice")).toBeNull();
  });
});
