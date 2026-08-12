// Talks to the EXISTING live NutraSmart backend (region-aware via CloudFront).
// Auth = Google ID token (same as the main app), sent as Bearer.
const API_BASE = import.meta.env.VITE_API_URL ?? "https://api.nutrasmart.in/api";

export function getToken() {
  return localStorage.getItem("auth_token");
}

function authHeaders(extra = {}) {
  const t = getToken();
  return { ...extra, ...(t ? { Authorization: `Bearer ${t}` } : {}) };
}

async function req(path, opts = {}, ms = 30000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    const r = await fetch(`${API_BASE}${path}`, { ...opts, signal: ctrl.signal });
    if (!r.ok) {
      // surface the backend's actual message (e.g. daily-limit text) instead of a bare code
      let detail = `HTTP ${r.status}`;
      try { const b = await r.json(); if (b && b.detail) detail = b.detail; } catch {}
      if (r.status === 401 || r.status === 403) detail = "Session expired — please sign in again.";
      throw new Error(detail);
    }
    const data = await r.json();
    console.log(`[nutrasmart] ${path} response:`, data);   // print backend response for checking
    return data;
  } finally {
    clearTimeout(timer);
  }
}

// Derive the data region + bucket from the presigned URL host, e.g.
// https://sci-neutrasmart-project-eu.s3.eu-west-1.amazonaws.com/... → {region, bucket}
export function regionFromPresign(url) {
  try {
    const host = new URL(url).host;
    const bucket = host.split(".s3")[0];
    const m = host.match(/s3[.-]([a-z]{2}-[a-z]+-\d)/);
    return { bucket, region: m ? m[1] : "unknown" };
  } catch {
    return { bucket: "?", region: "?" };
  }
}

export async function presign(filename, contentType, email) {
  return req("/upload/presign", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ filename, content_type: contentType, email }),
  });
}

export async function putToS3(url, file) {
  const r = await fetch(url, { method: "PUT", headers: { "Content-Type": file.type }, body: file });
  if (!r.ok) throw new Error(`S3 upload failed (HTTP ${r.status})`);
}

export async function analyze(images) {
  return req("/analyze", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ images }),
  });
}

export async function chat(message, history = []) {
  return req("/chat", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ message, history }),
  });
}

export async function generateWeeklySummary() {
  return req("/weekly-summary/generate", { method: "POST", headers: authHeaders() });
}

export async function getNutritionSummary(period = "daily") {
  return req(`/nutrition/summary?period=${period}`, { headers: authHeaders() });
}
