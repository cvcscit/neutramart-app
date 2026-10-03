import React, { useEffect, useRef, useState } from "react";
import * as api from "./api.js";

const RECORD_SECONDS = 30;

export default function FaceScanModal({ email, onClose, onResult }) {
  const [phase, setPhase] = useState("camera"); // camera | recording | uploading | analyzing | error
  const [secondsLeft, setSecondsLeft] = useState(RECORD_SECONDS);
  const [error, setError] = useState(null);
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const countdownRef = useRef(null);
  const completedRef = useRef(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    // StrictMode mounts effects twice in dev: track liveness so a getUserMedia promise
    // that resolves after cleanup stops its own stream instead of leaking it.
    mountedRef.current = true;
    startCamera();
    return () => {
      mountedRef.current = false;
      stopCamera();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function stopCamera() {
    if (countdownRef.current) { clearInterval(countdownRef.current); countdownRef.current = null; }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }

  async function startCamera() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
      if (!mountedRef.current) { stream.getTracks().forEach((t) => t.stop()); return; }
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = stream;
      completedRef.current = false;
      setError(null);
      setPhase("camera");
      setTimeout(() => { if (videoRef.current) videoRef.current.srcObject = stream; }, 0);
    } catch (e) {
      if (!mountedRef.current) return;
      setPhase("error");
      setError("Camera access denied or unavailable. Please allow camera permission and try again.");
    }
  }

  function stopRecording() {
    if (countdownRef.current) { clearInterval(countdownRef.current); countdownRef.current = null; }
    const recorder = recorderRef.current;
    if (recorder && recorder.state === "recording") recorder.stop();
  }

  function startRecording() {
    const stream = streamRef.current;
    if (!stream) return;
    chunksRef.current = [];
    completedRef.current = false;
    const mimeType = MediaRecorder.isTypeSupported("video/webm;codecs=vp8") ? "video/webm;codecs=vp8" : "video/webm";
    const recorder = new MediaRecorder(stream, { mimeType });
    recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
    recorder.onstop = handleRecordingComplete;
    recorderRef.current = recorder;
    recorder.start();

    setPhase("recording");
    setSecondsLeft(RECORD_SECONDS);
    // Side effects (stopping the recorder) must not live inside a state updater: StrictMode
    // runs updaters twice, and a second stop() on an inactive recorder throws during render.
    const deadline = Date.now() + RECORD_SECONDS * 1000;
    countdownRef.current = setInterval(() => {
      const left = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
      setSecondsLeft(left);
      if (left <= 0) stopRecording();
    }, 250);
  }

  async function handleRecordingComplete() {
    if (completedRef.current) return;
    completedRef.current = true;
    stopCamera();
    setPhase("uploading");
    try {
      const blob = new Blob(chunksRef.current, { type: "video/webm" });
      const file = new File([blob], `facescan-${Date.now()}.webm`, { type: "video/webm" });

      const { url, key } = await api.presign(file.name, file.type, email);
      await api.putToS3(url, file);

      setPhase("analyzing");
      const result = await api.faceScan(key, file.type);
      onResult(result);
    } catch (e) {
      setPhase("error");
      setError(e.message || "Face scan failed. Please try again.");
    }
  }

  const busy = phase === "uploading" || phase === "analyzing";

  function handleClose() {
    if (busy) return; // don't let a stray click discard an in-flight result
    if (recorderRef.current && recorderRef.current.state === "recording") {
      completedRef.current = true; // user cancelled mid-recording: skip upload
      stopRecording();
    }
    stopCamera();
    onClose();
  }

  return (
    <div className="drawer-scrim scan-scrim" onClick={handleClose}>
      <aside className="scan-modal" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-head">
          <h2>Face Scan</h2>
          <button className="icon-btn" onClick={handleClose} disabled={busy}>✕</button>
        </div>

        <div className="scan-body">
          {(phase === "camera" || phase === "recording") && (
            <>
              <video ref={videoRef} className="scan-video" autoPlay muted playsInline />
              {phase === "camera" ? (
                <>
                  <p className="muted-note">Hold still, face well-lit, for {RECORD_SECONDS}s.</p>
                  <button className="send-btn scan-action" onClick={startRecording}>Record ({RECORD_SECONDS}s)</button>
                </>
              ) : (
                <div className="scan-status">Recording… {secondsLeft}s</div>
              )}
            </>
          )}

          {(phase === "uploading" || phase === "analyzing") && (
            <div className="scan-status">{phase === "uploading" ? "Uploading scan…" : "Analyzing your scan…"}</div>
          )}

          {phase === "error" && (
            <>
              <div className="scan-error">{error}</div>
              <button className="send-btn scan-action" onClick={startCamera}>Try Again</button>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}
