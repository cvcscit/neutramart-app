// Client settings, read once from Vite's build-time environment (import.meta.env.VITE_*).
// Every VITE_* value is inlined into the public JS bundle: never put a secret in one.
// Only the request deadlines live here so far; the other scattered settings move in
// later (WEB-1 in documents/notes/steps.md).

const positiveInt = (raw, fallback) => {
  const n = Number(raw);
  return Number.isInteger(n) && n > 0 ? n : fallback;
};

// Default deadline for a call to the NutraSmart API.
export const API_TIMEOUT_MS = positiveInt(import.meta.env.VITE_API_TIMEOUT_MS, 30_000);

// /facescan/analyze: video download + MediaPipe extraction (+ first-request classifier
// import) run well past the default; kept under the edge's 300 s agent read timeout.
export const FACE_SCAN_TIMEOUT_MS = positiveInt(import.meta.env.VITE_FACE_SCAN_TIMEOUT_MS, 280_000);

// Browser -> S3 PUT of a meal photo or face-scan video through a presigned URL.
export const UPLOAD_TIMEOUT_MS = positiveInt(import.meta.env.VITE_UPLOAD_TIMEOUT_MS, 120_000);
