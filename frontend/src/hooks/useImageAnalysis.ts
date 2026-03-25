import { useState, useRef } from "react";
import { useAuth } from "../contexts/AuthContext";
import { getPresignedUrl, uploadToS3, analyzeFood } from "../services/api";

type Analysis = any; // replace with real API type

type Status = "idle" | "uploading" | "analyzing" | "success" | "error";

type LastScan = {
  preview: string;
  analysis: Analysis;
};

function loadLastScan(): LastScan | null {
  try {
    const saved = localStorage.getItem("last_scan");
    if (!saved) return null;
    return JSON.parse(saved);
  } catch {
    return null;
  }
}

export default function useImageAnalysis(onScanComplete?: () => void) {
  const { user, token } = useAuth();

  const lastScan = loadLastScan();

  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(
    lastScan?.preview || null,
  );
  const [progress, setProgress] = useState<number>(0);
  const [status, setStatus] = useState<Status>(lastScan ? "success" : "idle");
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [analysis, setAnalysis] = useState<Analysis | null>(
    lastScan?.analysis || null,
  );

  // Camera state
  const [cameraOpen, setCameraOpen] = useState(false);
  const [stream, setStream] = useState<MediaStream | null>(null);

  // Refs
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // ── File helpers ────────────────────────────────────────────────────────────

  function handleFile(selectedFile: File | null) {
    if (!selectedFile || !selectedFile.type.startsWith("image/")) return;
    setFile(selectedFile);
    setPreview(URL.createObjectURL(selectedFile));
    setStatus("idle");
    setProgress(0);
    setErrorMsg("");
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    handleFile(e.target.files?.[0] ?? null);
  }

  function handleRemove() {
    setFile(null);
    setPreview(null);
    setStatus("idle");
    setProgress(0);
    setErrorMsg("");
    setAnalysis(null);
    localStorage.removeItem("last_scan");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  // ── Upload & analyse ────────────────────────────────────────────────────────

  async function handleUpload() {
    if (!file || !user || !token) return;

    setStatus("uploading");
    setProgress(0);
    setErrorMsg("");

    try {
      const { url, key }: { url: string; key: string } = await getPresignedUrl(
        token,
        {
          filename: file.name,
          contentType: file.type,
          email: user.email,
        },
      );

      await uploadToS3(url, file, setProgress);

      setStatus("analyzing");

      const analysisData: Analysis = await analyzeFood(token, {
        key,
        contentType: file.type,
      });

      setAnalysis(analysisData);
      setStatus("success");

      // Persist to localStorage so the last scan survives a refresh
      const reader = new FileReader();
      reader.onloadend = () => {
        try {
          localStorage.setItem(
            "last_scan",
            JSON.stringify({ preview: reader.result, analysis: analysisData }),
          );
        } catch {}
      };
      reader.readAsDataURL(file);

      if (onScanComplete) setTimeout(() => onScanComplete(), 5000);
    } catch (err: any) {
      setStatus("error");
      setErrorMsg(err?.message || "Upload failed");
    }
  }

  // ── Camera helpers ──────────────────────────────────────────────────────────

  async function openCamera() {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
        audio: false,
      });
      setStream(mediaStream);
      setCameraOpen(true);
      // Give the <video> element a tick to mount before assigning srcObject
      setTimeout(() => {
        if (videoRef.current) videoRef.current.srcObject = mediaStream;
      }, 100);
    } catch {
      setStatus("error");
      setErrorMsg("Camera access denied – please allow camera permissions.");
    }
  }

  function closeCamera() {
    stream?.getTracks().forEach((t) => t.stop());
    setStream(null);
    setCameraOpen(false);
  }

  async function capturePhoto() {
    if (!videoRef.current || !canvasRef.current) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(
      async (blob) => {
        if (!blob) return;

        const captured = new File([blob], `photo-${Date.now()}.jpg`, {
          type: "image/jpeg",
        });

        if (captured.size > 4 * 1024 * 1024) {
          setStatus("error");
          setErrorMsg(
            "Photo is too large (max 4 MB). Try moving closer or improving lighting.",
          );
          closeCamera();
          return;
        }

        closeCamera();
        handleFile(captured);
      },
      "image/jpeg",
      0.95,
    );
  }

  // ── Public API ──────────────────────────────────────────────────────────────

  return {
    // state
    file,
    preview,
    progress,
    status,
    errorMsg,
    analysis,
    // file
    fileInputRef,
    handleFile,
    handleFileChange,
    handleRemove,
    handleUpload,
    // camera
    cameraOpen,
    openCamera,
    closeCamera,
    capturePhoto,
    videoRef,
    canvasRef,
  };
}
