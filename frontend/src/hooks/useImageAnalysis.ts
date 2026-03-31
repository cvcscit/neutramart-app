import { useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { getPresignedUrl, uploadToS3, analyzeFood } from "../services/api";

type Analysis = any;

type Status = "idle" | "uploading" | "analyzing" | "success" | "error";

type LastScan = {
  previews: string[];
  analysis: Analysis;
};

type ImageItem = {
  sig: string;
  file: File;
};

const MAX_IMAGES = 5;

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

  const [items, setItems] = useState<ImageItem[]>([]);
  const [generatedPreviews, setGeneratedPreviews] = useState<string[]>([]);
  const [persistedPreviews, setPersistedPreviews] = useState<string[]>(
    lastScan?.previews || [],
  );
  const [progress, setProgress] = useState<number>(0);
  const [status, setStatus] = useState<Status>(lastScan ? "success" : "idle");
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [analysis, setAnalysis] = useState<Analysis | null>(lastScan?.analysis || null);

  // Camera state
  const [cameraOpen, setCameraOpen] = useState(false);
  const [stream, setStream] = useState<MediaStream | null>(null);

  // Refs
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const previewUrlMapRef = useRef<Map<string, string>>(new Map());

  // ── File helpers ────────────────────────────────────────────────────────────

  const files = useMemo(() => items.map((it) => it.file), [items]);
  const previews = useMemo(
    () => (items.length ? generatedPreviews : persistedPreviews),
    [generatedPreviews, items.length, persistedPreviews],
  );

  useEffect(() => {
    const map = previewUrlMapRef.current;
    const currentSigs = new Set(items.map((it) => it.sig));

    // Create URLs for any new files
    for (const it of items) {
      if (!map.has(it.sig)) {
        map.set(it.sig, URL.createObjectURL(it.file));
      }
    }

    // Revoke URLs for removed files
    for (const [sig, url] of map.entries()) {
      if (!currentSigs.has(sig)) {
        URL.revokeObjectURL(url);
        map.delete(sig);
      }
    }

    setGeneratedPreviews(items.map((it) => map.get(it.sig)!).filter(Boolean));
  }, [items]);

  useEffect(() => {
    return () => {
      const map = previewUrlMapRef.current;
      for (const url of map.values()) URL.revokeObjectURL(url);
      map.clear();
    };
  }, []);

  function fileSig(f: File) {
    return `${f.name}__${f.size}__${f.lastModified}__${f.type}`;
  }

  function addFiles(incoming: File[]) {
    const valid = incoming.filter((f) => f.type.startsWith("image/"));
    if (!valid.length) return;

    setItems((prev) => {
      const existing = new Set(prev.map((p) => p.sig));
      const next: ImageItem[] = [...prev];

      for (const f of valid) {
        if (next.length >= MAX_IMAGES) break;
        const sig = fileSig(f);
        if (existing.has(sig)) continue;
        existing.add(sig);
        next.push({ sig, file: f });
      }

      return next;
    });

    setStatus("idle");
    setProgress(0);
    setErrorMsg("");
    setAnalysis(null);
    setPersistedPreviews([]);
    localStorage.removeItem("last_scan");
  }

  // Legacy single-file interface (used by dropzone + camera)
  function handleFile(selectedFile: File | null) {
    if (!selectedFile) return;
    addFiles([selectedFile]);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(e.target.files || []);
    addFiles(selected);
    // Reset input so re-selecting same file triggers change
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function handleRemove(index?: number) {
    if (index !== undefined) {
      setItems((prev) => prev.filter((_, i) => i !== index));
      if (items.length <= 1) {
        setStatus("idle");
        setAnalysis(null);
        setPersistedPreviews([]);
        localStorage.removeItem("last_scan");
      }
    } else {
      setItems([]);
      setPersistedPreviews([]);
      setStatus("idle");
      setProgress(0);
      setErrorMsg("");
      setAnalysis(null);
      localStorage.removeItem("last_scan");
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  // ── Upload & analyse ────────────────────────────────────────────────────────

  async function handleUpload() {
    if (!files.length || !user || !token) return;

    setStatus("uploading");
    setProgress(0);
    setErrorMsg("");

    try {
      // Track per-file progress and average them
      const progressArr = new Array(files.length).fill(0);
      const updateProgress = (i: number) => (p: number) => {
        progressArr[i] = p;
        const avg = Math.round(progressArr.reduce((a, b) => a + b, 0) / progressArr.length);
        setProgress(avg);
      };

      // Upload all files in parallel
      const uploaded = await Promise.all(
        files.map(async (file, i) => {
          const { url, key } = await getPresignedUrl(token, {
            filename: file.name,
            contentType: file.type,
            email: user.email,
          });
          await uploadToS3(url, file, updateProgress(i));
          return { key, contentType: file.type };
        })
      );

      setStatus("analyzing");

      const analysisData: Analysis = await analyzeFood(token, uploaded);

      setAnalysis(analysisData);
      setStatus("success");

      // Persist last scan
      try {
        localStorage.setItem(
          "last_scan",
          JSON.stringify({ previews, analysis: analysisData })
        );
      } catch {}

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
            "Photo is too large (max 4 MB). Try moving closer or improving lighting."
          );
          closeCamera();
          return;
        }

        closeCamera();
        handleFile(captured);
      },
      "image/jpeg",
      0.95
    );
  }

  // ── Public API ──────────────────────────────────────────────────────────────

  return {
    // state
    files,
    previews,
    progress,
    status,
    errorMsg,
    analysis,
    maxImages: MAX_IMAGES,
    // file
    fileInputRef,
    handleFile,
    handleFileChange,
    handleRemove,
    handleUpload,
    addFiles,
    // camera
    cameraOpen,
    openCamera,
    closeCamera,
    capturePhoto,
    videoRef,
    canvasRef,
  };
}
