"""
Load and cache mock campus data from JSON files (DEMO mode).
When USER mode is active, returns derived data from the user's campus dataset.

All callers use the same public API regardless of which mode is active.
"""
import json
from pathlib import Path
from functools import lru_cache
from typing import Dict, Any, List, Optional

DATA_DIR = Path(__file__).parent / "mock_data"

MONTHS_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                 "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ── Demo data loaders (cached) ────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_energy_demo() -> Dict[str, Any]:
    with open(DATA_DIR / "energy.json", "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_water_demo() -> Dict[str, Any]:
    with open(DATA_DIR / "water.json", "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_waste_demo() -> Dict[str, Any]:
    with open(DATA_DIR / "waste.json", "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_interventions() -> List[Dict[str, Any]]:
    with open(DATA_DIR / "interventions.json", "r", encoding="utf-8") as f:
        return json.load(f)


# ── Internal helper: resolve active user data ─────────────────────────────────

def _get_active_data(session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Return the active user campus data dict for this session (or global slot),
    or None if in demo mode.
    """
    import campus_data as cd
    if session_id:
        if cd.is_session_user_mode(session_id):
            return cd.get_session_data(session_id)
        return None
    # Legacy global path (tests / non-session callers)
    if cd.is_user_mode():
        return cd.get_user_campus_data()
    return None


def _is_active_user_mode(session_id: Optional[str] = None) -> bool:
    import campus_data as cd
    if session_id:
        return cd.is_session_user_mode(session_id)
    return cd.is_user_mode()


# ── Active-dataset-aware public loaders ──────────────────────────────────────

def load_energy(session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Return energy data for the active dataset.
    In USER mode the returned structure mirrors the demo format where possible.
    """
    import campus_data as cd
    data = _get_active_data(session_id)
    if data:
        derived = cd.derive_energy_data(data)
        monthly = derived.get("monthly_kwh") or []
        if monthly:
            return {
                "unit": "kWh",
                "year": 2024,
                "note": derived["note"],
                "has_monthly": True,
                "annual_kwh": derived["annual_kwh"],
                "buildings": [
                    {
                        "id": "campus",
                        "name": derived.get("campus_name", "Campus"),
                        "monthly": monthly,
                    }
                ],
                "data_source": "user",
            }
        else:
            return {
                "unit": "kWh",
                "year": 2024,
                "note": derived["note"],
                "has_monthly": False,
                "annual_kwh": derived["annual_kwh"],
                "buildings": [],
                "data_source": "user",
            }
    return _load_energy_demo()


def load_water(session_id: Optional[str] = None) -> Dict[str, Any]:
    import campus_data as cd
    data = _get_active_data(session_id)
    if data:
        derived = cd.derive_water_data(data)
        monthly = derived.get("monthly_m3") or []
        if monthly:
            return {
                "unit": "m3",
                "year": 2024,
                "note": derived["note"],
                "has_monthly": True,
                "annual_m3": derived["annual_m3"],
                "buildings": [
                    {
                        "id": "campus",
                        "name": derived.get("campus_name", "Campus"),
                        "monthly": monthly,
                    }
                ],
                "data_source": "user",
            }
        else:
            return {
                "unit": "m3",
                "year": 2024,
                "note": derived["note"],
                "has_monthly": False,
                "annual_m3": derived["annual_m3"],
                "buildings": [],
                "data_source": "user",
            }
    return _load_water_demo()


def load_waste(session_id: Optional[str] = None) -> Dict[str, Any]:
    import campus_data as cd
    data = _get_active_data(session_id)
    if data:
        derived = cd.derive_waste_data(data)
        annual_kg    = derived["annual_kg"]
        recycled_pct = derived.get("recycled_pct", 0) / 100
        composted_pct = derived.get("composted_pct", 0) / 100
        landfill_pct  = derived.get("landfill_pct", 0) / 100
        monthly_kg   = derived.get("monthly_kg") or []

        if monthly_kg and len(monthly_kg) == 12:
            monthly_list = [
                {
                    "month": MONTHS_LABELS[i],
                    "total": round(v, 2),
                    "recycled": round(v * recycled_pct, 2),
                    "compost": round(v * composted_pct, 2),
                    "landfill": round(v * landfill_pct, 2),
                }
                for i, v in enumerate(monthly_kg)
            ]
        else:
            # Distribute annual evenly across months for structure
            monthly_avg = annual_kg / 12
            monthly_list = [
                {
                    "month": MONTHS_LABELS[i],
                    "total": round(monthly_avg, 2),
                    "recycled": round(monthly_avg * recycled_pct, 2),
                    "compost": round(monthly_avg * composted_pct, 2),
                    "landfill": round(monthly_avg * landfill_pct, 2),
                }
                for i in range(12)
            ]

        return {
            "unit": "kg",
            "year": 2024,
            "note": derived["note"],
            "has_monthly": derived.get("has_monthly", False),
            "recycled_pct":  derived.get("recycled_pct", 0),
            "composted_pct": derived.get("composted_pct", 0),
            "landfill_pct":  derived.get("landfill_pct", 0),
            "monthly": monthly_list,
            "data_source": "user",
        }
    return _load_waste_demo()


# ── Utility helpers ───────────────────────────────────────────────────────────

def get_interventions_by_ids(ids: List[str]) -> List[Dict[str, Any]]:
    catalog = load_interventions()
    catalog_map = {item["id"]: item for item in catalog}
    return [catalog_map[i] for i in ids if i in catalog_map]


def get_annual_energy_kwh(session_id: Optional[str] = None) -> float:
    data = _get_active_data(session_id)
    if data:
        energy  = data.get("energy", {})
        monthly = energy.get("monthly_kwh") or []
        if monthly and len(monthly) == 12:
            return sum(monthly)
        return float(energy.get("annual_kwh") or 0)
    demo = _load_energy_demo()
    return sum(sum(b["monthly"]) for b in demo["buildings"])


def get_annual_water_m3(session_id: Optional[str] = None) -> float:
    data = _get_active_data(session_id)
    if data:
        water   = data.get("water", {})
        monthly = water.get("monthly_m3") or []
        if monthly and len(monthly) == 12:
            return sum(monthly)
        return float(water.get("annual_m3") or 0)
    demo = _load_water_demo()
    return sum(sum(b["monthly"]) for b in demo["buildings"])


def get_annual_waste_kg(session_id: Optional[str] = None) -> float:
    data = _get_active_data(session_id)
    if data:
        waste   = data.get("waste", {})
        monthly = waste.get("monthly_kg") or []
        if monthly and len(monthly) == 12:
            return sum(monthly)
        return float(waste.get("annual_kg") or 0)
    demo = _load_waste_demo()
    return sum(m["total"] for m in demo["monthly"])


def get_annual_recycled_kg(session_id: Optional[str] = None) -> float:
    data = _get_active_data(session_id)
    if data:
        waste       = data.get("waste", {})
        annual_kg   = get_annual_waste_kg(session_id)
        recycled_pct  = (waste.get("recycled_pct")  or 0) / 100
        composted_pct = (waste.get("composted_pct") or 0) / 100
        return annual_kg * (recycled_pct + composted_pct)
    demo = _load_waste_demo()
    return sum(m["recycled"] + m["compost"] for m in demo["monthly"])


def get_annual_landfill_kg(session_id: Optional[str] = None) -> float:
    data = _get_active_data(session_id)
    if data:
        waste       = data.get("waste", {})
        annual_kg   = get_annual_waste_kg(session_id)
        landfill_pct = (waste.get("landfill_pct") or 0) / 100
        return annual_kg * landfill_pct
    demo = _load_waste_demo()
    return sum(m["landfill"] for m in demo["monthly"])
