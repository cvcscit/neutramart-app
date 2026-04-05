// In dev, Vite proxies /api → http://localhost:8000.
// In production, set VITE_API_URL to the full backend URL (e.g. https://api.nutrasmart.in/api).
export const API_URL = import.meta.env.VITE_API_URL ?? "/api";