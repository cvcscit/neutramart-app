import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev proxies /api → the Node mock server on :5050 (mirrors the real app's setup).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:5050" },
  },
});
