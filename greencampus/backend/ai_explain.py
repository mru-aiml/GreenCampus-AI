"""
AI Explanation Service — abstraction layer.

Supports two modes controlled by environment variable GRANITE_MODE=1:
  - Granite mode: calls IBM Granite via ibm-watsonx-ai SDK (credentials from env).
  - Fallback / DEMO MODE: deterministic template-based explanations (default).

Callers always use explain_simulation() and answer_question().
They never need to know which mode is active.

Required env vars for Granite mode (never hard-coded):
  WATSONX_API_KEY       — IBM watsonx.ai API key
  WATSONX_PROJECT_ID    — watsonx.ai project ID
  WATSONX_URL           — (optional) default: https://us-south.ml.cloud.ibm.com
  GRANITE_MODEL_ID      — (optional) default: ibm/granite-4-h-small
                          Must be a model available in your watsonx.ai account.
                          ibm/granite-13b-instruct-v2 has been withdrawn and must not be used.
"""
import os
import json
import logging
from typing import Dict, Any, Optional, Tuple

log = logging.getLogger(__name__)

GRANITE_MODE: bool = os.getenv("GRANITE_MODE", "0").strip() == "1"
_DEMO_MODE_LABEL = "⚙️ DEMO MODE — deterministic template (set GRANITE_MODE=1 for IBM Granite)"

# ── Template Helpers ──────────────────────────────────────────────────────────

def _fmt_inr(value: float) -> str:
    if value >= 1_00_000:
        return f"₹{value / 1_00_000:.1f} lakh"
    return f"₹{value:,.0f}"


def _fmt_pct(value: float) -> str:
    return f"{value:.1f}%"


def _template_explain_simulation(result: Dict[str, Any]) -> str:
    """
    Deterministic template explanation.  All numbers come directly from `result` —
    no values are invented.  Sections:
      1. Portfolio summary
      2. Selection rationale (why these interventions)
      3. Budget utilisation
      4. Environmental impact
      5. Financial impact & payback
      6. Synergy effects
      7. Scoring (optimized mode)
      8. Savings methodology
      9. Assumptions & uncertainty
    """
    ivs = result.get("interventions_applied", [])
    names = [iv["name"] for iv in ivs]
    n = len(names)
    mode = result.get("mode", "optimized")
    is_opt = mode == "optimized"

    if n == 0:
        return f"{_DEMO_MODE_LABEL}\n\nNo interventions were selected for this simulation."

    names_str = (
        ", ".join(names[:-1]) + f" and {names[-1]}"
        if n > 1 else names[0]
    )

    # ── 1. Header ─────────────────────────────────────────────────────────────
    lines = [
        f"[{_DEMO_MODE_LABEL}]",
        "",
        f"### {'Optimized' if is_opt else 'Manual'} Portfolio — {n} Intervention{'s' if n > 1 else ''}",
        "",
    ]

    # ── 2. Selection rationale ────────────────────────────────────────────────
    lines += [
        "**Why these interventions?**",
    ]
    if is_opt:
        formula = result.get("objective_formula", {})
        w = formula.get("weights", {})
        lines.append(
            "The optimizer evaluated all feasible combinations within the budget and "
            f"ranked them by a weighted composite score "
            f"(energy {w.get('energy',0.25)*100:.0f}%, "
            f"water {w.get('water',0.15)*100:.0f}%, "
            f"waste {w.get('waste',0.10)*100:.0f}%, "
            f"CO₂ {w.get('co2',0.25)*100:.0f}%, "
            f"financial ROI {w.get('financial',0.25)*100:.0f}%). "
            f"This portfolio achieved the highest composite score of **{result.get('score', 0):.4f}** "
            "among all combinations that fit within the budget."
        )
    else:
        lines.append(
            f"Interventions were manually selected: **{names_str}**. "
            "The combined impact is calculated using compounded (not additive) savings."
        )
    lines.append("")

    # ── 3. Budget utilisation ─────────────────────────────────────────────────
    total_cost = result.get("total_cost_inr", 0)
    remaining  = result.get("remaining_budget_inr", 0)
    budget     = total_cost + max(remaining, 0) if remaining >= 0 else total_cost
    util_pct   = (total_cost / budget * 100) if budget > 0 else 0
    lines += [
        "**Budget utilisation:**",
        f"- Total investment: **{_fmt_inr(total_cost)}**",
        f"- Remaining budget: **{_fmt_inr(max(remaining, 0))}**",
        f"- Utilisation: **{util_pct:.1f}%** of available budget",
        "",
    ]

    # ── 4. Environmental impact ───────────────────────────────────────────────
    lines += [
        "**Projected environmental impact** *(compounded savings, not additive — see methodology below)*:",
        f"- Energy reduction: **{_fmt_pct(result.get('energy_saving_pct', 0))}** "
        f"({_fmt_inr(result.get('baseline_energy_kwh', 0) - result.get('projected_energy_kwh', 0))} kWh/yr avoided)",
        f"- Water reduction:  **{_fmt_pct(result.get('water_saving_pct', 0))}** "
        f"({result.get('baseline_water_m3', 0) - result.get('projected_water_m3', 0):,.0f} m³/yr avoided)",
        f"- Waste reduction:  **{_fmt_pct(result.get('waste_reduction_pct', 0))}** "
        f"({result.get('baseline_waste_kg', 0) - result.get('projected_waste_kg', 0):,.0f} kg/yr avoided)",
        f"- CO₂ reduction:    **{result.get('co2_reduction_pct', 0):.1f}%** "
        f"({result.get('projected_co2_kg', 0):,.0f} kg CO₂e/yr projected)",
        "",
    ]

    # ── 5. Financial impact & payback ─────────────────────────────────────────
    ann_sav = result.get("total_annual_savings_inr", 0)
    payback = result.get("avg_payback_years", float("inf"))
    pb_str  = f"{payback:.1f} years" if payback != float("inf") else "∞ (no financial savings)"
    lines += [
        "**Financial impact:**",
        f"- Annual financial savings: **{_fmt_inr(ann_sav)}/year**",
        f"- Simple payback period:    **{pb_str}**",
        f"  *(Simple payback = total cost ÷ annual savings. "
        "Excludes financing costs, inflation, and equipment degradation.)*",
        "",
    ]

    # ── 6. Synergy effects ────────────────────────────────────────────────────
    interactions = result.get("interactions_applied", [])
    if interactions:
        lines += [
            "**Synergy effects applied:**",
        ]
        for label in interactions:
            lines.append(f"- {label}")
        lines.append(
            "*(Synergy coefficients multiply the combined savings — "
            "e.g. HVAC + Solar: ×1.05 on energy and CO₂ dimensions.)*"
        )
        lines.append("")

    # ── 7. Scoring breakdown (optimized mode) ─────────────────────────────────
    if is_opt and result.get("score_breakdown"):
        bd = result["score_breakdown"]
        formula = result.get("objective_formula", {})
        norm = formula.get("normalisation_bounds", {})
        lines += [
            "**Objective score breakdown** *(each dimension normalised 0–1 against catalogue upper bound, then weighted)*:",
            f"| Dimension | Normalised | Weight | Contribution |",
            f"|---|---|---|---|",
        ]
        w = formula.get("weights", {
            "energy": 0.25, "water": 0.15, "waste": 0.10, "co2": 0.25, "financial": 0.25
        })
        for dim in ("energy", "water", "waste", "co2", "financial"):
            n_val = bd.get(dim, 0)
            wt    = w.get(dim, 0)
            bound = norm.get(dim, "—")
            lines.append(
                f"| {dim.capitalize()} | {n_val:.4f} | {wt*100:.0f}% | {n_val*wt:.4f} |"
            )
        lines.append(f"| **Composite** | | | **{result.get('score', 0):.4f}** |")
        lines.append("")

    # ── 8. Savings methodology ────────────────────────────────────────────────
    lines += [
        "**Savings combination methodology:**",
        "Percentage reductions are compounded, not added:",
        "```",
        "projected = baseline × (1 − r₁) × (1 − r₂) × … × (1 − rₙ)",
        "```",
        "This prevents the combined saving from exceeding 100% when multiple "
        "interventions address the same resource.",
        "",
    ]

    # ── 9. Assumptions & uncertainty ─────────────────────────────────────────
    lines += [
        "**Assumptions & uncertainty:**",
        "- Intervention savings percentages are prototype assumptions, not measured values.",
        "- Grid emission factor: 0.716 kg CO₂/kWh (CEA India, prototype approximation).",
        "- CO₂ from water treatment: 0.344 kg CO₂/m³ (prototype).",
        "- CO₂ from landfill waste: 0.50 kg CO₂e/kg (prototype).",
        "- Actual savings depend on occupancy, maintenance, local climate, and equipment age.",
        "",
        f"*{result.get('disclaimer', '')}*",
    ]

    return "\n".join(lines)


def _template_answer_question(question: str, context: Dict[str, Any]) -> str:
    q = question.lower()
    metrics = context.get("current_metrics", {})
    last_sim = context.get("last_simulation")

    if any(w in q for w in ["energy", "kwh", "electricity"]):
        kwh = metrics.get("annual_energy_kwh", "N/A")
        return (
            f"Based on the campus data, the current annual energy consumption is "
            f"**{kwh:,.0f} kWh**. "
            + (
                f"The last simulation projects reducing this to "
                f"**{last_sim['projected_energy_kwh']:,.0f} kWh** "
                f"(a {last_sim['energy_saving_pct']:.1f}% reduction)."
                if last_sim else ""
            )
        )

    if any(w in q for w in ["water", "litre", "liter", "m3", "m³"]):
        m3 = metrics.get("annual_water_m3", "N/A")
        return (
            f"Current annual water consumption is **{m3:,.0f} m³**. "
            + (
                f"The simulation projects **{last_sim['water_saving_pct']:.1f}%** reduction."
                if last_sim else ""
            )
        )

    if any(w in q for w in ["waste", "recycle", "landfill", "compost"]):
        waste = metrics.get("annual_waste_kg", "N/A")
        rate = metrics.get("recycling_rate_pct", "N/A")
        return (
            f"Campus generates **{waste:,.0f} kg** of waste annually. "
            f"Current recycling + composting rate is **{rate}%**."
        )

    if any(w in q for w in ["co2", "carbon", "emission", "greenhouse"]):
        co2 = metrics.get("annual_co2_kg", "N/A")
        return (
            f"Estimated annual CO₂e emissions are **{co2:,.0f} kg** "
            f"based on energy, water, and landfill waste factors."
        )

    if any(w in q for w in ["recommend", "suggest", "best", "top", "which"]):
        if last_sim:
            names = [iv["name"] for iv in last_sim.get("interventions_applied", [])]
            return (
                f"Based on the last optimized simulation, the recommended interventions are: "
                f"**{', '.join(names)}**. "
                f"They achieve a composite score of **{last_sim['score']:.4f}** and "
                f"deliver **{_fmt_inr(last_sim['total_annual_savings_inr'])}** annual savings."
            )
        return (
            "Run a Budget Optimization simulation first to get ranked recommendations "
            "tailored to your budget."
        )

    if any(w in q for w in ["payback", "roi", "return"]):
        if last_sim:
            return (
                f"The current portfolio has an average payback period of "
                f"**{last_sim['avg_payback_years']:.1f} years** on a total investment of "
                f"**{_fmt_inr(last_sim['total_cost_inr'])}**."
            )
        return "Please run a simulation first to calculate payback for a specific portfolio."

    # Generic fallback — ground the answer in available numbers
    parts = ["I can help with questions about:"]
    parts.append(f"- **Energy**: {metrics.get('annual_energy_kwh', 'N/A'):,} kWh/year" if isinstance(metrics.get('annual_energy_kwh'), (int, float)) else "- Energy consumption")
    parts.append(f"- **Water**: {metrics.get('annual_water_m3', 'N/A'):,} m³/year" if isinstance(metrics.get('annual_water_m3'), (int, float)) else "- Water consumption")
    parts.append(f"- **CO₂**: {metrics.get('annual_co2_kg', 'N/A'):,} kg/year" if isinstance(metrics.get('annual_co2_kg'), (int, float)) else "- CO₂ emissions")
    parts.append("- Intervention recommendations, payback periods, and simulation results.")
    parts.append("\nPlease ask a specific question about any of these topics.")
    return "\n".join(parts)


# ── Granite Mode ──────────────────────────────────────────────────────────────

def _build_granite_sim_prompt(result: Dict[str, Any], context: Optional[Dict[str, Any]]) -> str:
    """
    Structured prompt for IBM Granite — simulation explanation.
    Explicit instruction to use only provided data values.
    """
    # Slim down the result to the fields Granite needs — avoid token waste
    slim = {
        "mode":                    result.get("mode"),
        "interventions_applied":   [
            {"name": iv["name"], "cost_inr": iv["cost_inr"],
             "energy_saving_pct": iv["energy_saving_pct"],
             "water_saving_pct":  iv["water_saving_pct"],
             "waste_reduction_pct": iv["waste_reduction_pct"],
             "co2_reduction_kg_year": iv["co2_reduction_kg_year"],
             "annual_savings_inr": iv["annual_savings_inr"],
             "payback_years":     iv["payback_years"]}
            for iv in result.get("interventions_applied", [])
        ],
        "total_cost_inr":           result.get("total_cost_inr"),
        "remaining_budget_inr":     result.get("remaining_budget_inr"),
        "baseline_energy_kwh":      result.get("baseline_energy_kwh"),
        "projected_energy_kwh":     result.get("projected_energy_kwh"),
        "energy_saving_pct":        result.get("energy_saving_pct"),
        "water_saving_pct":         result.get("water_saving_pct"),
        "waste_reduction_pct":      result.get("waste_reduction_pct"),
        "co2_reduction_pct":        result.get("co2_reduction_pct"),
        "projected_co2_kg":         result.get("projected_co2_kg"),
        "total_annual_savings_inr": result.get("total_annual_savings_inr"),
        "avg_payback_years":        result.get("avg_payback_years"),
        "score":                    result.get("score"),
        "score_breakdown":          result.get("score_breakdown"),
        "interactions_applied":     result.get("interactions_applied", []),
        "objective_formula":        result.get("objective_formula", {}),
    }
    return (
        "You are a campus sustainability advisor producing a clear, factual explanation "
        "of an EcoSim-Opt simulation result.\n\n"
        "RULES (follow strictly):\n"
        "1. Use ONLY the numerical values present in the JSON below. Do NOT invent numbers.\n"
        "2. Explain: why these interventions were selected, budget utilisation, "
        "environmental impact, financial savings, payback, synergy effects if any, "
        "and the savings combination methodology (compounded, not additive).\n"
        "3. End with a single-sentence uncertainty disclaimer.\n"
        "4. Keep the explanation under 350 words.\n\n"
        f"Simulation result (JSON):\n{json.dumps(slim, indent=2)}\n\n"
        + (f"Additional context:\n{json.dumps(context, indent=2)}\n\n" if context else "")
        + "Explanation:"
    )


def _build_granite_qa_prompt(question: str, context: Dict[str, Any]) -> str:
    """Structured prompt for Q&A — strictly grounded in provided context."""
    return (
        "You are a campus sustainability advisor.\n\n"
        "RULES (follow strictly):\n"
        "1. Answer using ONLY the numerical values present in the JSON context below.\n"
        "2. Do NOT invent, estimate, or extrapolate any numbers not in the context.\n"
        "3. If the answer cannot be found in the context, say so clearly.\n"
        "4. Keep the answer concise (under 150 words).\n\n"
        f"Question: {question}\n\n"
        f"Context (JSON):\n{json.dumps(context, indent=2)}\n\n"
        "Answer:"
    )


def _call_granite(prompt: str) -> Tuple[str, bool]:
    """
    Call IBM Granite via ibm-watsonx-ai SDK.
    Credentials are read exclusively from environment variables — never hard-coded.

    Returns (response_text, success).
    On any failure, returns ("", False) so callers fall back to DEMO MODE.
    """
    api_key    = os.getenv("WATSONX_API_KEY", "").strip()
    project_id = os.getenv("WATSONX_PROJECT_ID", "").strip()
    url        = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com").strip()
    model_id   = os.getenv("GRANITE_MODEL_ID", "ibm/granite-4-h-small").strip()

    if not api_key or not project_id:
        log.warning(
            "GRANITE_MODE=1 but WATSONX_API_KEY or WATSONX_PROJECT_ID is missing. "
            "Falling back to DEMO MODE."
        )
        return "", False

    try:
        from ibm_watsonx_ai import APIClient, Credentials
        from ibm_watsonx_ai.foundation_models import ModelInference

        client = APIClient(Credentials(url=url, api_key=api_key))
        model  = ModelInference(
            model_id=model_id,
            api_client=client,
            project_id=project_id,
            params={"max_new_tokens": 512, "temperature": 0.1},
        )
        text = model.generate_text(prompt=prompt)
        return text, True
    except ImportError:
        log.error("ibm-watsonx-ai package not installed. Run: pip install ibm-watsonx-ai")
        return "", False
    except Exception as exc:
        log.error("Granite call failed: %s", str(exc)[:200])
        return "", False


# ── Public API ────────────────────────────────────────────────────────────────

def explain_simulation(result: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> str:
    """
    Generate a natural-language explanation of a simulation result.

    Granite mode (GRANITE_MODE=1):
      - Builds a structured, data-grounded prompt.
      - Calls IBM Granite; on any failure silently falls back to DEMO MODE.

    DEMO MODE (default / fallback):
      - Returns a deterministic template explanation.
      - Clearly labelled with _DEMO_MODE_LABEL so the user knows.
    """
    if GRANITE_MODE:
        prompt = _build_granite_sim_prompt(result, context)
        text, ok = _call_granite(prompt)
        if ok and text.strip():
            return text.strip()
    return _template_explain_simulation(result)


def answer_question(question: str, context: Dict[str, Any]) -> str:
    """
    Answer a natural-language sustainability question, grounded in provided context.

    Granite mode: structured prompt, strictly data-grounded.
    DEMO MODE: deterministic template matcher.
    """
    if GRANITE_MODE:
        prompt = _build_granite_qa_prompt(question, context)
        text, ok = _call_granite(prompt)
        if ok and text.strip():
            return text.strip()
    return _template_answer_question(question, context)


def get_mode_label() -> str:
    """Return a human-readable label for the currently active AI mode."""
    if GRANITE_MODE:
        api_key = os.getenv("WATSONX_API_KEY", "").strip()
        project_id = os.getenv("WATSONX_PROJECT_ID", "").strip()
        if api_key and project_id:
            model_id = os.getenv("GRANITE_MODEL_ID", "ibm/granite-4-h-small")
            return f"IBM Granite ({model_id})"
        return "IBM Granite — credentials missing, using DEMO MODE"
    return "DEMO MODE (deterministic template)"
