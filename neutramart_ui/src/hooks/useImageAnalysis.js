import { useState, useRef } from "react";
import { useAuth } from "../contexts/AuthContext";
import { getPresignedUrl, uploadToS3, analyzeFood } from "../services/api";

function loadLastScan() {
  try {
    const saved = localStorage.getItem("last_scan");
    if (!saved) return null;
    return JSON.parse(saved);
  } catch {
    return null;
  }
}

export default function useImageAnalysis(onScanComplete) {
  const { user, token } = useAuth();
  const lastScan = loadLastScan();
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(lastScan?.preview || null);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState(lastScan ? "success" : "idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [analysis, setAnalysis] = useState(lastScan?.analysis || null);
  const fileInputRef = useRef(null);

  function handleFile(selectedFile) {
    if (!selectedFile || !selectedFile.type.startsWith("image/")) return;
    setFile(selectedFile);
    setPreview(URL.createObjectURL(selectedFile));
    setStatus("idle");
    setProgress(0);
    setErrorMsg("");
  }

  function handleFileChange(e) {
    handleFile(e.target.files[0]);
  }

  function handleRemove() {
    setFile(null);
    setPreview(null);
    setStatus("idle");
    setProgress(0);
    setErrorMsg("");
    setAnalysis(null);
    localStorage.removeItem("last_scan");
    fileInputRef.current.value = "";
  }

  async function handleUpload() {
    if (!file) return;

    setStatus("uploading");
    setProgress(0);
    setErrorMsg("");

    try {
      const { url, key } = await getPresignedUrl(token, {
        filename: file.name,
        contentType: file.type,
        email: user.email,
      });

      await uploadToS3(url, file, setProgress);

      setStatus("analyzing");

      const analysisData = await analyzeFood(token, {
        key,
        contentType: file.type,
      });

      setAnalysis(analysisData);
      setStatus("success");

      // Save last scan to localStorage for persistence across refresh
      const reader = new FileReader();
      reader.onloadend = () => {
        try {
          localStorage.setItem("last_scan", JSON.stringify({
            preview: reader.result,
            analysis: analysisData,
          }));
        } catch { /* storage full — ignore */ }
      };
      reader.readAsDataURL(file);

      // Trigger weekly summary refresh after a delay (background generation takes time)
      if (onScanComplete) {
        setTimeout(() => onScanComplete(), 5000);
      }
    } catch (err) {
      setStatus("error");
      setErrorMsg(err.message);
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
  };
}
