const BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

async function request(path, options) {
  let res;
  try {
    res = await fetch(BASE + path, options);
  } catch {
    throw new Error(`Cannot reach the API at ${BASE}. Is uvicorn running?`);
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const d = body?.detail;
    throw new Error(typeof d === "string" ? d : d ? JSON.stringify(d) : `Request failed (${res.status})`);
  }
  return body;
}

const post = (path, data) =>
  request(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
const enc = encodeURIComponent;

export const api = {
  matchReviewers: (payload) => post("/match/reviewers", payload),
  indexProfessor: (id) => request(`/professor/${enc(id)}/index`, { method: "POST" }),
  indexBatch: (ids) => post("/professor/index-batch", { scholar_ids: ids }),
  listIndexed: () => request("/professor/indexed"),
  expertise: (id) => request(`/professor/${enc(id)}/expertise`),
  graph: (id) => request(`/graph/professor/${enc(id)}`),
};

// "a, b\nc" -> ["a","b","c"]
export const splitList = (text) => text.split(/[\n,]+/).map((s) => s.trim()).filter(Boolean);