import useImageAnalysis from "../../hooks/useImageAnalysis";
import useDropzone from "../../hooks/useDropzone";
import NutritionAnalysis from "../NutritionAnalysis/NutritionAnalysis";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Camera, Eye, Loader2, Upload, X } from "lucide-react";

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
    cameraOpen,
    openCamera,
    closeCamera,
    capturePhoto,
    videoRef,
    canvasRef,
  } = useImageAnalysis(onScanComplete);

  const { dragging, onDrop, onDragOver, onDragLeave } = useDropzone((file) => {
    handleFile(file);
  });

  const isLoading = status === "uploading" || status === "analyzing";

  return (
    <div className="my-15 container">
      {/* ── Brand header ── */}
      <div className="text-center mb-8 z-10 relative">
        <h1 className="text-7xl md:text-8xl lg:text-9xl inline mr-8 font-medium">
          Nutra<span className="text-green-600">Smart</span>
        </h1>
      </div>

      {/* ── Card ── */}
      <Card className="w-full max-w-4xl mx-auto z-10 relative">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Eye className="h-5 w-5" />
            Food Analysis &amp; Nutrition
          </CardTitle>
          <CardDescription>
            Upload food images to get detailed nutritional information, calorie
            counts, and ingredient analysis powered by AI
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-6">
          {/* ── Dropzone or file-item row ── */}
          {!preview ? (
            <div
              className={[
                "border-2 border-dashed rounded-lg p-8 flex flex-col items-center gap-1 cursor-pointer transition-colors",
                dragging
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-muted-foreground/50 hover:bg-muted/30",
                isLoading ? "opacity-50 pointer-events-none" : "",
              ].join(" ")}
              onDrop={onDrop}
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onClick={() => !isLoading && fileInputRef.current?.click()}
            >
              <input
                type="file"
                accept="image/*"
                ref={fileInputRef}
                onChange={handleFileChange}
                hidden
              />
              <div className="flex items-center justify-center rounded-full border p-2.5">
                <Upload className="size-6 text-muted-foreground" />
              </div>
              <p className="font-medium text-sm">
                Drag &amp; drop a food image here
              </p>
              <p className="text-muted-foreground text-xs">
                Or click to browse (up to 4 MB)
              </p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-2 w-fit"
                onClick={(e) => {
                  e.stopPropagation();
                  fileInputRef.current?.click();
                }}
                disabled={isLoading}
              >
                Browse files
              </Button>
            </div>
          ) : (
            /* ── Uploaded file row + results ── */
            <div className="space-y-3">
              {/* progress bar */}
              {isLoading && (
                <div className="h-1 w-full rounded-full bg-secondary overflow-hidden">
                  <div
                    className="h-full bg-primary rounded-full transition-all duration-300"
                    style={{
                      width: status === "analyzing" ? "95%" : `${progress}%`,
                    }}
                  />
                </div>
              )}

              {/* file item row */}
              <div className="flex items-center gap-2 border rounded-lg px-3 py-2.5">
                <div className="relative size-10 shrink-0">
                  <img
                    src={preview}
                    alt="Food preview"
                    className="size-10 rounded object-cover"
                  />
                </div>
                <div className="flex flex-col flex-1 min-w-0 gap-0.5">
                  <span className="text-sm font-medium truncate">
                    Selected image
                  </span>
                  {isLoading && (
                    <span className="text-xs text-muted-foreground">
                      {status === "uploading"
                        ? `Uploading… ${progress}%`
                        : "Analyzing food image…"}
                    </span>
                  )}
                  {status === "success" && (
                    <span className="text-xs text-green-600">
                      Analysis complete ✓
                    </span>
                  )}
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="size-7 shrink-0"
                  onClick={handleRemove}
                  disabled={isLoading}
                  title={status === "success" ? "Upload another" : "Remove"}
                >
                  {isLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <X className="h-4 w-4" />
                  )}
                </Button>
              </div>

              {/* nutrition results */}
              {status === "success" && analysis && (
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">
                    Scanned at {new Date().toLocaleString()}
                  </p>
                  <NutritionAnalysis analysis={analysis} />
                </div>
              )}
            </div>
          )}

          {/* ── Divider ── */}
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background px-2 text-muted-foreground">
                Or
              </span>
            </div>
          </div>

          {/* ── Camera section ── */}
          <div className="border rounded-lg p-4">
            {!cameraOpen ? (
              <div className="flex flex-col items-center gap-2">
                <div className="flex items-center justify-center rounded-full border p-2.5">
                  <Camera className="size-6 text-muted-foreground" />
                </div>
                <p className="font-medium text-sm">Take a photo</p>
                <p className="text-muted-foreground text-xs text-center">
                  Use your device camera to capture food images
                </p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-2"
                  onClick={openCamera}
                  disabled={isLoading || !!preview}
                >
                  <Camera className="mr-2 h-4 w-4" />
                  Open Camera
                </Button>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-4">
                <div className="relative w-full aspect-video bg-black rounded-lg overflow-hidden">
                  <video
                    ref={videoRef}
                    autoPlay
                    playsInline
                    muted
                    className="w-full h-full object-cover"
                  />
                </div>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    size="sm"
                    onClick={capturePhoto}
                    disabled={isLoading}
                  >
                    <Camera className="mr-2 h-4 w-4" />
                    Capture Photo
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={closeCamera}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            )}
          </div>

          {/* Hidden canvas for camera capture */}
          <canvas ref={canvasRef} className="hidden" />

          {/* ── Error alert ── */}
          {status === "error" && errorMsg && (
            <Alert variant="destructive">
              <AlertDescription>{errorMsg}</AlertDescription>
            </Alert>
          )}

          {/* ── Analyze button ── */}
          {preview && status !== "success" && (
            <Button
              type="button"
              className="w-full"
              size="lg"
              onClick={handleUpload}
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {status === "uploading"
                    ? `Uploading… ${progress}%`
                    : "Analyzing Image & Getting Nutrition Data…"}
                </>
              ) : (
                <>
                  <Eye className="mr-2 h-4 w-4" />
                  Analyze Image &amp; Get Nutrition Info
                </>
              )}
            </Button>
          )}

          {/* ── Upload another after success ── */}
          {status === "success" && (
            <Button
              type="button"
              variant="outline"
              className="w-full"
              size="lg"
              onClick={handleRemove}
            >
              Upload Another Image
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
