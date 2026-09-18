"""
GreenCampus AI – FastAPI backend
Run: uvicorn main:app --reload --port 8000
"""
import os
import io
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Response, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from models import (
    ManualSimulationRequest,
    OptimizationRequest,
    WhatIfRequest,
    AssistantRequest,
    ExplainRequest,
    CampusDataRequest,
    MetricsResponse,
    HealthResponse,
    CampusDataStatusResponse,
)
from calculations import compute_all_metrics, compute_annual_co2_kg
from data_loader import load_energy, load_water, load_waste, load_interventions
from simulator import run_manual_simulation, run_budget_optimization
from ai_explain import explain_simulation, answer_question, GRANITE_MODE, get_mode_label
from what_if_parser import parse_what_if, apply_what_if
import campus_data as cd
from data_validator import validate_campus_data, parse_csv_to_raw, generate_csv_template

app = FastAPI(
    title="GreenCampus AI",
    description="Campus sustainability decision-support platform – prototype",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://greencampus-ai-1.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load persisted user data (if any) on startup
cd.load_persisted_data()


# ── Session cookie helpers ────────────────────────────────────────────────────

def _get_session_id(
    request: Request,
    response: Response,
    gc_sid: Optional[str] = Cookie(default=None),
) -> str:
    """
    Resolve the current session ID from the HttpOnly cookie.
    If the cookie is missing or unrecognised, create a new session and
    set the cookie on the response.

    NOTE: This is a prototype-grade session — no database, no expiry
    enforcement beyond cookie max-age, no CSRF protection.
    """
    sid, is_new = cd._get_or_create_session(gc_sid)
    if is_new:
        response.set_cookie(
            key=cd.SESSION_COOKIE,
            value=sid,
            httponly=True,
            samesite="lax",
            max_age=cd._COOKIE_MAX_AGE,
            # secure=True should be added in a TLS-terminated production deploy
        )
    return sid


def _get_baseline(session_id: Optional[str] = None) -> Dict[str, float]:
    metrics = compute_all_metrics(session_id=session_id)
    return {
        "energy": metrics["annual_energy_kwh"],
        "water":  metrics["annual_water_m3"],
        "waste":  metrics["annual_waste_kg"],
        "co2":    metrics["annual_co2_kg"],
    }


def _get_active_budget(session_id: Optional[str] = None) -> float:
    """Return the user-defined budget if available, otherwise 500_000 default."""
    if session_id and cd.is_session_user_mode(session_id):
        data = cd.get_session_data(session_id)
        if data and data.get("budget_inr"):
            return float(data["budget_inr"])
    elif cd.is_user_mode():
        data = cd.get_user_campus_data()
        if data and data.get("budget_inr"):
            return float(data["budget_inr"])
    return 500_000.0


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse)
def health():
    return {
        "status": "ok",
        "version": "0.2.0",
        "granite_mode": GRANITE_MODE,
        "ai_mode_label": get_mode_label(),
    }


# ── Data Endpoints ────────────────────────────────────────────────────────────

@app.get("/api/metrics", response_model=MetricsResponse)
def get_metrics(
    request: Request,
    response: Response,
    gc_sid: Optional[str] = Cookie(default=None),
):
    sid = _get_session_id(request, response, gc_sid)
    return compute_all_metrics(session_id=sid)


@app.get("/api/energy")
def get_energy(
    request: Request,
    response: Response,
    gc_sid: Optional[str] = Cookie(default=None),
):
    sid = _get_session_id(request, response, gc_sid)
    return load_energy(session_id=sid)


@app.get("/api/water")
def get_water(
    request: Request,
    response: Response,
    gc_sid: Optional[str] = Cookie(default=None),
):
    sid = _get_session_id(request, response, gc_sid)
    return load_water(session_id=sid)


@app.get("/api/waste")
def get_waste(
    request: Request,
    response: Response,
    gc_sid: Optional[str] = Cookie(default=None),
):
    sid = _get_session_id(request, response, gc_sid)
    return load_waste(session_id=sid)


@app.get("/api/interventions")
def get_interventions():
    return load_interventions()


# ── Campus Data Management ────────────────────────────────────────────────────

@app.get("/api/campus-data/status", response_model=CampusDataStatusResponse)
def campus_data_status(
    request: Request,
    response: Response,
    gc_sid: Optional[str] = Cookie(default=None),
):
    """Return current active dataset mode and completeness."""
    sid = _get_session_id(request, response, gc_sid)
    mode = cd.get_session_mode(sid)
    user_data = cd.get_session_data(sid) if mode == "user" else None
    completeness = cd.get_completeness_flags(user_data, session_id=sid) if mode == "user" else None
    return {
        "mode": mode,
        "label": cd.get_data_source_label(session_id=sid),
        "has_user_data": user_data is not None,
        "completeness": completeness,
    }


@app.get("/api/campus-data")
def get_campus_data(
    request: Request,
    response: Response,
    gc_sid: Optional[str] = Cookie(default=None),
):
    """Return the current user campus data (if any) for this session."""
    sid = _get_session_id(request, response, gc_sid)
    if cd.is_session_user_mode(sid):
        data = cd.get_session_data(sid)
        if data:
            return {"mode": "user", "data": data}
    return {"mode": "demo", "data": None}


@app.get("/api/campus-data/demo")
def get_demo_campus_data():
    """
    Return the demo dataset expressed as a CampusDataRequest-shaped dict.

    This lets the frontend populate the Campus Data form with real demo values
    after a reset, without inventing any numbers.  All values are derived from
    the same mock_data JSON files used by every other demo-mode calculation.
    """
    from data_loader import _load_energy_demo, _load_water_demo, _load_waste_demo

    energy_raw = _load_energy_demo()
    water_raw  = _load_water_demo()
    waste_raw  = _load_waste_demo()

    # ── Energy: sum per-month across all buildings ────────────────────────────
    n_months = 12
    monthly_energy = [0.0] * n_months
    for building in energy_raw.get("buildings", []):
        for i, v in enumerate(building.get("monthly", [])):
            if i < n_months:
                monthly_energy[i] += v

    # ── Water: sum per-month across all buildings ─────────────────────────────
    monthly_water = [0.0] * n_months
    for building in water_raw.get("buildings", []):
        for i, v in enumerate(building.get("monthly", [])):
            if i < n_months:
                monthly_water[i] += v

    # ── Waste: monthly totals and recycled/compost/landfill percentages ───────
    monthly_waste_kg = [m["total"] for m in waste_raw.get("monthly", [])]
    annual_waste     = sum(monthly_waste_kg)
    annual_recycled  = sum(m["recycled"] for m in waste_raw.get("monthly", []))
    annual_composted = sum(m["compost"]  for m in waste_raw.get("monthly", []))
    annual_landfill  = sum(m["landfill"] for m in waste_raw.get("monthly", []))

    recycled_pct  = round(annual_recycled  / annual_waste * 100, 1) if annual_waste else 0
    composted_pct = round(annual_composted / annual_waste * 100, 1) if annual_waste else 0
    landfill_pct  = round(annual_landfill  / annual_waste * 100, 1) if annual_waste else 0

    # Ensure pcts sum exactly to 100 (adjust landfill for rounding)
    pct_sum = recycled_pct + composted_pct + landfill_pct
    if round(pct_sum, 1) != 100.0:
        landfill_pct = round(100.0 - recycled_pct - composted_pct, 1)

    return {
        "campus": {
            "name":      "Demo Campus",
            "area_m2":   50000,
            "students":  5000,
            "staff":     350,
            "buildings": len(energy_raw.get("buildings", [])),
        },
        "energy": {
            "annual_kwh":      None,   # form will calculate from monthly
            "annual_cost_inr": None,
            "monthly_kwh":     monthly_energy,
        },
        "water": {
            "annual_m3":       None,   # form will calculate from monthly
            "annual_cost_inr": None,
            "monthly_m3":      monthly_water,
        },
        "waste": {
            "annual_kg":      None,    # form will calculate from monthly
            "recycled_pct":   recycled_pct,
            "composted_pct":  composted_pct,
            "landfill_pct":   landfill_pct,
            "monthly_kg":     monthly_waste_kg,
        },
        "budget_inr":        500000,
        "existing_measures": {
            "solar_installed":       False,
            "led_retrofit":          False,
            "hvac_optimization":     False,
            "smart_metering":        False,
            "water_leak_detection":  False,
            "composting":            False,
            "waste_segregation":     False,
            "rainwater_harvesting":  False,
        },
    }


@app.post("/api/campus-data")
def submit_campus_data(
    req: CampusDataRequest,
    request: Request,
    response: Response,
    gc_sid: Optional[str] = Cookie(default=None),
):
    """
    Submit and activate a user campus dataset for this session.

    Validates all fields. On success, activates user dataset so all
    analytics (metrics, energy, water, waste, CO2, EcoSim-Opt, what-if)
    use the user data instead of synthetic demo data.

    Returns the calculated metrics immediately.
    """
    sid = _get_session_id(request, response, gc_sid)

    # Convert Pydantic model to dict for validator
    raw = req.model_dump()

    validated, errors = validate_campus_data(raw)
    if errors:
        raise HTTPException(
            status_code=422,
            detail={"errors": errors, "message": "Campus data validation failed."},
        )

    # Activate user dataset for this session
    cd.set_session_data(sid, validated)

    # Return updated metrics
    metrics = compute_all_metrics(session_id=sid)
    completeness = cd.get_completeness_flags(validated, session_id=sid)

    return {
        "status": "activated",
        "message": "Campus data accepted and activated. All analytics now use your dataset.",
        "data_source": "user",
        "data_source_label": cd.get_data_source_label(session_id=sid),
        "metrics": metrics,
        "completeness": completeness,
    }


@app.delete("/api/campus-data")
def reset_campus_data(
    request: Request,
    response: Response,
    gc_sid: Optional[str] = Cookie(default=None),
):
    """
    Reset to demo dataset for this session.

    Clears user data, reverts active mode to demo, and returns the fresh
    demo metrics so the frontend can update all dashboards in a single
    round-trip.
    """
    sid = _get_session_id(request, response, gc_sid)
    cd.reset_session_to_demo(sid)
    metrics = compute_all_metrics(session_id=sid)
    return {
        "success": True,
        "status": "reset",
        "mode": "demo",
        "message": "Reverted to demo synthetic dataset.",
        "data_source": "demo",
        "data_source_label": cd.get_data_source_label(session_id=sid),
        "metrics": metrics,
    }


@app.post("/api/campus-data/csv")
async def upload_campus_csv(
    file: UploadFile,
    request: Request,
    response: Response,
    gc_sid: Optional[str] = Cookie(default=None),
):
    """
    Upload a CSV file containing campus sustainability data.

    Expected format:
        metric,value,unit
        campus_area,50000,m2
        ...

    See /api/campus-data/csv-template for the full template.
    """
    sid = _get_session_id(request, response, gc_sid)

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=422,
            detail={"errors": ["File must be a .csv file."], "message": "Invalid file type."},
        )

    content = await file.read()
    try:
        csv_text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=422,
            detail={"errors": ["File must be UTF-8 encoded."], "message": "Encoding error."},
        )

    # Parse CSV to raw dict
    raw, parse_errors = parse_csv_to_raw(csv_text)
    if parse_errors:
        raise HTTPException(
            status_code=422,
            detail={"errors": parse_errors, "message": "CSV parsing failed."},
        )

    # Validate
    validated, val_errors = validate_campus_data(raw)
    if val_errors:
        raise HTTPException(
            status_code=422,
            detail={"errors": val_errors, "message": "CSV data validation failed."},
        )

    # Activate for this session
    cd.set_session_data(sid, validated)
    metrics = compute_all_metrics(session_id=sid)
    completeness = cd.get_completeness_flags(validated, session_id=sid)

    return {
        "status": "activated",
        "message": "CSV data accepted and activated. All analytics now use your dataset.",
        "data_source": "user",
        "data_source_label": cd.get_data_source_label(session_id=sid),
        "metrics": metrics,
        "completeness": completeness,
    }


@app.get("/api/campus-data/csv-template", response_class=PlainTextResponse)
def download_csv_template():
    """Download a pre-filled CSV template for campus data entry."""
    template = generate_csv_template()
    return PlainTextResponse(
        content=template,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=campus_data_template.csv"},
    )


# ── Simulation ────────────────────────────────────────────────────────────────

@app.post("/api/simulate")
def simulate(
    req: ManualSimulationRequest,
    request: Request,
    response: Response,
    gc_sid: Optional[str] = Cookie(default=None),
):
    """
    Manual simulation: user-selected interventions with a given budget.
    Budget validation is informational; we still compute if budget is exceeded.
    Uses the ACTIVE dataset as the baseline.
    """
    sid = _get_session_id(request, response, gc_sid)
    if req.budget_inr < 0:
        raise HTTPException(status_code=422, detail="budget_inr must be >= 0")

    baseline = _get_baseline(session_id=sid)
    result = run_manual_simulation(req.intervention_ids, req.budget_inr, baseline)
    result["explanation"] = explain_simulation(result)
    result["data_source"] = cd.get_session_mode(sid)

    if result["total_cost_inr"] > req.budget_inr:
        result["budget_warning"] = (
            f"Total cost ₹{result['total_cost_inr']:,.0f} exceeds "
            f"budget ₹{req.budget_inr:,.0f}. "
            "Shown as informational – reduce interventions or increase budget."
        )
    return result


@app.post("/api/optimize")
def optimize(
    req: OptimizationRequest,
    request: Request,
    response: Response,
    gc_sid: Optional[str] = Cookie(default=None),
):
    """
    Budget optimization: exhaustive portfolio search, returns top 3 portfolios.
    Uses the ACTIVE dataset as the baseline.
    """
    sid = _get_session_id(request, response, gc_sid)
    if req.budget_inr < 0:
        raise HTTPException(status_code=422, detail="budget_inr must be >= 0")

    baseline = _get_baseline(session_id=sid)
    portfolios = run_budget_optimization(
        budget_inr=req.budget_inr,
        baseline=baseline,
        weights=req.weights,
    )

    if not portfolios:
        return {
            "portfolios": [],
            "message": (
                "No feasible combination found within the given budget. "
                "The cheapest single intervention costs "
                f"₹{min(iv['cost_inr'] for iv in load_interventions()):,.0f}."
            ),
            "data_source": cd.get_session_mode(sid),
        }

    for p in portfolios:
        p["explanation"] = explain_simulation(p)
        p["data_source"] = cd.get_session_mode(sid)

    return {"portfolios": portfolios, "data_source": cd.get_session_mode(sid)}


# ── What-If ───────────────────────────────────────────────────────────────────

@app.post("/api/what-if")
def what_if(
    req: WhatIfRequest,
    request: Request,
    response: Response,
    gc_sid: Optional[str] = Cookie(default=None),
):
    sid = _get_session_id(request, response, gc_sid)
    scenario = parse_what_if(req.query)
    # If caller provided metrics, use them; otherwise use active dataset
    metrics = req.current_metrics or compute_all_metrics(session_id=sid)
    catalog = load_interventions()
    updated_metrics = apply_what_if(scenario, metrics, catalog)
    deltas = updated_metrics.pop("_what_if_deltas", {})

    explanation = (
        f"Scenario parsed as **{scenario['type'].replace('_', ' ')}** "
        f"(confidence: {scenario['parse_confidence']}). "
    )
    if deltas:
        explanation += "Changes: " + "; ".join(f"{k}={v}" for k, v in deltas.items()) + "."
    else:
        explanation += "No quantifiable change could be extracted from the query."

    return {
        "parsed_scenario": scenario,
        "updated_metrics": updated_metrics,
        "deltas": deltas,
        "explanation": explanation,
        "data_source": cd.get_session_mode(sid),
        "disclaimer": (
            "Estimated result based on model assumptions. "
            "Actual results should be validated using campus measurements."
        ),
    }


# ── AI Assistant ──────────────────────────────────────────────────────────────

@app.post("/api/assistant")
def assistant(
    req: AssistantRequest,
    request: Request,
    response: Response,
    gc_sid: Optional[str] = Cookie(default=None),
):
    sid = _get_session_id(request, response, gc_sid)
    context = req.context or {}
    if "current_metrics" not in context:
        context["current_metrics"] = compute_all_metrics(session_id=sid)
    if "available_interventions" not in context:
        context["available_interventions"] = [
            {"id": iv["id"], "name": iv["name"], "cost_inr": iv["cost_inr"]}
            for iv in load_interventions()
        ]
    # Inject data source info for grounding
    context["data_source"] = cd.get_session_mode(sid)
    context["data_source_label"] = cd.get_data_source_label(session_id=sid)

    answer = answer_question(req.question, context)
    sources = ["campus_metrics", "interventions_catalog"]
    if context.get("last_simulation"):
        sources.append("last_simulation_result")

    return {
        "answer": answer,
        "sources_used": sources,
        "data_source": cd.get_session_mode(sid),
        "disclaimer": (
            "Response is grounded in the provided campus data context. "
            "No numerical values have been invented."
        ),
    }


# ── Explain ───────────────────────────────────────────────────────────────────

@app.post("/api/explain")
def explain(
    req: ExplainRequest,
    request: Request,
    response: Response,
    gc_sid: Optional[str] = Cookie(default=None),
):
    sid = _get_session_id(request, response, gc_sid)
    text = explain_simulation(req.simulation_result, req.context)
    return {"explanation": text, "data_source": cd.get_session_mode(sid)}


# ── React Frontend ─────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

if FRONTEND_DIST.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_DIST / "assets"),
        name="assets",
    )

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        requested_file = FRONTEND_DIST / full_path

        if full_path and requested_file.is_file():
            return FileResponse(requested_file)

        return FileResponse(FRONTEND_DIST / "index.html")