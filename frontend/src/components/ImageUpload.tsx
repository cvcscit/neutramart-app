"use client";

import useImageAnalysis from "../hooks/useImageAnalysis";
import useDropzone from "../hooks/useDropzone";
import NutritionAnalysis from "./NutritionAnalysis";
import { AddToProfileDialog } from "./add-to-profile";
import { ArrowLeft, Camera, Eye, Loader2, Plus, Upload, X } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import type {
  SingleAnalysis,
  AnalysisResult,
  TotalNutrition,
  UploadedImage,
} from "@/types";

type Props = {
  onScanComplete?: () => void;
};

// ─── Build SingleAnalysis[] from whatever the hook returns ───────────────────

/** Parse a numeric value from a string like "350 kcal", "25g", or a number. */
function parseNum(val: unknown): number {
  if (typeof val === "number") return val;
  if (!val || val === "N/A") return 0;
  const m = String(val).match(/[\d.]+/);
  return m ? parseFloat(m[0]) : 0;
}

/**
 * Convert the flat Bedrock response (calories/protein/etc. as strings)
 * into a SingleAnalysis with a synthetic dish + totalNutrition so the
 * rest of the UI (NutritionAnalysis, AddToProfileDialog) works correctly.
 */
function flatResponseToAnalysis(
  r: Record<string, unknown>,
  preview: string,
  file: File | undefined,
  index: number,
): SingleAnalysis {
  const calories = parseNum(r.calories);
  const protein  = parseNum(r.protein);
  const carbs    = parseNum(r.carbs);
  const fat      = parseNum(r.fat);
  const fiber    = parseNum(r.fiber);
  const sugar    = parseNum(r.sugar);
  const weight   = String(r.weight ?? "1 serving");

  const totalNutrition: TotalNutrition = { calories, protein, carbs, fat, fiber, sugar };

  const dish = {
    name:        (r.description as string) ?? "Meal",
    servingSize: weight,
    nutrition: {
      food_name:             (r.description as string) ?? "Meal",
      serving_qty:           1,
      serving_unit:          "serving",
      serving_weight_grams:  parseNum(weight),
      nf_calories:           calories,
      nf_total_fat:          fat,
      nf_total_carbohydrate: carbs,
      nf_dietary_fiber:      fiber,
      nf_sugars:             sugar,
      nf_protein:            protein,
      nf_sodium:             0,
    },
  };

  return {
    imageKey:        `img-${index}`,
    imageUrl:        preview,
    imageName:       file?.name ?? `Image ${index + 1}`,
    description:     (r.description     as string)   ?? "",
    confidence:      (r.confidence      as number)   ?? 0.9,
    allergens:       (r.allergens       as string[]) ?? [],
    objects:         (r.objects         as string[]) ?? [],
    dishes:          [dish],
    totalNutrition,
    recommendation:  (r.recommendation  as string)   ?? undefined,
  };
}

function buildAnalyses(
  raw: unknown,
  previews: string[],
  files: File[],
): SingleAnalysis[] {
  if (!raw) return [];

  const r = raw as Record<string, unknown>;

  // 1. Already a bare array
  if (Array.isArray(raw)) {
    return (raw as Record<string, unknown>[]).map((a, i) => ({
      ...a,
      imageKey:  (a.imageKey  as string | undefined) ?? `img-${i}`,
      imageUrl:  (a.imageUrl  as string | undefined) ?? previews[i],
      imageName: (a.imageName as string | undefined) ?? files[i]?.name,
    })) as SingleAnalysis[];
  }

  // 2. Wrapped array under a known key
  const wrapped =
    Array.isArray(r.analyses) ? (r.analyses as Record<string, unknown>[]) :
    Array.isArray(r.results)  ? (r.results  as Record<string, unknown>[]) :
    Array.isArray(r.images)   ? (r.images   as Record<string, unknown>[]) :
    undefined;

  if (wrapped) {
    return wrapped.map((a, i) => ({
      ...a,
      imageKey:  (a.imageKey  as string | undefined) ?? `img-${i}`,
      imageUrl:  (a.imageUrl  as string | undefined) ?? previews[i],
      imageName: (a.imageName as string | undefined) ?? files[i]?.name,
    })) as SingleAnalysis[];
  }

  // 3. Flat structured object with dishes/totalNutrition already present
  if (r.dishes !== undefined || r.totalNutrition !== undefined) {
    return previews.map((preview, i) => ({
      imageKey:       `img-${i}`,
      imageUrl:       preview,
      imageName:      files[i]?.name ?? `Image ${i + 1}`,
      description:    (r.description as string)               ?? "",
      confidence:     (r.confidence  as number)               ?? 0.9,
      allergens:      (r.allergens   as string[])             ?? [],
      objects:        (r.objects     as string[])             ?? [],
      dishes:         (r.dishes          as SingleAnalysis["dishes"]) ?? [],
      totalNutrition: (r.totalNutrition  as TotalNutrition | undefined),
      recommendation: (r.recommendation as string | undefined),
    }));
  }

  // 4. Flat Bedrock response (calories/protein as strings) — convert to structured
  return previews.map((preview, i) =>
    flatResponseToAnalysis(r, preview, files[i], i),
  );
}

// ─── Sum TotalNutrition across multiple analyses ──────────────────────────────

function sumTotalNutrition(analyses: SingleAnalysis[]): TotalNutrition | undefined {
  const withNutrition = analyses.filter((a) => a.totalNutrition);
  if (withNutrition.length === 0) return undefined;
  return withNutrition.reduce(
    (acc, a) => ({
      calories: acc.calories + a.totalNutrition!.calories,
      protein:  acc.protein  + a.totalNutrition!.protein,
      carbs:    acc.carbs    + a.totalNutrition!.carbs,
      fat:      acc.fat      + a.totalNutrition!.fat,
      fiber:    acc.fiber    + a.totalNutrition!.fiber,
      sugar:    acc.sugar    + a.totalNutrition!.sugar,
    }),
    { calories: 0, protein: 0, carbs: 0, fat: 0, fiber: 0, sugar: 0 },
  );
}

// ─── Build AnalysisResult for AddToProfileDialog ──────────────────────────────
// imageIndex = undefined  →  combined "save all" payload
// imageIndex = N          →  single image payload

function toAnalysisResult(
  analyses: SingleAnalysis[],
  imageIndex?: number,
): AnalysisResult {
  if (imageIndex !== undefined) {
    const a = analyses[imageIndex];
    const uploadedImages: UploadedImage[] = a.imageUrl
      ? [{ url: a.imageUrl, key: a.imageKey, name: a.imageName ?? a.imageKey }]
      : [];
    return {
      description:    a.description,
      confidence:     a.confidence,
      allergens:      a.allergens,
      objects:        a.objects,
      dishes:         a.dishes,
      totalNutrition: a.totalNutrition,
      uploadedImages,
    };
  }

  // Combined
  return {
    description: `Combined meal from ${analyses.length} image${analyses.length !== 1 ? "s" : ""}`,
    allergens:   [...new Set(analyses.flatMap((a) => a.allergens ?? []))],
    objects:     [...new Set(analyses.flatMap((a) => a.objects   ?? []))],
    dishes:      analyses.flatMap((a) => a.dishes ?? []),
    totalNutrition: sumTotalNutrition(analyses),
    uploadedImages: analyses
      .filter((a) => a.imageUrl)
      .map((a) => ({ url: a.imageUrl!, key: a.imageKey, name: a.imageName ?? a.imageKey })),
  };
}

// ─── Component ────────────────────────────────────────────────────────────────

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

  const { dragging, onDrop, onDragOver, onDragLeave } = useDropzone((dropped) =>
    addFiles(dropped),
  );

  const isLoading = status === "uploading" || status === "analyzing";
  const hasImages = previews.length > 0;
  const canAddMore =
    previews.length < maxImages && !isLoading && status !== "success";

  const analyses = buildAnalyses(analysis, previews, files);
  const isMulti  = analyses.length > 1;

  const allDishesWithNutrition = analyses.flatMap(
    (a) => (a.dishes ?? []).filter((d) => d.nutrition),
  );

  return (
    <div className="my-15 container m-auto">
      {/* ── Brand header ── */}
      <div className="text-center mb-8 z-10 relative">
        <h1 className="text-7xl md:text-8xl lg:text-9xl inline mr-8 font-medium">
          Nutra<span className="text-green-600">Smart</span>
        </h1>
      </div>

      {/* ── Results view ── */}
      {status === "success" && analysis ? (
        <div className="space-y-4">
          <div className="w-full max-w-4xl mx-auto z-10 relative">
            <Button variant="outline" onClick={() => handleRemove()} className="gap-2">
              <ArrowLeft className="h-4 w-4" />
              New Analysis
            </Button>
          </div>

          <Card className="w-full max-w-4xl mx-auto z-10 relative">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Eye className="h-5 w-5" />
                Results
              </CardTitle>
              <CardDescription>
                Food nutrition analysis powered by AI. Scanned at{" "}
                {new Date().toLocaleString()}.
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4">
              {/* ── Save All (multi-image only, shown above the analysis) ── */}
              {isMulti && allDishesWithNutrition.length > 0 && (
                <AddToProfileDialog
                  analysisResult={toAnalysisResult(analyses)}
                  onSave={() => {}}
                  imageSpecific={false}
                  triggerButton={
                    <Button size="lg" className="w-full gap-2">
                      <Plus className="h-5 w-5" />
                      Save All to Profile ({allDishesWithNutrition.length} dish
                      {allDishesWithNutrition.length !== 1 ? "es" : ""} across{" "}
                      {analyses.length} images)
                    </Button>
                  }
                />
              )}

              {/*
               * NutritionAnalysis receives a renderImageAction prop so it can
               * inject a per-image "Save to Profile" button inside each
               * collapsible panel — scoped to that image's dishes only.
               */}
              <NutritionAnalysis
                analyses={analyses}
                renderImageAction={(a:any, index:any) => {
                  const imageDishes = (a.dishes ?? []).filter((d:any) => d.nutrition);
                  if (!a.totalNutrition && imageDishes.length === 0) return null;
                  return (
                    <AddToProfileDialog
                      analysisResult={toAnalysisResult(analyses, index)}
                      onSave={() => {}}
                      imageSpecific
                      imageName={a.imageName ?? `Image ${index + 1}`}
                      triggerButton={
                        <Button variant="outline" size="sm" className="w-full gap-2">
                          <Plus className="h-4 w-4" />
                          Save Image {index + 1} to Profile
                          {imageDishes.length > 0
                            ? ` (${imageDishes.length} dish${imageDishes.length !== 1 ? "es" : ""})`
                            : ""}
                        </Button>
                      }
                    />
                  );
                }}
              />

              {/* ── Save (single-image, shown below the analysis) ── */}
              {!isMulti && allDishesWithNutrition.length > 0 && (
                <AddToProfileDialog
                  analysisResult={toAnalysisResult(analyses)}
                  onSave={() => {}}
                  imageSpecific={false}
                  triggerButton={
                    <Button size="lg" className="w-full gap-2">
                      <Plus className="h-5 w-5" />
                      Save to Profile ({allDishesWithNutrition.length} dish
                      {allDishesWithNutrition.length !== 1 ? "es" : ""})
                    </Button>
                  }
                />
              )}
            </CardContent>
          </Card>
        </div>
      ) : (
        /* ── Upload view ── */
        <Card className="w-full max-w-4xl mx-auto z-10 relative">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Eye className="h-5 w-5" />
              Food Analysis
            </CardTitle>
            <CardDescription>
              Upload up to {maxImages} food images to get detailed nutritional
              information powered by AI
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-6">
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
              <div className="space-y-3">
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

                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">
                    {isLoading
                      ? status === "uploading"
                        ? `Uploading… ${progress}%`
                        : "Analyzing food images…"
                      : status === "success"
                        ? "Analysis complete ✓"
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
              </div>
            )}

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-background px-2 text-muted-foreground">Or</span>
              </div>
            </div>

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
                    <Button type="button" size="sm" onClick={capturePhoto} disabled={isLoading}>
                      <Camera className="mr-2 h-4 w-4" />
                      Capture Photo
                    </Button>
                    <Button type="button" variant="outline" size="sm" onClick={closeCamera}>
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
            </div>

            <canvas ref={canvasRef} className="hidden" />

            {status === "error" && errorMsg && (
              <Alert variant="destructive">
                <AlertDescription>{errorMsg}</AlertDescription>
              </Alert>
            )}

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
                    {files.length > 1 ? `${files.length} Images` : "Image"}{" "}
                    &amp; Get Nutrition Info
                  </>
                )}
              </Button>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}