import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

// Cross-origin isolation headers, applied to the SCAN PAGE ONLY.
//
// The Shen.AI SDK requires COOP/COEP (it uses SharedArrayBuffer), but COOP:same-origin
// severs window.opener and COEP:require-corp blocks Google's cross-origin iframe — either
// one breaks the Google login on the main app. Isolation is per top-level document, so
// /scan.html is isolated and / is not.
//
// NOTE for production: this only covers `vite dev`. CloudFront/ALB must send the same two
// headers for /scan.html (and nothing else) or the deployed scan will fail the same way.
function isolateScanPage() {
  return {
    name: "isolate-scan-page",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = req.url || "";

        if (url.startsWith("/scan")) {
          res.setHeader("Cross-Origin-Opener-Policy", "same-origin");
          // require-corp rather than credentialless: Safari doesn't support the latter.
          res.setHeader("Cross-Origin-Embedder-Policy", "require-corp");
        }

        // The SDK spawns a dedicated worker from /shenai-sdk/. In a cross-origin-isolated
        // document a worker script must ITSELF carry COEP, or the browser blocks it with
        // ERR_BLOCKED_BY_RESPONSE — which left the SDK waiting on a worker that never
        // loaded. CORP is set too so these files are embeddable by the isolated page.
        if (url.startsWith("/shenai-sdk/")) {
          res.setHeader("Cross-Origin-Embedder-Policy", "require-corp");
          res.setHeader("Cross-Origin-Resource-Policy", "same-origin");
        }

        next();
      });
    },
  };
}

export default defineConfig({
  // Shen.AI ships ES-module workers; Vite's default ("iife") can't load them.
  worker: { format: "es" },
  plugins: [react(), isolateScanPage()],
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),
        scan: resolve(__dirname, "scan.html"),
      },
    },
  },
  server: {
    port: 5174,
    strictPort: true,
  },
});
