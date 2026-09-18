"""
Campus data validation.
All validation is deterministic — no LLM involvement.
Returns clear human-readable error messages.
"""
from typing import Dict, Any, List, Optional, Tuple

MONTHS = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]

# ── Individual field validators ───────────────────────────────────────────────

def _check_non_negative(value: Any, field: str, errors: List[str]) -> Optional[float]:
    """Validate that a numeric value is non-negative. Returns float or None on error."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        errors.append(f"{field}: must be a number, got '{value}'.")
        return None
    import math
    if math.isnan(v) or math.isinf(v):
        errors.append(f"{field}: must be a finite number (got {value}).")
        return None
    if v < 0:
        errors.append(f"{field}: must be 0 or greater (got {v}).")
        return None
    return v


def _check_positive(value: Any, field: str, errors: List[str]) -> Optional[float]:
    """Validate that a numeric value is strictly positive."""
    v = _check_non_negative(value, field, errors)
    if v is not None and v <= 0:
        errors.append(f"{field}: must be greater than 0 (got {v}).")
        return None
    return v


def _check_percent(value: Any, field: str, errors: List[str]) -> Optional[float]:
    """Validate 0–100 percentage."""
    v = _check_non_negative(value, field, errors)
    if v is not None and v > 100:
        errors.append(f"{field}: percentage must be between 0 and 100 (got {v}).")
        return None
    return v


def _check_monthly_list(values: Any, field: str, errors: List[str]) -> Optional[List[float]]:
    """Validate a list of 12 non-negative monthly values."""
    if values is None:
        return None
    if not isinstance(values, (list, tuple)):
        errors.append(f"{field}: must be a list of 12 values.")
        return None
    if len(values) != 12:
        errors.append(f"{field}: must contain exactly 12 monthly values (got {len(values)}).")
        return None
    result = []
    for i, v in enumerate(values):
        validated = _check_non_negative(v, f"{field}[{MONTHS[i]}]", errors)
        if validated is None:
            return None
        result.append(validated)
    return result


# ── Top-level section validators ─────────────────────────────────────────────

def validate_campus_info(campus: Dict[str, Any], errors: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    name = campus.get("name", "").strip()
    if not name:
        errors.append("campus.name: campus name is required.")
    else:
        out["name"] = name

    area = campus.get("area_m2")
    v = _check_positive(area, "campus.area_m2", errors)
    if v is not None:
        out["area_m2"] = v

    students = campus.get("students")
    v = _check_non_negative(students, "campus.students", errors)
    if v is not None:
        out["students"] = int(v)

    staff = campus.get("staff")
    v = _check_non_negative(staff, "campus.staff", errors)
    if v is not None:
        out["staff"] = int(v)

    buildings = campus.get("buildings")
    v = _check_non_negative(buildings, "campus.buildings", errors)
    if v is not None:
        out["buildings"] = int(v)

    return out


def validate_energy(energy: Dict[str, Any], errors: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    annual_kwh = energy.get("annual_kwh")
    monthly = energy.get("monthly_kwh")

    # Monthly overrides annual if provided
    validated_monthly = None
    if monthly is not None:
        validated_monthly = _check_monthly_list(monthly, "energy.monthly_kwh", errors)
        if validated_monthly is not None:
            out["monthly_kwh"] = validated_monthly
            out["annual_kwh"] = round(sum(validated_monthly), 2)

    if validated_monthly is None:
        # Must have annual
        v = _check_non_negative(annual_kwh, "energy.annual_kwh", errors)
        if v is None:
            errors.append("energy: either annual_kwh or monthly_kwh must be provided.")
        else:
            if v == 0:
                errors.append("energy.annual_kwh: annual energy consumption must be greater than 0.")
            else:
                out["annual_kwh"] = v

    cost = energy.get("annual_cost_inr")
    if cost is not None:
        v = _check_non_negative(cost, "energy.annual_cost_inr", errors)
        if v is not None:
            out["annual_cost_inr"] = v

    return out


def validate_water(water: Dict[str, Any], errors: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    annual_m3 = water.get("annual_m3")
    monthly = water.get("monthly_m3")

    validated_monthly = None
    if monthly is not None:
        validated_monthly = _check_monthly_list(monthly, "water.monthly_m3", errors)
        if validated_monthly is not None:
            out["monthly_m3"] = validated_monthly
            out["annual_m3"] = round(sum(validated_monthly), 2)

    if validated_monthly is None:
        v = _check_non_negative(annual_m3, "water.annual_m3", errors)
        if v is None:
            errors.append("water: either annual_m3 or monthly_m3 must be provided.")
        else:
            if v == 0:
                errors.append("water.annual_m3: annual water consumption must be greater than 0.")
            else:
                out["annual_m3"] = v

    cost = water.get("annual_cost_inr")
    if cost is not None:
        v = _check_non_negative(cost, "water.annual_cost_inr", errors)
        if v is not None:
            out["annual_cost_inr"] = v

    return out


def validate_waste(waste: Dict[str, Any], errors: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    annual_kg = waste.get("annual_kg")
    monthly_kg = waste.get("monthly_kg")

    validated_monthly = None
    if monthly_kg is not None:
        validated_monthly = _check_monthly_list(monthly_kg, "waste.monthly_kg", errors)
        if validated_monthly is not None:
            out["monthly_kg"] = validated_monthly
            out["annual_kg"] = round(sum(validated_monthly), 2)

    if validated_monthly is None:
        v = _check_non_negative(annual_kg, "waste.annual_kg", errors)
        if v is None:
            errors.append("waste: either annual_kg or monthly_kg must be provided.")
        else:
            if v == 0:
                errors.append("waste.annual_kg: annual waste must be greater than 0.")
            else:
                out["annual_kg"] = v

    # Waste composition percentages
    recycled_pct = waste.get("recycled_pct", 0)
    composted_pct = waste.get("composted_pct", 0)
    landfill_pct = waste.get("landfill_pct", 0)

    r = _check_percent(recycled_pct, "waste.recycled_pct", errors)
    c = _check_percent(composted_pct, "waste.composted_pct", errors)
    l = _check_percent(landfill_pct, "waste.landfill_pct", errors)

    if r is not None and c is not None and l is not None:
        total = round(r + c + l, 6)
        if abs(total - 100.0) > 0.01:
            errors.append(
                f"waste: recycled_pct + composted_pct + landfill_pct must equal 100% "
                f"(got {r}% + {c}% + {l}% = {total:.2f}%)."
            )
        else:
            out["recycled_pct"] = r
            out["composted_pct"] = c
            out["landfill_pct"] = l

    return out


def validate_budget(budget: Any, errors: List[str]) -> Optional[float]:
    if budget is None:
        return None
    v = _check_non_negative(budget, "budget_inr", errors)
    return v


def validate_existing_measures(measures: Dict[str, Any]) -> Dict[str, bool]:
    """
    Validate and normalise existing sustainability measures.
    Only accepted keys are preserved; unrecognised keys are ignored.
    All values are coerced to bool.
    """
    ACCEPTED = {
        "solar_installed", "led_retrofit", "hvac_optimization",
        "smart_metering", "water_leak_detection", "composting",
        "waste_segregation", "rainwater_harvesting",
    }
    out: Dict[str, bool] = {}
    for key in ACCEPTED:
        if key in measures:
            out[key] = bool(measures[key])
    return out


# ── Top-level campus data validator ──────────────────────────────────────────

def validate_campus_data(raw: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """
    Validate a raw campus data submission.

    Returns:
        (validated_data, errors) where validated_data is None if errors is non-empty.

    Validation rules:
    - campus.name required
    - campus.area_m2 > 0 if provided
    - campus.students/staff/buildings >= 0 if provided
    - energy: annual_kwh > 0 OR monthly_kwh (12 non-negative values)
    - water: annual_m3 > 0 OR monthly_m3 (12 non-negative values)
    - waste: annual_kg > 0 OR monthly_kg (12 non-negative values)
    - waste percentages must sum to 100%
    - all costs >= 0
    - budget >= 0
    """
    errors: List[str] = []
    out: Dict[str, Any] = {}

    # Campus info
    campus_raw = raw.get("campus") or {}
    if not isinstance(campus_raw, dict):
        errors.append("campus: must be an object.")
        campus_raw = {}
    out["campus"] = validate_campus_info(campus_raw, errors)

    # Energy
    energy_raw = raw.get("energy") or {}
    if not isinstance(energy_raw, dict):
        errors.append("energy: must be an object.")
        energy_raw = {}
    out["energy"] = validate_energy(energy_raw, errors)

    # Water
    water_raw = raw.get("water") or {}
    if not isinstance(water_raw, dict):
        errors.append("water: must be an object.")
        water_raw = {}
    out["water"] = validate_water(water_raw, errors)

    # Waste
    waste_raw = raw.get("waste") or {}
    if not isinstance(waste_raw, dict):
        errors.append("waste: must be an object.")
        waste_raw = {}
    out["waste"] = validate_waste(waste_raw, errors)

    # Budget
    budget_val = validate_budget(raw.get("budget_inr"), errors)
    if budget_val is not None:
        out["budget_inr"] = budget_val

    # Existing measures
    measures_raw = raw.get("existing_measures") or {}
    if isinstance(measures_raw, dict):
        out["existing_measures"] = validate_existing_measures(measures_raw)

    if errors:
        return None, errors
    return out, []


# ── CSV parsing ───────────────────────────────────────────────────────────────

_CSV_METRIC_MAP = {
    "campus_name": ("campus", "name"),
    "campus_area": ("campus", "area_m2"),
    "students": ("campus", "students"),
    "staff": ("campus", "staff"),
    "buildings": ("campus", "buildings"),
    "annual_energy": ("energy", "annual_kwh"),
    "annual_energy_cost": ("energy", "annual_cost_inr"),
    "annual_water": ("water", "annual_m3"),
    "annual_water_cost": ("water", "annual_cost_inr"),
    "annual_waste": ("waste", "annual_kg"),
    "recycled_percent": ("waste", "recycled_pct"),
    "composted_percent": ("waste", "composted_pct"),
    "landfill_percent": ("waste", "landfill_pct"),
    "budget": ("budget_inr", None),
}

_MONTH_ENERGY_MAP = {
    "energy_jan": 0, "energy_feb": 1, "energy_mar": 2, "energy_apr": 3,
    "energy_may": 4, "energy_jun": 5, "energy_jul": 6, "energy_aug": 7,
    "energy_sep": 8, "energy_oct": 9, "energy_nov": 10, "energy_dec": 11,
}
_MONTH_WATER_MAP = {
    "water_jan": 0, "water_feb": 1, "water_mar": 2, "water_apr": 3,
    "water_may": 4, "water_jun": 5, "water_jul": 6, "water_aug": 7,
    "water_sep": 8, "water_oct": 9, "water_nov": 10, "water_dec": 11,
}
_MONTH_WASTE_MAP = {
    "waste_jan": 0, "waste_feb": 1, "waste_mar": 2, "waste_apr": 3,
    "waste_may": 4, "waste_jun": 5, "waste_jul": 6, "waste_aug": 7,
    "waste_sep": 8, "waste_oct": 9, "waste_nov": 10, "waste_dec": 11,
}


def parse_csv_to_raw(csv_text: str) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """
    Parse a CSV in metric/value/unit format into a raw campus data dict.

    Expected format:
        metric,value,unit
        campus_area,50000,m2
        ...

    Returns (raw_dict, errors).
    """
    errors: List[str] = []
    lines = [l.strip() for l in csv_text.strip().splitlines() if l.strip()]

    if not lines:
        return None, ["CSV file is empty."]

    # Parse header
    header_line = lines[0].lower()
    headers = [h.strip() for h in header_line.split(",")]
    required_headers = {"metric", "value"}
    if not required_headers.issubset(set(headers)):
        return None, [
            f"CSV header must contain at least 'metric' and 'value' columns. "
            f"Got: {headers}"
        ]

    try:
        metric_col = headers.index("metric")
        value_col = headers.index("value")
    except ValueError as e:
        return None, [f"CSV header parse error: {e}"]

    raw: Dict[str, Any] = {
        "campus": {},
        "energy": {},
        "water": {},
        "waste": {},
    }
    monthly_energy: List[Optional[float]] = [None] * 12
    monthly_water: List[Optional[float]] = [None] * 12
    monthly_waste: List[Optional[float]] = [None] * 12

    row_errors: List[str] = []

    for line_num, line in enumerate(lines[1:], start=2):
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < max(metric_col, value_col) + 1:
            row_errors.append(f"Row {line_num}: not enough columns in '{line}'.")
            continue

        metric = parts[metric_col].lower().strip()
        raw_val = parts[value_col].strip()

        # Skip empty rows
        if not metric:
            continue

        # Numeric conversion for all except campus_name
        if metric == "campus_name":
            raw["campus"]["name"] = raw_val
            continue

        try:
            num_val = float(raw_val.replace(",", ""))
        except ValueError:
            row_errors.append(
                f"Row {line_num}: metric '{metric}' has non-numeric value '{raw_val}'."
            )
            continue

        # Monthly energy
        if metric in _MONTH_ENERGY_MAP:
            monthly_energy[_MONTH_ENERGY_MAP[metric]] = num_val
            continue
        # Monthly water
        if metric in _MONTH_WATER_MAP:
            monthly_water[_MONTH_WATER_MAP[metric]] = num_val
            continue
        # Monthly waste
        if metric in _MONTH_WASTE_MAP:
            monthly_waste[_MONTH_WASTE_MAP[metric]] = num_val
            continue

        # Top-level mapping
        if metric not in _CSV_METRIC_MAP:
            row_errors.append(
                f"Row {line_num}: unrecognised metric '{metric}' — ignored."
            )
            continue

        section, field = _CSV_METRIC_MAP[metric]
        if field is None:
            # Direct top-level key (e.g. budget)
            raw[section] = num_val
        else:
            if section not in raw:
                raw[section] = {}
            raw[section][field] = num_val

    if row_errors:
        errors.extend(row_errors)
        return None, errors

    # Attach monthly arrays if any values were provided
    if any(v is not None for v in monthly_energy):
        if all(v is not None for v in monthly_energy):
            raw["energy"]["monthly_kwh"] = monthly_energy
        else:
            errors.append(
                "Monthly energy: some months are missing. Provide all 12 months "
                "(energy_jan through energy_dec) or none."
            )

    if any(v is not None for v in monthly_water):
        if all(v is not None for v in monthly_water):
            raw["water"]["monthly_m3"] = monthly_water
        else:
            errors.append(
                "Monthly water: some months are missing. Provide all 12 months "
                "(water_jan through water_dec) or none."
            )

    if any(v is not None for v in monthly_waste):
        if all(v is not None for v in monthly_waste):
            raw["waste"]["monthly_kg"] = monthly_waste
        else:
            errors.append(
                "Monthly waste: some months are missing. Provide all 12 months "
                "(waste_jan through waste_dec) or none."
            )

    if errors:
        return None, errors
    return raw, []


def generate_csv_template() -> str:
    """Generate the CSV template string for download."""
    lines = [
        "metric,value,unit",
        "# ── Campus Information ─────────────────────────────────────────────",
        "campus_name,My Campus,text",
        "campus_area,50000,m2",
        "students,5000,count",
        "staff,350,count",
        "buildings,8,count",
        "# ── Energy ─────────────────────────────────────────────────────────",
        "annual_energy,950000,kWh",
        "annual_energy_cost,8200000,INR",
        "# Optional monthly energy (energy_jan … energy_dec)",
        "# energy_jan,80000,kWh",
        "# energy_feb,75000,kWh",
        "# energy_mar,72000,kWh",
        "# energy_apr,70000,kWh",
        "# energy_may,78000,kWh",
        "# energy_jun,90000,kWh",
        "# energy_jul,98000,kWh",
        "# energy_aug,95000,kWh",
        "# energy_sep,85000,kWh",
        "# energy_oct,78000,kWh",
        "# energy_nov,73000,kWh",
        "# energy_dec,76000,kWh",
        "# ── Water ───────────────────────────────────────────────────────────",
        "annual_water,35000,m3",
        "annual_water_cost,1200000,INR",
        "# ── Waste ───────────────────────────────────────────────────────────",
        "annual_waste,85000,kg",
        "recycled_percent,30,percent",
        "composted_percent,20,percent",
        "landfill_percent,50,percent",
        "# ── Sustainability Budget ───────────────────────────────────────────",
        "budget,500000,INR",
    ]
    return "\n".join(lines)
