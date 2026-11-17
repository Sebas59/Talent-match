// Cliente HTTP. El token de acceso vive SOLO en memoria (como en V5); la sesión se recupera
// tras recargar la página con el refresh token en cookie HttpOnly (rotación en cada uso).
const API = "/api/v1";
let accessToken = null;
let refreshing = null;
let onSessionLost = () => {};

export const setSessionLostHandler = (fn) => { onSessionLost = fn; };
export const setToken = (t) => { accessToken = t; };

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

function message(data, status) {
  const d = data && data.detail;
  if (Array.isArray(d)) return d.map((x) => x.msg).join(". ");
  if (typeof d === "string") return d;
  if (status === 403) return "No tiene permisos para esta acción.";
  if (status === 429) return "Demasiadas solicitudes. Espere un minuto e intente de nuevo.";
  return `Error ${status}`;
}

export async function refreshSession() {
  if (!refreshing) {
    refreshing = fetch(`${API}/auth/refresh`, { method: "POST", credentials: "same-origin",
      headers: { "X-TM-Refresh": "1" } })
      .then(async (r) => {
        if (r.status !== 200) return null;
        const data = await r.json();
        accessToken = data.access_token;
        return data;
      })
      .catch(() => null)
      .finally(() => { setTimeout(() => { refreshing = null; }, 0); });
  }
  return refreshing;
}

export async function api(path, { method = "GET", json, form, body, raw = false, retry = true } = {}) {
  const headers = {};
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  if (json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(json); }
  if (form) { headers["Content-Type"] = "application/x-www-form-urlencoded"; body = new URLSearchParams(form); }
  const res = await fetch(API + path, { method, headers, body, credentials: "same-origin", cache: "no-store" });
  if (res.status === 401 && retry && accessToken && !path.startsWith("/auth/")) {
    const ok = await refreshSession();
    if (ok) return api(path, { method, json, form, body: json !== undefined ? undefined : body, raw, retry: false });
    accessToken = null;
    onSessionLost();
    throw new ApiError(401, "La sesión expiró. Inicie sesión de nuevo.");
  }
  if (raw) return res;
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, message(data, res.status));
  return data;
}

export const get = (p) => api(p);
export const post = (p, json) => api(p, { method: "POST", json: json ?? {} });
export const patch = (p, json) => api(p, { method: "PATCH", json });
export const put = (p, json) => api(p, { method: "PUT", json });
export const del = (p) => api(p, { method: "DELETE" });

export async function upload(path, file) {
  const fd = new FormData();
  fd.append("file", file);
  return api(path, { method: "POST", body: fd });
}

export async function login(email, password) {
  const data = await api("/auth/token", { method: "POST", form: { username: email, password } });
  accessToken = data.access_token;
  return data;
}

export async function logout() {
  try { await api("/auth/logout", { method: "POST" }); } catch { /* sesión ya cerrada */ }
  accessToken = null;
}

export async function download(path, filename) {
  const res = await api(path, { raw: true });
  if (!res.ok) throw new ApiError(res.status, "No se pudo descargar");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.rel = "noopener";
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}
