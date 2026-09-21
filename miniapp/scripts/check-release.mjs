import { readFileSync } from "node:fs";
import { isIP } from "node:net";
import { fileURLToPath } from "node:url";
import { loadEnv } from "vite";

const root = fileURLToPath(new URL("..", import.meta.url));
const manifest = JSON.parse(
  readFileSync(new URL("../src/manifest.json", import.meta.url), "utf8"),
);
const env = loadEnv("production", root, "VITE_");
const errors = [];
if (!/^wx[0-9a-f]{16}$/i.test(manifest["mp-weixin"]?.appid || "")) {
  errors.push(
    "请在 src/manifest.json 的 mp-weixin.appid 中填写真实微信 AppID。",
  );
}
try {
  const url = new URL(env.VITE_API_BASE_URL || "");
  if (
    url.protocol !== "https:" ||
    url.pathname !== "/" ||
    url.search ||
    url.hash ||
    url.username ||
    url.password ||
    isIP(url.hostname) ||
    url.hostname.startsWith("[") ||
    /(^|\.)(localhost|local)$/i.test(url.hostname) ||
    !url.hostname.includes(".")
  ) {
    throw new Error("origin");
  }
} catch {
  errors.push(
    "VITE_API_BASE_URL 需为已部署的 HTTPS 域名，不含 /api、账号、参数或本机地址。",
  );
}
if (
  Object.keys(env).some((key) =>
    /secret|password|token|session.?key/i.test(key),
  )
) {
  errors.push(
    "检测到可能包含凭据的 VITE_* 变量。前端变量会进入小程序包，请将凭据移到后端配置。",
  );
}
if (errors.length) {
  console.error(errors.join("\n"));
  process.exitCode = 1;
} else {
  console.log(
    "本地发布配置检查通过。仍需在微信后台核对合法域名、隐私声明并进行真机验证。",
  );
}
