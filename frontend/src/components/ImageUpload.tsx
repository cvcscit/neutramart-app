import useImageAnalysis from "../hooks/useImageAnalysis";
import useDropzone from "../hooks/useDropzone";
import NutritionAnalysis from "./NutritionAnalysis/NutritionAnalysis";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Camera, Eye, Loader2, Plus, Upload, X } from "lucide-react";

type Props = {
  onScanComplete?: () => void;
};

export default function ImageUpload({ onScanComplete }: Props) {
  const {
    files,
    previews,
    progress,
    status,
    errorMsg,
    analysis,
    maxImages,
    fileInputRef,
    handleFileChange,
    handleRemove,
    handleUpload,
    addFiles,
    cameraOpen,
    openCamera,
    closeCamera,
    capturePhoto,
    videoRef,
    canvasRef,
  } = useImageAnalysis(onScanComplete);

  const { dragging, onDrop, onDragOver, onDragLeave } = useDropzone(
    (dropped) => {
      addFiles(dropped);
    },
  );

  const isLoading = status === "uploading" || status === "analyzing";
  const hasImages = previews.length > 0;
  const canAddMore =
    previews.length < maxImages && !isLoading && status !== "success";

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
            Upload up to {maxImages} food images to get detailed nutritional
            information powered by AI
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-6">
          {/* ── Dropzone (shown when no images or can add more) ── */}
          {!hasImages ? (
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
                multiple
                ref={fileInputRef}
                onChange={handleFileChange}
                hidden
              />
              <div className="flex items-center justify-center rounded-full border p-2.5">
                <Upload className="size-6 text-muted-foreground" />
              </div>
              <p className="font-medium text-sm">
                Drag &amp; drop food images here
              </p>
              <p className="text-muted-foreground text-xs">
                Or click to browse · up to {maxImages} images · 4 MB each
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
            /* ── Image grid + results ── */
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

              {/* image thumbnails grid */}
              <div className="flex flex-wrap gap-2">
                {previews.map((src, i) => (
                  <div
                    key={i}
                    className="relative size-20 rounded-lg overflow-hidden border group"
                  >
                    <img
                      src={src}
                      alt={`Food image ${i + 1}`}
                      className="size-20 object-cover"
                    />
                    {!isLoading && status !== "success" && (
                      <button
                        type="button"
                        onClick={() => handleRemove(i)}
                        className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <X className="size-5 text-white" />
                      </button>
                    )}
                  </div>
                ))}

                {/* Add more button */}
                {canAddMore && (
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="size-20 rounded-lg border-2 border-dashed border-border flex flex-col items-center justify-center gap-1 text-muted-foreground hover:border-muted-foreground/50 hover:bg-muted/30 transition-colors"
                  >
                    <Plus className="size-5" />
                    <span className="text-xs">Add</span>
                  </button>
                )}

                <input
                  type="file"
                  accept="image/*"
                  multiple
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  hidden
                />
              </div>

              {/* status line */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">
                  {isLoading
                    ? status === "uploading"
                      ? `Uploading… ${progress}%`
                      : "Analyzing food images…"
                    : status === "success"
                      ? `Analysis complete ✓`
                      : `${files.length} image${files.length > 1 ? "s" : ""} selected`}
                </span>
                {!isLoading && status !== "success" && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-6 text-xs text-muted-foreground"
                    onClick={() => handleRemove()}
                  >
                    Remove all
                  </Button>
                )}
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
                  disabled={isLoading || (!canAddMore && hasImages)}
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
          {hasImages && status !== "success" && (
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
                    : "Analyzing Images & Getting Nutrition Data…"}
                </>
              ) : (
                <>
                  <Eye className="mr-2 h-4 w-4" />
                  Analyze{" "}
                  {files.length > 1 ? `${files.length} Images` : "Image"} &amp;
                  Get Nutrition Info
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
              onClick={() => handleRemove()}
            >
              Upload Another Image
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
