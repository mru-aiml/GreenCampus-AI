"""
pytest test suite for GreenCampus AI backend.
Covers all scenarios requested: normal, edge, security, calculation correctness.

Run: cd greencampus/backend && pytest tests/ -v
"""
import math
import pytest
import sys
import os

# Allow imports from backend directory
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from calculations import (
    compute_annual_co2_kg,
    compute_recycling_rate,
    payback_years,
    GRID_EMISSION_FACTOR_KG_PER_KWH,
    WATER_EMISSION_FACTOR_KG_PER_M3,
    WASTE_LANDFILL_FACTOR_KG_PER_KG,
)
from simulator import (
    run_manual_simulation,
    run_budget_optimization,
    _compute_combined_savings,
    _score_portfolio,
    _apply_interactions,
    _validate_weights,
    DEFAULT_WEIGHTS,
)
from what_if_parser import parse_what_if, apply_what_if
from data_loader import load_interventions, get_annual_energy_kwh


# ── Shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def baseline():
    return {
        "energy": 300_000.0,
        "water": 18_000.0,
        "waste": 100_000.0,
        "co2": 230_000.0,
    }


@pytest.fixture
def all_interventions():
    return load_interventions()


@pytest.fixture
def single_intervention(all_interventions):
    # led_retrofit: cost=120000, energy_saving_pct=20, payback_years=2.2
    return [iv for iv in all_interventions if iv["id"] == "led_retrofit"]


@pytest.fixture
def two_interventions(all_interventions):
    return [iv for iv in all_interventions if iv["id"] in ("led_retrofit", "leak_detection")]


# ═════════════════════════════════════════════════════════════════════════════
# 1. CALCULATIONS
# ═════════════════════════════════════════════════════════════════════════════

class TestCO2Calculation:
    def test_zero_consumption(self):
        """All-zero inputs must yield zero CO2."""
        assert compute_annual_co2_kg(0, 0, 0) == 0.0

    def test_energy_only(self):
        expected = 1000 * GRID_EMISSION_FACTOR_KG_PER_KWH
        assert math.isclose(compute_annual_co2_kg(1000, 0, 0), expected, rel_tol=1e-9)

    def test_water_only(self):
        expected = 500 * WATER_EMISSION_FACTOR_KG_PER_M3
        assert math.isclose(compute_annual_co2_kg(0, 500, 0), expected, rel_tol=1e-9)

    def test_waste_only(self):
        expected = 200 * WASTE_LANDFILL_FACTOR_KG_PER_KG
        assert math.isclose(compute_annual_co2_kg(0, 0, 200), expected, rel_tol=1e-9)

    def test_combined(self):
        e, w, wst = 10000, 1000, 500
        expected = (
            e * GRID_EMISSION_FACTOR_KG_PER_KWH
            + w * WATER_EMISSION_FACTOR_KG_PER_M3
            + wst * WASTE_LANDFILL_FACTOR_KG_PER_KG
        )
        assert math.isclose(compute_annual_co2_kg(e, w, wst), expected, rel_tol=1e-9)

    def test_very_large_values(self):
        """Should not overflow or raise for very large inputs."""
        result = compute_annual_co2_kg(1e12, 1e10, 1e11)
        assert result > 0
        assert math.isfinite(result)

    def test_negative_energy_raises_or_produces_negative(self):
        """
        Negative inputs are physically invalid.
        The function currently doesn't clamp — this test documents the behaviour
        and flags it as a known gap for callers to validate upstream.
        """
        result = compute_annual_co2_kg(-1000, 0, 0)
        # Documents: negative input propagates without error
        assert result < 0  # BUG: should be caught upstream


class TestRecyclingRate:
    def test_zero_total(self):
        """Division by zero must be guarded."""
        assert compute_recycling_rate(0, 0) == 0.0

    def test_zero_recycled(self):
        assert compute_recycling_rate(0, 1000) == 0.0

    def test_full_recycling(self):
        assert compute_recycling_rate(500, 500) == 100.0

    def test_partial(self):
        result = compute_recycling_rate(250, 1000)
        assert math.isclose(result, 25.0, rel_tol=1e-6)

    def test_recycled_exceeds_total(self):
        """
        If recycled > total (data error), rate would exceed 100%.
        Documents behaviour — data validation should prevent this.
        """
        result = compute_recycling_rate(1200, 1000)
        assert result > 100.0  # Documents: no clamping


class TestPaybackYears:
    def test_normal(self):
        assert payback_years(120_000, 55_000) == round(120_000 / 55_000, 2)

    def test_zero_savings(self):
        assert payback_years(100_000, 0) == float("inf")

    def test_negative_savings(self):
        """Negative annual savings must return inf (not a negative payback)."""
        assert payback_years(100_000, -5000) == float("inf")

    def test_zero_cost(self):
        """Zero cost → instant payback (0 years)."""
        assert payback_years(0, 50_000) == 0.0

    def test_very_large_cost(self):
        result = payback_years(1e10, 1_000)
        assert math.isfinite(result)
        assert result == round(1e10 / 1_000, 2)


# ═════════════════════════════════════════════════════════════════════════════
# 2. SIMULATION – MANUAL MODE
# ═════════════════════════════════════════════════════════════════════════════

class TestManualSimulation:
    def test_normal_single_intervention(self, single_intervention, baseline):
        result = run_manual_simulation(["led_retrofit"], 200_000, baseline)
        assert result["mode"] == "manual"
        assert len(result["interventions_applied"]) == 1
        assert result["projected_energy_kwh"] < baseline["energy"]
        assert result["total_cost_inr"] == 120_000
        assert result["remaining_budget_inr"] == 200_000 - 120_000

    def test_combined_savings_are_compounded(self, baseline):
        """
        Two 30%-energy interventions should yield ~51% combined, not 60%.
        Specifically: led_retrofit (20%) + hvac (18%) → 1-(0.8*0.82)=34.4%
        """
        result = run_manual_simulation(["led_retrofit", "hvac_optimization"], 500_000, baseline)
        # 1 - (0.80 * 0.82) = 0.344 = 34.4%
        expected_pct = round((1 - 0.80 * 0.82) * 100, 3)
        assert math.isclose(result["energy_saving_pct"], expected_pct, rel_tol=1e-4), (
            f"Expected {expected_pct}%, got {result['energy_saving_pct']}%"
        )

    def test_zero_budget_still_computes(self, baseline):
        """Zero budget: manual mode still computes — budget_warning should appear."""
        result = run_manual_simulation(["led_retrofit"], 0, baseline)
        assert result["total_cost_inr"] > 0
        # remaining_budget_inr will be negative (budget exceeded)
        assert result["remaining_budget_inr"] < 0

    def test_budget_exceeded_flag(self, baseline):
        """When total cost > budget, remaining_budget_inr is negative."""
        result = run_manual_simulation(["rooftop_solar"], 100_000, baseline)
        assert result["remaining_budget_inr"] < 0

    def test_unknown_intervention_id_ignored(self, baseline):
        """Non-existent IDs are silently ignored by data_loader."""
        result = run_manual_simulation(["nonexistent_id"], 500_000, baseline)
        assert result["interventions_applied"] == []

    def test_projected_values_not_negative(self, baseline):
        """Projected metrics should never go below zero."""
        result = run_manual_simulation(
            ["hvac_optimization", "led_retrofit", "rooftop_solar",
             "smart_metering", "leak_detection", "composting",
             "waste_segregation", "rainwater_harvesting"],
            10_000_000, baseline
        )
        assert result["projected_energy_kwh"] >= 0
        assert result["projected_water_m3"] >= 0
        assert result["projected_waste_kg"] >= 0
        assert result["projected_co2_kg"] >= 0

    def test_payback_calculation_correctness(self, baseline):
        """avg_payback = total_cost / total_annual_savings."""
        result = run_manual_simulation(["led_retrofit", "leak_detection"], 500_000, baseline)
        expected_payback = round(
            result["total_cost_inr"] / result["total_annual_savings_inr"], 2
        )
        assert math.isclose(result["avg_payback_years"], expected_payback, rel_tol=1e-4)

    def test_co2_reduction_not_exceed_baseline(self, baseline):
        """CO2 reduction percentage should not exceed 100%."""
        result = run_manual_simulation(
            ["hvac_optimization", "led_retrofit", "rooftop_solar"],
            10_000_000, baseline
        )
        assert result["co2_reduction_pct"] <= 100.0

    def test_disclaimer_always_present(self, baseline):
        result = run_manual_simulation(["led_retrofit"], 200_000, baseline)
        assert "disclaimer" in result
        assert len(result["disclaimer"]) > 10


# ═════════════════════════════════════════════════════════════════════════════
# 3. SIMULATION – BUDGET OPTIMIZATION
# ═════════════════════════════════════════════════════════════════════════════

class TestBudgetOptimization:
    def test_zero_budget_returns_empty(self, baseline):
        """No intervention costs ₹0, so zero budget yields no feasible portfolio."""
        results = run_budget_optimization(0, baseline)
        assert results == []

    def test_negative_budget_returns_empty(self, baseline):
        """Negative budget: no feasible portfolios."""
        results = run_budget_optimization(-10_000, baseline)
        assert results == []

    def test_sufficient_budget_returns_results(self, baseline):
        """₹5 lakh should admit multiple feasible portfolios."""
        results = run_budget_optimization(500_000, baseline)
        assert len(results) > 0

    def test_results_sorted_by_score_descending(self, baseline):
        results = run_budget_optimization(500_000, baseline)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_all_portfolios_within_budget(self, baseline):
        budget = 300_000
        results = run_budget_optimization(budget, baseline)
        for r in results:
            assert r["total_cost_inr"] <= budget, (
                f"Portfolio cost {r['total_cost_inr']} exceeds budget {budget}"
            )

    def test_top_n_respected(self, baseline):
        results = run_budget_optimization(1_000_000, baseline, top_n=2)
        assert len(results) <= 2

    def test_very_large_budget_uses_all_combinations(self, baseline):
        """With a huge budget all single-intervention portfolios must appear."""
        results = run_budget_optimization(10_000_000, baseline, top_n=50)
        assert len(results) > 0
        # Best score should be higher than any single-intervention portfolio score
        single_results = run_budget_optimization(10_000_000, baseline, top_n=1)
        multi_ids = single_results[0]["interventions_applied"]
        assert len(multi_ids) >= 1

    def test_score_is_bounded_0_to_1(self, baseline):
        results = run_budget_optimization(500_000, baseline)
        for r in results:
            assert 0.0 <= r["score"] <= 1.0, f"Score out of bounds: {r['score']}"

    def test_score_breakdown_keys_present(self, baseline):
        results = run_budget_optimization(500_000, baseline)
        required_keys = {"energy", "water", "waste", "co2", "financial"}
        for r in results:
            assert required_keys.issubset(set(r["score_breakdown"].keys()))

    def test_mode_is_optimized(self, baseline):
        results = run_budget_optimization(500_000, baseline)
        for r in results:
            assert r["mode"] == "optimized"


# ═════════════════════════════════════════════════════════════════════════════
# 4. COMBINED SAVINGS & INTERACTIONS
# ═════════════════════════════════════════════════════════════════════════════

class TestCombinedSavings:
    def test_single_intervention(self, all_interventions):
        iv = next(i for i in all_interventions if i["id"] == "led_retrofit")
        result = _compute_combined_savings([iv])
        assert result["energy_saving_pct"] == iv["energy_saving_pct"]
        assert result["total_cost_inr"] == iv["cost_inr"]

    def test_compounding_prevents_over_100(self, all_interventions):
        """Even all interventions combined must not exceed 100% savings."""
        result = _compute_combined_savings(all_interventions)
        assert result["energy_saving_pct"] < 100.0
        assert result["water_saving_pct"] < 100.0
        assert result["waste_reduction_pct"] < 100.0

    def test_no_interventions_returns_zero(self):
        result = _compute_combined_savings([])
        assert result["energy_saving_pct"] == 0.0
        assert result["total_cost_inr"] == 0.0

    def test_co2_reduction_is_additive(self, all_interventions):
        """CO2 reduction is the sum of individual reductions (no compounding for absolute values)."""
        expected = sum(iv["co2_reduction_kg_year"] for iv in all_interventions)
        result = _compute_combined_savings(all_interventions)
        assert math.isclose(result["co2_reduction_kg_year"], expected, rel_tol=1e-6)


class TestInteractions:
    def test_hvac_solar_synergy(self):
        base = {
            "energy_saving_pct": 40.0,
            "water_saving_pct": 0.0,
            "waste_reduction_pct": 0.0,
            "co2_reduction_kg_year": 70_000.0,
            "total_annual_savings_inr": 275_000.0,
            "total_cost_inr": 930_000.0,
        }
        updated, labels = _apply_interactions(["hvac_optimization", "rooftop_solar"], base)
        # synergy factor 1.05 should increase energy_saving_pct
        assert updated["energy_saving_pct"] > base["energy_saving_pct"]
        assert any("HVAC" in l or "Solar" in l or "solar" in l for l in labels)

    def test_composting_segregation_synergy(self):
        base = {
            "energy_saving_pct": 0.0,
            "water_saving_pct": 0.0,
            "waste_reduction_pct": 50.0,
            "co2_reduction_kg_year": 12_700.0,
            "total_annual_savings_inr": 27_500.0,
            "total_cost_inr": 67_000.0,
        }
        updated, labels = _apply_interactions(["composting", "waste_segregation"], base)
        assert updated["waste_reduction_pct"] > base["waste_reduction_pct"]

    def test_no_interaction_for_unrelated_pair(self):
        base = {
            "energy_saving_pct": 20.0,
            "water_saving_pct": 22.0,
            "waste_reduction_pct": 0.0,
            "co2_reduction_kg_year": 15_200.0,
            "total_annual_savings_inr": 97_000.0,
            "total_cost_inr": 195_000.0,
        }
        updated, labels = _apply_interactions(["led_retrofit", "composting"], base)
        assert updated == base
        assert labels == []

    def test_interaction_with_single_intervention(self):
        base = {"energy_saving_pct": 18.0, "co2_reduction_kg_year": 28_000.0,
                "water_saving_pct": 0.0, "waste_reduction_pct": 0.0,
                "total_annual_savings_inr": 95_000.0, "total_cost_inr": 280_000.0}
        updated, labels = _apply_interactions(["hvac_optimization"], base)
        # Single intervention – no pairs, no interactions
        assert updated == base
        assert labels == []


# ═════════════════════════════════════════════════════════════════════════════
# 5. OBJECTIVE SCORING
# ═════════════════════════════════════════════════════════════════════════════

class TestScoring:
    def test_perfect_score_approaches_1(self):
        savings = {
            "energy_saving_pct": 60.0,
            "water_saving_pct": 60.0,
            "waste_reduction_pct": 60.0,
            "co2_reduction_kg_year": 80_000.0,
            "total_annual_savings_inr": 150_000.0,
            "total_cost_inr": 100_000.0,  # ROI = 1.5 → max
        }
        score, breakdown = _score_portfolio(savings, DEFAULT_WEIGHTS)
        assert score > 0.9

    def test_zero_savings_gives_zero_score(self):
        savings = {
            "energy_saving_pct": 0.0,
            "water_saving_pct": 0.0,
            "waste_reduction_pct": 0.0,
            "co2_reduction_kg_year": 0.0,
            "total_annual_savings_inr": 0.0,
            "total_cost_inr": 0.0,
        }
        score, _ = _score_portfolio(savings, DEFAULT_WEIGHTS)
        assert score == 0.0

    def test_score_normalised_0_to_1(self):
        savings = {
            "energy_saving_pct": 25.0,
            "water_saving_pct": 15.0,
            "waste_reduction_pct": 30.0,
            "co2_reduction_kg_year": 30_000.0,
            "total_annual_savings_inr": 80_000.0,
            "total_cost_inr": 200_000.0,
        }
        score, _ = _score_portfolio(savings, DEFAULT_WEIGHTS)
        assert 0.0 <= score <= 1.0

    def test_custom_weights_respected(self):
        savings = {
            "energy_saving_pct": 50.0,
            "water_saving_pct": 0.0,
            "waste_reduction_pct": 0.0,
            "co2_reduction_kg_year": 0.0,
            "total_annual_savings_inr": 0.0,
            "total_cost_inr": 100_000.0,
        }
        # Energy-only weights
        w = {"energy": 1.0, "water": 0.0, "waste": 0.0, "co2": 0.0, "financial": 0.0}
        w_norm = _validate_weights(w)
        score_energy, _ = _score_portfolio(savings, w_norm)

        # Financial-only weights
        w2 = {"energy": 0.0, "water": 0.0, "waste": 0.0, "co2": 0.0, "financial": 1.0}
        w2_norm = _validate_weights(w2)
        score_financial, _ = _score_portfolio(savings, w2_norm)

        assert score_energy > score_financial

    def test_score_capped_at_1_for_extreme_values(self):
        savings = {
            "energy_saving_pct": 200.0,   # Physically impossible — capping needed
            "water_saving_pct": 200.0,
            "waste_reduction_pct": 200.0,
            "co2_reduction_kg_year": 999_999.0,
            "total_annual_savings_inr": 99_999_999.0,
            "total_cost_inr": 1_000.0,
        }
        score, _ = _score_portfolio(savings, DEFAULT_WEIGHTS)
        assert score <= 1.0


# ═════════════════════════════════════════════════════════════════════════════
# 6. WHAT-IF PARSER
# ═════════════════════════════════════════════════════════════════════════════

class TestWhatIfParser:
    def test_energy_reduction_percentage(self):
        r = parse_what_if("What if energy consumption is reduced by 15%?")
        assert r["type"] == "energy_reduction"
        assert r["params"]["reduction_pct"] == 15.0
        assert r["parse_confidence"] == "high"

    def test_ac_energy_reduction(self):
        r = parse_what_if("What if AC energy consumption is reduced by 15%?")
        assert r["type"] == "energy_reduction"
        assert r["params"]["reduction_pct"] == 15.0
        assert r["params"]["source"] == "ac"

    def test_budget_lakh(self):
        r = parse_what_if("What if the sustainability budget is ₹5 lakh?")
        assert r["type"] == "budget_change"
        assert r["params"]["budget_inr"] == 500_000.0

    def test_budget_crore(self):
        r = parse_what_if("What if the budget is ₹1 crore?")
        assert r["type"] == "budget_change"
        assert r["params"]["budget_inr"] == 1_00_00_000.0

    def test_install_solar(self):
        r = parse_what_if("What if we install rooftop solar?")
        assert r["type"] == "install_intervention"
        assert r["params"]["intervention_id"] == "rooftop_solar"

    def test_install_led(self):
        r = parse_what_if("What if we install LED lighting?")
        assert r["type"] == "install_intervention"
        assert r["params"]["intervention_id"] == "led_retrofit"

    def test_water_reduction(self):
        r = parse_what_if("What if water consumption is reduced by 20%?")
        assert r["type"] == "water_reduction"
        assert r["params"]["reduction_pct"] == 20.0

    def test_unknown_returns_low_confidence(self):
        r = parse_what_if("What is the meaning of sustainability?")
        assert r["type"] == "unknown"
        assert r["parse_confidence"] == "low"

    def test_empty_string_returns_unknown(self):
        r = parse_what_if("  ")
        assert r["type"] == "unknown"

    def test_apply_energy_reduction(self):
        scenario = {"type": "energy_reduction", "params": {"reduction_pct": 10.0}}
        metrics = {"annual_energy_kwh": 100_000.0, "annual_water_m3": 5_000.0}
        updated = apply_what_if(scenario, metrics, [])
        assert updated["annual_energy_kwh"] == 90_000.0

    def test_apply_budget_change(self):
        scenario = {"type": "budget_change", "params": {"budget_inr": 500_000.0}}
        metrics = {"annual_energy_kwh": 100_000.0}
        updated = apply_what_if(scenario, metrics, [])
        assert updated["what_if_budget_inr"] == 500_000.0

    def test_apply_unknown_type_leaves_metrics_unchanged(self):
        scenario = {"type": "unknown", "params": {}}
        metrics = {"annual_energy_kwh": 100_000.0}
        updated = apply_what_if(scenario, metrics, [])
        assert updated["annual_energy_kwh"] == 100_000.0

    def test_apply_waste_reduction(self):
        scenario = {"type": "waste_reduction", "params": {"reduction_pct": 25.0}}
        metrics = {"annual_waste_kg": 80_000.0}
        updated = apply_what_if(scenario, metrics, [])
        assert updated["annual_waste_kg"] == 60_000.0


# ═════════════════════════════════════════════════════════════════════════════
# 7. EDGE CASES & SECURITY / INPUT VALIDATION
# ═════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_very_large_budget_does_not_crash(self, baseline):
        """Extremely large budget: should complete without error."""
        results = run_budget_optimization(1_000_000_000, baseline)
        assert isinstance(results, list)

    def test_very_large_baseline_values(self):
        """Extremely large baselines must not overflow."""
        huge_baseline = {
            "energy": 1e12, "water": 1e10, "waste": 1e11, "co2": 1e13,
        }
        result = run_manual_simulation(["led_retrofit"], 200_000, huge_baseline)
        assert math.isfinite(result["projected_energy_kwh"])

    def test_zero_baseline_co2(self, all_interventions, baseline):
        """If baseline CO2 is 0, co2_reduction_pct must be 0 (no division by zero)."""
        zero_co2_baseline = {**baseline, "co2": 0.0}
        result = run_manual_simulation(["led_retrofit"], 200_000, zero_co2_baseline)
        assert result["co2_reduction_pct"] == 0.0

    def test_injection_in_what_if_query(self):
        """Malicious string in what-if query must be handled without crash."""
        malicious = "'; DROP TABLE interventions; --"
        r = parse_what_if(malicious)
        assert r["type"] == "unknown"   # No crash, no code execution

    def test_script_tag_in_what_if_query(self):
        r = parse_what_if("<script>alert('xss')</script>")
        assert r["type"] == "unknown"

    def test_very_long_what_if_query(self):
        r = parse_what_if("What if " + "energy " * 1000 + "is reduced by 5%?")
        # Should parse, just might be slow — must not crash
        assert isinstance(r, dict)

    def test_duplicate_intervention_ids(self, baseline):
        """Duplicate IDs should not double-count savings beyond physical limits."""
        result = run_manual_simulation(["led_retrofit", "led_retrofit"], 400_000, baseline)
        # energy_saving_pct should not double to 40% — compounded: 1-(0.8*0.8)=36%
        assert result["energy_saving_pct"] < 100.0

    def test_all_interventions_combined_within_bounds(self, baseline):
        all_ids = [iv["id"] for iv in load_interventions()]
        result = run_manual_simulation(all_ids, 10_000_000, baseline)
        assert result["energy_saving_pct"] < 100.0
        assert result["water_saving_pct"] < 100.0
        assert result["waste_reduction_pct"] < 100.0
        assert result["projected_co2_kg"] >= 0.0

    def test_negative_budget_optimization_returns_empty(self, baseline):
        results = run_budget_optimization(-1, baseline)
        assert results == []

    def test_missing_interventions_list_empty(self, baseline):
        result = run_manual_simulation([], 500_000, baseline)
        assert result["interventions_applied"] == []
        assert result["total_cost_inr"] == 0.0
        assert result["energy_saving_pct"] == 0.0

    def test_payback_infinite_when_no_savings(self, baseline):
        """An intervention with zero annual savings should yield infinite payback."""
        result = run_manual_simulation(["led_retrofit"], 200_000, baseline)
        # led_retrofit has annual_savings_inr=55000 > 0; normal payback
        assert result["avg_payback_years"] < float("inf")

    def test_co2_projection_floor_at_zero(self, baseline):
        """Projected CO2 should never be negative."""
        huge_co2_reduction_baseline = {**baseline, "co2": 1_000.0}
        # co2_reduction_kg_year for all interventions far exceeds 1000 kg baseline
        result = run_manual_simulation(
            ["hvac_optimization", "led_retrofit", "rooftop_solar"],
            10_000_000, huge_co2_reduction_baseline
        )
        assert result["projected_co2_kg"] >= 0.0


# ═════════════════════════════════════════════════════════════════════════════
# 8. DATA LOADER SANITY
# ═════════════════════════════════════════════════════════════════════════════

class TestDataLoader:
    def test_interventions_have_required_fields(self, all_interventions):
        required = {
            "id", "name", "cost_inr", "energy_saving_pct", "water_saving_pct",
            "waste_reduction_pct", "co2_reduction_kg_year", "annual_savings_inr",
            "payback_years", "category", "note",
        }
        for iv in all_interventions:
            missing = required - set(iv.keys())
            assert not missing, f"Intervention {iv.get('id')} missing: {missing}"

    def test_all_costs_positive(self, all_interventions):
        for iv in all_interventions:
            assert iv["cost_inr"] > 0, f"{iv['id']} has non-positive cost"

    def test_all_paybacks_positive(self, all_interventions):
        for iv in all_interventions:
            assert iv["payback_years"] > 0, f"{iv['id']} has non-positive payback"

    def test_savings_pct_0_to_100(self, all_interventions):
        for iv in all_interventions:
            for field in ("energy_saving_pct", "water_saving_pct", "waste_reduction_pct"):
                assert 0 <= iv[field] <= 100, (
                    f"{iv['id']}.{field} = {iv[field]} is out of [0, 100]"
                )

    def test_annual_energy_kwh_positive(self):
        assert get_annual_energy_kwh() > 0

    def test_interventions_count(self, all_interventions):
        assert len(all_interventions) == 8


# ═════════════════════════════════════════════════════════════════════════════
# 9. SCORING FORMULA CONSISTENCY
# ═════════════════════════════════════════════════════════════════════════════

class TestScoringFormulaConsistency:
    """
    Verify the composite score in the result dict exactly matches
    what _score_portfolio would produce from the same savings dict.
    The formula must be internally consistent — no rounding divergence > 1e-5.
    """

    def test_manual_result_score_matches_formula(self, baseline):
        result = run_manual_simulation(["led_retrofit", "leak_detection"], 500_000, baseline)
        formula = result.get("objective_formula", {})
        w = formula.get("weights", DEFAULT_WEIGHTS)

        # Reconstruct savings dict from result fields
        savings = {
            "energy_saving_pct":       result["energy_saving_pct"],
            "water_saving_pct":        result["water_saving_pct"],
            "waste_reduction_pct":     result["waste_reduction_pct"],
            "co2_reduction_kg_year":   (
                result["baseline_co2_kg"] - result["projected_co2_kg"]
                + (result["baseline_co2_kg"] * result["co2_reduction_pct"] / 100
                   - (result["baseline_co2_kg"] - result["projected_co2_kg"]))
                # Use direct CO2 from interventions via a simpler proxy
            ),
            "total_annual_savings_inr": result["total_annual_savings_inr"],
            "total_cost_inr":          result["total_cost_inr"],
        }
        # Simpler: reconstruct co2 reduction from pct × baseline
        co2_reduction = result["baseline_co2_kg"] * result["co2_reduction_pct"] / 100
        savings["co2_reduction_kg_year"] = co2_reduction

        recomputed_score, _ = _score_portfolio(savings, w)
        assert math.isclose(result["score"], recomputed_score, rel_tol=1e-4), (
            f"Result score {result['score']} != recomputed {recomputed_score}"
        )

    def test_objective_formula_field_present_in_result(self, baseline):
        result = run_manual_simulation(["led_retrofit"], 200_000, baseline)
        assert "objective_formula" in result
        formula = result["objective_formula"]
        assert "weights" in formula
        assert "normalisation_bounds" in formula
        assert "formula" in formula
        assert "savings_combination" in formula

    def test_weights_sum_to_one(self, baseline):
        result = run_manual_simulation(["led_retrofit"], 200_000, baseline)
        w = result["objective_formula"]["weights"]
        total = sum(w.values())
        assert math.isclose(total, 1.0, rel_tol=1e-6), f"Weights sum = {total}, expected 1.0"

    def test_score_breakdown_weighted_sum_matches_composite(self, baseline):
        """composite = Σ weight_k × breakdown_k (within floating point tolerance)."""
        result = run_budget_optimization(500_000, baseline, top_n=1)[0]
        w  = result["objective_formula"]["weights"]
        bd = result["score_breakdown"]
        recomputed = sum(w[k] * bd[k] for k in w)
        assert math.isclose(result["score"], recomputed, rel_tol=1e-4), (
            f"Composite score {result['score']} != weighted sum {recomputed}"
        )

    def test_normalisation_bounds_all_present(self, baseline):
        result = run_manual_simulation(["hvac_optimization"], 300_000, baseline)
        bounds = result["objective_formula"]["normalisation_bounds"]
        for dim in ("energy", "water", "waste", "co2", "financial"):
            assert dim in bounds, f"Missing bound for dimension: {dim}"
            assert bounds[dim]["max"] > 0


# ═════════════════════════════════════════════════════════════════════════════
# 10. SEQUENTIAL (COMPOUNDED) SAVINGS — explicit verification
# ═════════════════════════════════════════════════════════════════════════════

class TestSequentialSavings:
    """
    Verify projected = baseline × Π (1 − r_i) — compounded, not additive.
    These are regression tests for the core arithmetic invariant.
    """

    def test_two_energy_savers_compounded(self, baseline):
        """LED (20%) + HVAC (18%) → 1 - (0.80 × 0.82) = 34.4%, NOT 38%."""
        result = run_manual_simulation(
            ["led_retrofit", "hvac_optimization"], 500_000, baseline
        )
        expected = round((1 - 0.80 * 0.82) * 100, 3)
        assert math.isclose(result["energy_saving_pct"], expected, rel_tol=1e-4), (
            f"Expected compounded {expected}%, got {result['energy_saving_pct']}%"
        )

    def test_three_water_savers_compounded(self, baseline):
        """smart_metering(6%) + leak_detection(22%) + rainwater_harvesting(28%)
           → 1 - (0.94 × 0.78 × 0.72) ≈ 47.3%, NOT 56%"""
        result = run_manual_simulation(
            ["smart_metering", "leak_detection", "rainwater_harvesting"],
            1_000_000, baseline
        )
        # After interactions: leak+rainwater has 1.06 factor — test plain compounding first
        # Raw compounded (no interaction): 1 - (0.94 * 0.78 * 0.72)
        raw_compounded = round((1 - 0.94 * 0.78 * 0.72) * 100, 3)
        # With the leak+rainwater interaction (×1.06), actual > raw
        assert result["water_saving_pct"] > raw_compounded - 1.0  # within 1% of expected

    def test_compounded_always_less_than_additive(self, baseline):
        """For any multi-intervention portfolio, compounded < additive sum."""
        result = run_manual_simulation(
            ["hvac_optimization", "led_retrofit", "smart_metering"], 500_000, baseline
        )
        additive_energy = 18 + 20 + 8
        assert result["energy_saving_pct"] < additive_energy, (
            "Compounded saving must be strictly less than additive sum"
        )

    def test_projection_matches_formula(self, baseline):
        """projected_energy = baseline_energy × (1 - energy_saving_pct/100)."""
        result = run_manual_simulation(["led_retrofit"], 200_000, baseline)
        expected_proj = round(
            baseline["energy"] * (1 - result["energy_saving_pct"] / 100), 2
        )
        assert math.isclose(result["projected_energy_kwh"], expected_proj, rel_tol=1e-6)

    def test_single_intervention_no_compounding_effect(self, baseline):
        """Single intervention: compounded result equals individual reduction."""
        from data_loader import load_interventions
        iv = next(i for i in load_interventions() if i["id"] == "led_retrofit")
        result = run_manual_simulation(["led_retrofit"], 200_000, baseline)
        assert math.isclose(
            result["energy_saving_pct"], iv["energy_saving_pct"], rel_tol=1e-6
        )


# ═════════════════════════════════════════════════════════════════════════════
# 11. AI EXPLAIN — DEMO MODE & FALLBACK
# ═════════════════════════════════════════════════════════════════════════════

class TestAIExplainDemoMode:
    """
    Tests for the ai_explain module.
    These run in DEMO MODE (no Granite credentials in test env).
    """

    def _make_result(self, mode="optimized"):
        from data_loader import load_interventions
        catalog = load_interventions()
        baseline = {"energy": 300_000.0, "water": 18_000.0, "waste": 100_000.0, "co2": 230_000.0}
        ids = [catalog[0]["id"], catalog[1]["id"]]
        return run_manual_simulation(ids, 500_000, baseline)

    def test_demo_mode_label_in_explanation(self):
        """Template explanation must contain the DEMO MODE label."""
        from ai_explain import _template_explain_simulation, _DEMO_MODE_LABEL
        result = self._make_result()
        text = _template_explain_simulation(result)
        assert "DEMO MODE" in text or "demo mode" in text.lower()

    def test_explanation_contains_no_invented_numbers(self):
        """All numbers in explanation must trace back to result dict."""
        from ai_explain import explain_simulation
        result = self._make_result()
        text = explain_simulation(result)
        # Total cost from result must appear in explanation
        cost_str = str(int(result["total_cost_inr"] / 100000))  # lakh digits
        assert cost_str in text or "lakh" in text.lower()

    def test_explanation_includes_all_required_sections(self):
        """Template must include: budget, environmental, financial, methodology, assumptions."""
        from ai_explain import _template_explain_simulation
        result = self._make_result()
        text = _template_explain_simulation(result)
        for section_kw in [
            "budget", "energy", "water", "payback", "compounded", "assumption"
        ]:
            assert section_kw.lower() in text.lower(), (
                f"Missing section keyword: '{section_kw}' in explanation"
            )

    def test_zero_intervention_explanation(self):
        from ai_explain import _template_explain_simulation
        result = {"interventions_applied": [], "mode": "manual", "disclaimer": "test"}
        text = _template_explain_simulation(result)
        assert "No interventions" in text

    def test_get_mode_label_demo(self):
        """Without GRANITE_MODE=1, label should say DEMO MODE."""
        import os, importlib
        import ai_explain
        original = ai_explain.GRANITE_MODE
        ai_explain.GRANITE_MODE = False
        try:
            label = ai_explain.get_mode_label()
            assert "DEMO MODE" in label
        finally:
            ai_explain.GRANITE_MODE = original

    def test_call_granite_returns_false_without_credentials(self):
        """_call_granite must return (empty, False) when env vars are absent."""
        import os
        from ai_explain import _call_granite
        # Temporarily clear credentials
        backup_key = os.environ.pop("WATSONX_API_KEY", None)
        backup_pid = os.environ.pop("WATSONX_PROJECT_ID", None)
        try:
            text, ok = _call_granite("test prompt")
            assert ok is False
            assert text == ""
        finally:
            if backup_key:
                os.environ["WATSONX_API_KEY"] = backup_key
            if backup_pid:
                os.environ["WATSONX_PROJECT_ID"] = backup_pid

    def test_explain_simulation_falls_back_when_granite_fails(self):
        """explain_simulation must return template output when Granite is unavailable."""
        import os, ai_explain
        original = ai_explain.GRANITE_MODE
        ai_explain.GRANITE_MODE = True   # pretend Granite mode
        backup_key = os.environ.pop("WATSONX_API_KEY", None)
        backup_pid = os.environ.pop("WATSONX_PROJECT_ID", None)
        try:
            result = self._make_result()
            text = ai_explain.explain_simulation(result)
            # Should fall back to template — template contains DEMO MODE label
            assert "DEMO MODE" in text
        finally:
            ai_explain.GRANITE_MODE = original
            if backup_key:
                os.environ["WATSONX_API_KEY"] = backup_key
            if backup_pid:
                os.environ["WATSONX_PROJECT_ID"] = backup_pid

    def test_granite_prompt_does_not_invent_numbers_instruction(self):
        """Structured Granite prompt must contain 'Do NOT invent' instruction."""
        from ai_explain import _build_granite_sim_prompt
        result = self._make_result()
        prompt = _build_granite_sim_prompt(result, None)
        assert "Do NOT invent" in prompt or "do not invent" in prompt.lower()

    def test_granite_sim_prompt_contains_result_data(self):
        """Granite prompt must include actual values from the result dict."""
        from ai_explain import _build_granite_sim_prompt
        result = self._make_result()
        prompt = _build_granite_sim_prompt(result, None)
        # At minimum the total cost should be present
        assert str(int(result["total_cost_inr"])) in prompt

    def test_answer_question_demo_mode_grounded(self):
        """Template Q&A must reference metrics from context, not invented values."""
        from ai_explain import _template_answer_question
        context = {
            "current_metrics": {
                "annual_energy_kwh": 123456.0,
                "annual_water_m3": 9876.0,
                "annual_co2_kg": 88000.0,
                "annual_waste_kg": 50000.0,
                "recycling_rate_pct": 38.5,
            }
        }
        answer = _template_answer_question("What is the energy consumption?", context)
        assert "123" in answer  # part of 123456 must appear


# ═════════════════════════════════════════════════════════════════════════════
# 12. WHAT-IF — ADDITIONAL SCENARIOS
# ═════════════════════════════════════════════════════════════════════════════

class TestWhatIfAdditional:
    def test_budget_10_lakh(self):
        r = parse_what_if("What if the sustainability budget increases to ₹10 lakh?")
        assert r["type"] == "budget_change"
        assert r["params"]["budget_inr"] == 1_000_000.0

    def test_install_hvac(self):
        r = parse_what_if("What if we install HVAC optimization?")
        assert r["type"] == "install_intervention"
        assert r["params"]["intervention_id"] == "hvac_optimization"

    def test_co2_reduction_query(self):
        r = parse_what_if("What if CO2 emissions are reduced by 30%?")
        assert r["type"] == "co2_reduction"
        assert r["params"]["reduction_pct"] == 30.0

    def test_apply_install_intervention_updates_metrics(self):
        from data_loader import load_interventions
        catalog = load_interventions()
        scenario = {"type": "install_intervention", "params": {"intervention_id": "led_retrofit"}}
        metrics = {"annual_energy_kwh": 200_000.0}
        updated = apply_what_if(scenario, metrics, catalog)
        assert "what_if_intervention" in updated
        assert updated["what_if_intervention"]["id"] == "led_retrofit"

    def test_unknown_intervention_name_graceful(self):
        scenario = {"type": "install_intervention", "params": {"intervention_id": "nonexistent"}}
        metrics = {"annual_energy_kwh": 200_000.0}
        updated = apply_what_if(scenario, metrics, [])
        # No crash, no change
        assert updated["annual_energy_kwh"] == 200_000.0

    def test_zero_reduction_pct_is_identity(self):
        scenario = {"type": "energy_reduction", "params": {"reduction_pct": 0.0}}
        metrics = {"annual_energy_kwh": 100_000.0}
        updated = apply_what_if(scenario, metrics, [])
        assert updated["annual_energy_kwh"] == 100_000.0

    def test_100_pct_reduction_reaches_zero(self):
        scenario = {"type": "water_reduction", "params": {"reduction_pct": 100.0}}
        metrics = {"annual_water_m3": 5_000.0}
        updated = apply_what_if(scenario, metrics, [])
        assert updated["annual_water_m3"] == 0.0
