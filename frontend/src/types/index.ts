// src/types/index.ts
import type { ReactNode } from "react";

// ─── Raw per-dish nutrition (from Nutritionix / backend) ─────────────────────

export interface NutritionData {
    food_name: string;
    serving_qty: number;
    serving_unit: string;
    serving_weight_grams: number;
    nf_calories: number;
    nf_total_fat: number;
    nf_total_carbohydrate: number;
    nf_dietary_fiber: number;
    nf_sugars: number;
    nf_protein: number;
    nf_sodium?: number;
    nf_saturated_fat?: number;
    nf_cholesterol?: number;
  }
  
  // ─── A single identified dish inside an image ────────────────────────────────
  
  export interface Dish {
    name: string;
    servingSize: string;
    nutrition?: NutritionData;
    error?: string;
  }
  
  // ─── Summed totals for an image or a combined set of images ──────────────────
  
  export interface TotalNutrition {
    calories: number;
    protein: number;
    carbs: number;
    fat: number;
    fiber: number;
    sugar: number;
  }
  
  // ─── One uploaded image reference ────────────────────────────────────────────
  
  export interface UploadedImage {
    url: string;
    key: string;
    name: string;
  }
  
  // ─── What the backend returns per image after analysis ───────────────────────
  
  export interface SingleAnalysis {
    /** Stable key used as React key and collapse-state ID */
    imageKey: string;
    imageName?: string;
    imageUrl?: string;
  
    description: string;
    confidence?: number;
    allergens?: string[];
    /** Ingredient / food-object tags */
    objects?: string[];
    dishes?: Dish[];
    totalNutrition?: TotalNutrition;
    micronutrients?: Record<string, string>;
    recommendation?: string;
  }

  // ─── What AddToProfileDialog receives as `analysisResult` ────────────────────
  // Intentionally looser than SingleAnalysis so it can be built for both
  // "save one image" and "save all images" scenarios.
  
  export interface AnalysisResult {
    description?: string;
    confidence?: number;
    allergens?: string[];
    objects?: string[];
    dishes?: Dish[];
    totalNutrition?: TotalNutrition;
    uploadedImages?: UploadedImage[];
  }
  
  // ─── AddToProfileDialog props ─────────────────────────────────────────────────
  
  export interface AddToProfileDialogProps {
    analysisResult: AnalysisResult;
    onSave: () => void;
    /** True when saving a single image rather than the combined total */
    imageSpecific?: boolean;
    /** Label shown in the dialog header when imageSpecific is true */
    imageName?: string;
    /** Custom trigger element; defaults to a full-width "Add to Profile" button */
    triggerButton?: ReactNode;
  }
  
  // ─── POST /api/meals request body (mirrors meals.py Pydantic models) ─────────
  
  export interface SaveMealRequest {
    mealName: string;
    mealType: "breakfast" | "lunch" | "dinner" | "snack" | "other";
    description: string;
    imageUrl: string;
    totalNutrition: TotalNutrition;
    dishes: Array<{
      name: string;
      servingSize: string;
      nutrition?: NutritionData;
    }>;
  }
  
  // ─── GET /api/meals response ──────────────────────────────────────────────────
  
  export interface SavedMeal {
    meal_id: string;
    meal_name: string;
    meal_type: string;
    description: string;
    image_url: string;
    logged_at: string;
    total_nutrition: TotalNutrition;
    dishes: Array<{
      name: string;
      servingSize: string;
      nutrition?: NutritionData;
    }>;
  }

  export interface NutritionAnalysisProps {
    analyses: SingleAnalysis[];
    renderImageAction?: (
      analysis: SingleAnalysis,
      index: number,
    ) => ReactNode;
  }