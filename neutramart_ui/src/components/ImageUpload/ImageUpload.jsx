import { useState, useRef } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { API_URL } from "../../config/api";
import NutritionAnalysis from "../NutritionAnalysis/NutritionAnalysis";
import "./ImageUpload.css";

export default function ImageUpload() {
  const { user } = useAuth();
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState("idle"); // idle | uploading | analyzing | success | error
  const [errorMsg, setErrorMsg] = useState("");
  const [dragging, setDragging] = useState(false);
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

  function handleDrop(e) {
    e.preventDefault();
    setDragging(false);
    handleFile(e.dataTransfer.files[0]);
  }

  function handleDragOver(e) {
    e.preventDefault();
    setDragging(true);
  }

  function handleDragLeave() {
    setDragging(false);
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
      const res = await fetch(`${API_URL}/upload/presign`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filename: file.name,
          content_type: file.type,
          email: user.email,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to get upload URL");
      }

      const { url } = await res.json();

      await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("PUT", url);
        xhr.setRequestHeader("Content-Type", file.type);

        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            setProgress(Math.round((e.loaded / e.total) * 100));
          }
        };

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve();
          } else {
            reject(new Error("Upload to S3 failed"));
          }
        };

        xhr.onerror = () => reject(new Error("Network error during upload"));
        xhr.send(file);
      });

      setStatus("analyzing");

      // TODO: Replace with real API call to analyze the food image
      // e.g. const analysisRes = await fetch(`${API_URL}/analyze`, { ... });
      const placeholderAnalysis = {
        description: "—",
        calories: "—",
        fat: "—",
        carbs: "—",
        protein: "—",
        fiber: "—",
        sugar: "—",
        summary: "—",
        recommendation: "—",
      };

      setAnalysis(placeholderAnalysis);
      setStatus("success");
    } catch (err) {
      setStatus("error");
      setErrorMsg(err.message);
    }
  }

  return (
    <div className="upload-card">
      {!preview ? (
        <div
          className={`dropzone ${dragging ? "dropzone--active" : ""}`}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => fileInputRef.current.click()}
        >
          <input
            type="file"
            accept="image/*"
            ref={fileInputRef}
            onChange={handleFileChange}
            hidden
          />
          <div className="dropzone-icon">+</div>
          <p className="dropzone-text">Drop an image here or click to upload</p>
        </div>
      ) : (
        <div className="preview">
          <img src={preview} alt="Preview" className="preview-img" />

          {(status === "uploading" || status === "analyzing") && (
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{ width: status === "analyzing" ? "100%" : `${progress}%` }}
              />
            </div>
          )}

          {status === "analyzing" && (
            <p className="status-msg status-msg--analyzing">Analyzing food image...</p>
          )}

          {status === "error" && (
            <p className="status-msg status-msg--error">{errorMsg}</p>
          )}

          {status === "success" && analysis && (
            <NutritionAnalysis analysis={analysis} />
          )}

          <div className="preview-actions">
            {status !== "uploading" && status !== "analyzing" && status !== "success" && (
              <button className="btn btn--upload" onClick={handleUpload}>
                Analyze Food
              </button>
            )}
            <button
              className="btn btn--remove"
              onClick={handleRemove}
              disabled={status === "uploading" || status === "analyzing"}
            >
              {status === "success" ? "Upload another" : "Remove"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
