const configured = (import.meta.env.VITE_API_BASE_URL || "")
  .trim()
  .replace(/\/+$/, "");
export const serviceOrigin =
  configured || (import.meta.env.DEV ? "http://127.0.0.1:8765" : "");
export const storageScope = encodeURIComponent(serviceOrigin || "same-origin");
export let requestOrigin = serviceOrigin;
export let isWeChat = false;

// #ifdef H5
requestOrigin = "";
// #endif

// #ifdef MP-WEIXIN
isWeChat = true;
// #endif
