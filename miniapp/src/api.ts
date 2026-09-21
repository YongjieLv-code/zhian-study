import { requestOrigin } from "./config";
import { goLogin, session, sessionGeneration, setSession } from "./session";
import type { AuthConfig, MiniSession, WechatResult, Workspace } from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public reason = "",
  ) {
    super(message);
  }
}

type Method = "GET" | "POST" | "PUT" | "DELETE";

export function request<T>(
  path: string,
  method: Method = "GET",
  body?: unknown,
  publicRequest = false,
): Promise<T> {
  const started = sessionGeneration();
  const current = session.value;
  if (!publicRequest && !current)
    return Promise.reject(new ApiError("请先登录你的学习账号", 401));
  const header: Record<string, string> = { "Content-Type": "application/json" };
  if (!publicRequest && current) {
    header.Authorization = `Bearer ${current.access_token}`;
    header["X-Workspace-ID"] = current.account.id;
  }
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${requestOrigin}/api${path}`,
      method,
      header,
      data: body as UniApp.RequestOptions["data"],
      timeout: 15000,
      success: (response) => {
        if (!publicRequest && started !== sessionGeneration()) {
          reject(new ApiError("账号已切换，请在当前账号重新操作", 409));
          return;
        }
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(
            response.statusCode === 204
              ? (undefined as T)
              : (response.data as T),
          );
          return;
        }
        const headers = response.header || {};
        const reason = String(
          headers["X-Zhian-Reason"] || headers["x-zhian-reason"] || "",
        );
        if (
          !publicRequest &&
          (response.statusCode === 401 ||
            reason === "workspace-changed" ||
            reason === "session-changed")
        ) {
          setSession(null);
          goLogin();
        }
        const payload = response.data as { detail?: unknown } | null;
        reject(
          new ApiError(
            typeof payload?.detail === "string"
              ? payload.detail
              : "操作未完成，请稍后重试",
            response.statusCode,
            reason,
          ),
        );
      },
      fail: () =>
        reject(
          new ApiError(
            "暂时无法连接服务，请检查网络后重试。尚未确认保存的内容会保留在当前页面。",
            0,
          ),
        ),
    });
  });
}

export const api = {
  config: () =>
    request<AuthConfig>("/mini/auth/config", "GET", undefined, true),
  login: (body: unknown) =>
    request<MiniSession>("/mini/auth/login", "POST", body, true),
  register: (body: unknown) =>
    request<MiniSession>("/mini/auth/register", "POST", body, true),
  wechat: (code: string, purpose: "login" | "bind") =>
    request<WechatResult>("/mini/auth/wechat", "POST", { code, purpose }, true),
  bind: (body: unknown) =>
    request<MiniSession>("/mini/auth/wechat/bind", "POST", body, true),
  logout: () => request<void>("/mini/auth/logout", "POST"),
  workspace: () => request<Workspace>("/workspace"),
  account: () =>
    request<Omit<MiniSession, "access_token" | "token_type">>(
      "/mini/auth/session",
    ),
};

export function wechatCode(): Promise<string> {
  return new Promise((resolve, reject) =>
    uni.login({
      provider: "weixin",
      success: (result) =>
        result.code
          ? resolve(result.code)
          : reject(new Error("未取得微信登录凭证，请重试")),
      fail: () => reject(new Error("微信登录未完成，请重试或使用账号密码登录")),
    }),
  );
}
