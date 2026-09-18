"""
EcoSim-Opt – Intervention Simulator and Budget Optimizer.

Two modes:
  A. Manual Simulation  – user picks interventions + budget, compute combined impact.
  B. Budget Optimization – exhaustive combination search over intervention catalogue,
                           scored by a transparent multi-objective function.

Interaction coefficients:
  Some intervention pairs have synergy or diminishing returns captured via
  optional interaction factors loaded from the catalogue or hardcoded below.
"""
from itertools import combinations
from typing import List, Dict, Any, Optional, Tuple
import math

from data_loader import load_interventions, get_interventions_by_ids
from calculations import compute_annual_co2_kg

# ── Interaction Coefficients ──────────────────────────────────────────────────
# Format: frozenset({id_a, id_b}): {field: factor}
# factor < 1 → diminishing returns; factor > 1 → synergy
INTERACTION_COEFFICIENTS: Dict[frozenset, Dict[str, float]] = {
    frozenset({"hvac_optimization", "rooftop_solar"}): {
        "energy_saving_pct": 1.05,   # 5% synergy: solar offsets HVAC peak load
        "co2_reduction_kg_year": 1.05,
        "label": "HVAC + Solar synergy: peak load offset",
    },
    frozenset({"led_retrofit", "smart_metering"}): {
        "energy_saving_pct": 1.03,   # Smart meters reinforce LED savings
        "label": "LED + Smart Metering synergy: real-time feedback loop",
    },
    frozenset({"composting", "waste_segregation"}): {
        "waste_reduction_pct": 1.08,  # Segregation feeds composting
        "co2_reduction_kg_year": 1.08,
        "label": "Composting + Segregation synergy: higher diversion rate",
    },
    frozenset({"leak_detection", "rainwater_harvesting"}): {
        "water_saving_pct": 1.06,    # Harvested water + plugged leaks multiply savings
        "label": "Leak Detection + Rainwater Harvesting synergy",
    },
}

# ── Default Objective Weights ─────────────────────────────────────────────────
DEFAULT_WEIGHTS = {
    "energy": 0.25,
    "water": 0.15,
    "waste": 0.10,
    "co2": 0.25,
    "financial": 0.25,   # ROI = annual_savings / cost
}

WEIGHT_KEYS = set(DEFAULT_WEIGHTS.keys())


def _validate_weights(weights: Optional[Dict[str, float]]) -> Dict[str, float]:
    """Normalise custom weights; fall back to defaults for missing keys."""
    if weights is None:
        return DEFAULT_WEIGHTS.copy()
    merged = DEFAULT_WEIGHTS.copy()
    for k, v in weights.items():
        if k in WEIGHT_KEYS and v >= 0:
            merged[k] = v
    total = sum(merged.values())
    if total <= 0:
        return DEFAULT_WEIGHTS.copy()
    return {k: v / total for k, v in merged.items()}


def _apply_interactions(
    selected_ids: List[str],
    base_savings: Dict[str, float],
) -> Tuple[Dict[str, float], List[str]]:
    """
    Apply pairwise interaction coefficients.
    Returns updated savings dict and list of applied interaction labels.
    """
    savings = base_savings.copy()
    applied_labels: List[str] = []

    for id_a, id_b in combinations(selected_ids, 2):
        key = frozenset({id_a, id_b})
        if key in INTERACTION_COEFFICIENTS:
            coeff = INTERACTION_COEFFICIENTS[key]
            for field, factor in coeff.items():
                if field == "label":
                    continue
                if field in savings:
                    savings[field] = savings[field] * factor
            applied_labels.append(coeff.get("label", f"{id_a}+{id_b}"))

    return savings, applied_labels


def _compute_combined_savings(
    interventions: List[Dict[str, Any]],
) -> Dict[str, float]:
    """
    Combine savings from multiple interventions.
    Savings are compounded (not additive) to avoid exceeding 100%.
    e.g. two 30% energy savers → 1 - (0.7 * 0.7) = 51% combined, not 60%.
    """
    energy_remaining = 1.0
    water_remaining = 1.0
    waste_remaining = 1.0
    total_co2 = 0.0
    total_annual_savings = 0.0
    total_cost = 0.0

    for iv in interventions:
        energy_remaining *= (1 - iv["energy_saving_pct"] / 100)
        water_remaining *= (1 - iv["water_saving_pct"] / 100)
        waste_remaining *= (1 - iv["waste_reduction_pct"] / 100)
        total_co2 += iv["co2_reduction_kg_year"]
        total_annual_savings += iv["annual_savings_inr"]
        total_cost += iv["cost_inr"]

    return {
        "energy_saving_pct": round((1 - energy_remaining) * 100, 3),
        "water_saving_pct": round((1 - water_remaining) * 100, 3),
        "waste_reduction_pct": round((1 - waste_remaining) * 100, 3),
        "co2_reduction_kg_year": round(total_co2, 2),
        "total_annual_savings_inr": round(total_annual_savings, 2),
        "total_cost_inr": round(total_cost, 2),
    }


# ── Scoring normalisation bounds (exposed for transparency) ──────────────────
SCORE_BOUNDS = {
    "energy":    {"max": 60.0,      "unit": "% saving",     "description": "max 60% energy reduction achievable with this catalogue"},
    "water":     {"max": 60.0,      "unit": "% saving",     "description": "max 60% water reduction achievable with this catalogue"},
    "waste":     {"max": 60.0,      "unit": "% reduction",  "description": "max 60% waste reduction achievable with this catalogue"},
    "co2":       {"max": 80_000.0,  "unit": "kg/year",      "description": "sum of all catalogue CO₂ reductions (upper bound)"},
    "financial": {"max": 1.5,       "unit": "ROI ratio",    "description": "annual_savings / cost normalised at ROI = 1.5"},
}


def _score_portfolio(
    savings: Dict[str, float],
    weights: Dict[str, float],
) -> Tuple[float, Dict[str, float]]:
    """
    Transparent multi-objective score in [0, 1].

    Each dimension is normalised against SCORE_BOUNDS then capped at 1.0:
      energy:    energy_saving_pct / 60
      water:     water_saving_pct  / 60
      waste:     waste_reduction_pct / 60
      co2:       co2_reduction_kg_year / 80 000
      financial: (annual_savings / cost) / 1.5

    composite = Σ weight_k × normalised_k   (weights sum to 1.0)
    """
    cost   = savings.get("total_cost_inr", 1)
    annual = savings.get("total_annual_savings_inr", 0)
    roi    = (annual / cost) if cost > 0 else 0.0

    components = {
        "energy":    min(savings.get("energy_saving_pct",    0) / SCORE_BOUNDS["energy"]["max"],    1.0),
        "water":     min(savings.get("water_saving_pct",     0) / SCORE_BOUNDS["water"]["max"],     1.0),
        "waste":     min(savings.get("waste_reduction_pct",  0) / SCORE_BOUNDS["waste"]["max"],     1.0),
        "co2":       min(savings.get("co2_reduction_kg_year",0) / SCORE_BOUNDS["co2"]["max"],       1.0),
        "financial": min(roi                                    / SCORE_BOUNDS["financial"]["max"],  1.0),
    }

    score = sum(weights[k] * components[k] for k in weights)
    return round(score, 6), {k: round(v, 4) for k, v in components.items()}


def _build_result(
    mode: str,
    interventions: List[Dict[str, Any]],
    budget_inr: float,
    baseline: Dict[str, float],
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Compute full SimulationResult dict from a selected portfolio."""
    w = _validate_weights(weights)
    ids = [iv["id"] for iv in interventions]

    savings = _compute_combined_savings(interventions)
    savings, interactions = _apply_interactions(ids, savings)

    proj_energy = baseline["energy"] * (1 - savings["energy_saving_pct"] / 100)
    proj_water  = baseline["water"]  * (1 - savings["water_saving_pct"]  / 100)
    proj_waste  = baseline["waste"]  * (1 - savings["waste_reduction_pct"] / 100)
    # CO2 projection: subtract absolute reduction from baseline CO2
    proj_co2 = max(0, baseline["co2"] - savings["co2_reduction_kg_year"])

    total_cost     = savings["total_cost_inr"]
    annual_savings = savings["total_annual_savings_inr"]

    avg_payback = round(total_cost / annual_savings, 2) if annual_savings > 0 else float("inf")

    score, score_breakdown = _score_portfolio(savings, w)

    co2_reduction_pct = (
        round((savings["co2_reduction_kg_year"] / baseline["co2"]) * 100, 2)
        if baseline["co2"] > 0 else 0.0
    )

    # Objective formula metadata — fully exposed for UI transparency
    objective_formula = {
        "weights": w,
        "normalisation_bounds": {
            dim: {"max": SCORE_BOUNDS[dim]["max"], "unit": SCORE_BOUNDS[dim]["unit"]}
            for dim in SCORE_BOUNDS
        },
        "formula": "composite = Σ weight_k × min(metric_k / max_k, 1.0)",
        "savings_combination": "projected = baseline × Π (1 − reduction_i)",
    }

    return {
        "mode": mode,
        "interventions_applied": [
            {
                "id": iv["id"],
                "name": iv["name"],
                "cost_inr": iv["cost_inr"],
                "energy_saving_pct": iv["energy_saving_pct"],
                "water_saving_pct": iv["water_saving_pct"],
                "waste_reduction_pct": iv["waste_reduction_pct"],
                "co2_reduction_kg_year": iv["co2_reduction_kg_year"],
                "annual_savings_inr": iv["annual_savings_inr"],
                "payback_years": iv["payback_years"],
            }
            for iv in interventions
        ],
        "total_cost_inr": total_cost,
        "remaining_budget_inr": round(budget_inr - total_cost, 2),
        "baseline_energy_kwh": baseline["energy"],
        "baseline_water_m3": baseline["water"],
        "baseline_waste_kg": baseline["waste"],
        "baseline_co2_kg": baseline["co2"],
        "projected_energy_kwh": round(proj_energy, 2),
        "projected_water_m3": round(proj_water, 2),
        "projected_waste_kg": round(proj_waste, 2),
        "projected_co2_kg": round(proj_co2, 2),
        "energy_saving_pct": savings["energy_saving_pct"],
        "water_saving_pct": savings["water_saving_pct"],
        "waste_reduction_pct": savings["waste_reduction_pct"],
        "co2_reduction_pct": co2_reduction_pct,
        "total_annual_savings_inr": annual_savings,
        "avg_payback_years": avg_payback,
        "score": score,
        "score_breakdown": score_breakdown,
        "objective_formula": objective_formula,
        "interactions_applied": interactions,
        "disclaimer": (
            "Estimated result based on model assumptions. "
            "Actual results should be validated using campus measurements."
        ),
    }


# ── Public API ────────────────────────────────────────────────────────────────

def run_manual_simulation(
    intervention_ids: List[str],
    budget_inr: float,
    baseline: Dict[str, float],
) -> Dict[str, Any]:
    """
    Manual mode: compute combined impact for the user's chosen interventions.
    Budget validation is informational (we flag exceeded but still compute).
    """
    interventions = get_interventions_by_ids(intervention_ids)
    return _build_result("manual", interventions, budget_inr, baseline)


def run_budget_optimization(
    budget_inr: float,
    baseline: Dict[str, float],
    weights: Optional[Dict[str, float]] = None,
    top_n: int = 3,
) -> List[Dict[str, Any]]:
    """
    Optimization mode: exhaustive evaluation of all feasible subsets.
    Returns top_n portfolios ranked by objective score.

    With 8 interventions the search space is 2^8 - 1 = 255 combinations —
    fully enumerable at runtime.
    """
    catalog = load_interventions()
    w = _validate_weights(weights)
    results = []

    n = len(catalog)
    for r in range(1, n + 1):
        for subset in combinations(catalog, r):
            total_cost = sum(iv["cost_inr"] for iv in subset)
            if total_cost > budget_inr:
                continue
            result = _build_result("optimized", list(subset), budget_inr, baseline, weights)
            results.append(result)

    if not results:
        return []

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_n]
