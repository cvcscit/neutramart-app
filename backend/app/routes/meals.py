import json
import logging
from collections import defaultdict
from datetime import datetime, date, timezone, timedelta
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.auth import get_current_user
from app.regions import get_data_context
from app.limiter import limiter

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Pydantic models (mirrors the frontend payload) ───────────────────────────

class NutritionData(BaseModel):
    food_name: Optional[str] = None
    serving_qty: Optional[float] = None
    serving_unit: Optional[str] = None
    serving_weight_grams: Optional[float] = None
    nf_calories: float
    nf_total_fat: float
    nf_total_carbohydrate: float
    nf_dietary_fiber: float
    nf_sugars: float
    nf_protein: float
    nf_sodium: Optional[float] = None
    nf_saturated_fat: Optional[float] = None
    nf_cholesterol: Optional[float] = None


class Dish(BaseModel):
    name: str
    servingSize: str
    nutrition: Optional[NutritionData] = None


class TotalNutrition(BaseModel):
    calories: float
    protein: float
    carbs: float
    fat: float
    fiber: float
    sugar: float = 0.0


class SaveMealRequest(BaseModel):
    mealName: str
    mealType: str                    # breakfast | lunch | dinner | snack | other
    description: Optional[str] = ""
    imageUrl: Optional[str] = ""
    totalNutrition: TotalNutrition
    dishes: list[Dish] = []


# ─── Helper ───────────────────────────────────────────────────────────────────

def _user_id(email: str) -> str:
    return email.replace("@", "_at_").replace(".", "_")


# ─── POST /api/meals ──────────────────────────────────────────────────────────

@router.post("/meals")
@limiter.limit("30/minute")
def save_meal(
    request: Request,
    body: SaveMealRequest,
    _user=Depends(get_current_user),
    ctx: dict = Depends(get_data_context),
):
    """
    Save a meal (with its selected dishes) to S3.

    S3 key:  users/{user_id}/meals/{timestamp}.json
    """
    if not body.mealName.strip():
        raise HTTPException(status_code=400, detail="mealName is required.")

    if len(body.dishes) == 0:
        raise HTTPException(status_code=400, detail="At least one dish is required.")

    uid = _user_id(_user["email"])
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    meal_id = f"{timestamp}_{body.mealName[:30].replace(' ', '_')}"
    meal_key = f"users/{uid}/meals/{meal_id}.json"

    meal_record = {
        "meal_id": meal_id,
        "meal_name": body.mealName.strip(),
        "meal_type": body.mealType,
        "description": body.description,
        "image_url": body.imageUrl,
        "logged_at": timestamp,
        "total_nutrition": body.totalNutrition.model_dump(),
        "dishes": [d.model_dump() for d in body.dishes],
    }

    try:
        ctx["s3"].put_object(
            Bucket=ctx["bucket"],
            Key=meal_key,
            Body=json.dumps(meal_record),
            ContentType="application/json",
        )
    except Exception as e:
        logger.error(f"Failed to save meal for {uid}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save meal.")

    return {
        "meal_id": meal_id,
        "message": f"Meal '{body.mealName}' saved successfully.",
    }


# ─── GET /api/meals ───────────────────────────────────────────────────────────

def _parse_num(val) -> float:
    """Parse a numeric value from strings like '350 kcal', '25g', or a number."""
    if isinstance(val, (int, float)):
        return float(val)
    if not val or val == "N/A":
        return 0.0
    import re
    m = re.search(r"[\d.]+", str(val))
    return float(m.group(0)) if m else 0.0


def _scan_to_meal(scan: dict) -> dict:
    """Convert a scan JSON into a meal-like dict so the dashboard can use it."""
    return {
        "meal_id": f"scan_{scan.get('timestamp', '')}",
        "meal_name": scan.get("description", "Scanned meal"),
        "meal_type": "other",
        "description": scan.get("description", ""),
        "image_url": "",
        "logged_at": scan.get("timestamp", ""),
        "total_nutrition": {
            "calories": _parse_num(scan.get("calories")),
            "protein": _parse_num(scan.get("protein")),
            "carbs": _parse_num(scan.get("carbs")),
            "fat": _parse_num(scan.get("fat")),
            "fiber": _parse_num(scan.get("fiber")),
            "sugar": _parse_num(scan.get("sugar")),
        },
        "micronutrients": {
            k: _parse_num(v)
            for k, v in (scan.get("micronutrients") or {}).items()
        },
        "dishes": [],
    }


def _load_s3_jsons(uid: str, folder: str, s3, bucket: str) -> list[dict]:
    """Fetch all JSON files from users/{uid}/{folder}/ in the regional bucket."""
    prefix = f"users/{uid}/{folder}/"
    try:
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    except Exception as e:
        logger.error(f"Failed to list {folder} for {uid}: {e}")
        return []

    if "Contents" not in response:
        return []

    items = []
    for obj in response["Contents"]:
        try:
            data = s3.get_object(Bucket=bucket, Key=obj["Key"])
            items.append(json.loads(data["Body"].read()))
        except Exception as e:
            logger.warning(f"Skipping unreadable {obj['Key']}: {e}")
    return items


def _load_all_meals(uid: str, s3, bucket: str) -> list[dict]:
    """Fetch meals AND scans for this user, returning unified meal-like dicts."""
    meals = _load_s3_jsons(uid, "meals", s3, bucket)
    scans = _load_s3_jsons(uid, "scans", s3, bucket)
    # Convert scans to meal format
    for scan in scans:
        meals.append(_scan_to_meal(scan))
    return meals


def _flatten_meal(meal: dict) -> dict:
    """Flatten total_nutrition into top-level fields expected by the frontend."""
    tn = meal.get("total_nutrition") or {}
    return {
        "id": meal.get("meal_id", ""),
        "meal_name": meal.get("meal_name", ""),
        "meal_type": meal.get("meal_type", ""),
        "description": meal.get("description", ""),
        "image_url": meal.get("image_url", ""),
        "logged_at": meal.get("logged_at", ""),
        "total_calories": tn.get("calories", 0),
        "total_protein": tn.get("protein", 0),
        "total_carbs": tn.get("carbs", 0),
        "total_fat": tn.get("fat", 0),
        "total_fiber": tn.get("fiber", 0),
        "total_sugar": tn.get("sugar", 0),
        "meal_dishes": meal.get("dishes", []),
    }


def _parse_logged_at(logged_at: str, tz: ZoneInfo) -> date | None:
    """Parse the stored timestamp (YYYYMMDDTHHMMSSz or ISO) and return local date."""
    try:
        if "T" in logged_at and logged_at.endswith("Z"):
            dt = datetime.strptime(logged_at, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(logged_at).replace(tzinfo=timezone.utc)
        return dt.astimezone(tz).date()
    except Exception:
        return None


@router.get("/meals")
@limiter.limit("30/minute")
def get_meals(
    request: Request,
    startDate: Optional[str] = Query(None),
    endDate: Optional[str] = Query(None),
    limit: int = Query(100),
    _user=Depends(get_current_user),
    ctx: dict = Depends(get_data_context),
):
    """
    Return saved meals for the current user, newest first.
    Optionally filter by startDate / endDate (YYYY-MM-DD).
    """
    uid = _user_id(_user["email"])
    meals = _load_all_meals(uid, ctx["s3"], ctx["bucket"])

    # Parse date filters
    start = date.fromisoformat(startDate) if startDate else None
    end = date.fromisoformat(endDate) if endDate else None
    tz = ZoneInfo("UTC")

    def _meal_date(m: dict) -> date | None:
        return _parse_logged_at(m.get("logged_at", ""), tz)

    if start or end:
        filtered = []
        for m in meals:
            d = _meal_date(m)
            if d is None:
                continue
            if start and d < start:
                continue
            if end and d > end:
                continue
            filtered.append(m)
        meals = filtered

    meals.sort(key=lambda m: m.get("logged_at", ""), reverse=True)
    meals = meals[:limit]

    return {"meals": [_flatten_meal(m) for m in meals]}


# ─── GET /api/nutrition/summary ──────────────────────────────────────────────

@router.get("/nutrition/summary")
@limiter.limit("30/minute")
def get_nutrition_summary(
    request: Request,
    period: str = Query("daily"),          # daily | weekly | monthly | yearly
    startDate: Optional[str] = Query(None),
    endDate: Optional[str] = Query(None),
    limit: int = Query(365),
    timezone: str = Query("UTC"),
    _user=Depends(get_current_user),
    ctx: dict = Depends(get_data_context),
):
    """
    Aggregate nutrition totals by period for the current user.
    Returns { data: [ { date/week_start/month_start/year_start, total_*, meal_count } ] }
    """
    uid = _user_id(_user["email"])

    try:
        tz = ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")

    start = date.fromisoformat(startDate) if startDate else None
    end = date.fromisoformat(endDate) if endDate else None

    meals = _load_all_meals(uid, ctx["s3"], ctx["bucket"])

    # Group meals by period bucket
    MICRO_KEYS = ("vitamin_a", "vitamin_c", "vitamin_d", "vitamin_b12", "iron", "calcium", "potassium", "sodium", "zinc", "magnesium")

    buckets: dict[str, dict] = defaultdict(lambda: {
        "total_calories": 0.0,
        "total_protein": 0.0,
        "total_carbs": 0.0,
        "total_fat": 0.0,
        "total_fiber": 0.0,
        "total_sugar": 0.0,
        "meal_count": 0,
        **{f"total_{mk}": 0.0 for mk in MICRO_KEYS},
    })

    for meal in meals:
        d = _parse_logged_at(meal.get("logged_at", ""), tz)
        if d is None:
            continue
        if start and d < start:
            continue
        if end and d > end:
            continue

        tn = meal.get("total_nutrition") or {}

        if period == "daily":
            key = d.isoformat()
        elif period == "weekly":
            # ISO week Monday
            key = (d - timedelta(days=d.weekday())).isoformat()
        elif period == "monthly":
            key = date(d.year, d.month, 1).isoformat()
        elif period == "yearly":
            key = date(d.year, 1, 1).isoformat()
        else:
            key = d.isoformat()

        b = buckets[key]
        b["total_calories"] += tn.get("calories", 0)
        b["total_protein"]  += tn.get("protein", 0)
        b["total_carbs"]    += tn.get("carbs", 0)
        b["total_fat"]      += tn.get("fat", 0)
        b["total_fiber"]    += tn.get("fiber", 0)
        b["total_sugar"]    += tn.get("sugar", 0)
        b["meal_count"]     += 1

        # Aggregate micronutrients
        micro = meal.get("micronutrients") or {}
        for mk in MICRO_KEYS:
            b[f"total_{mk}"] += micro.get(mk, 0)

    period_key_map = {
        "daily":   "date",
        "weekly":  "week_start",
        "monthly": "month_start",
        "yearly":  "year_start",
    }
    date_field = period_key_map.get(period, "date")

    data = sorted(
        [{date_field: k, **v} for k, v in buckets.items()],
        key=lambda x: x[date_field],
    )
    data = data[:limit]

    return {"data": data}


# ─── DELETE /api/meals/{meal_id} ─────────────────────────────────────────────

@router.delete("/meals/{meal_id}")
@limiter.limit("30/minute")
def delete_meal(
    request: Request,
    meal_id: str,
    _user=Depends(get_current_user),
    ctx: dict = Depends(get_data_context),
):
    """
    Delete a specific meal by its meal_id.
    The meal_id is the filename stem, so we reconstruct the full S3 key.
    """
    uid = _user_id(_user["email"])
    meal_key = f"users/{uid}/meals/{meal_id}.json"

    try:
        ctx["s3"].head_object(Bucket=ctx["bucket"], Key=meal_key)
    except Exception:
        raise HTTPException(status_code=404, detail="Meal not found.")

    try:
        ctx["s3"].delete_object(Bucket=ctx["bucket"], Key=meal_key)
    except Exception as e:
        logger.error(f"Failed to delete meal {meal_key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete meal.")

    return {"message": "Meal deleted successfully."}