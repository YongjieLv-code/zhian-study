import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { MiniSession } from "./types";

vi.mock("./config", () => ({
  storageScope: "test-server",
  requestOrigin: "https://study.example.com",
  isWeChat: true,
}));
vi.mock("@dcloudio/uni-app", () => ({
  onShow: vi.fn(),
  onPullDownRefresh: vi.fn(),
}));

const login = (owner: string): MiniSession => ({
  account: { id: owner, username: owner },
  access_token: owner.repeat(48),
  token_type: "Bearer",
  expires_at: "2099-10-01T00:00:00Z",
  wechat_bound: false,
});
let calls: UniApp.RequestOptions[];
function answer(
  index: number,
  statusCode: number,
  data: unknown,
  header: Record<string, string> = {},
) {
  calls[index].success?.({
    statusCode,
    data: data as UniApp.RequestSuccessCallbackResult["data"],
    header,
    cookies: [],
    errMsg: "request:ok",
  });
}
beforeEach(() => {
  vi.resetModules();
  calls = [];
  vi.stubGlobal("getCurrentPages", () => []);
  vi.stubGlobal("uni", {
    getStorageSync: vi.fn(),
    setStorageSync: vi.fn(),
    removeStorageSync: vi.fn(),
    request: vi.fn((options: UniApp.RequestOptions) => calls.push(options)),
    reLaunch: vi.fn((options) => options.complete?.()),
    stopPullDownRefresh: vi.fn(),
  });
});
afterEach(() => vi.unstubAllGlobals());

describe("mobile request identity", () => {
  it("sends an explicit bearer token and account guard for learning writes", async () => {
    const auth = await import("./session");
    const { request } = await import("./api");
    auth.setSession(login("alice"));
    const body = { id: "retry-safe-record", title: "学习记录" };
    const result = request("/logs", "POST", body);
    expect(calls[0]).toMatchObject({
      url: "https://study.example.com/api/logs",
      method: "POST",
      timeout: 15000,
      data: body,
      header: {
        Authorization: `Bearer ${login("alice").access_token}`,
        "X-Workspace-ID": "alice",
      },
    });
    expect(calls[0].header).not.toHaveProperty("X-CSRF-Token");
    answer(0, 201, body);
    await expect(result).resolves.toEqual(body);
  });

  it("does not display a delayed result from a previous account", async () => {
    const auth = await import("./session");
    const { request } = await import("./api");
    auth.setSession(login("alice"));
    const pending = request("/workspace");
    auth.setSession(login("bob"));
    answer(0, 200, { private_data: "alice" });
    await expect(pending).rejects.toMatchObject({ status: 409 });
    expect(auth.session.value?.account.id).toBe("bob");
  });

  it("does not log out the new account when an old request returns 401", async () => {
    const auth = await import("./session");
    const { request } = await import("./api");
    auth.setSession(login("alice"));
    const pending = request("/overview");
    auth.setSession(login("bob"));
    answer(0, 401, { detail: "expired" });
    await expect(pending).rejects.toMatchObject({ status: 409 });
    expect(auth.session.value?.account.id).toBe("bob");
    expect(uni.reLaunch).not.toHaveBeenCalled();
  });

  it("clears expired credentials, but retains the login on a network failure", async () => {
    const auth = await import("./session");
    const { request } = await import("./api");
    auth.setSession(login("alice"));
    const offline = request("/logs", "POST", { id: "unchanged-retry-id" });
    calls[0].fail?.({ errMsg: "request:fail timeout" });
    await expect(offline).rejects.toMatchObject({ status: 0 });
    expect(auth.session.value?.account.id).toBe("alice");
    const expired = request("/overview");
    answer(1, 401, { detail: "请重新登录" });
    await expect(expired).rejects.toMatchObject({ status: 401 });
    expect(auth.session.value).toBeNull();
    expect(uni.reLaunch).toHaveBeenCalledOnce();
  });

  it("never attaches a stored token to password or WeChat sign-in requests", async () => {
    const auth = await import("./session");
    const { api } = await import("./api");
    auth.setSession(login("alice"));
    const pending = api.bind({
      binding_token: "temporary-proof",
      username: "alice",
      password: "wrong",
    });
    expect(calls[0].header).not.toHaveProperty("Authorization");
    answer(0, 401, { detail: "用户名或密码不正确" });
    await expect(pending).rejects.toMatchObject({ status: 401 });
    expect(auth.session.value?.account.id).toBe("alice");
  });

  it("clears cached learning data immediately on account change and ignores the old refresh", async () => {
    const auth = await import("./session");
    const data = await import("./workspace");
    auth.setSession(login("alice"));
    const first = data.refreshWorkspace();
    answer(0, 200, {
      auth: { account: { id: "alice" } },
      logs: [{ title: "Alice 的记录" }],
    });
    expect(await first).toBe(true);
    expect(data.workspace.value?.logs[0].title).toBe("Alice 的记录");
    const delayed = data.refreshWorkspace();
    auth.setSession(login("bob"));
    expect(data.workspace.value).toBeNull();
    const current = data.refreshWorkspace();
    answer(1, 200, {
      auth: { account: { id: "alice" } },
      logs: [{ title: "旧记录" }],
    });
    expect(await delayed).toBe(false);
    expect(data.workspace.value).toBeNull();
    answer(2, 200, { auth: { account: { id: "bob" } }, logs: [] });
    expect(await current).toBe(true);
    expect(data.workspace.value?.auth.account?.id).toBe("bob");
  });
});
