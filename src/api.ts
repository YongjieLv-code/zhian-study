import type {
  AuthStatus,
  Overview,
  Plan,
  Profile,
  ReviewAttempt,
  ReviewItem,
  StudyLog,
  Subject,
  Workspace,
} from "./types";

let auth: AuthStatus | null = null;
let sessionGeneration = 0;

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public reason = "",
  ) {
    super(message);
  }
}

export function setSession(value: AuthStatus | null) {
  if (
    auth?.account?.id !== value?.account?.id ||
    auth?.csrf_token !== value?.csrf_token
  )
    sessionGeneration++;
  auth = value;
}

async function fetchApi(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<Response> {
  const unscoped = [
    "/auth/status",
    "/auth/login",
    "/auth/register",
    "/workspace",
  ].includes(path);
  const generation = sessionGeneration;
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (!unscoped && auth?.account) headers["X-Workspace-ID"] = auth.account.id;
  if (!unscoped && method !== "GET" && auth?.csrf_token)
    headers["X-CSRF-Token"] = auth.csrf_token;
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers,
      credentials: "same-origin",
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(15000),
    });
  } catch {
    throw new Error(
      "暂时无法连接服务，请检查网络和服务状态后重试。尚未确认保存的内容请保留后再试。",
    );
  }
  if (!unscoped && generation !== sessionGeneration)
    throw new ApiError("账户已切换，请在当前账户重新操作。", 409);
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const reason = response.headers.get("X-Zhian-Reason") ?? "";
    if (
      !unscoped &&
      (response.status === 401 ||
        reason === "workspace-changed" ||
        reason === "session-changed")
    ) {
      window.dispatchEvent(new Event("zhian:session-changed"));
    }
    throw new ApiError(
      typeof error.detail === "string"
        ? error.detail
        : "操作没有完成，请稍后重试。",
      response.status,
      reason,
    );
  }
  return response;
}

export async function request<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetchApi(path, method, body);
  return response.status === 204
    ? (undefined as T)
    : (response.json() as Promise<T>);
}

export async function download(path: string, filename: string) {
  // Validate the visible account first; the download URL guards it again if a
  // different tab switches the cookie before the browser starts the download.
  await fetchApi("/profile");
  const url = new URL(`/api${path}`, location.origin);
  if (auth?.account) url.searchParams.set("workspace_id", auth.account.id);
  const link = document.createElement("a");
  link.href = url.toString();
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

export const api = {
  workspace: () => request<Workspace>("/workspace"),
  auth: () => request<AuthStatus>("/auth/status"),
  overview: () => request<Overview>("/overview"),
  subjects: () => request<Subject[]>("/subjects"),
  plans: () => request<Plan[]>("/plans"),
  logs: () => request<StudyLog[]>("/logs"),
  reviews: () => request<ReviewItem[]>("/reviews"),
  profile: (body: unknown) => request<Profile>("/profile", "PUT", body),
  history: (id: string) => request<ReviewAttempt[]>(`/reviews/${id}/history`),
};
