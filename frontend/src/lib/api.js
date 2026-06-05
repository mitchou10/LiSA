// Minimal API client for the LiSA backend.
const BASE_URL = (
  import.meta.env.VITE_API_URL || "http://localhost:8000"
).replace(/\/$/, "");

const API_V1 = `${BASE_URL}/api/v1`;

const TOKEN_KEY = "lisa_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request(path, options = {}) {
  const token = getToken();
  const res = await fetch(`${API_V1}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    const error = new Error(detail);
    error.status = res.status;
    throw error;
  }
  if (res.status === 204) return null;
  return res.json();
}

export async function getHealth() {
  const res = await fetch(`${BASE_URL}/health`);
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

// Authentication ----------------------------------------------------------
export async function login({ username, password }) {
  const data = await request("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  setToken(data.access_token);
  return data;
}

export async function getMe() {
  return request("/auth/me");
}

export function logout() {
  clearToken();
}

export async function submitTask({
  userId,
  inputData,
  serviceId = null,
  parentTaskId = null,
}) {
  return request("/tasks", {
    method: "POST",
    body: JSON.stringify({
      user_id: userId,
      input_data: inputData,
      service_id: serviceId,
      parent_task_id: parentTaskId,
    }),
  });
}

export async function getTask(taskId) {
  return request(`/tasks/${taskId}`);
}

function buildQuery(params) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, value);
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

// Normalize a list response into a paginated envelope. Tolerates an older
// backend that returns a plain array (no pagination metadata).
function toPage(data, { limit, offset }) {
  if (Array.isArray(data)) {
    return { items: data, total: data.length, limit, offset };
  }
  return {
    items: data?.items ?? [],
    total: data?.total ?? 0,
    limit: data?.limit ?? limit,
    offset: data?.offset ?? offset,
  };
}

// Returns the full paginated envelope: { items, total, limit, offset }.
export async function getTasksPage({
  userId,
  status,
  serviceId,
  rootsOnly,
  limit = 20,
  offset = 0,
} = {}) {
  const query = buildQuery({
    user_id: userId,
    status,
    service_id: serviceId,
    roots_only: rootsOnly,
    limit,
    offset,
  });
  const data = await request(`/tasks${query}`);
  return toPage(data, { limit, offset });
}

// Backward-compatible: returns just the array of tasks.
export async function getTasks(params = {}) {
  const page = await getTasksPage({ limit: 200, ...params });
  return Array.isArray(page) ? page : (page?.items ?? []);
}

export async function getTaskChildren(taskId) {
  return request(`/tasks/${taskId}/children`);
}

export async function revokeTask(taskId) {
  return request(`/tasks/${taskId}/revoke`, { method: "POST" });
}

export async function retryTask(taskId) {
  return request(`/tasks/${taskId}/retry`, { method: "POST" });
}

export async function deleteTask(taskId) {
  return request(`/tasks/${taskId}`, { method: "DELETE" });
}

// Returns the full paginated envelope: { items, total, limit, offset }.
export async function getServicesPage({
  q,
  type,
  limit = 20,
  offset = 0,
} = {}) {
  const query = buildQuery({ q, type, limit, offset });
  const data = await request(`/services${query}`);
  return toPage(data, { limit, offset });
}

// Backward-compatible: returns just the array of services.
export async function getServices(params = {}) {
  const page = await getServicesPage({ limit: 200, ...params });
  return Array.isArray(page) ? page : (page?.items ?? []);
}

// Aggregated analytics for the monitoring dashboard.
export async function getDashboardStats({ userId, days = 30 } = {}) {
  const query = buildQuery({ user_id: userId, days });
  return request(`/analytics/dashboard${query}`);
}

export { BASE_URL };
