import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, request, setSession } from "./api";
import type { AuthStatus } from "./types";

const account = (id: string): AuthStatus => ({
  account: { id, username: id },
  csrf_token: `csrf-${id}`,
  local_mode: false,
  can_register: false,
  first_account: false,
  requires_bootstrap: false,
  registration_open: false,
});
afterEach(() => {
  setSession(null);
  vi.unstubAllGlobals();
});

describe("workspace request isolation", () => {
  it("attaches current workspace and CSRF to a write, while discovery is unscoped", async () => {
    const fetch = vi
      .fn()
      .mockImplementation(() => Promise.resolve(new Response("{}")));
    vi.stubGlobal("fetch", fetch);
    setSession(account("alice"));
    await request("/logs", "POST", { title: "练习" });
    expect(fetch.mock.calls[0]?.[1].headers).toMatchObject({
      "X-Workspace-ID": "alice",
      "X-CSRF-Token": "csrf-alice",
    });
    await request("/workspace");
    expect(fetch.mock.calls[1]?.[1].headers).not.toHaveProperty(
      "X-Workspace-ID",
    );
  });
  it("rejects an old account's pending result after a switch", async () => {
    let resolve!: (response: Response) => void;
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>((done) => {
            resolve = done;
          }),
      ),
    );
    setSession(account("alice"));
    const pending = request("/logs");
    setSession(account("bob"));
    resolve(new Response('[{"title":"Alice private note"}]'));
    await expect(pending).rejects.toMatchObject({ status: 409 });
  });
  it("clears the workspace on session expiry but keeps login errors in the form", async () => {
    const dispatchEvent = vi.fn();
    vi.stubGlobal("window", { dispatchEvent });
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(new Response('{"detail":"请登录"}', { status: 401 })),
      ),
    );
    await expect(request("/logs")).rejects.toBeInstanceOf(ApiError);
    expect(dispatchEvent).toHaveBeenCalledTimes(1);
    await expect(request("/auth/login", "POST", {})).rejects.toBeInstanceOf(
      ApiError,
    );
    expect(dispatchEvent).toHaveBeenCalledTimes(1);
  });
});
