"""
Campus sustainability calculations.
All formulas are documented inline.
Emission factors from MoEFCC / CEA India (prototype values).

Calculations are always deterministic — the LLM is never involved in producing numbers.
"""
from typing import Dict, Any, Optional
from data_loader import (
    load_energy, load_water, load_waste,
    get_annual_energy_kwh, get_annual_water_m3,
    get_annual_waste_kg, get_annual_recycled_kg,
    get_annual_landfill_kg,
)
import campus_data as cd

# ── Emission Factors (Prototype – India grid average 2023) ────────────────────
# Source: CEA CO2 Baseline Database for Indian Power Sector (prototype approximation)
GRID_EMISSION_FACTOR_KG_PER_KWH = 0.716   # kg CO2 per kWh
WATER_EMISSION_FACTOR_KG_PER_M3 = 0.344   # kg CO2 per m³ (pumping + treatment)
WASTE_LANDFILL_FACTOR_KG_PER_KG = 0.50    # kg CO2e per kg landfilled (methane + transport)


def compute_annual_co2_kg(
    energy_kwh: float,
    water_m3: float,
    landfill_waste_kg: float,
) -> float:
    """
    Total annual CO2e (kg) from energy + water + waste.
    Each component is independently traceable.
    DO NOT ask the LLM to perform this calculation.
    """
    co2_energy = energy_kwh * GRID_EMISSION_FACTOR_KG_PER_KWH
    co2_water  = water_m3  * WATER_EMISSION_FACTOR_KG_PER_M3
    co2_waste  = landfill_waste_kg * WASTE_LANDFILL_FACTOR_KG_PER_KG
    return co2_energy + co2_water + co2_waste


def compute_recycling_rate(recycled_kg: float, total_kg: float) -> float:
    """Recycling + composting rate as percentage of total waste."""
    if total_kg <= 0:
        return 0.0
    return round((recycled_kg / total_kg) * 100, 2)


def get_energy_per_building(session_id: Optional[str] = None) -> Dict[str, float]:
    """
    Returns per-building annual energy consumption.
    In user mode returns a single 'campus' entry if building data is unavailable.
    """
    data = load_energy(session_id=session_id)
    if data.get("data_source") == "user":
        buildings = data.get("buildings", [])
        if not buildings:
            return {"campus": get_annual_energy_kwh(session_id=session_id)}
        return {b["id"]: sum(b["monthly"]) for b in buildings}
    return {b["id"]: sum(b["monthly"]) for b in data["buildings"]}


def get_water_per_building(session_id: Optional[str] = None) -> Dict[str, float]:
    data = load_water(session_id=session_id)
    if data.get("data_source") == "user":
        buildings = data.get("buildings", [])
        if not buildings:
            return {"campus": get_annual_water_m3(session_id=session_id)}
        return {b["id"]: sum(b["monthly"]) for b in buildings}
    return {b["id"]: sum(b["monthly"]) for b in data["buildings"]}


def compute_all_metrics(session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Compute the full set of overview metrics from the active dataset.
    Always uses deterministic calculations — never LLM.
    """
    energy   = get_annual_energy_kwh(session_id=session_id)
    water    = get_annual_water_m3(session_id=session_id)
    waste    = get_annual_waste_kg(session_id=session_id)
    recycled = get_annual_recycled_kg(session_id=session_id)
    landfill = get_annual_landfill_kg(session_id=session_id)
    co2      = compute_annual_co2_kg(energy, water, landfill)
    recycling_rate = compute_recycling_rate(recycled, waste)

    # Data source metadata
    if session_id:
        mode         = cd.get_session_mode(session_id)
        source_label = cd.get_data_source_label(session_id=session_id)
        completeness = cd.get_completeness_flags(session_id=session_id)
    else:
        mode         = cd.get_active_mode()
        source_label = cd.get_data_source_label()
        completeness = cd.get_completeness_flags()

    note = "User-provided campus data \u2013 Prototype" if mode == "user" else \
           "Synthetic campus data \u2013 prototype only"

    return {
        "annual_energy_kwh":    round(energy, 2),
        "annual_water_m3":      round(water, 2),
        "annual_waste_kg":      round(waste, 2),
        "annual_co2_kg":        round(co2, 2),
        "recycling_rate_pct":   recycling_rate,
        "energy_per_building":  {k: round(v, 2) for k, v in get_energy_per_building(session_id).items()},
        "water_per_building":   {k: round(v, 2) for k, v in get_water_per_building(session_id).items()},
        "note":                 note,
        "data_source":          mode,
        "data_source_label":    source_label,
        "completeness":         completeness,
    }


def payback_years(cost_inr: float, annual_savings_inr: float) -> float:
    """
    Simple payback = cost / annual_savings.
    Returns None-equivalent (float('inf')) if annual savings <= 0.
    """
    if annual_savings_inr <= 0:
        return float("inf")
    return round(cost_inr / annual_savings_inr, 2)
