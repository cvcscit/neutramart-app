import { useState, useRef } from "react";
import { useAuth } from "../contexts/AuthContext";
import { getPresignedUrl, uploadToS3, analyzeFood } from "../services/api";

export default function useImageAnalysis() {
  const { user, token } = useAuth();
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [analysis, setAnalysis] = useState(null);
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
