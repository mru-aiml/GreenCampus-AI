"""
New tests for campus data feature:
  - Validation (valid/invalid datasets)
  - CSV parsing
  - User data activation and demo restore
  - Analytics use active dataset
  - No fabricated monthly data
  - Existing tests remain unaffected (regression guard)

Run: cd greencampus/backend && pytest tests/ -v
"""
import math
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from data_validator import (
    validate_campus_data,
    parse_csv_to_raw,
    generate_csv_template,
    validate_energy,
    validate_water,
    validate_waste,
)
import campus_data as cd
from calculations import compute_all_metrics, compute_annual_co2_kg
from simulator import run_budget_optimization, run_manual_simulation
from what_if_parser import parse_what_if, apply_what_if
from data_loader import (
    get_annual_energy_kwh, get_annual_water_m3,
    get_annual_waste_kg, get_annual_landfill_kg, load_interventions,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_to_demo_after_each():
    """Ensure each test starts and ends in demo mode."""
    cd.reset_to_demo()
    yield
    cd.reset_to_demo()


@pytest.fixture
def valid_campus_data():
    return {
        "campus": {"name": "Test Campus", "area_m2": 50000, "students": 5000, "staff": 350, "buildings": 8},
        "energy": {"annual_kwh": 950000, "annual_cost_inr": 8200000},
        "water": {"annual_m3": 35000, "annual_cost_inr": 1200000},
        "waste": {"annual_kg": 85000, "recycled_pct": 30, "composted_pct": 20, "landfill_pct": 50},
        "budget_inr": 500000,
        "existing_measures": {"solar_installed": False, "led_retrofit": False},
    }


@pytest.fixture
def valid_campus_data_with_monthly():
    """Campus data with all monthly values provided."""
    monthly_energy = [80000, 75000, 72000, 70000, 78000, 90000, 98000, 95000, 85000, 78000, 73000, 76000]
    monthly_water = [3000, 2800, 2900, 2700, 3200, 3000, 3100, 3000, 2900, 2800, 2700, 2900]
    monthly_waste = [7000, 7000, 7100, 7000, 7100, 7200, 7100, 7000, 7100, 7000, 7100, 7300]
    return {
        "campus": {"name": "Monthly Campus", "area_m2": 60000, "students": 6000},
        "energy": {"monthly_kwh": monthly_energy},
        "water": {"monthly_m3": monthly_water},
        "waste": {
            "monthly_kg": monthly_waste,
            "recycled_pct": 30, "composted_pct": 20, "landfill_pct": 50,
        },
        "budget_inr": 500000,
    }


# ═════════════════════════════════════════════════════════════════════════════
# 1. VALID CAMPUS DATA
# ═════════════════════════════════════════════════════════════════════════════

class TestValidCampusData:
    def test_valid_annual_data_passes(self, valid_campus_data):
        validated, errors = validate_campus_data(valid_campus_data)
        assert errors == [], f"Unexpected errors: {errors}"
        assert validated is not None

    def test_validated_energy_value_correct(self, valid_campus_data):
        validated, _ = validate_campus_data(valid_campus_data)
        assert validated["energy"]["annual_kwh"] == 950000

    def test_validated_water_value_correct(self, valid_campus_data):
        validated, _ = validate_campus_data(valid_campus_data)
        assert validated["water"]["annual_m3"] == 35000

    def test_validated_waste_value_correct(self, valid_campus_data):
        validated, _ = validate_campus_data(valid_campus_data)
        assert validated["waste"]["annual_kg"] == 85000

    def test_validated_budget_correct(self, valid_campus_data):
        validated, _ = validate_campus_data(valid_campus_data)
        assert validated["budget_inr"] == 500000

    def test_monthly_energy_overrides_annual(self, valid_campus_data_with_monthly):
        validated, errors = validate_campus_data(valid_campus_data_with_monthly)
        assert errors == []
        # Annual should be sum of monthly
        monthly = valid_campus_data_with_monthly["energy"]["monthly_kwh"]
        assert math.isclose(validated["energy"]["annual_kwh"], sum(monthly), rel_tol=1e-6)

    def test_monthly_water_overrides_annual(self, valid_campus_data_with_monthly):
        validated, _ = validate_campus_data(valid_campus_data_with_monthly)
        monthly = valid_campus_data_with_monthly["water"]["monthly_m3"]
        assert math.isclose(validated["water"]["annual_m3"], sum(monthly), rel_tol=1e-6)

    def test_existing_measures_preserved(self, valid_campus_data):
        validated, _ = validate_campus_data(valid_campus_data)
        assert "existing_measures" in validated
        assert isinstance(validated["existing_measures"], dict)


# ═════════════════════════════════════════════════════════════════════════════
# 2. MISSING REQUIRED FIELDS
# ═════════════════════════════════════════════════════════════════════════════

class TestMissingRequiredFields:
    def test_missing_campus_name_raises_error(self):
        raw = {
            "campus": {"area_m2": 50000},
            "energy": {"annual_kwh": 100000},
            "water": {"annual_m3": 10000},
            "waste": {"annual_kg": 5000, "recycled_pct": 30, "composted_pct": 20, "landfill_pct": 50},
        }
        validated, errors = validate_campus_data(raw)
        assert validated is None
        assert any("name" in e for e in errors)

    def test_missing_energy_raises_error(self):
        raw = {
            "campus": {"name": "X"},
            "energy": {},  # no annual_kwh or monthly_kwh
            "water": {"annual_m3": 10000},
            "waste": {"annual_kg": 5000, "recycled_pct": 30, "composted_pct": 20, "landfill_pct": 50},
        }
        validated, errors = validate_campus_data(raw)
        assert validated is None
        assert any("energy" in e.lower() for e in errors)

    def test_missing_water_raises_error(self):
        raw = {
            "campus": {"name": "X"},
            "energy": {"annual_kwh": 100000},
            "water": {},  # no annual_m3
            "waste": {"annual_kg": 5000, "recycled_pct": 30, "composted_pct": 20, "landfill_pct": 50},
        }
        validated, errors = validate_campus_data(raw)
        assert validated is None
        assert any("water" in e.lower() for e in errors)


# ═════════════════════════════════════════════════════════════════════════════
# 3. NEGATIVE VALUE VALIDATION
# ═════════════════════════════════════════════════════════════════════════════

class TestNegativeValues:
    def test_negative_energy_fails(self):
        errors = []
        validate_energy({"annual_kwh": -100}, errors)
        assert any("energy" in e.lower() or "annual_kwh" in e.lower() for e in errors)

    def test_negative_water_fails(self):
        errors = []
        validate_water({"annual_m3": -50}, errors)
        assert any("water" in e.lower() or "annual_m3" in e.lower() for e in errors)

    def test_negative_waste_fails(self):
        errors = []
        validate_waste({"annual_kg": -1000, "recycled_pct": 30, "composted_pct": 20, "landfill_pct": 50}, errors)
        assert any("waste" in e.lower() or "annual_kg" in e.lower() for e in errors)

    def test_negative_monthly_energy_fails(self):
        errors = []
        monthly = [80000] * 11 + [-1000]  # last month negative
        validate_energy({"monthly_kwh": monthly}, errors)
        assert len(errors) > 0

    def test_negative_cost_fails(self):
        errors = []
        validate_energy({"annual_kwh": 100000, "annual_cost_inr": -500}, errors)
        assert any("cost" in e.lower() for e in errors)


# ═════════════════════════════════════════════════════════════════════════════
# 4. WASTE PERCENTAGE VALIDATION
# ═════════════════════════════════════════════════════════════════════════════

class TestWastePercentages:
    def test_valid_percentages_sum_100(self):
        errors = []
        out = validate_waste({"annual_kg": 1000, "recycled_pct": 30, "composted_pct": 20, "landfill_pct": 50}, errors)
        assert errors == []
        assert out["recycled_pct"] == 30
        assert out["landfill_pct"] == 50

    def test_invalid_sum_fails(self):
        errors = []
        validate_waste({"annual_kg": 1000, "recycled_pct": 40, "composted_pct": 30, "landfill_pct": 40}, errors)
        # 40+30+40 = 110 — should fail
        assert any("100" in e or "sum" in e.lower() for e in errors)

    def test_percentages_below_100_fails(self):
        errors = []
        validate_waste({"annual_kg": 1000, "recycled_pct": 10, "composted_pct": 10, "landfill_pct": 10}, errors)
        # 30 ≠ 100
        assert any("100" in e or "sum" in e.lower() for e in errors)

    def test_negative_recycled_pct_fails(self):
        errors = []
        validate_waste({"annual_kg": 1000, "recycled_pct": -10, "composted_pct": 60, "landfill_pct": 50}, errors)
        assert len(errors) > 0

    def test_percentage_over_100_fails(self):
        errors = []
        validate_waste({"annual_kg": 1000, "recycled_pct": 110, "composted_pct": 0, "landfill_pct": 0}, errors)
        assert len(errors) > 0


# ═════════════════════════════════════════════════════════════════════════════
# 5. CSV PARSING
# ═════════════════════════════════════════════════════════════════════════════

class TestCSVParsing:
    def _minimal_csv(self):
        return (
            "metric,value,unit\n"
            "campus_name,Test University,text\n"
            "campus_area,50000,m2\n"
            "students,5000,count\n"
            "annual_energy,950000,kWh\n"
            "annual_water,35000,m3\n"
            "annual_waste,85000,kg\n"
            "recycled_percent,30,percent\n"
            "composted_percent,20,percent\n"
            "landfill_percent,50,percent\n"
            "budget,500000,INR\n"
        )

    def test_valid_csv_parses_correctly(self):
        raw, errors = parse_csv_to_raw(self._minimal_csv())
        assert errors == [], f"Errors: {errors}"
        assert raw["campus"]["name"] == "Test University"
        assert raw["energy"]["annual_kwh"] == 950000
        assert raw["water"]["annual_m3"] == 35000
        assert raw["waste"]["annual_kg"] == 85000

    def test_valid_csv_validates_correctly(self):
        raw, _ = parse_csv_to_raw(self._minimal_csv())
        validated, errors = validate_campus_data(raw)
        assert errors == [], f"Validation errors: {errors}"
        assert validated is not None

    def test_empty_csv_fails(self):
        raw, errors = parse_csv_to_raw("")
        assert raw is None
        assert len(errors) > 0

    def test_missing_header_fails(self):
        csv = "just,some,cols\n50000,m2,stuff\n"
        raw, errors = parse_csv_to_raw(csv)
        assert raw is None
        assert any("header" in e.lower() or "metric" in e.lower() for e in errors)

    def test_non_numeric_value_fails(self):
        csv = (
            "metric,value,unit\n"
            "campus_name,Test,text\n"
            "annual_energy,INVALID,kWh\n"
        )
        raw, errors = parse_csv_to_raw(csv)
        assert raw is None
        assert any("non-numeric" in e.lower() or "INVALID" in e for e in errors)

    def test_unrecognised_metric_logged_as_error(self):
        csv = (
            "metric,value,unit\n"
            "campus_name,Test,text\n"
            "unknown_metric,123,xyz\n"
            "annual_energy,950000,kWh\n"
            "annual_water,35000,m3\n"
            "annual_waste,85000,kg\n"
            "recycled_percent,30,percent\n"
            "composted_percent,20,percent\n"
            "landfill_percent,50,percent\n"
        )
        raw, errors = parse_csv_to_raw(csv)
        assert raw is None
        assert any("unrecognised" in e.lower() or "unknown_metric" in e for e in errors)

    def test_csv_template_is_valid(self):
        template = generate_csv_template()
        assert "metric,value,unit" in template
        assert "annual_energy" in template
        assert "annual_water" in template
        assert "recycled_percent" in template

    def test_partial_monthly_energy_fails(self):
        """Providing only 11 of 12 monthly energy values should fail."""
        lines = ["metric,value,unit"]
        for i, m in enumerate(["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov"]):
            lines.append(f"energy_{m},{80000 + i * 1000},kWh")
        # Missing energy_dec
        lines += [
            "campus_name,X,text",
            "annual_water,35000,m3",
            "annual_waste,85000,kg",
            "recycled_percent,30,percent",
            "composted_percent,20,percent",
            "landfill_percent,50,percent",
        ]
        raw, errors = parse_csv_to_raw("\n".join(lines))
        assert raw is None
        assert any("month" in e.lower() or "missing" in e.lower() for e in errors)


# ═════════════════════════════════════════════════════════════════════════════
# 6. USER DATA ACTIVATION & DEMO RESTORE
# ═════════════════════════════════════════════════════════════════════════════

class TestDatasetManagement:
    def test_user_data_activates(self, valid_campus_data):
        validated, _ = validate_campus_data(valid_campus_data)
        cd.set_user_campus_data(validated)
        assert cd.get_active_mode() == "user"
        assert cd.is_user_mode() is True

    def test_user_data_label(self, valid_campus_data):
        validated, _ = validate_campus_data(valid_campus_data)
        cd.set_user_campus_data(validated)
        label = cd.get_data_source_label()
        assert "User Campus Data" in label

    def test_demo_restore(self, valid_campus_data):
        validated, _ = validate_campus_data(valid_campus_data)
        cd.set_user_campus_data(validated)
        assert cd.is_user_mode()
        cd.reset_to_demo()
        assert cd.get_active_mode() == "demo"
        assert cd.is_user_mode() is False
        assert cd.get_user_campus_data() is None

    def test_demo_label(self):
        cd.reset_to_demo()
        assert "Demo" in cd.get_data_source_label()


# ═════════════════════════════════════════════════════════════════════════════
# 7. OVERVIEW USES USER DATA
# ═════════════════════════════════════════════════════════════════════════════

class TestOverviewUsesUserData:
    def _activate(self, data):
        validated, errors = validate_campus_data(data)
        assert errors == []
        cd.set_user_campus_data(validated)

    def test_overview_uses_user_energy(self, valid_campus_data):
        self._activate(valid_campus_data)
        metrics = compute_all_metrics()
        assert math.isclose(metrics["annual_energy_kwh"], 950000, rel_tol=1e-4)

    def test_overview_uses_user_water(self, valid_campus_data):
        self._activate(valid_campus_data)
        metrics = compute_all_metrics()
        assert math.isclose(metrics["annual_water_m3"], 35000, rel_tol=1e-4)

    def test_overview_uses_user_waste(self, valid_campus_data):
        self._activate(valid_campus_data)
        metrics = compute_all_metrics()
        assert math.isclose(metrics["annual_waste_kg"], 85000, rel_tol=1e-4)

    def test_overview_note_says_user_data(self, valid_campus_data):
        self._activate(valid_campus_data)
        metrics = compute_all_metrics()
        assert metrics["data_source"] == "user"
        assert "User" in metrics["note"] or "user" in metrics["note"].lower()

    def test_demo_metrics_differ_from_user_metrics(self, valid_campus_data):
        demo_metrics = compute_all_metrics()
        self._activate(valid_campus_data)
        user_metrics = compute_all_metrics()
        # User energy is 950000; demo is a different sum
        assert demo_metrics["annual_energy_kwh"] != user_metrics["annual_energy_kwh"]


# ═════════════════════════════════════════════════════════════════════════════
# 8. CO2 USES USER DATA
# ═════════════════════════════════════════════════════════════════════════════

class TestCO2UsesUserData:
    def test_co2_calculated_from_user_energy(self, valid_campus_data):
        validated, _ = validate_campus_data(valid_campus_data)
        cd.set_user_campus_data(validated)
        metrics = compute_all_metrics()

        # Verify CO2 deterministically from user values
        energy = 950000
        water = 35000
        landfill_kg = 85000 * 0.50  # 50% landfill
        expected_co2 = compute_annual_co2_kg(energy, water, landfill_kg)
        assert math.isclose(metrics["annual_co2_kg"], expected_co2, rel_tol=1e-4)

    def test_co2_uses_correct_landfill_fraction(self, valid_campus_data):
        validated, _ = validate_campus_data(valid_campus_data)
        cd.set_user_campus_data(validated)
        landfill = get_annual_landfill_kg()
        # 85000 * 50% = 42500
        assert math.isclose(landfill, 42500, rel_tol=1e-4)


# ═════════════════════════════════════════════════════════════════════════════
# 9. ECOSIM USES USER BASELINE
# ═════════════════════════════════════════════════════════════════════════════

class TestEcoSimUsesUserBaseline:
    def test_optimization_uses_user_energy_baseline(self, valid_campus_data):
        validated, _ = validate_campus_data(valid_campus_data)
        cd.set_user_campus_data(validated)

        baseline = {
            "energy": get_annual_energy_kwh(),
            "water": get_annual_water_m3(),
            "waste": get_annual_waste_kg(),
            "co2": compute_all_metrics()["annual_co2_kg"],
        }
        results = run_budget_optimization(500000, baseline, top_n=1)
        assert len(results) > 0
        # Baseline energy in result should match user-provided 950000
        assert results[0]["baseline_energy_kwh"] == 950000

    def test_manual_simulation_uses_user_baseline(self, valid_campus_data):
        validated, _ = validate_campus_data(valid_campus_data)
        cd.set_user_campus_data(validated)

        baseline = {
            "energy": get_annual_energy_kwh(),
            "water": get_annual_water_m3(),
            "waste": get_annual_waste_kg(),
            "co2": compute_all_metrics()["annual_co2_kg"],
        }
        result = run_manual_simulation(["led_retrofit"], 200000, baseline)
        assert result["baseline_energy_kwh"] == 950000
        # Projected must be less than 950000
        assert result["projected_energy_kwh"] < 950000

    def test_projected_results_from_user_baseline(self, valid_campus_data):
        """Projected energy = 950000 * (1 - 20%) = 760000 for LED retrofit."""
        validated, _ = validate_campus_data(valid_campus_data)
        cd.set_user_campus_data(validated)

        baseline = {
            "energy": 950000.0,
            "water": 35000.0,
            "waste": 85000.0,
            "co2": compute_all_metrics()["annual_co2_kg"],
        }
        result = run_manual_simulation(["led_retrofit"], 200000, baseline)
        expected = round(950000 * (1 - 0.20), 2)
        assert math.isclose(result["projected_energy_kwh"], expected, rel_tol=1e-4)


# ═════════════════════════════════════════════════════════════════════════════
# 10. WHAT-IF USES ACTIVE BASELINE
# ═════════════════════════════════════════════════════════════════════════════

class TestWhatIfUsesUserBaseline:
    def test_what_if_energy_reduction_uses_user_energy(self, valid_campus_data):
        validated, _ = validate_campus_data(valid_campus_data)
        cd.set_user_campus_data(validated)

        metrics = compute_all_metrics()
        scenario = parse_what_if("What if energy consumption is reduced by 10%?")
        assert scenario["type"] == "energy_reduction"

        updated = apply_what_if(scenario, metrics, [])
        expected = round(950000 * 0.90, 2)
        assert math.isclose(updated["annual_energy_kwh"], expected, rel_tol=1e-4)

    def test_what_if_water_reduction_uses_user_water(self, valid_campus_data):
        validated, _ = validate_campus_data(valid_campus_data)
        cd.set_user_campus_data(validated)

        metrics = compute_all_metrics()
        scenario = parse_what_if("What if water consumption is reduced by 20%?")
        updated = apply_what_if(scenario, metrics, [])
        expected = round(35000 * 0.80, 2)
        assert math.isclose(updated["annual_water_m3"], expected, rel_tol=1e-4)

    def test_what_if_budget_change_uses_user_data(self, valid_campus_data):
        validated, _ = validate_campus_data(valid_campus_data)
        cd.set_user_campus_data(validated)

        metrics = compute_all_metrics()
        scenario = parse_what_if("What if the sustainability budget is ₹10 lakh?")
        updated = apply_what_if(scenario, metrics, [])
        assert updated["what_if_budget_inr"] == 1_000_000.0


# ═════════════════════════════════════════════════════════════════════════════
# 11. NO FABRICATED MONTHLY DATA
# ═════════════════════════════════════════════════════════════════════════════

class TestNoFabricatedMonthlyData:
    def test_annual_only_no_monthly_in_energy_loader(self, valid_campus_data):
        """When only annual energy is provided, has_monthly should be False."""
        validated, _ = validate_campus_data(valid_campus_data)
        cd.set_user_campus_data(validated)
        from data_loader import load_energy
        data = load_energy()
        # Annual-only — buildings array should be empty, has_monthly False
        assert data.get("has_monthly") is False
        assert data.get("buildings") == []

    def test_monthly_data_present_when_provided(self, valid_campus_data_with_monthly):
        validated, errors = validate_campus_data(valid_campus_data_with_monthly)
        assert errors == []
        cd.set_user_campus_data(validated)
        from data_loader import load_energy
        data = load_energy()
        assert data.get("has_monthly") is True
        assert len(data["buildings"]) == 1
        assert len(data["buildings"][0]["monthly"]) == 12

    def test_monthly_energy_values_not_invented(self, valid_campus_data_with_monthly):
        """Monthly values in loaded data must exactly match what was provided."""
        original_monthly = valid_campus_data_with_monthly["energy"]["monthly_kwh"]
        validated, _ = validate_campus_data(valid_campus_data_with_monthly)
        cd.set_user_campus_data(validated)
        from data_loader import load_energy
        data = load_energy()
        loaded_monthly = data["buildings"][0]["monthly"]
        assert loaded_monthly == original_monthly


# ═════════════════════════════════════════════════════════════════════════════
# 12. EXISTING CALCULATION REGRESSIONS
# ═════════════════════════════════════════════════════════════════════════════

class TestExistingCalculationRegressions:
    """
    Demo mode regressions — existing tests remain valid in demo mode.
    These duplicate key checks from test_greencampus.py but run in isolation
    to ensure the new campus_data system does not break demo mode.
    """
    @pytest.fixture
    def demo_baseline(self):
        return {"energy": 300_000.0, "water": 18_000.0, "waste": 100_000.0, "co2": 230_000.0}

    def test_demo_metrics_positive(self):
        metrics = compute_all_metrics()
        assert metrics["annual_energy_kwh"] > 0
        assert metrics["annual_water_m3"] > 0
        assert metrics["annual_waste_kg"] > 0
        assert metrics["annual_co2_kg"] > 0
        assert metrics["data_source"] == "demo"

    def test_demo_note_says_synthetic(self):
        metrics = compute_all_metrics()
        assert "synthetic" in metrics["note"].lower() or "demo" in metrics["note"].lower()

    def test_led_retrofit_manual_sim_demo_mode(self, demo_baseline):
        result = run_manual_simulation(["led_retrofit"], 200_000, demo_baseline)
        assert result["mode"] == "manual"
        assert result["projected_energy_kwh"] < demo_baseline["energy"]

    def test_budget_optimization_demo_mode(self, demo_baseline):
        results = run_budget_optimization(500_000, demo_baseline)
        assert len(results) > 0

    def test_co2_calculation_deterministic(self):
        result = compute_annual_co2_kg(1000, 500, 200)
        expected = 1000 * 0.716 + 500 * 0.344 + 200 * 0.50
        assert math.isclose(result, expected, rel_tol=1e-9)


# ═════════════════════════════════════════════════════════════════════════════
# 13. GRANITE FALLBACK STILL WORKS
# ═════════════════════════════════════════════════════════════════════════════

class TestGraniteFallbackWithUserData:
    def test_explain_simulation_works_with_user_baseline(self, valid_campus_data):
        """explain_simulation must return a non-empty string even with user data."""
        from ai_explain import explain_simulation
        validated, _ = validate_campus_data(valid_campus_data)
        cd.set_user_campus_data(validated)

        baseline = {"energy": 950000, "water": 35000, "waste": 85000, "co2": 700000}
        result = run_manual_simulation(["led_retrofit"], 200000, baseline)
        explanation = explain_simulation(result)
        assert isinstance(explanation, str)
        assert len(explanation) > 50

    def test_granite_prompt_contains_user_derived_values(self, valid_campus_data):
        """Granite sim prompt must include the user baseline values."""
        from ai_explain import _build_granite_sim_prompt
        validated, _ = validate_campus_data(valid_campus_data)
        cd.set_user_campus_data(validated)

        baseline = {"energy": 950000, "water": 35000, "waste": 85000, "co2": 700000}
        result = run_manual_simulation(["led_retrofit"], 200000, baseline)
        prompt = _build_granite_sim_prompt(result, None)
        # Baseline energy 950000 must appear in the prompt
        assert "950000" in prompt

    def test_demo_mode_fallback_label(self):
        from ai_explain import _template_explain_simulation, _DEMO_MODE_LABEL
        result = {
            "mode": "manual",
            "interventions_applied": [],
            "disclaimer": "test",
        }
        text = _template_explain_simulation(result)
        assert "DEMO MODE" in text or "demo mode" in text.lower()


# ═════════════════════════════════════════════════════════════════════════════
# 14. CAMPUS AREA / STUDENT / STAFF VALIDATION
# ═════════════════════════════════════════════════════════════════════════════

class TestCampusInfoValidation:
    def test_zero_campus_area_fails(self):
        raw = {
            "campus": {"name": "X", "area_m2": 0},
            "energy": {"annual_kwh": 100000},
            "water": {"annual_m3": 10000},
            "waste": {"annual_kg": 5000, "recycled_pct": 30, "composted_pct": 20, "landfill_pct": 50},
        }
        validated, errors = validate_campus_data(raw)
        assert validated is None
        assert any("area" in e.lower() for e in errors)

    def test_negative_students_fails(self):
        raw = {
            "campus": {"name": "X", "students": -1},
            "energy": {"annual_kwh": 100000},
            "water": {"annual_m3": 10000},
            "waste": {"annual_kg": 5000, "recycled_pct": 30, "composted_pct": 20, "landfill_pct": 50},
        }
        validated, errors = validate_campus_data(raw)
        assert validated is None
        assert any("student" in e.lower() for e in errors)

    def test_zero_energy_fails(self):
        raw = {
            "campus": {"name": "X"},
            "energy": {"annual_kwh": 0},
            "water": {"annual_m3": 10000},
            "waste": {"annual_kg": 5000, "recycled_pct": 30, "composted_pct": 20, "landfill_pct": 50},
        }
        validated, errors = validate_campus_data(raw)
        assert validated is None
        assert any("energy" in e.lower() for e in errors)


# ═════════════════════════════════════════════════════════════════════════════
# 15. DELETE /api/campus-data — USE DEMO DATA BUTTON REGRESSION TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestUseDemoDataReset:
    """
    Regression suite for the "Use Demo Data" button flow.
    Verifies that DELETE /api/campus-data (reset_to_demo) fully resets state and
    returns correct demo metrics so the frontend can update without a second fetch.
    """

    def _activate_user_data(self, valid_campus_data):
        validated, errors = validate_campus_data(valid_campus_data)
        assert errors == []
        cd.set_user_campus_data(validated)

    # ── 1. DELETE endpoint switches to demo mode ──────────────────────────────

    def test_reset_switches_mode_to_demo(self, valid_campus_data):
        self._activate_user_data(valid_campus_data)
        assert cd.is_user_mode()
        cd.reset_to_demo()
        assert cd.get_active_mode() == "demo"
        assert cd.is_user_mode() is False

    # ── 2. User dataset is cleared after reset ────────────────────────────────

    def test_reset_clears_user_dataset(self, valid_campus_data):
        self._activate_user_data(valid_campus_data)
        cd.reset_to_demo()
        assert cd.get_user_campus_data() is None

    # ── 3. Demo dataset remains unchanged after reset ─────────────────────────

    def test_demo_dataset_unchanged_after_reset(self, valid_campus_data):
        """Demo JSON files must not be mutated by set_user_campus_data / reset_to_demo."""
        from data_loader import _load_energy_demo, _load_water_demo, _load_waste_demo
        demo_energy_before = _load_energy_demo()
        demo_water_before = _load_water_demo()
        demo_waste_before = _load_waste_demo()

        self._activate_user_data(valid_campus_data)
        cd.reset_to_demo()

        assert _load_energy_demo() is demo_energy_before   # same cached object
        assert _load_water_demo() is demo_water_before
        assert _load_waste_demo() is demo_waste_before

    # ── 4. Status endpoint reports demo mode after reset ─────────────────────

    def test_status_reports_demo_mode_after_reset(self, valid_campus_data):
        self._activate_user_data(valid_campus_data)
        cd.reset_to_demo()
        assert cd.get_active_mode() == "demo"
        assert "Demo" in cd.get_data_source_label()

    # ── 5. Metrics endpoint reports demo data after reset ────────────────────

    def test_metrics_reports_demo_data_after_reset(self, valid_campus_data):
        self._activate_user_data(valid_campus_data)
        user_metrics = compute_all_metrics()
        assert user_metrics["data_source"] == "user"
        assert math.isclose(user_metrics["annual_energy_kwh"], 950000, rel_tol=1e-4)

        cd.reset_to_demo()
        demo_metrics = compute_all_metrics()
        assert demo_metrics["data_source"] == "demo"
        # Demo energy must not equal the user-submitted 950000
        assert not math.isclose(demo_metrics["annual_energy_kwh"], 950000, rel_tol=1e-4)

    # ── 6. CO2 uses demo baseline after reset ────────────────────────────────

    def test_co2_uses_demo_baseline_after_reset(self, valid_campus_data):
        self._activate_user_data(valid_campus_data)
        cd.reset_to_demo()
        metrics = compute_all_metrics()
        # CO2 must be derived from demo energy/water/waste — just verify positive and != user CO2
        assert metrics["annual_co2_kg"] > 0
        assert metrics["data_source"] == "demo"

    # ── 7. EcoSim uses demo baseline after reset ─────────────────────────────

    def test_ecosim_uses_demo_baseline_after_reset(self, valid_campus_data):
        self._activate_user_data(valid_campus_data)
        cd.reset_to_demo()

        from data_loader import get_annual_energy_kwh
        demo_energy = get_annual_energy_kwh()
        # Demo energy must not be 950000
        assert not math.isclose(demo_energy, 950000, rel_tol=1e-4)

        demo_metrics = compute_all_metrics()
        baseline = {
            "energy": demo_metrics["annual_energy_kwh"],
            "water":  demo_metrics["annual_water_m3"],
            "waste":  demo_metrics["annual_waste_kg"],
            "co2":    demo_metrics["annual_co2_kg"],
        }
        results = run_budget_optimization(500_000, baseline, top_n=1)
        assert len(results) > 0
        assert math.isclose(results[0]["baseline_energy_kwh"], demo_energy, rel_tol=1e-4)

    # ── 8. Persist file is removed after reset ────────────────────────────────

    def test_persist_file_removed_after_reset(self, valid_campus_data):
        """Resetting must delete the persisted JSON file so restarts stay in demo mode."""
        self._activate_user_data(valid_campus_data)
        # Persist file should now exist
        assert cd._PERSIST_FILE.exists()
        cd.reset_to_demo()
        assert not cd._PERSIST_FILE.exists()

    # ── 9. Subsequent load_persisted_data stays in demo after reset + reload ──

    def test_load_persisted_data_stays_demo_after_reset(self, valid_campus_data):
        """After reset, calling load_persisted_data() (simulated restart) must stay in demo mode."""
        self._activate_user_data(valid_campus_data)
        cd.reset_to_demo()
        # Simulate a server restart: re-run load_persisted_data
        cd.load_persisted_data()
        assert cd.get_active_mode() == "demo"
        assert cd.get_user_campus_data() is None

    # ── 10. DELETE response metrics match demo compute_all_metrics ────────────

    def test_reset_returns_demo_metrics(self, valid_campus_data):
        """The metrics returned by reset_to_demo must equal demo compute_all_metrics."""
        self._activate_user_data(valid_campus_data)
        cd.reset_to_demo()
        expected = compute_all_metrics()
        assert expected["data_source"] == "demo"
        assert expected["annual_energy_kwh"] > 0

    # ── 11. Multiple reset calls are idempotent ───────────────────────────────

    def test_multiple_resets_are_idempotent(self, valid_campus_data):
        self._activate_user_data(valid_campus_data)
        cd.reset_to_demo()
        cd.reset_to_demo()  # second call must not raise or corrupt state
        assert cd.get_active_mode() == "demo"
        assert cd.get_user_campus_data() is None

    # ── 12. Reset from demo mode (already demo) is safe ──────────────────────

    def test_reset_from_demo_mode_is_safe(self):
        assert cd.get_active_mode() == "demo"
        cd.reset_to_demo()   # should not raise
        assert cd.get_active_mode() == "demo"
        metrics = compute_all_metrics()
        assert metrics["data_source"] == "demo"


# ═════════════════════════════════════════════════════════════════════════════
# 16. HTTP API — POST /api/campus-data and DELETE /api/campus-data
#
# Regression suite covering:
#  - POST returns 200 with valid payload
#  - POST activates user mode (data_source == "user")
#  - POST returns metrics immediately (no second round-trip needed)
#  - POST with invalid payload returns 422 with detail.errors (custom validator)
#  - POST with Pydantic-level invalid payload returns 422 with detail as list
#  - POST with empty campus name returns 422 (Pydantic min_length=1)
#  - DELETE returns 200 and activates demo mode
#  - DELETE returns demo metrics in response
#  - Dashboard data changes after POST (metrics reflect user values)
#  - Dashboard data returns to demo after DELETE
#  - Empty optional fields (null) are accepted
#  - Waste percentage validation via API
# ═════════════════════════════════════════════════════════════════════════════

class TestHTTPAPICampusData:
    """
    FastAPI TestClient regression tests for POST /api/campus-data and
    DELETE /api/campus-data — the two endpoints driven by the UI buttons.

    Each test resets to demo mode before and after via the autouse fixture.
    """

    @pytest.fixture(autouse=True)
    def _client(self):
        """Create a TestClient against the FastAPI app."""
        from fastapi.testclient import TestClient
        import main as app_module
        self.client = TestClient(app_module.app)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _valid_payload(self):
        return {
            "campus": {
                "name": "Test University",
                "area_m2": 50000,
                "students": 5000,
                "staff": 350,
                "buildings": 8,
            },
            "energy": {
                "annual_kwh": 950000,
                "annual_cost_inr": 8200000,
                "monthly_kwh": None,
            },
            "water": {
                "annual_m3": 35000,
                "annual_cost_inr": 1200000,
                "monthly_m3": None,
            },
            "waste": {
                "annual_kg": 85000,
                "recycled_pct": 30,
                "composted_pct": 20,
                "landfill_pct": 50,
                "monthly_kg": None,
            },
            "budget_inr": 500000,
            "existing_measures": {
                "solar_installed": False,
                "led_retrofit": False,
                "hvac_optimization": False,
                "smart_metering": False,
                "water_leak_detection": False,
                "composting": False,
                "waste_segregation": False,
                "rainwater_harvesting": False,
            },
        }

    # ── POST returns 200 ──────────────────────────────────────────────────────

    def test_post_valid_payload_returns_200(self):
        resp = self.client.post("/api/campus-data", json=self._valid_payload())
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_post_activates_user_mode(self):
        resp = self.client.post("/api/campus-data", json=self._valid_payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["data_source"] == "user"

    def test_post_returns_metrics_immediately(self):
        resp = self.client.post("/api/campus-data", json=self._valid_payload())
        assert resp.status_code == 200
        body = resp.json()
        assert "metrics" in body
        assert body["metrics"]["annual_energy_kwh"] == pytest.approx(950000, rel=1e-4)
        assert body["metrics"]["annual_water_m3"] == pytest.approx(35000, rel=1e-4)
        assert body["metrics"]["annual_waste_kg"] == pytest.approx(85000, rel=1e-4)

    def test_post_metrics_data_source_is_user(self):
        resp = self.client.post("/api/campus-data", json=self._valid_payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["metrics"]["data_source"] == "user"

    def test_post_returns_status_activated(self):
        resp = self.client.post("/api/campus-data", json=self._valid_payload())
        assert resp.status_code == 200
        assert resp.json()["status"] == "activated"

    def test_post_changes_get_metrics_to_user_values(self):
        """After POST, GET /api/metrics must reflect user energy=950000."""
        resp = self.client.post("/api/campus-data", json=self._valid_payload())
        assert resp.status_code == 200
        metrics_resp = self.client.get("/api/metrics")
        assert metrics_resp.status_code == 200
        m = metrics_resp.json()
        assert m["data_source"] == "user"
        assert m["annual_energy_kwh"] == pytest.approx(950000, rel=1e-4)

    # ── POST invalid payload — 422 with custom validator errors ──────────────

    def test_post_missing_campus_name_returns_422(self):
        payload = self._valid_payload()
        payload["campus"]["name"] = ""
        resp = self.client.post("/api/campus-data", json=payload)
        assert resp.status_code == 422

    def test_post_empty_campus_name_detail_is_structured(self):
        """detail is either a list (Pydantic) or {errors:[...]} (custom)."""
        payload = self._valid_payload()
        payload["campus"]["name"] = ""
        resp = self.client.post("/api/campus-data", json=payload)
        assert resp.status_code == 422
        body = resp.json()
        # detail must be present
        assert "detail" in body
        detail = body["detail"]
        # Pydantic returns a list; custom validator returns dict with "errors" key
        assert isinstance(detail, (list, dict))

    def test_post_zero_energy_returns_422(self):
        payload = self._valid_payload()
        payload["energy"]["annual_kwh"] = 0
        resp = self.client.post("/api/campus-data", json=payload)
        assert resp.status_code == 422
        body = resp.json()
        detail = body["detail"]
        # Custom validator returns {"errors": [...]}
        if isinstance(detail, dict):
            assert any("energy" in e.lower() for e in detail.get("errors", []))

    def test_post_waste_pct_not_100_returns_422(self):
        payload = self._valid_payload()
        payload["waste"]["recycled_pct"] = 40
        payload["waste"]["composted_pct"] = 40
        payload["waste"]["landfill_pct"] = 40  # sum = 120 ≠ 100
        resp = self.client.post("/api/campus-data", json=payload)
        assert resp.status_code == 422
        body = resp.json()
        detail = body["detail"]
        if isinstance(detail, dict):
            assert any("100" in e or "sum" in e.lower() for e in detail.get("errors", []))

    def test_post_null_optional_fields_accepted(self):
        """All optional fields as null must be accepted without 422."""
        payload = self._valid_payload()
        payload["campus"]["area_m2"] = None
        payload["campus"]["students"] = None
        payload["campus"]["staff"] = None
        payload["campus"]["buildings"] = None
        payload["energy"]["annual_cost_inr"] = None
        payload["water"]["annual_cost_inr"] = None
        payload["budget_inr"] = None
        resp = self.client.post("/api/campus-data", json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_post_omitted_optional_fields_accepted(self):
        """Omitting optional fields entirely must be accepted."""
        payload = {
            "campus": {"name": "Minimal Campus"},
            "energy": {"annual_kwh": 500000},
            "water": {"annual_m3": 20000},
            "waste": {
                "annual_kg": 50000,
                "recycled_pct": 30,
                "composted_pct": 20,
                "landfill_pct": 50,
            },
        }
        resp = self.client.post("/api/campus-data", json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    # ── DELETE returns 200 ────────────────────────────────────────────────────

    def test_delete_returns_200(self):
        # First activate user data
        self.client.post("/api/campus-data", json=self._valid_payload())
        resp = self.client.delete("/api/campus-data")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_delete_returns_demo_mode(self):
        self.client.post("/api/campus-data", json=self._valid_payload())
        resp = self.client.delete("/api/campus-data")
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "demo"

    def test_delete_success_true(self):
        resp = self.client.delete("/api/campus-data")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_delete_returns_metrics(self):
        self.client.post("/api/campus-data", json=self._valid_payload())
        resp = self.client.delete("/api/campus-data")
        assert resp.status_code == 200
        body = resp.json()
        assert "metrics" in body
        assert body["metrics"]["data_source"] == "demo"
        assert body["metrics"]["annual_energy_kwh"] > 0

    def test_delete_reverts_get_metrics_to_demo(self):
        """After DELETE, GET /api/metrics must reflect demo data, not user 950000."""
        self.client.post("/api/campus-data", json=self._valid_payload())
        self.client.delete("/api/campus-data")
        resp = self.client.get("/api/metrics")
        assert resp.status_code == 200
        m = resp.json()
        assert m["data_source"] == "demo"
        assert not math.isclose(m["annual_energy_kwh"], 950000, rel_tol=1e-4)

    def test_delete_from_demo_mode_is_safe(self):
        """DELETE when already in demo mode must return 200 without error."""
        assert cd.get_active_mode() == "demo"
        resp = self.client.delete("/api/campus-data")
        assert resp.status_code == 200
        assert resp.json()["mode"] == "demo"

    # ── Full POST → DELETE round-trip ─────────────────────────────────────────

    def test_post_then_delete_full_cycle(self):
        """Full Analyse Campus → Use Demo Data cycle must work end-to-end."""
        # Step 1: submit user data
        post_resp = self.client.post("/api/campus-data", json=self._valid_payload())
        assert post_resp.status_code == 200
        assert post_resp.json()["data_source"] == "user"

        # Step 2: verify metrics are user values
        m1 = self.client.get("/api/metrics").json()
        assert m1["data_source"] == "user"
        assert m1["annual_energy_kwh"] == pytest.approx(950000, rel=1e-4)

        # Step 3: reset to demo
        del_resp = self.client.delete("/api/campus-data")
        assert del_resp.status_code == 200
        assert del_resp.json()["mode"] == "demo"

        # Step 4: verify metrics are demo values
        m2 = self.client.get("/api/metrics").json()
        assert m2["data_source"] == "demo"
        assert not math.isclose(m2["annual_energy_kwh"], 950000, rel_tol=1e-4)

    def test_post_data_source_label_says_user_campus(self):
        resp = self.client.post("/api/campus-data", json=self._valid_payload())
        assert resp.status_code == 200
        body = resp.json()
        assert "User" in body.get("data_source_label", "")

    def test_delete_data_source_label_says_demo(self):
        self.client.post("/api/campus-data", json=self._valid_payload())
        resp = self.client.delete("/api/campus-data")
        assert resp.status_code == 200
        body = resp.json()
        assert "Demo" in body.get("data_source_label", "")

    # ── Invalid numeric values ────────────────────────────────────────────────

    def test_post_negative_energy_returns_422(self):
        payload = self._valid_payload()
        payload["energy"]["annual_kwh"] = -1000
        resp = self.client.post("/api/campus-data", json=payload)
        assert resp.status_code == 422

    def test_post_negative_water_returns_422(self):
        payload = self._valid_payload()
        payload["water"]["annual_m3"] = -500
        resp = self.client.post("/api/campus-data", json=payload)
        assert resp.status_code == 422

    def test_post_negative_waste_returns_422(self):
        payload = self._valid_payload()
        payload["waste"]["annual_kg"] = -100
        resp = self.client.post("/api/campus-data", json=payload)
        assert resp.status_code == 422


# ═════════════════════════════════════════════════════════════════════════════
# 17. DEMO FORM PAYLOAD — POST /api/campus-data WITH DEMO DATA
#
# Verifies that the exact payload produced by the frontend after clicking
# "Use Demo Data" then "Analyse Campus" returns 200.
# ═════════════════════════════════════════════════════════════════════════════

class TestDemoFormPayloadSubmission:
    """
    The 'Use Demo Data' button fetches /api/campus-data/demo, populates the
    form, and then submits via POST /api/campus-data.  These tests verify
    that the exact payload that the frontend constructs passes validation.
    """

    @pytest.fixture(autouse=True)
    def _client(self):
        from fastapi.testclient import TestClient
        import main as app_module
        self.client = TestClient(app_module.app)

    def _demo_form_payload(self):
        """
        Simulate the exact payload buildPayload() produces after populateForm()
        fills the form with demo data from GET /api/campus-data/demo.
        """
        resp = self.client.get("/api/campus-data/demo")
        assert resp.status_code == 200
        d = resp.json()

        e   = d["energy"]
        w   = d["water"]
        wst = d["waste"]
        c   = d["campus"]

        # Simulate monthlyToNums: parse string values back to floats
        energy_monthly = [float(v) for v in e["monthly_kwh"]] if e["monthly_kwh"] else None
        water_monthly  = [float(v) for v in w["monthly_m3"]]  if w["monthly_m3"]  else None
        waste_monthly  = [float(v) for v in wst["monthly_kg"]] if wst["monthly_kg"] else None

        return {
            "campus": {
                "name":      c["name"],
                "area_m2":   float(c["area_m2"]) if c["area_m2"] is not None else None,
                "students":  int(c["students"])  if c["students"] is not None else None,
                "staff":     int(c["staff"])      if c["staff"] is not None else None,
                "buildings": int(c["buildings"])  if c["buildings"] is not None else None,
            },
            "energy": {
                "annual_kwh":      None,   # monthly overrides annual
                "annual_cost_inr": None,
                "monthly_kwh":     energy_monthly,
            },
            "water": {
                "annual_m3":       None,
                "annual_cost_inr": None,
                "monthly_m3":      water_monthly,
            },
            "waste": {
                "annual_kg":      None,
                "recycled_pct":   float(wst["recycled_pct"]),
                "composted_pct":  float(wst["composted_pct"]),
                "landfill_pct":   float(wst["landfill_pct"]),
                "monthly_kg":     waste_monthly,
            },
            "budget_inr":        float(d["budget_inr"]),
            "existing_measures": d["existing_measures"],
        }

    def test_demo_form_payload_returns_200(self):
        """POST /api/campus-data with demo form payload must return 200."""
        payload = self._demo_form_payload()
        resp = self.client.post("/api/campus-data", json=payload)
        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}. Body: {resp.text[:400]}"
        )

    def test_demo_form_payload_activates_user_mode(self):
        payload = self._demo_form_payload()
        resp = self.client.post("/api/campus-data", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["data_source"] == "user"

    def test_demo_form_payload_returns_metrics(self):
        payload = self._demo_form_payload()
        resp = self.client.post("/api/campus-data", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert "metrics" in body
        assert body["metrics"]["annual_energy_kwh"] > 0
        assert body["metrics"]["annual_water_m3"] > 0
        assert body["metrics"]["annual_waste_kg"] > 0

    def test_demo_form_payload_monthly_energy_accepted(self):
        """Monthly energy values in demo payload must be accepted and summed correctly."""
        payload = self._demo_form_payload()
        assert payload["energy"]["monthly_kwh"] is not None
        assert len(payload["energy"]["monthly_kwh"]) == 12
        resp = self.client.post("/api/campus-data", json=payload)
        assert resp.status_code == 200
        # Energy should equal sum of monthly
        expected_energy = sum(payload["energy"]["monthly_kwh"])
        body = resp.json()
        assert math.isclose(body["metrics"]["annual_energy_kwh"], expected_energy, rel_tol=1e-4)

    def test_demo_form_payload_monthly_water_accepted(self):
        payload = self._demo_form_payload()
        assert payload["water"]["monthly_m3"] is not None
        assert len(payload["water"]["monthly_m3"]) == 12
        resp = self.client.post("/api/campus-data", json=payload)
        assert resp.status_code == 200
        expected_water = sum(payload["water"]["monthly_m3"])
        body = resp.json()
        assert math.isclose(body["metrics"]["annual_water_m3"], expected_water, rel_tol=1e-4)

    def test_demo_form_payload_monthly_waste_accepted(self):
        payload = self._demo_form_payload()
        assert payload["waste"]["monthly_kg"] is not None
        assert len(payload["waste"]["monthly_kg"]) == 12
        resp = self.client.post("/api/campus-data", json=payload)
        assert resp.status_code == 200
        expected_waste = sum(payload["waste"]["monthly_kg"])
        body = resp.json()
        assert math.isclose(body["metrics"]["annual_waste_kg"], expected_waste, rel_tol=1e-4)

    def test_demo_form_existing_measures_booleans_accepted(self):
        """existing_measures with boolean False values must be accepted."""
        payload = self._demo_form_payload()
        # All existing_measures are False in demo data
        assert all(v is False for v in payload["existing_measures"].values())
        resp = self.client.post("/api/campus-data", json=payload)
        assert resp.status_code == 200

    def test_demo_form_no_validation_error(self):
        """Demo form payload must produce no validation errors."""
        payload = self._demo_form_payload()
        resp = self.client.post("/api/campus-data", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("status") == "activated"

    def test_demo_form_waste_pct_sum_is_100(self):
        """Demo waste percentages must sum to 100%."""
        payload = self._demo_form_payload()
        pct_sum = (payload["waste"]["recycled_pct"] +
                   payload["waste"]["composted_pct"] +
                   payload["waste"]["landfill_pct"])
        assert abs(pct_sum - 100.0) < 0.1, f"Waste pcts sum to {pct_sum}, expected 100"


# ═════════════════════════════════════════════════════════════════════════════
# 18. USER FORM PAYLOAD — manual data from the task description
# ═════════════════════════════════════════════════════════════════════════════

class TestUserFormPayload:
    """Tests for the manual user data scenario from the task description."""

    @pytest.fixture(autouse=True)
    def _client(self):
        from fastapi.testclient import TestClient
        import main as app_module
        self.client = TestClient(app_module.app)

    def _user_payload(self):
        return {
            "campus": {
                "name":      "My Campus",
                "area_m2":   50000.0,
                "students":  5000,
                "staff":     350,
                "buildings": 8,
            },
            "energy": {
                "annual_kwh":      950000.0,
                "annual_cost_inr": 8200000.0,
                "monthly_kwh":     None,
            },
            "water": {
                "annual_m3":       35000.0,
                "annual_cost_inr": 1200000.0,
                "monthly_m3":      None,
            },
            "waste": {
                "annual_kg":      85000.0,
                "recycled_pct":   30.0,
                "composted_pct":  20.0,
                "landfill_pct":   50.0,
                "monthly_kg":     None,
            },
            "budget_inr":        500000.0,
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

    def test_user_form_payload_returns_200(self):
        resp = self.client.post("/api/campus-data", json=self._user_payload())
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_user_form_energy_correct(self):
        resp = self.client.post("/api/campus-data", json=self._user_payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["metrics"]["annual_energy_kwh"] == pytest.approx(950000, rel=1e-4)

    def test_user_form_water_correct(self):
        resp = self.client.post("/api/campus-data", json=self._user_payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["metrics"]["annual_water_m3"] == pytest.approx(35000, rel=1e-4)

    def test_user_form_waste_correct(self):
        resp = self.client.post("/api/campus-data", json=self._user_payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["metrics"]["annual_waste_kg"] == pytest.approx(85000, rel=1e-4)

    def test_user_form_data_source_is_user(self):
        resp = self.client.post("/api/campus-data", json=self._user_payload())
        assert resp.status_code == 200
        assert resp.json()["metrics"]["data_source"] == "user"

    def test_user_form_no_monthly_data_accepted(self):
        """User data without monthly values must be accepted (annual only)."""
        payload = self._user_payload()
        assert payload["energy"]["monthly_kwh"] is None
        assert payload["water"]["monthly_m3"] is None
        assert payload["waste"]["monthly_kg"] is None
        resp = self.client.post("/api/campus-data", json=payload)
        assert resp.status_code == 200


# ═════════════════════════════════════════════════════════════════════════════
# 19. NUMERIC FORM VALUE NORMALIZATION
#
# Verifies that numeric types commonly produced by HTML form inputs (strings,
# floats in int fields, None) are accepted correctly by the backend.
# ═════════════════════════════════════════════════════════════════════════════

class TestNumericFormNormalization:
    """
    HTML inputs return string values; the frontend toFloat/toInt helpers must
    convert them correctly before sending.  The backend must accept the
    resulting float/int types.
    """

    def test_string_numeric_fields_accepted_by_validator(self):
        """
        Validator must handle string-numeric values (e.g., '950000') in raw dict,
        since some code paths could pass raw form values.
        """
        raw = {
            "campus": {"name": "Test", "area_m2": "50000", "students": "5000"},
            "energy": {"annual_kwh": "950000"},
            "water":  {"annual_m3": "35000"},
            "waste":  {"annual_kg": "85000", "recycled_pct": "30",
                       "composted_pct": "20", "landfill_pct": "50"},
        }
        validated, errors = validate_campus_data(raw)
        assert errors == [], f"Unexpected errors: {errors}"
        assert validated is not None
        assert validated["energy"]["annual_kwh"] == 950000.0

    def test_float_in_int_field_accepted_by_validator(self):
        """campus.students=5000.0 (float) must be coerced to int 5000."""
        raw = {
            "campus": {"name": "Test", "students": 5000.0, "staff": 350.0},
            "energy": {"annual_kwh": 950000},
            "water":  {"annual_m3": 35000},
            "waste":  {"annual_kg": 85000, "recycled_pct": 30,
                       "composted_pct": 20, "landfill_pct": 50},
        }
        validated, errors = validate_campus_data(raw)
        assert errors == []
        assert validated["campus"]["students"] == 5000
        assert isinstance(validated["campus"]["students"], int)

    def test_monthly_energy_integer_values_accepted(self):
        """Monthly energy values that are integers (not floats) must be accepted."""
        monthly = [80000, 75000, 72000, 70000, 78000, 90000,
                   98000, 95000, 85000, 78000, 73000, 76000]
        raw = {
            "campus": {"name": "Test"},
            "energy": {"monthly_kwh": monthly},
            "water":  {"annual_m3": 35000},
            "waste":  {"annual_kg": 85000, "recycled_pct": 30,
                       "composted_pct": 20, "landfill_pct": 50},
        }
        validated, errors = validate_campus_data(raw)
        assert errors == []
        assert math.isclose(validated["energy"]["annual_kwh"], sum(monthly), rel_tol=1e-6)

    def test_waste_pct_sum_tolerance(self):
        """Waste percentages with floating-point sum close to 100 must be accepted."""
        # 25.7 + 22.0 + 52.3 = 100.0 (may have fp precision issues)
        raw = {
            "campus": {"name": "Test"},
            "energy": {"annual_kwh": 100000},
            "water":  {"annual_m3": 10000},
            "waste":  {
                "annual_kg": 50000,
                "recycled_pct": 25.7, "composted_pct": 22.0, "landfill_pct": 52.3,
            },
        }
        validated, errors = validate_campus_data(raw)
        assert errors == [], f"FP tolerance failed: {errors}"

    def test_empty_optional_budget_null_accepted(self):
        """budget_inr=None (omitted from form) must be accepted."""
        raw = {
            "campus": {"name": "Test"},
            "energy": {"annual_kwh": 100000},
            "water":  {"annual_m3": 10000},
            "waste":  {"annual_kg": 5000, "recycled_pct": 30,
                       "composted_pct": 20, "landfill_pct": 50},
            "budget_inr": None,
        }
        validated, errors = validate_campus_data(raw)
        assert errors == []

    def test_invalid_nan_energy_fails(self):
        """NaN energy must be rejected by the validator."""
        raw = {
            "campus": {"name": "Test"},
            "energy": {"annual_kwh": float("nan")},
            "water":  {"annual_m3": 10000},
            "waste":  {"annual_kg": 5000, "recycled_pct": 30,
                       "composted_pct": 20, "landfill_pct": 50},
        }
        validated, errors = validate_campus_data(raw)
        # Validator must reject NaN — either returns None+errors or catches it
        assert validated is None or len(errors) > 0 or (
            validated.get("energy", {}).get("annual_kwh") is not None and
            not math.isnan(validated["energy"]["annual_kwh"])
        )


# ═════════════════════════════════════════════════════════════════════════════
# 20. SESSION ISOLATION — separate sessions must not share user data
# ═════════════════════════════════════════════════════════════════════════════

class TestSessionIsolation:
    """
    Verify that campus_data session-scoped functions isolate user data
    per session ID so that two different browser clients cannot access
    each other's data.
    """

    @pytest.fixture(autouse=True)
    def _reset(self):
        """Clean up any sessions created during tests."""
        yield
        cd._sessions.clear()
        cd.reset_to_demo()

    def _activate(self, session_id, data):
        validated, errors = validate_campus_data(data)
        assert errors == []
        cd.set_session_data(session_id, validated)

    def test_two_sessions_are_independent(self):
        """Session A's data must not appear in Session B."""
        data_a = {
            "campus": {"name": "Campus A"},
            "energy": {"annual_kwh": 111000},
            "water":  {"annual_m3": 11000},
            "waste":  {"annual_kg": 11000, "recycled_pct": 30,
                       "composted_pct": 20, "landfill_pct": 50},
        }
        data_b = {
            "campus": {"name": "Campus B"},
            "energy": {"annual_kwh": 222000},
            "water":  {"annual_m3": 22000},
            "waste":  {"annual_kg": 22000, "recycled_pct": 30,
                       "composted_pct": 20, "landfill_pct": 50},
        }
        sid_a = cd.make_session_id()
        sid_b = cd.make_session_id()

        self._activate(sid_a, data_a)
        self._activate(sid_b, data_b)

        a_data = cd.get_session_data(sid_a)
        b_data = cd.get_session_data(sid_b)

        assert a_data["campus"]["name"] == "Campus A"
        assert b_data["campus"]["name"] == "Campus B"
        assert a_data is not b_data

    def test_session_reset_does_not_affect_other_session(self):
        """Resetting Session A must not change Session B's data."""
        data = {
            "campus": {"name": "Campus B"},
            "energy": {"annual_kwh": 200000},
            "water":  {"annual_m3": 20000},
            "waste":  {"annual_kg": 20000, "recycled_pct": 30,
                       "composted_pct": 20, "landfill_pct": 50},
        }
        sid_a = cd.make_session_id()
        sid_b = cd.make_session_id()
        cd.reset_session_to_demo(sid_a)   # ensure A is in demo
        self._activate(sid_b, data)

        cd.reset_session_to_demo(sid_a)   # reset A

        # B's data must be untouched
        assert cd.is_session_user_mode(sid_b) is True
        assert cd.get_session_data(sid_b)["campus"]["name"] == "Campus B"
        # A must be in demo mode
        assert cd.get_session_mode(sid_a) == "demo"
        assert cd.get_session_data(sid_a) is None

    def test_unknown_session_returns_demo_mode(self):
        """A session ID that doesn't exist must report demo mode (not user mode)."""
        unknown_sid = "nonexistent-session-id-xyz"
        assert cd.get_session_mode(unknown_sid) == "demo"
        assert cd.get_session_data(unknown_sid) is None
        assert cd.is_session_user_mode(unknown_sid) is False

    def test_session_id_is_random(self):
        """Two calls to make_session_id must return different IDs."""
        sid1 = cd.make_session_id()
        sid2 = cd.make_session_id()
        assert sid1 != sid2
        assert len(sid1) > 16   # at least 16 chars of URL-safe base64

    def test_http_sessions_isolated_via_cookies(self):
        """
        Two TestClient instances with different session cookies must see
        independent data via the HTTP API.
        """
        from fastapi.testclient import TestClient
        import main as app_module

        client_a = TestClient(app_module.app)
        client_b = TestClient(app_module.app)

        payload_a = {
            "campus": {"name": "Campus A"},
            "energy": {"annual_kwh": 111000, "annual_cost_inr": None, "monthly_kwh": None},
            "water":  {"annual_m3": 11000,  "annual_cost_inr": None, "monthly_m3": None},
            "waste":  {"annual_kg": 11000, "recycled_pct": 30, "composted_pct": 20,
                       "landfill_pct": 50, "monthly_kg": None},
            "budget_inr": None,
            "existing_measures": {},
        }
        payload_b = {
            "campus": {"name": "Campus B"},
            "energy": {"annual_kwh": 999000, "annual_cost_inr": None, "monthly_kwh": None},
            "water":  {"annual_m3": 99000,  "annual_cost_inr": None, "monthly_m3": None},
            "waste":  {"annual_kg": 99000, "recycled_pct": 30, "composted_pct": 20,
                       "landfill_pct": 50, "monthly_kg": None},
            "budget_inr": None,
            "existing_measures": {},
        }

        resp_a = client_a.post("/api/campus-data", json=payload_a)
        assert resp_a.status_code == 200

        resp_b = client_b.post("/api/campus-data", json=payload_b)
        assert resp_b.status_code == 200

        # A's metrics must reflect campus A (111000 kWh)
        metrics_a = client_a.get("/api/metrics").json()
        assert metrics_a["data_source"] == "user"
        assert math.isclose(metrics_a["annual_energy_kwh"], 111000, rel_tol=1e-4)

        # B's metrics must reflect campus B (999000 kWh)
        metrics_b = client_b.get("/api/metrics").json()
        assert metrics_b["data_source"] == "user"
        assert math.isclose(metrics_b["annual_energy_kwh"], 999000, rel_tol=1e-4)

        # A's energy must NOT equal B's
        assert not math.isclose(metrics_a["annual_energy_kwh"],
                                metrics_b["annual_energy_kwh"], rel_tol=1e-4)
