# GreenCampus AI

AI-powered campus sustainability decision-support platform.

> This prototype supports both **synthetic demo data** and **user-provided campus data**. All figures are illustrative unless you enter real campus values.

---

## Quick Start

### 1. Backend

```bash
cd greencampus/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API available at: http://localhost:8000  
Swagger docs: http://localhost:8000/docs

### 2. Frontend

```bash
cd greencampus/frontend
npm install
npm run dev
```

App available at: http://localhost:5173

---

## Campus Data

### Overview

GreenCampus AI supports two data modes:

| Mode | Description |
|---|---|
| **Demo Synthetic Data** (default) | Pre-built synthetic dataset — available immediately, no input needed |
| **User Campus Data** | Your real campus sustainability data — drives all analytics |

The active data source is clearly indicated in the header, nav banner, and on every dashboard page.

### Entering Campus Data Manually

1. Open GreenCampus AI.
2. Click **📋 Campus Data** in the navigation.
3. Fill in the form sections:
   - **Section A** — Campus name, area, student/staff/building counts
   - **Section B** — Annual electricity consumption (kWh) and optional monthly values
   - **Section C** — Annual water consumption (m³) and optional monthly values
   - **Section D** — Annual waste (kg), recycled/composted/landfill percentages (must sum to 100%), optional monthly values
   - **Section E** — Sustainability budget (₹) — becomes the default EcoSim-Opt budget
   - **Section F** — Existing sustainability measures (checkboxes)
4. Click **🔬 Analyse Campus**.
5. All dashboards (Overview, Energy, Water, Waste, CO₂, EcoSim-Opt, What-If, AI Assistant) immediately update to use your data.

### CSV Upload

1. On the Campus Data page, click **⬇ Download CSV Template**.
2. Edit the template with your campus values.
3. Upload the file with **⬆ Upload CSV**.

#### CSV Format

The CSV uses a `metric,value,unit` format. One metric per row. Lines starting with `#` are comments.

```csv
metric,value,unit
# ── Campus Information ─────────────────────────────────────────────
campus_name,My Campus,text
campus_area,50000,m2
students,5000,count
staff,350,count
buildings,8,count
# ── Energy ─────────────────────────────────────────────────────────
annual_energy,950000,kWh
annual_energy_cost,8200000,INR
# Optional monthly energy values (uncomment to include):
# energy_jan,80000,kWh
# energy_feb,75000,kWh
# ...
# energy_dec,76000,kWh
# ── Water ───────────────────────────────────────────────────────────
annual_water,35000,m3
annual_water_cost,1200000,INR
# ── Waste ───────────────────────────────────────────────────────────
annual_waste,85000,kg
recycled_percent,30,percent
composted_percent,20,percent
landfill_percent,50,percent
# ── Sustainability Budget ───────────────────────────────────────────
budget,500000,INR
```

**Supported metric names:**

| Metric | Description | Unit |
|---|---|---|
| `campus_name` | Campus name | text |
| `campus_area` | Area in m² | m2 |
| `students` | Number of students | count |
| `staff` | Number of staff | count |
| `buildings` | Number of buildings | count |
| `annual_energy` | Annual electricity kWh | kWh |
| `annual_energy_cost` | Annual energy cost ₹ | INR |
| `annual_water` | Annual water m³ | m3 |
| `annual_water_cost` | Annual water cost ₹ | INR |
| `annual_waste` | Annual total waste kg | kg |
| `recycled_percent` | Recycled waste % | percent |
| `composted_percent` | Composted waste % | percent |
| `landfill_percent` | Landfill waste % | percent |
| `budget` | Sustainability budget ₹ | INR |
| `energy_jan` … `energy_dec` | Monthly energy kWh | kWh |
| `water_jan` … `water_dec` | Monthly water m³ | m3 |
| `waste_jan` … `waste_dec` | Monthly waste kg | kg |

### Required Fields

The following fields must be provided (either directly or derived from monthly values):

- Campus name
- Annual energy consumption (kWh) — or all 12 monthly values
- Annual water consumption (m³) — or all 12 monthly values  
- Annual waste (kg) — or all 12 monthly values
- Waste composition percentages (recycled + composted + landfill = 100%)

### Monthly Data

Monthly values are **optional**. If provided (all 12 months for a resource), they enable:
- Monthly trend charts in Energy/Water/Waste pages
- More accurate seasonal analysis

If only annual totals are provided:
- Calculations use the annual total
- Monthly trend charts are **not shown** (data is not fabricated)
- A clear notice is shown on the dashboard

### Switching Between Demo and User Data

- **Use Demo Data**: Click the 🔄 button on the Campus Data page, or navigate to Campus Data and click "Use Demo Data". The original synthetic prototype dataset is immediately restored.
- **Enter Your Data**: Fill the form and click "Analyse Campus".

### Data Validation

The following validation rules are enforced:

- Campus name is required
- Energy consumption > 0
- Water consumption > 0
- Waste > 0
- All numeric values ≥ 0 (no negatives)
- Percentages between 0 and 100
- Recycled + Composted + Landfill must equal exactly 100%
- Monthly arrays must contain exactly 12 values if provided
- All monthly values ≥ 0

Errors are returned as clear, human-readable messages. Data is **never silently corrected or fabricated**.

### Privacy Considerations

- Do **not** upload personally identifiable information (student names, IDs, contact details).
- Do **not** upload confidential financial or legal records.
- Only sustainability and operational data should be entered (energy kWh, water m³, waste kg, costs).
- User data is stored locally on the backend server. It is **not transmitted to any external service** except IBM watsonx.ai (only when `GRANITE_MODE=1` is set).
- This prototype does **not** require IoT hardware. Values can be entered from utility bills, audit reports, or sustainability databases.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GRANITE_MODE` | No (default `0`) | Set to `1` to enable IBM Granite explanations |
| `WATSONX_API_KEY` | Only if `GRANITE_MODE=1` | IBM watsonx.ai API key |
| `WATSONX_PROJECT_ID` | Only if `GRANITE_MODE=1` | watsonx.ai project ID |
| `WATSONX_URL` | No | Default: `https://us-south.ml.cloud.ibm.com` |
| `GRANITE_MODEL_ID` | No | Default: `ibm/granite-4-h-small` |

**Never hard-code credentials.** Set them as shell environment variables:

```powershell
# Windows PowerShell
$env:GRANITE_MODE        = "1"
$env:WATSONX_API_KEY     = "your-api-key"
$env:WATSONX_PROJECT_ID  = "your-project-id"
uvicorn main:app --reload --port 8000
```

> **Model ID note:** The default model is `ibm/granite-4-h-small`.
> Replace with a model available in your watsonx.ai account.
> If `GRANITE_MODE=1` but Granite is unavailable, the app silently falls back to DEMO MODE.

---

## Run Tests

```bash
cd greencampus/backend
pytest tests/ -v
```

**Expected result:** All 167 tests pass.

---

## API Endpoints

### Existing Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Health check + Granite mode |
| GET | `/api/metrics` | All campus KPIs (active dataset) |
| GET | `/api/energy` | Energy data (active dataset) |
| GET | `/api/water` | Water data (active dataset) |
| GET | `/api/waste` | Waste data (active dataset) |
| GET | `/api/interventions` | Intervention catalogue |
| POST | `/api/simulate` | Manual simulation (active baseline) |
| POST | `/api/optimize` | Budget optimization (active baseline) |
| POST | `/api/what-if` | Natural-language what-if (active baseline) |
| POST | `/api/assistant` | AI assistant (active dataset context) |
| POST | `/api/explain` | Explain a simulation result |

### New Campus Data Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/campus-data/status` | Active mode, label, completeness |
| GET | `/api/campus-data` | Return current user data (if any) |
| POST | `/api/campus-data` | Submit campus data (validate + activate) |
| DELETE | `/api/campus-data` | Reset to demo dataset |
| POST | `/api/campus-data/csv` | Upload a CSV file |
| GET | `/api/campus-data/csv-template` | Download the CSV template |

---

## Demo Flow (No Hardware Required)

### With Demo Data (immediate)

1. Open the app — **Overview** shows synthetic campus metrics instantly.
2. Click **EcoSim-Opt** → enter ₹5,00,000 → click Optimize Portfolio.
3. View top-3 ranked portfolios with scores, payback, and CO₂ impact.
4. Use **What-If**: *"What if AC energy consumption is reduced by 15%?"*
5. Use **AI Assistant**: *"Why did you recommend these interventions?"*
6. Review **Responsible AI** for full transparency disclosures.

### With User Data

1. Click **📋 Campus Data** in the navigation.
2. Enter your campus values (or upload a CSV).
3. Click **🔬 Analyse Campus**.
4. All dashboards update immediately to show results based on your data.
5. Open **EcoSim-Opt** — the baseline is your campus data.
6. Open **AI Assistant** — ask: *"How much electricity does my campus consume?"*
7. Click **🔄 Use Demo Data** to instantly restore the original synthetic dataset.

---

## Architecture

```
User Data (form / CSV)
      ↓
Validation (data_validator.py)
      ↓
campus_data.py (in-memory store)
      ↓
data_loader.py (active-dataset-aware)
      ↓
calculations.py (deterministic CO₂, metrics)
      ↓
simulator.py (EcoSim-Opt, user baseline)
      ↓
what_if_parser.py (user baseline)
      ↓
Calculated Results
      ↓
ai_explain.py (Granite / template — never calculates numbers)
      ↓
Dashboard (React + Recharts)
```

**Key principle:** The LLM (Granite) is **never** the source of numerical truth. All CO₂ calculations, optimization scores, and projections come from deterministic Python code.

---

## Files Changed / Added (v0.2.0)

**Backend:**
- `campus_data.py` — new: in-memory dataset store, demo/user mode management
- `data_validator.py` — new: all validation rules, CSV parser, template generator
- `data_loader.py` — updated: active-dataset-aware, all loaders check user mode
- `calculations.py` — updated: uses active dataset, emits data_source metadata
- `models.py` — updated: added CampusDataRequest, CampusDataStatusResponse
- `main.py` — updated: 6 new campus data endpoints, all analytics use active dataset
- `simulator.py` — updated: removed duplicate import

**Frontend:**
- `src/components/CampusData.jsx` — new: manual form + CSV upload page
- `src/App.jsx` — updated: Campus Data tab, data source badge, state management
- `src/api.js` — updated: 6 new campus data API functions
- `src/components/MetricsSummary.jsx` — updated: data source indicator, completeness
- `src/components/EnergyDashboard.jsx` — updated: handles user mode, no fabricated monthly
- `src/components/WaterDashboard.jsx` — updated: handles user mode
- `src/components/WasteDashboard.jsx` — updated: handles user mode
- `src/components/CO2Dashboard.jsx` — updated: data source badge
- `src/components/EcoSimOpt.jsx` — updated: data source badge, uses active budget
- `src/components/ResponsibleAI.jsx` — updated: user data section, emission factor table

**Tests:**
- `tests/test_campus_data.py` — new: 61 new tests across 14 test classes
