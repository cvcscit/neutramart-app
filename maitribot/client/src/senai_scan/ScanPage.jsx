// Full-page Shen.AI scan, served from /scan.html.
//
// Why a separate page instead of a modal in the chat app: the SDK requires
// cross-origin isolation (COOP/COEP) for SharedArrayBuffer, and those headers break
// Google Identity Services. Isolation only applies to a top-level document, so the scan
// gets its own page and the chat app at / stays non-isolated.
//
// Hand-off is via storage (same origin, so both pages share it):
//   - in:  localStorage "auth_token"        — who's scanning (set by login on /)
//   - out: sessionStorage PENDING_KEY       — the result, picked up by App.jsx on return

import React, { useEffect, useRef, useState } from "react";
import { jwtDecode } from "jwt-decode";
import { initShenai, deinitShenai } from "./sdk.js";
import { toVitals, statusText } from "./adapter.js";

const CANVAS_ID = "mxcanvas";
const CANVAS_SELECTOR = "#" + CANVAS_ID;

export const PENDING_KEY = "senai_pending_vitals";
const RETURN_TO = "/";

function currentEmail() {
  try {
    const t = localStorage.getItem("auth_token");
    return t ? jwtDecode(t).email ?? "" : "";
  } catch {
    return "";
  }
}

export default function ScanPage() {
  const [phase, setPhase] = useState("loading"); // loading | scanning | error
  const [status, setStatus] = useState("Starting…");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);
  const hostRef = useRef(null);
  const mountedRef = useRef(true);
  const deliveredRef = useRef(false);

  useEffect(() => {
    mountedRef.current = true;
    deliveredRef.current = false;
    let pollId = null;
    let canvas = null;

    (async () => {
      try {
        // Created imperatively and kept out of React's tree: the SDK reparents this
        // node, so letting React reconcile it throws NotFoundError on the next render.
        canvas = document.createElement("canvas");
        canvas.id = CANVAS_ID;
        canvas.className = "senai-canvas";
        hostRef.current?.appendChild(canvas);

        const sdk = await initShenai(
          currentEmail(),
          {
            showUserInterface: true,
            showFacePositioningOverlay: true,
            showVisualWarnings: true,
            showFaceMask: true,
            enableSummaryScreen: false,
            enableStartAfterSuccess: false,
          },
          (stage, p) => {
            if (!mountedRef.current) return;
            if (stage === "runtime") {
              const pct = p > 0 ? ` ${Math.round(p * 100)}%` : "";
              setStatus(`Loading Shen.AI engine${pct}…`);
            } else {
              setStatus("Activating licence…");
            }
          }
        );

        if (!mountedRef.current) {
          deinitShenai();
          return;
        }

        sdk.setMeasurementPreset(sdk.MeasurementPreset.THIRTY_SECONDS_ALL_METRICS);
        sdk.attachToCanvas(CANVAS_SELECTOR);
        setPhase("scanning");

        pollId = setInterval(() => {
          if (!mountedRef.current) return;

          const state = sdk.getMeasurementState();
          setStatus(statusText(sdk, state, sdk.getFaceState()));
          setProgress(sdk.getMeasurementProgressPercentage() ?? 0);

          // The SDK idles in POSITIONING until told to measure, so it would sit at
          // NOT_STARTED forever otherwise. The user already opted in by opening this
          // page, so start automatically (mirrors the SDK's own js example).
          if (
            state !== sdk.MeasurementState.FINISHED &&
            state !== sdk.MeasurementState.FINALIZING &&
            sdk.getOperatingMode() !== sdk.OperatingMode.MEASURE
          ) {
            sdk.setOperatingMode(sdk.OperatingMode.MEASURE);
          }

          if (state === sdk.MeasurementState.FINISHED && !deliveredRef.current) {
            deliveredRef.current = true;
            clearInterval(pollId);
            pollId = null;
            finish(toVitals(sdk.getMeasurementResults()));
          } else if (state === sdk.MeasurementState.FAILED) {
            clearInterval(pollId);
            pollId = null;
            setPhase("error");
            setError("The scan failed. Make sure your face is well lit, then try again.");
          }
        }, 300);
      } catch (e) {
        if (!mountedRef.current) return;
        setPhase("error");
        setError(e.message);
      }
    })();

    return () => {
      mountedRef.current = false;
      if (pollId) clearInterval(pollId);
      deinitShenai();
      canvas?.remove();
    };
  }, []);

  function finish(vitals) {
    try {
      sessionStorage.setItem(PENDING_KEY, JSON.stringify(vitals));
    } catch {
      // Storage full/blocked: better to return without the result than to strand the
      // user on this page with no way back.
    }
    deinitShenai();
    window.location.href = RETURN_TO;
  }

  return (
    <div className="scan-page">
      <header className="topbar">
        <div className="brand">
          <span className="logo">🫀</span>
          <div>
            <div className="brand-name">Vitals Scan</div>
            <div className="brand-sub">Shen.AI · on-device</div>
          </div>
        </div>
        <button className="dash-btn" onClick={() => (window.location.href = RETURN_TO)}>
          ← Back to chat
        </button>
      </header>

      <main className="scan-page-body">
        <div ref={hostRef} className="senai-canvas-host"
             style={phase === "error" ? { display: "none" } : undefined} />

        {phase === "error" ? (
          <>
            <div className="scan-error">{error}</div>
            <button className="send-btn scan-action"
                    onClick={() => (window.location.href = RETURN_TO)}>
              Back to chat
            </button>
          </>
        ) : (
          <>
            <div className="scan-status">{status}</div>
            {phase === "scanning" && (
              <div className="senai-progress">
                <div className="senai-progress-bar" style={{ width: `${progress}%` }} />
              </div>
            )}
            <p className="muted-note">
              Sit still in even lighting and look at the camera. Nothing is uploaded —
              this scan runs entirely on your device.
            </p>
          </>
        )}
      </main>
    </div>
  );
}
