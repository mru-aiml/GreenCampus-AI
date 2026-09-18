"""
What-if scenario parser.
Lightweight rule-based parser — no LLM dependency.

Handles patterns like:
  "What if AC energy consumption is reduced by 15%?"
  "What if the sustainability budget is ₹5 lakh?"
  "What if we install rooftop solar?"
  "What if water usage drops by 20%?"
"""
import re
from typing import Dict, Any, Optional

# ── Pattern Library ───────────────────────────────────────────────────────────

# Percentage reduction patterns
_PCT_REDUCE = re.compile(
    r"(energy|water|waste|co2|carbon)"
    r"\s+(?:consumption|emissions?|usage)?\s*"
    r"(?:(?:is|are)\s+)?(?:reduced?|cut|decrease[sd]?|drop[s]?|lower[sed]?)\s+by\s+(\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)

# Budget patterns — matches:
#   "budget is ₹5 lakh", "budget increases to ₹10 lakh", "budget ₹5 lakh"
_BUDGET_LAKH = re.compile(
    r"budget\s+(?:is|increases?\s+to|changes?\s+to|set\s+to)?\s*"
    r"(?:₹|rs\.?\s*)?(\d+(?:\.\d+)?)\s*lakh",
    re.IGNORECASE,
)
_BUDGET_CRORE = re.compile(
    r"budget\s+(?:is|increases?\s+to|changes?\s+to|set\s+to)?\s*"
    r"(?:₹|rs\.?\s*)?(\d+(?:\.\d+)?)\s*crore",
    re.IGNORECASE,
)
_BUDGET_RAW = re.compile(
    r"budget\s+(?:is|increases?\s+to|changes?\s+to|set\s+to)?\s*"
    r"(?:₹|rs\.?\s*)?([\d,]+)",
    re.IGNORECASE,
)

# Install intervention
_INSTALL = re.compile(
    r"(?:install|add|deploy|implement)\s+(.+?)(?:\?|$)",
    re.IGNORECASE,
)

# AC-specific energy reduction
_AC_PCT = re.compile(
    r"ac\s+(?:energy\s+)?consumption\s+(?:is\s+)?(?:reduced?\s+)?by\s+(\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)

# Emission factor change
_EMISSION_FACTOR = re.compile(
    r"(?:grid\s+)?emission\s+factor\s+(?:is\s+|changes?\s+to\s+)?(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

# ── Intervention name → ID mapping ───────────────────────────────────────────
_NAME_MAP = {
    "rooftop solar": "rooftop_solar",
    "solar panels": "rooftop_solar",
    "solar": "rooftop_solar",
    "led": "led_retrofit",
    "led lighting": "led_retrofit",
    "led retrofit": "led_retrofit",
    "hvac": "hvac_optimization",
    "hvac optimization": "hvac_optimization",
    "smart metering": "smart_metering",
    "smart meter": "smart_metering",
    "leak detection": "leak_detection",
    "composting": "composting",
    "waste segregation": "waste_segregation",
    "segregation": "waste_segregation",
    "rainwater harvesting": "rainwater_harvesting",
    "rainwater": "rainwater_harvesting",
}


def _fuzzy_match_intervention(text: str) -> Optional[str]:
    text_lower = text.lower().strip()
    for phrase, id_ in _NAME_MAP.items():
        if phrase in text_lower:
            return id_
    return None


def parse_what_if(query: str) -> Dict[str, Any]:
    """
    Parse a natural-language what-if query into a structured scenario dict.

    Returns:
        {
          "type": "energy_reduction" | "water_reduction" | "waste_reduction" |
                  "co2_reduction" | "budget_change" | "install_intervention" |
                  "emission_factor_change" | "unknown",
          "params": { ... type-specific parameters ... },
          "original_query": query,
          "parse_confidence": "high" | "medium" | "low",
        }
    """
    q = query.strip()

    # Budget
    m = _BUDGET_LAKH.search(q)
    if m:
        return {
            "type": "budget_change",
            "params": {"budget_inr": float(m.group(1)) * 1_00_000},
            "original_query": q,
            "parse_confidence": "high",
        }

    m = _BUDGET_CRORE.search(q)
    if m:
        return {
            "type": "budget_change",
            "params": {"budget_inr": float(m.group(1)) * 1_00_00_000},
            "original_query": q,
            "parse_confidence": "high",
        }

    m = _BUDGET_RAW.search(q)
    if m:
        raw = m.group(1).replace(",", "")
        return {
            "type": "budget_change",
            "params": {"budget_inr": float(raw)},
            "original_query": q,
            "parse_confidence": "medium",
        }

    # AC energy reduction
    m = _AC_PCT.search(q)
    if m:
        return {
            "type": "energy_reduction",
            "params": {"reduction_pct": float(m.group(1)), "source": "ac"},
            "original_query": q,
            "parse_confidence": "high",
        }

    # Generic reduction
    m = _PCT_REDUCE.search(q)
    if m:
        category = m.group(1).lower()
        if category == "carbon":
            category = "co2"
        return {
            "type": f"{category}_reduction",
            "params": {"reduction_pct": float(m.group(2))},
            "original_query": q,
            "parse_confidence": "high",
        }

    # Install intervention
    m = _INSTALL.search(q)
    if m:
        matched_id = _fuzzy_match_intervention(m.group(1))
        if matched_id:
            return {
                "type": "install_intervention",
                "params": {"intervention_id": matched_id},
                "original_query": q,
                "parse_confidence": "high",
            }
        return {
            "type": "install_intervention",
            "params": {"intervention_id": None, "raw_name": m.group(1).strip()},
            "original_query": q,
            "parse_confidence": "low",
        }

    # Emission factor
    m = _EMISSION_FACTOR.search(q)
    if m:
        return {
            "type": "emission_factor_change",
            "params": {"new_factor_kg_per_kwh": float(m.group(1))},
            "original_query": q,
            "parse_confidence": "medium",
        }

    return {
        "type": "unknown",
        "params": {},
        "original_query": q,
        "parse_confidence": "low",
    }


def apply_what_if(
    scenario: Dict[str, Any],
    current_metrics: Dict[str, Any],
    interventions_catalog: list,
) -> Dict[str, Any]:
    """
    Apply a parsed what-if scenario to current metrics.
    Returns updated metrics and a human-readable delta summary.
    """
    t = scenario["type"]
    p = scenario["params"]
    updated = current_metrics.copy()
    deltas: Dict[str, Any] = {}

    if t == "energy_reduction":
        pct = p.get("reduction_pct", 0)
        original = updated.get("annual_energy_kwh", 0)
        updated["annual_energy_kwh"] = round(original * (1 - pct / 100), 2)
        deltas["energy_kwh_saved"] = round(original - updated["annual_energy_kwh"], 2)
        deltas["reduction_pct"] = pct

    elif t == "water_reduction":
        pct = p.get("reduction_pct", 0)
        original = updated.get("annual_water_m3", 0)
        updated["annual_water_m3"] = round(original * (1 - pct / 100), 2)
        deltas["water_m3_saved"] = round(original - updated["annual_water_m3"], 2)
        deltas["reduction_pct"] = pct

    elif t == "waste_reduction":
        pct = p.get("reduction_pct", 0)
        original = updated.get("annual_waste_kg", 0)
        updated["annual_waste_kg"] = round(original * (1 - pct / 100), 2)
        deltas["waste_kg_saved"] = round(original - updated["annual_waste_kg"], 2)
        deltas["reduction_pct"] = pct

    elif t == "budget_change":
        updated["what_if_budget_inr"] = p.get("budget_inr", 0)
        deltas["new_budget_inr"] = updated["what_if_budget_inr"]

    elif t == "install_intervention":
        iv_id = p.get("intervention_id")
        if iv_id:
            match = next((iv for iv in interventions_catalog if iv["id"] == iv_id), None)
            if match:
                updated["what_if_intervention"] = match
                deltas["intervention_name"] = match["name"]
                deltas["cost_inr"] = match["cost_inr"]
                deltas["energy_saving_pct"] = match["energy_saving_pct"]
                deltas["water_saving_pct"] = match["water_saving_pct"]
                deltas["co2_reduction_kg_year"] = match["co2_reduction_kg_year"]

    elif t == "emission_factor_change":
        updated["what_if_emission_factor"] = p.get("new_factor_kg_per_kwh")
        deltas["new_emission_factor"] = updated["what_if_emission_factor"]

    updated["_what_if_deltas"] = deltas
    return updated
