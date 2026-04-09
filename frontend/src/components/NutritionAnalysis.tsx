"use client";

import { useState } from "react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChevronDown, ChevronUp, Lightbulb, ShieldAlert, Utensils } from "lucide-react";

import type { NutritionAnalysisProps } from "@/types";

function fmtN(value: number, unit = "g"): string {
  return `${Math.round(value * 10) / 10}${unit}`;
}

export default function NutritionAnalysis({
  analyses,
  renderImageAction,
}: NutritionAnalysisProps) {
  const [openMap, setOpenMap] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(analyses.map((a) => [a.imageKey, true])),
  );

  const toggle = (key: string) =>
    setOpenMap((prev) => ({ ...prev, [key]: !prev[key] }));

  if (analyses.length === 0) return null;

  return (
    <div className="space-y-4">
      {analyses.map((analysis, index) => {
        const dishesWithNutrition = (analysis.dishes ?? []).filter(
          (d) => d.nutrition,
        );
        const isOpen = openMap[analysis.imageKey] ?? true;

        return (
          <Collapsible
            key={analysis.imageKey}
            open={isOpen}
            onOpenChange={() => toggle(analysis.imageKey)}
          >
            <Card>
              <CardHeader className="pb-3">
                <CollapsibleTrigger asChild>
                  <button
                    type="button"
                    className="flex items-center justify-between w-full text-left"
                  >
                    <CardTitle className="text-base flex items-center gap-2">
                      <Utensils className="h-4 w-4" />
                      {analysis.imageName ?? `Image ${index + 1}`}
                      {analysis.confidence !== undefined && (
                        <Badge variant="secondary" className="text-xs font-normal">
                          {Math.round(analysis.confidence * 100)}% confidence
                        </Badge>
                      )}
                    </CardTitle>
                    {isOpen ? (
                      <ChevronUp className="h-4 w-4 text-muted-foreground shrink-0" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
                    )}
                  </button>
                </CollapsibleTrigger>
              </CardHeader>

              <CollapsibleContent>
                <CardContent className="space-y-4 pt-0">
                  {/* Image thumbnail */}
                  {analysis.imageUrl && (
                    <img
                      src={analysis.imageUrl}
                      alt={analysis.imageName ?? `Food image ${index + 1}`}
                      className="w-full max-h-48 object-cover rounded-lg"
                    />
                  )}

                  {/* Description */}
                  {analysis.description && (
                    <p className="text-sm text-muted-foreground">
                      {analysis.description}
                    </p>
                  )}

                  {/* Total nutrition */}
                  {analysis.totalNutrition && (
                    <Card className="bg-gradient-to-r from-green-50 to-blue-50 border-green-200">
                      <CardContent className="pt-4">
                        <p className="text-sm font-semibold text-green-800 mb-3">
                          Total Nutrition
                        </p>
                        <div className="grid grid-cols-3 gap-3">
                          <div className="text-center">
                            <div className="text-xl font-bold text-green-700">
                              {Math.round(analysis.totalNutrition.calories)}
                            </div>
                            <div className="text-xs text-green-600">Calories</div>
                          </div>
                          <div className="text-center">
                            <div className="text-lg font-semibold text-blue-700">
                              {fmtN(analysis.totalNutrition.protein)}
                            </div>
                            <div className="text-xs text-blue-600">Protein</div>
                          </div>
                          <div className="text-center">
                            <div className="text-lg font-semibold text-orange-700">
                              {fmtN(analysis.totalNutrition.carbs)}
                            </div>
                            <div className="text-xs text-orange-600">Carbs</div>
                          </div>
                          <div className="text-center">
                            <div className="text-lg font-semibold text-yellow-700">
                              {fmtN(analysis.totalNutrition.fat)}
                            </div>
                            <div className="text-xs text-yellow-600">Fat</div>
                          </div>
                          <div className="text-center">
                            <div className="text-lg font-semibold text-purple-700">
                              {fmtN(analysis.totalNutrition.fiber)}
                            </div>
                            <div className="text-xs text-purple-600">Fiber</div>
                          </div>
                          <div className="text-center">
                            <div className="text-lg font-semibold text-red-700">
                              {fmtN(analysis.totalNutrition.sugar)}
                            </div>
                            <div className="text-xs text-red-600">Sugar</div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Micronutrients */}
                  {analysis.micronutrients && (
                    <Card className="bg-gradient-to-r from-purple-50 to-pink-50 border-purple-200">
                      <CardContent className="pt-4">
                        <p className="text-sm font-semibold text-purple-800 mb-3">
                          Micronutrients
                        </p>
                        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                          {[
                            { key: "vitamin_a", label: "Vit A", color: "text-orange-700" },
                            { key: "vitamin_c", label: "Vit C", color: "text-yellow-700" },
                            { key: "vitamin_d", label: "Vit D", color: "text-amber-700" },
                            { key: "vitamin_b12", label: "Vit B12", color: "text-pink-700" },
                            { key: "iron", label: "Iron", color: "text-red-700" },
                            { key: "calcium", label: "Calcium", color: "text-blue-700" },
                            { key: "potassium", label: "Potassium", color: "text-green-700" },
                            { key: "sodium", label: "Sodium", color: "text-slate-700" },
                            { key: "zinc", label: "Zinc", color: "text-teal-700" },
                            { key: "magnesium", label: "Magnesium", color: "text-indigo-700" },
                          ].map((item) => {
                            const val = analysis.micronutrients?.[item.key];
                            if (!val || val === "N/A") return null;
                            return (
                              <div key={item.key} className="text-center">
                                <div className={`text-sm font-semibold ${item.color}`}>
                                  {val}
                                </div>
                                <div className="text-xs text-muted-foreground">{item.label}</div>
                              </div>
                            );
                          })}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Dishes */}
                  {dishesWithNutrition.length > 0 && (
                    <div className="space-y-3">
                      <p className="text-sm font-semibold">Dishes in This Image</p>
                      {dishesWithNutrition.map((dish, di) => (
                        <Card key={di} className="border">
                          <CardContent className="pt-4 pb-3">
                            <div className="flex items-center justify-between mb-3">
                              <p className="font-semibold text-base capitalize">
                                {dish.name}
                              </p>
                              <Badge variant="outline" className="text-xs shrink-0">
                                {dish.servingSize}
                              </Badge>
                            </div>
                            {dish.nutrition && (
                              <>
                                <div className="grid grid-cols-4 gap-3 mb-2">
                                  <div className="text-center">
                                    <div className="text-lg font-bold text-green-700">
                                      {Math.round(dish.nutrition.nf_calories)}
                                    </div>
                                    <div className="text-xs text-muted-foreground">Calories</div>
                                  </div>
                                  <div className="text-center">
                                    <div className="text-lg font-semibold text-blue-700">
                                      {fmtN(dish.nutrition.nf_protein)}
                                    </div>
                                    <div className="text-xs text-muted-foreground">Protein</div>
                                  </div>
                                  <div className="text-center">
                                    <div className="text-lg font-semibold text-orange-700">
                                      {fmtN(dish.nutrition.nf_total_carbohydrate)}
                                    </div>
                                    <div className="text-xs text-muted-foreground">Carbs</div>
                                  </div>
                                  <div className="text-center">
                                    <div className="text-lg font-semibold text-yellow-700">
                                      {fmtN(dish.nutrition.nf_total_fat)}
                                    </div>
                                    <div className="text-xs text-muted-foreground">Fat</div>
                                  </div>
                                </div>
                                <p className="text-xs text-muted-foreground">
                                  Serving: {dish.nutrition.serving_weight_grams}g
                                </p>
                              </>
                            )}
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  )}

                  {/* Ingredients / Objects Identified */}
                  {analysis.objects && analysis.objects.length > 0 && (
                    <Card className="border-blue-200 bg-blue-50">
                      <CardContent className="py-3">
                        <p className="text-sm font-semibold text-blue-800 mb-2">
                          Ingredients Identified
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {analysis.objects.map((obj, oi) => (
                            <Badge key={oi} variant="secondary" className="text-xs">
                              {obj}
                            </Badge>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Allergens */}
                  {analysis.allergens && analysis.allergens.length > 0 && (
                    <Card className="border-red-200 bg-red-50">
                      <CardContent className="py-3">
                        <div className="flex items-center gap-2 mb-2">
                          <ShieldAlert className="h-4 w-4 text-red-600" />
                          <p className="text-sm font-semibold text-red-700">
                            Allergens
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {analysis.allergens.map((allergen, ai) => (
                            <Badge
                              key={ai}
                              variant="destructive"
                              className="text-xs"
                            >
                              {allergen}
                            </Badge>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Recommendation */}
                  {analysis.recommendation && (
                    <Card className="border-green-200 bg-green-50">
                      <CardContent className="py-3">
                        <div className="flex items-center gap-2 mb-2">
                          <Lightbulb className="h-4 w-4 text-green-700" />
                          <p className="text-sm font-semibold text-green-800">
                            Recommendation
                          </p>
                        </div>
                        <p className="text-sm leading-relaxed text-green-900">
                          {analysis.recommendation}
                        </p>
                      </CardContent>
                    </Card>
                  )}

                  {/* Activity Suggestions */}
                  {analysis.totalNutrition && analysis.totalNutrition.calories > 0 && (
                    <Card className="border-amber-200 bg-gradient-to-r from-amber-50 to-orange-50">
                      <CardContent className="pt-4">
                        <p className="text-sm font-semibold text-amber-800 mb-1">
                          Activity Suggestions to Burn Total Calories
                        </p>
                        <p className="text-xs text-amber-600 mb-3">
                          Approximate time needed to burn {Math.round(analysis.totalNutrition.calories)} calories
                        </p>
                        <div className="grid grid-cols-4 gap-3">
                          {[
                            { label: "Running", calsPerMin: 10, icon: "🏃" },
                            { label: "Cycling", calsPerMin: 8, icon: "🚴" },
                            { label: "Walking", calsPerMin: 6, icon: "🚶" },
                            { label: "Swimming", calsPerMin: 11, icon: "🏊" },
                          ].map((activity) => {
                            const mins = Math.round(analysis.totalNutrition!.calories / activity.calsPerMin);
                            return (
                              <div key={activity.label} className="text-center">
                                <div className="text-2xl mb-1">{activity.icon}</div>
                                <div className="text-lg font-bold text-amber-800">
                                  {mins} min
                                </div>
                                <div className="text-xs text-amber-600">{activity.label}</div>
                              </div>
                            );
                          })}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Per-image save action */}
                  {renderImageAction && renderImageAction(analysis, index)}
                </CardContent>
              </CollapsibleContent>
            </Card>
          </Collapsible>
        );
      })}
    </div>
  );
}
