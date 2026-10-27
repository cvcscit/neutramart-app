// Talks to the EXISTING live NutraSmart backend (region-aware via CloudFront).
// Auth = Google ID token (same as the main app), sent as Bearer. The CloudFront
// X-Origin-Verify secret is added by CloudFront itself and never ships in this bundle.
import { API_TIMEOUT_MS, FACE_SCAN_TIMEOUT_MS, UPLOAD_TIMEOUT_MS } from "./config.js";

const API_BASE = import.meta.env.VITE_API_URL ?? "https://api.nutrasmart.in/api";

export function getToken() {
  return localStorage.getItem("auth_token");
}

// Called on any 401/403 so the app can drop the stored token and show the login gate.
let onUnauthorized = () => {};
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler ?? (() => {});
}

function authHeaders(extra = {}) {
  const t = getToken();
  return {
    ...extra,
    ...(t ? { Authorization: `Bearer ${t}` } : {}),
  };
}

// Runs `request(signal)` with a deadline; a timeout surfaces as `timeoutMessage` instead of
// the browser's bare AbortError text.
async function withDeadline(ms, timeoutMessage, request) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    return await request(ctrl.signal);
  } catch (e) {
    if (ctrl.signal.aborted) throw new Error(timeoutMessage);
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

async function req(path, opts = {}, ms = API_TIMEOUT_MS) {
  return withDeadline(ms, "The server took too long to respond — please try again.", async (signal) => {
    const r = await fetch(`${API_BASE}${path}`, { ...opts, signal });
    if (r.status === 401 || r.status === 403) {
      onUnauthorized();
      throw new Error("Session expired — please sign in again.");
    }
    if (!r.ok) {
      // surface the backend's actual message (e.g. daily-limit text) instead of a bare code
      let detail = `HTTP ${r.status}`;
      try { const b = await r.json(); if (b && b.detail) detail = b.detail; } catch {}
      throw new Error(detail);
    }
    const data = await r.json();
    if (import.meta.env.DEV) console.log(`[nutrasmart] ${path} response:`, data);   // dev builds only: bodies hold health data
    return data;
  });
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

// The backend builds the object key from the signed-in user; the body names only the file.
export async function presign(filename, contentType) {
  return req("/upload/presign", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ filename, content_type: contentType }),
  });
}

export async function putToS3(url, file) {
  await withDeadline(UPLOAD_TIMEOUT_MS, "Upload timed out — please try again.", async (signal) => {
    const r = await fetch(url, { method: "PUT", headers: { "Content-Type": file.type }, body: file, signal });
    if (!r.ok) throw new Error(`S3 upload failed (HTTP ${r.status})`);
  });
}

export async function analyze(images) {
  return req("/analyze", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ images }),
  });
}

export async function faceScan(key, contentType) {
  return req("/facescan/analyze", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ key, content_type: contentType }),
  }, FACE_SCAN_TIMEOUT_MS);
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
