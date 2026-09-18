"""
Pydantic request/response models for GreenCampus AI API.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator


# ── Request Models ────────────────────────────────────────────────────────────

class ManualSimulationRequest(BaseModel):
    intervention_ids: List[str] = Field(..., min_items=1, description="Selected intervention IDs")
    budget_inr: float = Field(..., ge=0, description="Available budget in INR")


class OptimizationRequest(BaseModel):
    budget_inr: float = Field(..., ge=0, description="Available budget in INR")
    weights: Optional[Dict[str, float]] = Field(
        default=None,
        description="Optional objective weights: energy, water, waste, co2, financial"
    )


class WhatIfRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural-language what-if query")
    current_metrics: Optional[Dict[str, Any]] = None


class AssistantRequest(BaseModel):
    question: str = Field(..., min_length=1)
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured context: metrics, last simulation, interventions"
    )


class ExplainRequest(BaseModel):
    simulation_result: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None


# ── Campus Data Models ────────────────────────────────────────────────────────

class CampusInfoInput(BaseModel):
    name: str = Field(..., min_length=1, description="Campus name")
    area_m2: Optional[float] = Field(None, gt=0, description="Campus area in m²")
    students: Optional[int] = Field(None, ge=0, description="Number of students")
    staff: Optional[int] = Field(None, ge=0, description="Number of staff")
    buildings: Optional[int] = Field(None, ge=0, description="Number of buildings")


class EnergyInput(BaseModel):
    annual_kwh: Optional[float] = Field(None, ge=0, description="Annual electricity consumption (kWh)")
    annual_cost_inr: Optional[float] = Field(None, ge=0, description="Annual electricity cost (₹)")
    monthly_kwh: Optional[List[float]] = Field(None, description="Monthly consumption Jan–Dec (12 values)")


class WaterInput(BaseModel):
    annual_m3: Optional[float] = Field(None, ge=0, description="Annual water consumption (m³)")
    annual_cost_inr: Optional[float] = Field(None, ge=0, description="Annual water cost (₹)")
    monthly_m3: Optional[List[float]] = Field(None, description="Monthly consumption Jan–Dec (12 values)")


class WasteInput(BaseModel):
    annual_kg: Optional[float] = Field(None, ge=0, description="Annual total waste (kg)")
    recycled_pct: Optional[float] = Field(None, ge=0, le=100, description="Recycled waste (%)")
    composted_pct: Optional[float] = Field(None, ge=0, le=100, description="Composted waste (%)")
    landfill_pct: Optional[float] = Field(None, ge=0, le=100, description="Landfill waste (%)")
    monthly_kg: Optional[List[float]] = Field(None, description="Monthly waste Jan–Dec (12 values)")


class ExistingMeasuresInput(BaseModel):
    solar_installed: Optional[bool] = None
    led_retrofit: Optional[bool] = None
    hvac_optimization: Optional[bool] = None
    smart_metering: Optional[bool] = None
    water_leak_detection: Optional[bool] = None
    composting: Optional[bool] = None
    waste_segregation: Optional[bool] = None
    rainwater_harvesting: Optional[bool] = None


class CampusDataRequest(BaseModel):
    """Full campus sustainability dataset submission."""
    campus: CampusInfoInput
    energy: EnergyInput
    water: WaterInput
    waste: WasteInput
    budget_inr: Optional[float] = Field(None, ge=0, description="Available sustainability budget (₹)")
    existing_measures: Optional[ExistingMeasuresInput] = None


# ── Response Models ───────────────────────────────────────────────────────────

class InterventionItem(BaseModel):
    id: str
    name: str
    description: str
    cost_inr: float
    energy_saving_pct: float
    water_saving_pct: float
    waste_reduction_pct: float
    co2_reduction_kg_year: float
    annual_savings_inr: float
    payback_years: float
    category: str
    note: str


class SimulationInterventionDetail(BaseModel):
    id: str
    name: str
    cost_inr: float
    energy_saving_pct: float
    water_saving_pct: float
    waste_reduction_pct: float
    co2_reduction_kg_year: float
    annual_savings_inr: float
    payback_years: float


class SimulationResult(BaseModel):
    mode: str                                # "manual" | "optimized"
    interventions_applied: List[SimulationInterventionDetail]
    total_cost_inr: float
    remaining_budget_inr: float
    # Baseline
    baseline_energy_kwh: float
    baseline_water_m3: float
    baseline_waste_kg: float
    baseline_co2_kg: float
    # Projected
    projected_energy_kwh: float
    projected_water_m3: float
    projected_waste_kg: float
    projected_co2_kg: float
    # Savings
    energy_saving_pct: float
    water_saving_pct: float
    waste_reduction_pct: float
    co2_reduction_pct: float
    total_annual_savings_inr: float
    avg_payback_years: float
    # Scoring (optimizer mode)
    score: Optional[float] = None
    score_breakdown: Optional[Dict[str, float]] = None
    # Interactions applied
    interactions_applied: Optional[List[str]] = None
    # Explanation
    explanation: Optional[str] = None
    # Disclaimer
    disclaimer: str = (
        "Estimated result based on model assumptions. "
        "Actual results should be validated using campus measurements."
    )


class MetricsResponse(BaseModel):
    annual_energy_kwh: float
    annual_water_m3: float
    annual_waste_kg: float
    annual_co2_kg: float
    recycling_rate_pct: float
    energy_per_building: Dict[str, float]
    water_per_building: Dict[str, float]
    note: str = "Synthetic campus data – prototype only"
    data_source: str = "demo"
    data_source_label: str = "Demo Synthetic Data"
    completeness: Optional[Dict[str, bool]] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    granite_mode: bool
    ai_mode_label: str = "DEMO MODE (deterministic template)"


class CampusDataStatusResponse(BaseModel):
    mode: str                          # "demo" | "user"
    label: str                         # human-readable
    has_user_data: bool
    completeness: Optional[Dict[str, bool]] = None


class WhatIfResponse(BaseModel):
    parsed_scenario: Dict[str, Any]
    result: Dict[str, Any]
    explanation: str


class AssistantResponse(BaseModel):
    answer: str
    sources_used: List[str]
    disclaimer: str = (
        "Response is grounded in the provided campus data context. "
        "No numerical values have been invented."
    )
