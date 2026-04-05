"use client";

import { useState, useEffect } from "react";
import { useAuth } from "../contexts/AuthContext";
import { API_URL } from "../config/api";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import { Plus, Loader2, Save, Utensils, ShieldAlert } from "lucide-react";
import { toast } from "sonner";

import {
  NutritionData,
  Dish,
  AnalysisResult,
  AddToProfileDialogProps,
} from "@/types";

function fmtN(value: number, unit = "g"): string {
  return `${Math.round(value * 10) / 10}${unit}`;
}

/** Re-sum nutrition from only the selected dishes */
function sumSelectedNutrition(dishes: Dish[], selectedIds: Set<number>) {
  const selected = dishes.filter((_, i) => selectedIds.has(i));
  if (selected.length === 0) return null;

  return selected.reduce(
    (acc, dish) => {
      if (!dish.nutrition) return acc;
      return {
        calories: acc.calories + dish.nutrition.nf_calories,
        protein:  acc.protein  + dish.nutrition.nf_protein,
        carbs:    acc.carbs    + dish.nutrition.nf_total_carbohydrate,
        fat:      acc.fat      + dish.nutrition.nf_total_fat,
        fiber:    acc.fiber    + dish.nutrition.nf_dietary_fiber,
        sugar:    acc.sugar    + (dish.nutrition.nf_sugars ?? 0),
      };
    },
    { calories: 0, protein: 0, carbs: 0, fat: 0, fiber: 0, sugar: 0 },
  );
}

export function AddToProfileDialog({
  analysisResult,
  onSave,
  imageSpecific = false,
  imageName,
  triggerButton,
}: AddToProfileDialogProps) {
  const { token } = useAuth();
  const [open, setOpen]           = useState(false);
  const [saving, setSaving]       = useState(false);
  const [mealName, setMealName]   = useState("");
  const [mealType, setMealType]   = useState("breakfast");
  const [description, setDescription] = useState(analysisResult.description || "");

  const dishesWithNutrition = (analysisResult.dishes ?? []).filter(
    (d) => d.nutrition,
  );

  // All dishes selected by default
  const [selectedDishIds, setSelectedDishIds] = useState<Set<number>>(
    () => new Set(dishesWithNutrition.map((_, i) => i)),
  );

  // Reset selection whenever dialog opens
  useEffect(() => {
    if (open) {
      setSelectedDishIds(new Set(dishesWithNutrition.map((_, i) => i)));
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "unset";
    }
    return () => { document.body.style.overflow = "unset"; };
  }, [open]);

  const toggleDish = (index: number) => {
    setSelectedDishIds((prev) => {
      const next = new Set(prev);
      next.has(index) ? next.delete(index) : next.add(index);
      return next;
    });
  };

  const allSelected  = selectedDishIds.size === dishesWithNutrition.length;
  const noneSelected = selectedDishIds.size === 0;

  const toggleAll = () =>
    setSelectedDishIds(
      allSelected
        ? new Set()
        : new Set(dishesWithNutrition.map((_, i) => i)),
    );

  // Live-recalculated totals based on selection
  const selectedNutrition = sumSelectedNutrition(
    dishesWithNutrition,
    selectedDishIds,
  );

  const handleSave = async () => {
    if (!mealName.trim()) {
      toast.error("Please enter a meal name");
      return;
    }
    if (!selectedNutrition) {
      toast.error("Select at least one dish to save");
      return;
    }

    setSaving(true);
    try {
      const selectedDishes = dishesWithNutrition.filter((_, i) =>
        selectedDishIds.has(i),
      );

      const mealData = {
        mealName:       mealName.trim(),
        mealType,
        description:    description.trim(),
        imageUrl:       analysisResult.uploadedImages?.[0]?.url ?? "",
        totalNutrition: selectedNutrition,
        // Each dish is saved individually so it can be logged / queried later
        dishes: selectedDishes.map((d) => ({
          name:        d.name,
          servingSize: d.servingSize,
          nutrition:   d.nutrition,
        })),
      };

      const response = await fetch(`${API_URL}/meals`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(mealData),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error || "Failed to save meal");
      }

      toast.success("Meal saved to profile!", {
        description: `${mealName} (${selectedDishes.length} dish${selectedDishes.length !== 1 ? "es" : ""}) added to your nutrition log`,
      });

      setOpen(false);
      setMealName("");
      setDescription(analysisResult.description || "");
      onSave();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to save meal";
      toast.error(message);
    } finally {
      setSaving(false);
    }
  };

  if (!analysisResult.totalNutrition && dishesWithNutrition.length === 0) {
    return null;
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {triggerButton || (
          <Button className="w-full" size="lg">
            <Plus className="mr-2 h-4 w-4" />
            Add to Profile
          </Button>
        )}
      </DialogTrigger>

      <DialogContent className="max-w-[620px] max-h-[90vh] mt-10 p-0 flex flex-col overflow-hidden">
        {/* ── Fixed header ── */}
        <div className="px-6 pt-6 pb-4 border-b shrink-0 bg-background">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Save className="h-5 w-5" />
              {imageSpecific
                ? `Save ${imageName || "Image"} to Profile`
                : "Save Meal to Profile"}
            </DialogTitle>
            <DialogDescription>
              {imageSpecific
                ? "Add this image's dishes to your nutrition log"
                : "Choose which dishes to save to your nutrition tracking profile"}
            </DialogDescription>
          </DialogHeader>
        </div>

        {/* ── Scrollable body ── */}
        <div
          className="flex-1 overflow-y-auto px-6 py-4 overscroll-contain space-y-6"
          onWheel={(e) => e.stopPropagation()}
        >
          {/* Meal details */}
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="meal-name">Meal Name *</Label>
              <Input
                id="meal-name"
                placeholder={
                  imageSpecific
                    ? `Enter name for ${imageName || "this meal"}…`
                    : "Enter meal name…"
                }
                value={mealName}
                onChange={(e) => setMealName(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="meal-type">Meal Type</Label>
              <Select value={mealType} onValueChange={setMealType}>
                <SelectTrigger>
                  <SelectValue placeholder="Select meal type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="breakfast">Breakfast</SelectItem>
                  <SelectItem value="lunch">Lunch</SelectItem>
                  <SelectItem value="dinner">Dinner</SelectItem>
                  <SelectItem value="snack">Snack</SelectItem>
                  <SelectItem value="other">Other</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Notes</Label>
              <Textarea
                id="description"
                placeholder="Any additional notes about this meal…"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
              />
            </div>
          </div>

          <Separator />

          {/* ── Dish selector ── */}
          {dishesWithNutrition.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-semibold">
                  Select Dishes to Save
                </Label>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 text-xs px-2"
                  onClick={toggleAll}
                >
                  {allSelected ? "Deselect all" : "Select all"}
                </Button>
              </div>

              <div className="space-y-2">
                {dishesWithNutrition.map((dish:any, i:any) => {
                  const checked = selectedDishIds.has(i);
                  return (
                    <div
                      key={i}
                      onClick={() => toggleDish(i)}
                      className={[
                        "flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors",
                        checked
                          ? "border-green-300 bg-green-50"
                          : "border-border bg-muted/30 hover:bg-muted/50",
                      ].join(" ")}
                    >
                      <Checkbox
                        checked={checked}
                        onCheckedChange={() => toggleDish(i)}
                        className="mt-0.5 shrink-0"
                        onClick={(e) => e.stopPropagation()}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <p className="font-medium text-sm capitalize truncate">
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
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── Live nutrition summary (recalculates with selection) ── */}
          {selectedNutrition ? (
            <Card className="bg-gradient-to-r from-green-50 to-blue-50 border-green-200">
              <CardHeader className="pb-3">
                <CardTitle className="text-base text-green-800 flex items-center gap-2">
                  <Utensils className="h-4 w-4" />
                  Nutrition to be Saved
                  <Badge variant="secondary" className="text-xs ml-auto">
                    {selectedDishIds.size} dish{selectedDishIds.size !== 1 ? "es" : ""}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-3">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-green-700">
                      {Math.round(selectedNutrition.calories)}
                    </div>
                    <div className="text-xs text-green-600">Calories</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-semibold text-blue-700">
                      {fmtN(selectedNutrition.protein)}
                    </div>
                    <div className="text-xs text-blue-600">Protein</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-semibold text-orange-700">
                      {fmtN(selectedNutrition.carbs)}
                    </div>
                    <div className="text-xs text-orange-600">Carbs</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-semibold text-yellow-700">
                      {fmtN(selectedNutrition.fat)}
                    </div>
                    <div className="text-xs text-yellow-600">Fat</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-semibold text-purple-700">
                      {fmtN(selectedNutrition.fiber)}
                    </div>
                    <div className="text-xs text-purple-600">Fiber</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-semibold text-red-700">
                      {fmtN(selectedNutrition.sugar)}
                    </div>
                    <div className="text-xs text-red-600">Sugar</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card className="border-amber-200 bg-amber-50">
              <CardContent className="py-4 text-center text-sm text-amber-800">
                Select at least one dish to preview nutrition
              </CardContent>
            </Card>
          )}

          {/* Allergens */}
          {analysisResult.allergens && analysisResult.allergens.length > 0 && (
            <Card className="border-red-200 bg-red-50">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-red-700 flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4" /> Allergen Warning
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-1.5">
                  {analysisResult.allergens.map((a:any, i:any) => (
                    <Badge key={i} variant="destructive" className="text-xs">
                      {a}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* ── Fixed footer ── */}
        <div className="px-6 py-4 border-t bg-background shrink-0">
          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={() => setOpen(false)}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={saving || !mealName.trim() || noneSelected}
              className="flex-1"
            >
              {saving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving…
                </>
              ) : (
                <>
                  <Save className="mr-2 h-4 w-4" />
                  Save {selectedDishIds.size > 0 ? `${selectedDishIds.size} Dish${selectedDishIds.size !== 1 ? "es" : ""}` : "to Profile"}
                </>
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}