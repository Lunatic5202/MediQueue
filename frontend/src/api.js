const TOKEN_KEY = "mediqueue.token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === "string" ? detail : detail?.message || detail?.code || `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

async function request(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const resp = await fetch(`/api${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (resp.status === 401) {
    setToken(null);
    if (!path.startsWith("/auth/")) window.location.assign("/login");
  }
  let data = null;
  try {
    data = await resp.json();
  } catch {
    data = null;
  }
  if (!resp.ok) throw new ApiError(resp.status, data?.detail ?? data);
  return data;
}

export const api = {
  login: (username, password) => request("/auth/login", { method: "POST", body: { username, password } }),
  me: () => request("/auth/me"),
  health: () => request("/health"),
  queue: () => request("/queue"),
  patient: (id) => request(`/patients/${encodeURIComponent(id)}`),
  history: (id) => request(`/patients/${encodeURIComponent(id)}/history`),
  risk: (id) => request(`/patients/${encodeURIComponent(id)}/risk`),
  timeline: (id) => request(`/patients/${encodeURIComponent(id)}/timeline`),
  alerts: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return request(`/alerts${q ? `?${q}` : ""}`);
  },
  recommendations: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return request(`/recommendations${q ? `?${q}` : ""}`);
  },
  confirm: (id, rationale) => request(`/recommendations/${id}/confirm`, { method: "POST", body: { rationale } }),
  reject: (id, rationale) => request(`/recommendations/${id}/reject`, { method: "POST", body: { rationale } }),
  override: (id, override_priority, rationale) =>
    request(`/recommendations/${id}/override`, { method: "POST", body: { override_priority, rationale } }),
  audit: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return request(`/audit${q ? `?${q}` : ""}`);
  },
  events: (sinceId = 0, limit = 200) => request(`/events?since_id=${sinceId}&limit=${limit}`),
  replayStatus: () => request("/replay/status"),
  replayStart: (body) => request("/replay/start", { method: "POST", body }),
  replayStop: () => request("/replay/stop", { method: "POST", body: {} }),
  metaFrontend: () => request("/meta/frontend"),
};
