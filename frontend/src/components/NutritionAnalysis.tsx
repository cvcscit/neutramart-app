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

                  {/* Dishes */}
                  {dishesWithNutrition.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-sm font-semibold">Dishes Identified</p>
                      {dishesWithNutrition.map((dish, di) => (
                        <div
                          key={di}
                          className="p-3 rounded-lg bg-muted/40 border"
                        >
                          <div className="flex items-center gap-2">
                            <p className="font-medium text-sm capitalize truncate flex-1">
                              {dish.name}
                            </p>
                            <Badge variant="outline" className="text-xs shrink-0">
                              {dish.servingSize}
                            </Badge>
                          </div>
                          {dish.nutrition && (
                            <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1">
                              <span className="text-xs text-green-700 font-medium">
                                {Math.round(dish.nutrition.nf_calories)} cal
                              </span>
                              <span className="text-xs text-muted-foreground">
                                P: {fmtN(dish.nutrition.nf_protein)}
                              </span>
                              <span className="text-xs text-muted-foreground">
                                C: {fmtN(dish.nutrition.nf_total_carbohydrate)}
                              </span>
                              <span className="text-xs text-muted-foreground">
                                F: {fmtN(dish.nutrition.nf_total_fat)}
                              </span>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
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
                              {fmtN(analysis.totalNutrition.sodium, " mg")}
                            </div>
                            <div className="text-xs text-red-600">Sodium</div>
                          </div>
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
