const API_BASE = ""; // same-origin: FastAPI serves this app itself

async function apiFetch(path, options) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // response wasn't JSON -- fall back to statusText
    }
    throw new Error(detail);
  }
  return response.json();
}

export function getHealth() {
  return apiFetch("/api/health");
}

export function listRuns() {
  return apiFetch("/api/lessons/runs");
}

export function getRun(runId) {
  return apiFetch(`/api/lessons/runs/${encodeURIComponent(runId)}`);
}

export function generateLesson(payload) {
  return apiFetch("/api/lessons/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
