import { defineConfig, loadEnv } from "vite";
import uniModule from "@dcloudio/vite-plugin-uni";

// The CLI package exposes a CommonJS default inside an ESM config.
const uni =
  (uniModule as unknown as { default?: typeof uniModule }).default || uniModule;

export default defineConfig(({ mode, command }) => {
  const env = loadEnv(mode, process.cwd(), "ZHIAN_DEV_");
  return {
    base:
      command === "build" && process.env.UNI_PLATFORM === "h5" ? "/mini/" : "/",
    plugins: [uni()],
    server: {
      host: "127.0.0.1",
      port: 5174,
      strictPort: true,
      proxy: {
        "/api": {
          target:
            env.ZHIAN_DEV_API_TARGET ||
            process.env.ZHIAN_DEV_API_TARGET ||
            "http://127.0.0.1:8765",
          changeOrigin: true,
        },
      },
    },
  };
});
