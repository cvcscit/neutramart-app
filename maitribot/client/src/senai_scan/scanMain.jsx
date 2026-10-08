// Entry point for /scan.html (the cross-origin-isolated scan page).

import React from "react";
import { createRoot } from "react-dom/client";
import ScanPage from "./ScanPage.jsx";
import ScanBoundary from "./ScanBoundary.jsx";
import "../styles.css";

createRoot(document.getElementById("scan-root")).render(
  // StrictMode is deliberately omitted: it double-mounts effects, which would
  // initialize + tear down the SDK's WASM runtime and camera twice on every load.
  <ScanBoundary onClose={() => (window.location.href = "/")}>
    <ScanPage />
  </ScanBoundary>
);
