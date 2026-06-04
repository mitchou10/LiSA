// Minimal API client for the LiSA backend.
const BASE_URL = (
  import.meta.env.VITE_API_URL || "http://localhost:8000"
).replace(/\/$/, "");

const API_V1 = `${BASE_URL}/api/v1`;

async function request(path, options = {}) {
  const res = await fetch(`${API_V1}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

export async function getHealth() {
  const res = await fetch(`${BASE_URL}/health`);
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
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

export async function getTasks({ limit = 200, offset = 0 } = {}) {
  return request(`/tasks?limit=${limit}&offset=${offset}`);
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

export async function getServices() {
  return request("/services");
}

export { BASE_URL };
