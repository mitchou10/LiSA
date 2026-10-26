// Minimal API client for the LiSA backend.
const BASE_URL = (
  import.meta.env.VITE_API_URL || "http://localhost:8000"
).replace(/\/$/, "");

const API_V1 = `${BASE_URL}/api/v1`;

// Dev-only: when the backend runs with a service token and no Keycloak, this
// value is sent as a Bearer token so the API accepts the calls.
const DEV_SERVICE_TOKEN = import.meta.env.VITE_DEV_SERVICE_TOKEN || "";

async function request(path, options = {}) {
  const res = await fetch(`${API_V1}${path}`, {
    // BFF mode: the session cookie is the credential (HttpOnly, never read here).
    credentials: "include",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(DEV_SERVICE_TOKEN ? { Authorization: `Bearer ${DEV_SERVICE_TOKEN}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (Array.isArray(body?.detail)) {
        // FastAPI validation errors: [{loc, msg}, ...]
        detail = body.detail
          .map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`.replace(/^: /, ""))
          .join("; ");
      } else if (body?.detail) {
        detail = body.detail;
      }
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
// Keycloak only. The browser is redirected to the backend, which runs the OIDC
// flow and sets the session cookie: no token ever reaches JavaScript.
export function oidcLoginUrl(redirect = "/dashboard") {
  return `${API_V1}/auth/login?redirect=${encodeURIComponent(redirect)}`;
}

export async function oidcLogout() {
  const data = await request("/auth/logout", { method: "POST" });
  return data.redirectUrl;
}

export async function getMe() {
  return request("/auth/me");
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

// Get tasks for the current authenticated user.
export async function getMyTasks({
  status,
  serviceId,
  projectId,
  rootsOnly,
  limit = 50,
  offset = 0,
} = {}) {
  const query = buildQuery({
    status,
    service_id: serviceId,
    project_id: projectId,
    roots_only: rootsOnly,
    limit,
    offset,
  });
  const data = await request(`/tasks/me${query}`);
  return toPage(data, { limit, offset });
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
export async function getDashboardStats({ userId, projectId, days = 30 } = {}) {
  const query = buildQuery({ user_id: userId, project_id: projectId, days });
  return request(`/analytics/dashboard${query}`);
}

// Detection profiles (versioned, editable sensitive-data settings) ---------
export async function getDetectionProfile(serviceKey) {
  return request(`/detection-profiles/${serviceKey}`);
}

export async function getProfileVersions(serviceKey, { limit = 50 } = {}) {
  const data = await request(
    `/detection-profiles/${serviceKey}/versions${buildQuery({ limit })}`
  );
  return data?.items ?? [];
}

export async function saveProfileVersion(serviceKey, { config, comment }) {
  return request(`/detection-profiles/${serviceKey}/versions`, {
    method: "POST",
    body: JSON.stringify({ config, comment: comment || null }),
  });
}

export async function restoreProfileVersion(serviceKey, version) {
  return request(`/detection-profiles/${serviceKey}/versions/${version}/activate`, {
    method: "POST",
  });
}

export { BASE_URL };

// Projects and what they look for ----------------------------------------
// kind: "entities" | "relations" | "classifications" | "safety"
export const DEFINITION_KINDS = ["entities", "relations", "classifications", "safety"];

const json = (method, body) => ({ method, body: JSON.stringify(body) });

export async function getProjects() {
  const data = await request("/projects?limit=500");
  return data?.items ?? [];
}

export const getProject = (id) => request(`/projects/${id}`);
export const createProject = (data) => request("/projects", json("POST", data));
export const updateProject = (id, data) =>
  request(`/projects/${id}`, json("PATCH", data));
export const deleteProject = (id) => request(`/projects/${id}`, { method: "DELETE" });

export const getDefinitions = (projectId, kind) =>
  request(`/projects/${projectId}/${kind}`);
export const createDefinition = (projectId, kind, data) =>
  request(`/projects/${projectId}/${kind}`, json("POST", data));
export const updateDefinition = (projectId, kind, id, data) =>
  request(`/projects/${projectId}/${kind}/${id}`, json("PATCH", data));
export const deleteDefinition = (projectId, kind, id) =>
  request(`/projects/${projectId}/${kind}/${id}`, { method: "DELETE" });

// Upload a file to object storage; returns its metadata (id, s3_key, ...).
export async function uploadFile(file) {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch(`${API_V1}/files`, {
    method: "POST",
    credentials: "include",
    headers: {
      ...(DEV_SERVICE_TOKEN ? { Authorization: `Bearer ${DEV_SERVICE_TOKEN}` } : {}),
    },
    body, // the browser sets the multipart Content-Type itself
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      detail = (await res.json())?.detail || detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    const error = new Error(detail);
    error.status = res.status;
    throw error;
  }
  return res.json();
}

// Start a run: analyse a text or files with what the project looks for.
// body: { text | file_ids, blur_screenshots?, entity_ids?, relation_ids?,
//         classification_ids?, safety_ids? }
export const startRun = (projectId, body) =>
  request(`/projects/${projectId}/runs`, json("POST", body));

// Start a default run: the same analysis without any project. The seeded
// defaults (PII entities, safety checks) are applied, nothing to select.
export const startDefaultRun = (body) =>
  request("/tasks/runs", json("POST", body));

// The screenshot of a page parsed by a parser task, as a blob URL (the caller
// revokes it). 410 means the image was deleted from storage.
export async function fetchPageImage(parserTaskId, pageNumber) {
  const res = await fetch(
    `${API_V1}/tasks/${parserTaskId}/pages/${pageNumber}/image`,
    {
      credentials: "include",
      headers: {
        ...(DEV_SERVICE_TOKEN ? { Authorization: `Bearer ${DEV_SERVICE_TOKEN}` } : {}),
      },
    }
  );
  if (!res.ok) {
    const error = new Error(`${res.status} ${res.statusText}`);
    error.status = res.status;
    throw error;
  }
  return URL.createObjectURL(await res.blob());
}

// Export the pages of a finished file run: blurred entities, boxes, labels,
// as PNG (one page), ZIP or PDF (every page). Returns a blob URL the caller
// revokes after the download.
export async function renderRunDocument(runId, body) {
  const res = await fetch(`${API_V1}/tasks/${runId}/render`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(DEV_SERVICE_TOKEN ? { Authorization: `Bearer ${DEV_SERVICE_TOKEN}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const payload = await res.json();
      if (payload?.detail) detail = payload.detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    const error = new Error(detail);
    error.status = res.status;
    throw error;
  }
  return URL.createObjectURL(await res.blob());
}
