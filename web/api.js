export const DEMO_TOKEN = "unified-demo-token-local-only-2026";
function storedToken() {
  try { const value = localStorage.getItem("unified-token"); if (value) return value; } catch {}
  try { return sessionStorage.getItem("unified-token") || ""; } catch { return ""; }
}
let token = storedToken();
export function setToken(value) {
  token = value;
  try { localStorage.setItem("unified-token", value); } catch {}
  try { sessionStorage.setItem("unified-token", value); } catch {}
}
export function getToken() { return token; }
export async function connectWorkspace(value) {
  const snapshot = await request("/snapshot", undefined, "GET", value);
  setToken(value);
  return snapshot;
}
export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}
export async function request(path, body, method = body ? "POST" : "GET", credential = token) {
  const response = await fetch("/api/v1" + path, {
    method,
    signal: AbortSignal.timeout(15000),
    headers: {
      Authorization: "Bearer " + credential,
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (!response.ok) {
    let error;
    try {
      error = await response.json();
    } catch {}
    throw new ApiError(
      response.status,
      typeof error?.detail === "string"
        ? error.detail
        : `HTTP ${response.status} · 請確認欄位及連線設定`,
    );
  }
  return response.json();
}
export async function downloadLog(id) {
  const r = await fetch(`/api/v1/jobs/${id}/log.txt`, {
    signal: AbortSignal.timeout(60000),
    headers: { Authorization: "Bearer " + token },
  });
  if (!r.ok) throw new Error("日誌下載失敗");
  const url = URL.createObjectURL(await r.blob()),
    a = document.createElement("a");
  a.href = url;
  a.download = id + ".log";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function terminal(host) {
  const ws = new WebSocket(
    `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/v1/hosts/${host}/terminal`,
  );
  ws.onopen = () => ws.send(JSON.stringify({ token }));
  return ws;
}
