import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@radix-ui/react-collapsible";
import {
  Activity,
  Utensils,
  ShieldAlert,
  ChevronDown,
  ChevronRight,
  ImageIcon,
  Info,
  Lightbulb,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface NutritionData {
  food_name: string;
  serving_qty: number;
  serving_unit: string;
  serving_weight_grams: number;
  nf_calories: number;
  nf_total_fat: number;
  nf_saturated_fat?: number;
  nf_cholesterol?: number;
  nf_sodium?: number;
  nf_total_carbohydrate: number;
  nf_dietary_fiber: number;
  nf_sugars: number;
  nf_protein: number;
}

export interface Dish {
  name: string;
  servingSize: string;
  nutrition?: NutritionData;
  error?: string;
}

export interface TotalNutrition {
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
  fiber: number;
  sodium: number;
}

export interface SingleAnalysis {
  imageKey: string;
  imageName?: string;
  imageUrl?: string;
  description: string;
  confidence?: number;
  allergens?: string[];
  objects?: string[];
  dishes?: Dish[];
  totalNutrition?: TotalNutrition;
  // Flat string fields from the API (e.g. "Bread: ~12g | Burger: ~35g | Total: ~47g")
  calories?: string;
  protein?: string;
  carbs?: string;
  fat?: string;
  fiber?: string;
  sugar?: string;
  sodium?: string;
  weight?: string;
  summary?: string;
  recommendation?: string;
}

export interface NutritionAnalysisProps {
  analyses: SingleAnalysis[];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Extracts the "Total: ~1000" value from strings like
 * "Bread slice: ~380 kcal | Burger: ~620 kcal | Total: ~1000 kcal"
 * Falls back to the last number found in the string.
 */
function parseTotal(str?: string | number): number {
  if (str === undefined || str === null) return 0;
  if (typeof str === "number") return str;
  const totalMatch = str.match(/Total:\s*~?([\d.]+)/i);
  if (totalMatch) return parseFloat(totalMatch[1]);
  const allNums = [...str.matchAll(/~?([\d.]+)/g)];
  if (!allNums.length) return 0;
  return parseFloat(allNums[allNums.length - 1][1]);
}

function fmtN(value: number, unit = "g"): string {
  return `${Math.round(value * 10) / 10}${unit}`;
}

/**
 * Resolves the effective TotalNutrition for an analysis,
 * falling back to parsing the raw string fields if structured
 * data is absent.
 */
function resolveNutrition(a: SingleAnalysis): TotalNutrition | null {
  if (a.totalNutrition) return a.totalNutrition;
  const calories = parseTotal(a.calories);
  if (!calories) return null;
  return {
    calories,
    protein: parseTotal(a.protein),
    carbs:   parseTotal(a.carbs),
    fat:     parseTotal(a.fat),
    fiber:   parseTotal(a.fiber),
    sodium:  parseTotal(a.sodium),
  };
}

function hasActualFood(a: SingleAnalysis): boolean {
  if (a.dishes && a.dishes.length > 0) return true;
  if (resolveNutrition(a) !== null) return true;
  if (a.description && !a.description.toLowerCase().includes("no food")) return true;
  return false;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function NutritionGrid({ nutrition, large = false }: { nutrition: TotalNutrition; large?: boolean }) {
  const items = [
    { value: String(Math.round(nutrition.calories)), label: "Calories",  color: "green"  },
    { value: fmtN(nutrition.protein),               label: "Protein",   color: "blue"   },
    { value: fmtN(nutrition.carbs),                 label: "Carbs",     color: "orange" },
    { value: fmtN(nutrition.fat),                   label: "Fat",       color: "yellow" },
    { value: fmtN(nutrition.fiber),                 label: "Fiber",     color: "purple" },
    { value: fmtN(nutrition.sodium, " mg"),         label: "Sodium",    color: "red"    },
  ] as const;

  const colorMap = {
    green:  { val: "text-green-700",  sub: "text-green-600"  },
    blue:   { val: "text-blue-700",   sub: "text-blue-600"   },
    orange: { val: "text-orange-700", sub: "text-orange-600" },
    yellow: { val: "text-yellow-700", sub: "text-yellow-600" },
    purple: { val: "text-purple-700", sub: "text-purple-600" },
    red:    { val: "text-red-700",    sub: "text-red-600"    },
  };

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
      {items.map(({ value, label, color }) => (
        <div key={label} className="text-center">
          <div className={`${large ? "text-2xl" : "text-xl"} font-bold ${colorMap[color].val}`}>
            {value}
          </div>
          <div className={`text-sm ${colorMap[color].sub}`}>
            {label === "Calories" ? "Total Calories" : `Total ${label}`}
          </div>
        </div>
      ))}
    </div>
  );
}

function DishCard({ dish }: { dish: Dish }) {
  return (
    <Card className="border-l-4 border-l-green-400">
      <CardHeader className="pb-2 pt-3 px-4">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm capitalize">{dish.name}</CardTitle>
          <Badge variant="outline" className="text-xs">{dish.servingSize}</Badge>
        </div>
      </CardHeader>
      <CardContent className="px-4 pb-3">
        {dish.nutrition ? (
          <div className="space-y-2">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {[
                { val: String(Math.round(dish.nutrition.nf_calories)), label: "Calories",  bg: "bg-green-50",  vc: "text-green-700",  lc: "text-green-600"  },
                { val: fmtN(dish.nutrition.nf_protein),                label: "Protein",   bg: "bg-blue-50",   vc: "text-blue-700",   lc: "text-blue-600"   },
                { val: fmtN(dish.nutrition.nf_total_carbohydrate),     label: "Carbs",     bg: "bg-orange-50", vc: "text-orange-700", lc: "text-orange-600" },
                { val: fmtN(dish.nutrition.nf_total_fat),              label: "Fat",       bg: "bg-yellow-50", vc: "text-yellow-700", lc: "text-yellow-600" },
              ].map(({ val, label, bg, vc, lc }) => (
                <div key={label} className={`${bg} p-2 rounded text-center`}>
                  <div className={`text-sm font-semibold ${vc}`}>{val}</div>
                  <div className={`text-xs ${lc}`}>{label}</div>
                </div>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              Serving: {dish.nutrition.serving_qty} {dish.nutrition.serving_unit} ({dish.nutrition.serving_weight_grams}g)
            </p>
          </div>
        ) : (
          <Alert className="border-amber-200 bg-amber-50">
            <AlertDescription className="text-amber-800 text-sm">
              {dish.error ?? "Nutrition data not available for this dish"}
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}

function ImageDetail({ a }: { a: SingleAnalysis }) {
  const nutrition = resolveNutrition(a);
  const isFood = hasActualFood(a);

  if (!isFood) {
    return (
      <Alert>
        <Info className="h-4 w-4" />
        <AlertDescription>No food was detected in this image.</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-4">
      {/* Per-image nutrition summary */}
      {nutrition && (
        <Card className="bg-gradient-to-r from-blue-50 to-purple-50 border-blue-200 mt-5">
          <CardHeader className="pb-3">
            <CardTitle className="text-base text-blue-800">Image Nutritional Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {[
                { val: String(Math.round(nutrition.calories)),  label: "Calories", vc: "text-lg font-bold text-blue-700",   lc: "text-xs text-blue-600"   },
                { val: fmtN(nutrition.protein),                 label: "Protein",  vc: "text-sm font-semibold text-blue-700", lc: "text-xs text-blue-600" },
                { val: fmtN(nutrition.carbs),                   label: "Carbs",    vc: "text-sm font-semibold text-orange-700", lc: "text-xs text-orange-600" },
                { val: fmtN(nutrition.fat),                     label: "Fat",      vc: "text-sm font-semibold text-yellow-700", lc: "text-xs text-yellow-600" },
                { val: fmtN(nutrition.fiber),                   label: "Fiber",    vc: "text-sm font-semibold text-purple-700", lc: "text-xs text-purple-600" },
                { val: fmtN(nutrition.sodium, " mg"),           label: "Sodium",   vc: "text-sm font-semibold text-red-700",    lc: "text-xs text-red-600"    },
              ].map(({ val, label, vc, lc }) => (
                <div key={label} className="text-center">
                  <div className={vc}>{val}</div>
                  <div className={lc}>{label}</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Allergens */}
      {(a.allergens?.length ?? 0) > 0 && (
        <Card className="border-red-200 bg-red-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-red-700 flex items-center gap-2">
              <ShieldAlert className="h-4 w-4" /> Allergen Warning
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-1.5">
              {a.allergens!.map((al, i) => (
                <Badge key={i} variant="destructive" className="text-xs text-white">{al}</Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Dishes */}
      {(a.dishes?.length ?? 0) > 0 && (
        <div className="space-y-3">
          <h5 className="text-base font-semibold">Dishes in This Image</h5>
          {a.dishes!.map((dish, i) => <DishCard key={i} dish={dish} />)}
        </div>
      )}

      {/* Ingredients / objects */}
      {(a.objects?.length ?? 0) > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Ingredients Identified</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-1.5">
              {a.objects!.map((obj, i) => (
                <Badge key={i} variant="secondary" className="text-xs">{obj}</Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Description */}
      {a.description && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Image Description</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-relaxed text-muted-foreground">{a.description}</p>
            {a.confidence !== undefined && (
              <p className="text-xs text-muted-foreground mt-2">
                Confidence: {Math.round(a.confidence * 100)}%
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Summary */}
      {a.summary && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-relaxed text-muted-foreground">{a.summary}</p>
          </CardContent>
        </Card>
      )}

      {/* Recommendation */}
      {a.recommendation && (
        <Card className="border-green-200 bg-green-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-green-800 flex items-center gap-2">
              <Lightbulb className="h-4 w-4" /> Nutrition Recommendation
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-relaxed text-green-800">{a.recommendation}</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ─── Main export ──────────────────────────────────────────────────────────────

export default function NutritionAnalysis({ analyses }: NutritionAnalysisProps) {
  const [openKeys, setOpenKeys] = useState<Set<string>>(
    () => new Set(analyses.length > 0 ? [analyses[0].imageKey] : []),
  );

  const toggle = (key: string) =>
    setOpenKeys((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  // Aggregate totals across all analyses
  const allNutrition = analyses.map(resolveNutrition).filter(Boolean) as TotalNutrition[];
  const hasAnyCombinedData = allNutrition.length > 0;

  const totalCalories = allNutrition.reduce((s, n) => s + n.calories, 0);
  const combinedNutrition: TotalNutrition = {
    calories: allNutrition.reduce((s, n) => s + n.calories, 0),
    protein:  allNutrition.reduce((s, n) => s + n.protein, 0),
    carbs:    allNutrition.reduce((s, n) => s + n.carbs, 0),
    fat:      allNutrition.reduce((s, n) => s + n.fat, 0),
    fiber:    allNutrition.reduce((s, n) => s + n.fiber, 0),
    sodium:   allNutrition.reduce((s, n) => s + n.sodium, 0),
  };

  // Single-image shortcut: skip the collapsible wrapper
  if (analyses.length === 1) {
    return (
      <div className="space-y-6">
        {hasAnyCombinedData && (
          <>
            {/* Combined nutrition */}
            <Card className="bg-blue-100 border-blue-200">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg text-green-800 flex items-center gap-2">
                  <Utensils className="h-5 w-5" /> Combined Nutritional Information
                </CardTitle>
                <CardDescription className="text-green-600">
                  Total nutrition from this image
                </CardDescription>
              </CardHeader>
              <CardContent>
                <NutritionGrid nutrition={combinedNutrition} large />
              </CardContent>
            </Card>

            {/* Activity suggestions */}
            {totalCalories > 0 && (
              <Card className="bg-gradient-to-r from-purple-50 to-pink-50 border-purple-200">
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg text-purple-800 flex items-center gap-2">
                    <Activity className="h-5 w-5" /> Activity Suggestions
                  </CardTitle>
                  <CardDescription className="text-purple-600">
                    Approximate time to burn {Math.round(totalCalories)} calories
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {([
                      { label: "Running",  d: 10 },
                      { label: "Cycling",  d: 8  },
                      { label: "Walking",  d: 6  },
                      { label: "Swimming", d: 12 },
                    ] as const).map(({ label, d }) => (
                      <div key={label} className="text-center p-3 bg-white rounded-lg">
                        <div className="text-lg font-semibold text-purple-700">
                          {Math.round(totalCalories / d)} min
                        </div>
                        <div className="text-sm text-purple-600">{label}</div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </>
        )}

        <ImageDetail a={analyses[0]} />
      </div>
    );
  }

  // ── Multi-image ───────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">
      {/* Combined nutrition summary */}
      {hasAnyCombinedData && (
        <Card className="bg-blue-100 border-blue-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg text-green-800 flex items-center gap-2">
              <Utensils className="h-5 w-5" /> Combined Nutritional Information
            </CardTitle>
            <CardDescription className="text-green-600">
              Total nutrition from all {analyses.length} image{analyses.length !== 1 ? "s" : ""}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <NutritionGrid nutrition={combinedNutrition} large />
          </CardContent>
        </Card>
      )}

      {/* Activity suggestions */}
      {totalCalories > 0 && (
        <Card className="bg-gradient-to-r from-purple-50 to-pink-50 border-purple-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg text-purple-800 flex items-center gap-2">
              <Activity className="h-5 w-5" /> Activity Suggestions to Burn Total Calories
            </CardTitle>
            <CardDescription className="text-purple-600">
              Approximate time needed to burn {Math.round(totalCalories)} calories from all images
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {([
                { label: "Running",  d: 10 },
                { label: "Cycling",  d: 8  },
                { label: "Walking",  d: 6  },
                { label: "Swimming", d: 12 },
              ] as const).map(({ label, d }) => (
                <div key={label} className="text-center p-3 bg-white rounded-lg">
                  <div className="text-lg font-semibold text-purple-700">
                    {Math.round(totalCalories / d)} min
                  </div>
                  <div className="text-sm text-purple-600">{label}</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Individual image analysis */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Individual Image Analysis</h2>
          <div className="flex gap-1">
            <Button
              variant="ghost" size="sm" className="text-xs h-7 px-2"
              onClick={() => setOpenKeys(new Set(analyses.map((a) => a.imageKey)))}
            >
              Expand all
            </Button>
            <Button
              variant="ghost" size="sm" className="text-xs h-7 px-2"
              onClick={() => setOpenKeys(new Set())}
            >
              Collapse all
            </Button>
          </div>
        </div>

        {analyses.map((a, index) => {
          const nutrition = resolveNutrition(a);
          const calories  = nutrition?.calories;
          const isOpen    = openKeys.has(a.imageKey);
          const isFood    = hasActualFood(a);

          return (
            <Card key={a.imageKey} className="overflow-hidden">
              <Collapsible open={isOpen} onOpenChange={() => toggle(a.imageKey)}>
                <CollapsibleTrigger asChild>
                  <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        {/* Thumbnail */}
                        <div className="relative w-16 h-16 rounded-lg overflow-hidden flex-shrink-0 bg-muted">
                          {a.imageUrl ? (
                            <img
                              src={a.imageUrl}
                              alt={a.imageName ?? `Image ${index + 1}`}
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center">
                              <ImageIcon className="h-6 w-6 text-muted-foreground" />
                            </div>
                          )}
                        </div>
                        <div>
                          <CardTitle className="text-base">
                            Image {index + 1}{a.imageName ? `: ${a.imageName}` : ""}
                          </CardTitle>
                          <CardDescription>
                            {isFood && calories !== undefined
                              ? `${Math.round(calories)} calories`
                              : "Click to view details"}
                          </CardDescription>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        {isFood && calories !== undefined && calories > 0 && (
                          <Badge variant="secondary">{Math.round(calories)} cal</Badge>
                        )}
                        {!isFood && (
                          <Badge variant="outline" className="text-muted-foreground">No food</Badge>
                        )}
                        {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                      </div>
                    </div>
                  </CardHeader>
                </CollapsibleTrigger>

                <CollapsibleContent>
                  <CardContent className="space-y-6 pb-5">
                    <ImageDetail a={a} />
                  </CardContent>
                </CollapsibleContent>
              </Collapsible>
            </Card>
          );
        })}
      </div>
    </div>
  );
}