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

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  function handleFile(selectedFile: File | null) {
    if (!selectedFile || !selectedFile.type.startsWith("image/")) return;

    setFile(selectedFile);
    setPreview(URL.createObjectURL(selectedFile));
    setStatus("idle");
    setProgress(0);
    setErrorMsg("");
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] || null;
    handleFile(file);
  }

  function handleRemove() {
    setFile(null);
    setPreview(null);
    setStatus("idle");
    setProgress(0);
    setErrorMsg("");
    setAnalysis(null);

    localStorage.removeItem("last_scan");

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

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

      const reader = new FileReader();
      reader.onloadend = () => {
        try {
          localStorage.setItem(
            "last_scan",
            JSON.stringify({
              preview: reader.result,
              analysis: analysisData,
            }),
          );
        } catch {}
      };
      reader.readAsDataURL(file);

      if (onScanComplete) {
        setTimeout(() => onScanComplete(), 5000);
      }
    } catch (err: any) {
      setStatus("error");
      setErrorMsg(err?.message || "Upload failed");
    }
  }

  return {
    file,
    preview,
    progress,
    status,
    errorMsg,
    analysis,
    fileInputRef,
    handleFileChange,
    handleRemove,
    handleUpload,
    handleFile,
  };
}
