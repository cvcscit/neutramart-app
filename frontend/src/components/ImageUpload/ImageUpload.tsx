import useImageAnalysis from "../../hooks/useImageAnalysis";
import useDropzone from "../../hooks/useDropzone";
import NutritionAnalysis from "../NutritionAnalysis/NutritionAnalysis";
import "./ImageUpload.css";

type Props = {
  onScanComplete?: () => void;
};

export default function ImageUpload({ onScanComplete }: Props) {
  const {
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
  } = useImageAnalysis(onScanComplete);

  const { dragging, onDrop, onDragOver, onDragLeave } = useDropzone((file) => {
    handleFile(file);
  });

  return (
    <div className="upload-card">
      {!preview ? (
        <div
          className={`dropzone ${dragging ? "dropzone--active" : ""}`}
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onClick={() => fileInputRef.current?.click()}
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
                style={{
                  width: status === "analyzing" ? "100%" : `${progress}%`,
                }}
              />
            </div>
          )}

          {status === "analyzing" && (
            <div className="analyzing-indicator">
              <span className="spinner" />
              <p className="status-msg status-msg--analyzing">
                Analyzing food image...
              </p>
            </div>
          )}

          {status === "error" && (
            <p className="status-msg status-msg--error">{errorMsg}</p>
          )}

          {status === "success" && analysis && (
            <>
              <p className="scan-timestamp">
                Scanned at {new Date().toLocaleString()}
              </p>
              <NutritionAnalysis analysis={analysis} />
            </>
          )}

          <div className="preview-actions">
            {status !== "uploading" &&
              status !== "analyzing" &&
              status !== "success" && (
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
