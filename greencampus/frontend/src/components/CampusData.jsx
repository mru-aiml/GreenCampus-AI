import { useState, useEffect, useRef } from 'react'
import {
  postCampusData,
  deleteCampusData,
  uploadCampusCSV,
  fetchCSVTemplate,
  fetchCampusData,
  fetchDemoData,
} from '../api.js'
import { fmtINR, fmtNum } from '../utils/formatters.js'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// ── Small helpers ──────────────────────────────────────────────────────────────

function SectionHeader({ title, subtitle }) {
  return (
    <div className="mb-4">
      <h3 className="text-base font-bold text-green-800">{title}</h3>
      {subtitle && <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>}
    </div>
  )
}

function FormField({ label, hint, required, error, children }) {
  return (
    <div className="mb-4">
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label}{required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {hint && <p className="text-xs text-gray-400 mb-1">{hint}</p>}
      {children}
      {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
    </div>
  )
}

function NumInput({ value, onChange, placeholder, min = '0', step = 'any', disabled }) {
  return (
    <input
      type="number"
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      min={min}
      step={step}
      disabled={disabled}
      className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-full focus:outline-none focus:ring-2 focus:ring-green-400 disabled:bg-gray-100"
    />
  )
}

function TextInput({ value, onChange, placeholder, disabled }) {
  return (
    <input
      type="text"
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      disabled={disabled}
      className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-full focus:outline-none focus:ring-2 focus:ring-green-400 disabled:bg-gray-100"
    />
  )
}

function MonthlyGrid({ values, onChange, unit }) {
  return (
    <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 mt-2">
      {MONTHS.map((m, i) => (
        <div key={m}>
          <label className="block text-xs text-gray-500 mb-0.5">{m}</label>
          <input
            type="number"
            value={values[i] ?? ''}
            onChange={e => {
              const next = [...values]
              next[i] = e.target.value
              onChange(next)
            }}
            min="0"
            step="any"
            placeholder="—"
            className="border border-gray-200 rounded px-2 py-1 text-xs w-full focus:outline-none focus:ring-1 focus:ring-green-400"
          />
        </div>
      ))}
      <div className="col-span-3 sm:col-span-4 text-xs text-gray-400 italic mt-1">
        Unit: {unit}
      </div>
    </div>
  )
}

function CheckboxRow({ label, id, checked, onChange }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-700">
      <input
        type="checkbox"
        id={id}
        checked={checked}
        onChange={e => onChange(e.target.checked)}
        className="w-4 h-4 text-green-600 rounded border-gray-300 focus:ring-green-400"
      />
      {label}
    </label>
  )
}

// ── Initial form state ─────────────────────────────────────────────────────────

const INITIAL = {
  campus: { name: '', area_m2: '', students: '', staff: '', buildings: '' },
  energy: { annual_kwh: '', annual_cost_inr: '', monthly_kwh: Array(12).fill('') },
  water: { annual_m3: '', annual_cost_inr: '', monthly_m3: Array(12).fill('') },
  waste: { annual_kg: '', recycled_pct: '', composted_pct: '', landfill_pct: '', monthly_kg: Array(12).fill('') },
  budget_inr: '',
  existing_measures: {
    solar_installed: false,
    led_retrofit: false,
    hvac_optimization: false,
    smart_metering: false,
    water_leak_detection: false,
    composting: false,
    waste_segregation: false,
    rainwater_harvesting: false,
  },
  _showMonthlyEnergy: false,
  _showMonthlyWater: false,
  _showMonthlyWaste: false,
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function CampusData({ onDataActivated }) {
  const [form, setForm] = useState(INITIAL)
  const [submitting, setSubmitting] = useState(false)
  const [validationErrors, setValidationErrors] = useState([])
  const [successMsg, setSuccessMsg] = useState(null)
  const [activeMetrics, setActiveMetrics] = useState(null)

  // CSV upload
  const [csvFile, setCsvFile] = useState(null)
  const [csvUploading, setCsvUploading] = useState(false)
  const [csvError, setCsvError] = useState(null)
  const fileInputRef = useRef(null)

  // Demo reset
  const [resetting, setResetting] = useState(false)

  // Load existing user data on mount
  useEffect(() => {
    fetchCampusData().then(res => {
      if (res.mode === 'user' && res.data) {
        populateForm(res.data)
      }
    }).catch(() => {})
  }, [])

  const populateForm = (data) => {
    const e = data.energy || {}
    const w = data.water || {}
    const wst = data.waste || {}
    const c = data.campus || {}
    setForm(prev => ({
      ...prev,
      campus: {
        name: c.name || '',
        area_m2: c.area_m2 ?? '',
        students: c.students ?? '',
        staff: c.staff ?? '',
        buildings: c.buildings ?? '',
      },
      energy: {
        annual_kwh: e.annual_kwh ?? '',
        annual_cost_inr: e.annual_cost_inr ?? '',
        monthly_kwh: e.monthly_kwh ? e.monthly_kwh.map(String) : Array(12).fill(''),
      },
      water: {
        annual_m3: w.annual_m3 ?? '',
        annual_cost_inr: w.annual_cost_inr ?? '',
        monthly_m3: w.monthly_m3 ? w.monthly_m3.map(String) : Array(12).fill(''),
      },
      waste: {
        annual_kg: wst.annual_kg ?? '',
        recycled_pct: wst.recycled_pct ?? '',
        composted_pct: wst.composted_pct ?? '',
        landfill_pct: wst.landfill_pct ?? '',
        monthly_kg: wst.monthly_kg ? wst.monthly_kg.map(String) : Array(12).fill(''),
      },
      budget_inr: data.budget_inr ?? '',
      existing_measures: data.existing_measures || INITIAL.existing_measures,
      _showMonthlyEnergy: !!(e.monthly_kwh && e.monthly_kwh.length === 12),
      _showMonthlyWater: !!(w.monthly_m3 && w.monthly_m3.length === 12),
      _showMonthlyWaste: !!(wst.monthly_kg && wst.monthly_kg.length === 12),
    }))
  }

  // ── Field update helpers ───────────────────────────────────────────────────

  const setSection = (section, field, value) => {
    setForm(prev => ({ ...prev, [section]: { ...prev[section], [field]: value } }))
  }

  const setMeasure = (key, value) => {
    setForm(prev => ({
      ...prev,
      existing_measures: { ...prev.existing_measures, [key]: value },
    }))
  }

  // ── Waste pct live sum (computed before handleSubmit so closure can reference it) ─
  const wastePctSum = [form.waste.recycled_pct, form.waste.composted_pct, form.waste.landfill_pct]
    .map(v => { const n = parseFloat(v); return Number.isFinite(n) ? n : 0 })
    .reduce((a, b) => a + b, 0)
  const wastePctOk = Math.abs(wastePctSum - 100) <= 0.01

  // ── Prepare submission payload ─────────────────────────────────────────────

  const buildPayload = () => {
    // Convert a form value (string, number, null, '') to a float, or null if absent/NaN.
    const toFloat = (v) => {
      if (v === '' || v === null || v === undefined) return null
      const n = parseFloat(v)
      return Number.isFinite(n) ? n : null
    }
    // Convert a form value to an integer, or null if absent/NaN.
    const toInt = (v) => {
      if (v === '' || v === null || v === undefined) return null
      const n = parseInt(v, 10)
      return Number.isFinite(n) ? n : null
    }
    // Convert an array of form values to floats; return null if any are invalid.
    const monthlyToNums = (arr) => {
      const parsed = arr.map(v => parseFloat(v))
      return parsed.every(v => Number.isFinite(v) && v >= 0) ? parsed : null
    }

    const energyMonthly = form._showMonthlyEnergy ? monthlyToNums(form.energy.monthly_kwh) : null
    const waterMonthly  = form._showMonthlyWater  ? monthlyToNums(form.water.monthly_m3)  : null
    const wasteMonthly  = form._showMonthlyWaste  ? monthlyToNums(form.waste.monthly_kg)  : null

    return {
      campus: {
        name:      form.campus.name,
        area_m2:   toFloat(form.campus.area_m2),
        students:  toInt(form.campus.students),
        staff:     toInt(form.campus.staff),
        buildings: toInt(form.campus.buildings),
      },
      energy: {
        annual_kwh:      energyMonthly ? null : toFloat(form.energy.annual_kwh),
        annual_cost_inr: toFloat(form.energy.annual_cost_inr),
        monthly_kwh:     energyMonthly,
      },
      water: {
        annual_m3:       waterMonthly ? null : toFloat(form.water.annual_m3),
        annual_cost_inr: toFloat(form.water.annual_cost_inr),
        monthly_m3:      waterMonthly,
      },
      waste: {
        annual_kg:     wasteMonthly ? null : toFloat(form.waste.annual_kg),
        recycled_pct:  toFloat(form.waste.recycled_pct),
        composted_pct: toFloat(form.waste.composted_pct),
        landfill_pct:  toFloat(form.waste.landfill_pct),
        monthly_kg:    wasteMonthly,
      },
      budget_inr:        toFloat(form.budget_inr),
      existing_measures: form.existing_measures,
    }
  }

  // ── Submit ─────────────────────────────────────────────────────────────────

  const handleSubmit = async () => {
    setValidationErrors([])
    setSuccessMsg(null)

    // ── Frontend pre-validation ──────────────────────────────────────────────
    const preErrors = []
    if (!form.campus.name.trim()) {
      preErrors.push('Campus name is required.')
    }
    const hasMonthlyEnergy = form._showMonthlyEnergy
    const hasMonthlyWater  = form._showMonthlyWater
    const hasMonthlyWaste  = form._showMonthlyWaste
    if (!hasMonthlyEnergy && form.energy.annual_kwh === '') {
      preErrors.push('Annual electricity consumption is required (or provide monthly values).')
    }
    if (!hasMonthlyWater && form.water.annual_m3 === '') {
      preErrors.push('Annual water consumption is required (or provide monthly values).')
    }
    if (!hasMonthlyWaste && form.waste.annual_kg === '') {
      preErrors.push('Annual total waste is required (or provide monthly values).')
    }
    // Waste percentage validation — only if any pct field is filled
    const anyPct = form.waste.recycled_pct !== '' || form.waste.composted_pct !== '' || form.waste.landfill_pct !== ''
    if (anyPct && !wastePctOk) {
      preErrors.push(`Waste percentages must total 100% (currently ${wastePctSum.toFixed(1)}%).`)
    }
    if (preErrors.length > 0) {
      setValidationErrors(preErrors)
      return
    }

    setSubmitting(true)
    try {
      const payload = buildPayload()
      console.log('[CampusData] POST /api/campus-data →', JSON.stringify(payload, null, 2))
      const res = await postCampusData(payload)
      console.log('[CampusData] POST /api/campus-data ← 200', res)
      setActiveMetrics(res.metrics)
      setSuccessMsg(res.message)
      onDataActivated?.('user', res.metrics)
    } catch (err) {
      console.error('[CampusData] POST /api/campus-data failed:', err?.response?.status, err?.response?.data)
      const detail = err?.response?.data?.detail
      // Pydantic returns detail as an array of {loc, msg, type} objects.
      // Our custom validator returns detail as {errors: [...], message: "..."}.
      if (detail?.errors && Array.isArray(detail.errors)) {
        // Custom validator errors — already human-readable strings
        setValidationErrors(detail.errors)
      } else if (Array.isArray(detail)) {
        // Pydantic native validation errors — convert to readable messages
        const msgs = detail.map(e => {
          const loc = Array.isArray(e.loc) ? e.loc.slice(1).join('.') : String(e.loc ?? '')
          const msg = e.msg || e.message || String(e)
          return loc ? `${loc}: ${msg}` : msg
        })
        setValidationErrors(msgs.length > 0 ? msgs : ['Campus data could not be submitted. Check all required fields.'])
      } else if (typeof detail === 'string') {
        setValidationErrors([detail])
      } else {
        setValidationErrors(['Campus data could not be submitted. Please check all fields and try again.'])
      }
    } finally {
      setSubmitting(false)
    }
  }

  // ── Reset to demo ──────────────────────────────────────────────────────────

  const handleResetDemo = async () => {
    setResetting(true)
    setSuccessMsg(null)
    setValidationErrors([])
    try {
      console.log('[CampusData] DELETE /api/campus-data →')
      const res = await deleteCampusData()
      console.log('[CampusData] DELETE /api/campus-data ← 200', res)

      // Fetch the demo dataset so the form can be populated with real demo values
      let demoFormData = null
      try {
        demoFormData = await fetchDemoData()
        console.log('[CampusData] GET /api/campus-data/demo ←', demoFormData)
      } catch (fetchErr) {
        console.error('[CampusData] GET /api/campus-data/demo failed:', fetchErr)
        // DELETE succeeded but demo fetch failed — clear form and report the error
        setForm(INITIAL)
        setActiveMetrics(null)
        setValidationErrors([
          'Demo data restored on the server, but fetching demo form values failed. ' +
          'Please refresh the page.',
        ])
        onDataActivated?.('demo', res?.metrics ?? null)
        return
      }

      // Populate the form with the demo dataset values
      populateForm(demoFormData)

      // Use metrics returned by the DELETE response — no extra round-trip needed
      const demoMetrics = res?.metrics ?? null
      setActiveMetrics(null)
      setSuccessMsg('Demo data restored.')
      // Notify App.jsx so all dashboards refresh
      onDataActivated?.('demo', demoMetrics)
    } catch (err) {
      console.error('[CampusData] DELETE /api/campus-data failed:', err?.response?.status, err?.response?.data)
      setValidationErrors([
        'Unable to restore demo data. Please check that the backend is running.',
      ])
    } finally {
      setResetting(false)
    }
  }

  // ── CSV upload ─────────────────────────────────────────────────────────────

  const handleCSVUpload = async () => {
    if (!csvFile) return
    setCsvUploading(true)
    setCsvError(null)
    setValidationErrors([])
    setSuccessMsg(null)
    try {
      const res = await uploadCampusCSV(csvFile)
      setActiveMetrics(res.metrics)
      setSuccessMsg(res.message)
      // Reload form with the new data
      const data = await fetchCampusData()
      if (data.mode === 'user' && data.data) populateForm(data.data)
      setCsvFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      onDataActivated?.('user', res.metrics)
    } catch (err) {
      const detail = err?.response?.data?.detail
      if (detail?.errors) {
        setCsvError(detail.errors.join('\n'))
      } else {
        setCsvError('CSV upload failed. Check format and try again.')
      }
    } finally {
      setCsvUploading(false)
    }
  }

  const handleDownloadTemplate = async () => {
    const text = await fetchCSVTemplate()
    const blob = new Blob([text], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'campus_data_template.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-xl font-bold text-green-800">📋 Campus Data</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Enter your campus sustainability data. Once submitted, all dashboards and analytics use your data.
          </p>
        </div>
        <button
          onClick={handleResetDemo}
          disabled={resetting}
          className="ml-4 bg-amber-100 hover:bg-amber-200 disabled:opacity-60 text-amber-800 border border-amber-300 px-4 py-2 rounded-lg text-sm font-medium transition-colors whitespace-nowrap"
        >
          {resetting ? '⏳ Restoring demo data…' : '🔄 Use Demo Data'}
        </button>
      </div>

      {/* Privacy notice */}
      <div className="bg-blue-50 border border-blue-200 text-blue-800 text-xs rounded-lg px-4 py-2.5 mb-4">
        🔒 <strong>Privacy:</strong> Do not upload personally identifiable information or confidential records.
        Only sustainability and operational data (energy, water, waste). This prototype stores data locally on the server.
      </div>

      {/* Success / error banners */}
      {successMsg && (
        <div className="bg-green-50 border border-green-300 text-green-800 text-sm rounded-lg px-4 py-3 mb-4">
          ✅ {successMsg}
          {activeMetrics && (
            <div className="mt-2 grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: 'Annual Energy', value: `${fmtNum(activeMetrics.annual_energy_kwh, 0)} kWh` },
                { label: 'Annual Water', value: `${fmtNum(activeMetrics.annual_water_m3, 0)} m³` },
                { label: 'Annual Waste', value: `${fmtNum(activeMetrics.annual_waste_kg, 0)} kg` },
                { label: 'CO₂ Equivalent', value: `${fmtNum(activeMetrics.annual_co2_kg, 0)} kg` },
              ].map(m => (
                <div key={m.label} className="bg-white rounded-lg border border-green-200 p-2.5 text-center">
                  <div className="text-xs text-gray-500">{m.label}</div>
                  <div className="font-bold text-green-700 text-sm">{m.value}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {validationErrors.length > 0 && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-4">
          <div className="font-semibold mb-1">⚠ Please fix the following errors:</div>
          <ul className="list-disc list-inside space-y-0.5">
            {validationErrors.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        </div>
      )}

      {/* ── CSV Upload section ───────────────────────────────────────────── */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <SectionHeader
          title="📂 CSV Upload"
          subtitle="Upload a structured CSV file. Download the template first to see the required format."
        />
        <div className="flex flex-wrap gap-3 items-center">
          <button
            onClick={handleDownloadTemplate}
            className="text-xs bg-gray-100 hover:bg-green-100 text-gray-700 border border-gray-300 px-3 py-1.5 rounded-lg transition-colors"
          >
            ⬇ Download CSV Template
          </button>
          <div className="flex gap-2 items-center">
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={e => setCsvFile(e.target.files[0] || null)}
              className="text-xs text-gray-600 file:mr-2 file:py-1 file:px-3 file:rounded file:border file:border-gray-300 file:text-xs file:bg-gray-50 file:text-gray-700"
            />
            <button
              onClick={handleCSVUpload}
              disabled={!csvFile || csvUploading}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white px-4 py-1.5 rounded-lg text-xs font-medium transition-colors"
            >
              {csvUploading ? '⏳ Uploading…' : '⬆ Upload CSV'}
            </button>
          </div>
        </div>
        {csvError && (
          <pre className="mt-2 text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2 whitespace-pre-wrap">
            {csvError}
          </pre>
        )}
        <p className="text-xs text-gray-400 mt-2 italic">
          Supported format: metric, value, unit (one row per metric). Lines starting with # are comments.
        </p>
      </div>

      {/* ── Manual entry form ────────────────────────────────────────────── */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
        <SectionHeader
          title="Section A — Campus Information"
          subtitle="Descriptive fields about your campus."
        />
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <FormField label="Campus Name" required>
            <TextInput value={form.campus.name} onChange={v => setSection('campus', 'name', v)} placeholder="e.g. Green University" />
          </FormField>
          <FormField label="Campus Area (m²)" hint="Total campus area in square metres">
            <NumInput value={form.campus.area_m2} onChange={v => setSection('campus', 'area_m2', v)} placeholder="e.g. 50000" />
          </FormField>
          <FormField label="Number of Students">
            <NumInput value={form.campus.students} onChange={v => setSection('campus', 'students', v)} placeholder="e.g. 5000" step="1" />
          </FormField>
          <FormField label="Number of Staff">
            <NumInput value={form.campus.staff} onChange={v => setSection('campus', 'staff', v)} placeholder="e.g. 350" step="1" />
          </FormField>
          <FormField label="Number of Buildings">
            <NumInput value={form.campus.buildings} onChange={v => setSection('campus', 'buildings', v)} placeholder="e.g. 8" step="1" />
          </FormField>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
        <SectionHeader
          title="Section B — Energy"
          subtitle="Annual electricity data. Optionally provide monthly values for trend charts."
        />
        <div className="grid sm:grid-cols-2 gap-4">
          <FormField label="Annual Electricity Consumption (kWh)" required={!form._showMonthlyEnergy}>
            <NumInput
              value={form.energy.annual_kwh}
              onChange={v => setSection('energy', 'annual_kwh', v)}
              placeholder="e.g. 950000"
              disabled={form._showMonthlyEnergy}
            />
            {form._showMonthlyEnergy && <p className="text-xs text-blue-600 mt-0.5">Calculated from monthly values below.</p>}
          </FormField>
          <FormField label="Annual Electricity Cost (₹)">
            <NumInput value={form.energy.annual_cost_inr} onChange={v => setSection('energy', 'annual_cost_inr', v)} placeholder="e.g. 8200000" />
          </FormField>
        </div>
        <div className="mt-2">
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
            <input type="checkbox" checked={form._showMonthlyEnergy}
              onChange={e => setForm(f => ({ ...f, _showMonthlyEnergy: e.target.checked }))}
              className="rounded border-gray-300 text-green-600" />
            Provide monthly electricity data (optional — enables monthly trend charts)
          </label>
          {form._showMonthlyEnergy && (
            <MonthlyGrid
              values={form.energy.monthly_kwh}
              onChange={vals => setSection('energy', 'monthly_kwh', vals)}
              unit="kWh"
            />
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
        <SectionHeader
          title="Section C — Water"
          subtitle="Annual water consumption data."
        />
        <div className="grid sm:grid-cols-2 gap-4">
          <FormField label="Annual Water Consumption (m³)" required={!form._showMonthlyWater}>
            <NumInput
              value={form.water.annual_m3}
              onChange={v => setSection('water', 'annual_m3', v)}
              placeholder="e.g. 35000"
              disabled={form._showMonthlyWater}
            />
            {form._showMonthlyWater && <p className="text-xs text-blue-600 mt-0.5">Calculated from monthly values below.</p>}
          </FormField>
          <FormField label="Annual Water Cost (₹)">
            <NumInput value={form.water.annual_cost_inr} onChange={v => setSection('water', 'annual_cost_inr', v)} placeholder="e.g. 1200000" />
          </FormField>
        </div>
        <div className="mt-2">
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
            <input type="checkbox" checked={form._showMonthlyWater}
              onChange={e => setForm(f => ({ ...f, _showMonthlyWater: e.target.checked }))}
              className="rounded border-gray-300 text-green-600" />
            Provide monthly water data (optional)
          </label>
          {form._showMonthlyWater && (
            <MonthlyGrid
              values={form.water.monthly_m3}
              onChange={vals => setSection('water', 'monthly_m3', vals)}
              unit="m³"
            />
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
        <SectionHeader
          title="Section D — Waste"
          subtitle="Annual waste data. Percentages must total 100%."
        />
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <FormField label="Annual Total Waste (kg)" required={!form._showMonthlyWaste}>
            <NumInput
              value={form.waste.annual_kg}
              onChange={v => setSection('waste', 'annual_kg', v)}
              placeholder="e.g. 85000"
              disabled={form._showMonthlyWaste}
            />
            {form._showMonthlyWaste && <p className="text-xs text-blue-600 mt-0.5">Calculated from monthly.</p>}
          </FormField>
          <FormField label="Recycled (%)">
            <NumInput value={form.waste.recycled_pct} onChange={v => setSection('waste', 'recycled_pct', v)} placeholder="e.g. 30" />
          </FormField>
          <FormField label="Composted (%)">
            <NumInput value={form.waste.composted_pct} onChange={v => setSection('waste', 'composted_pct', v)} placeholder="e.g. 20" />
          </FormField>
          <FormField label="Landfill (%)">
            <NumInput value={form.waste.landfill_pct} onChange={v => setSection('waste', 'landfill_pct', v)} placeholder="e.g. 50" />
          </FormField>
        </div>
        {(form.waste.recycled_pct || form.waste.composted_pct || form.waste.landfill_pct) && (
          <p className={`text-xs mt-1 ${wastePctOk ? 'text-green-600' : 'text-red-500'}`}>
            {wastePctOk
              ? `✓ Percentages sum to 100% (${wastePctSum.toFixed(1)}%)`
              : `⚠ Percentages sum to ${wastePctSum.toFixed(1)}% — must equal 100%`}
          </p>
        )}
        <div className="mt-2">
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
            <input type="checkbox" checked={form._showMonthlyWaste}
              onChange={e => setForm(f => ({ ...f, _showMonthlyWaste: e.target.checked }))}
              className="rounded border-gray-300 text-green-600" />
            Provide monthly waste data (optional)
          </label>
          {form._showMonthlyWaste && (
            <MonthlyGrid
              values={form.waste.monthly_kg}
              onChange={vals => setSection('waste', 'monthly_kg', vals)}
              unit="kg"
            />
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
        <SectionHeader
          title="Section E — Sustainability Budget"
          subtitle="This becomes the default EcoSim-Opt budget."
        />
        <div className="max-w-xs">
          <FormField label="Available Sustainability Budget (₹)">
            <NumInput value={form.budget_inr} onChange={v => setForm(f => ({ ...f, budget_inr: v }))} placeholder="e.g. 500000" />
          </FormField>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <SectionHeader
          title="Section F — Existing Sustainability Measures"
          subtitle="Check measures already installed. EcoSim-Opt will take these into account."
        />
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {[
            { key: 'solar_installed', label: '☀️ Solar panels installed' },
            { key: 'led_retrofit', label: '💡 LED lighting retrofit done' },
            { key: 'hvac_optimization', label: '❄️ HVAC optimization done' },
            { key: 'smart_metering', label: '📊 Smart metering installed' },
            { key: 'water_leak_detection', label: '🔍 Water leak detection active' },
            { key: 'composting', label: '🌱 Composting in operation' },
            { key: 'waste_segregation', label: '♻️ Waste segregation active' },
            { key: 'rainwater_harvesting', label: '🌧 Rainwater harvesting active' },
          ].map(m => (
            <CheckboxRow
              key={m.key}
              id={m.key}
              label={m.label}
              checked={!!form.existing_measures[m.key]}
              onChange={v => setMeasure(m.key, v)}
            />
          ))}
        </div>
        <p className="text-xs text-gray-400 mt-3 italic">
          Note: EcoSim-Opt will still show these interventions in the catalogue.
          Installed measures are recorded for context only in this prototype.
        </p>
      </div>

      {/* Submit */}
      <div className="flex flex-wrap gap-3 items-center">
        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="bg-green-700 hover:bg-green-800 disabled:bg-gray-400 text-white px-8 py-2.5 rounded-lg font-semibold text-sm transition-colors"
        >
          {submitting ? '⏳ Analysing…' : '🔬 Analyse Campus'}
        </button>
        <button
          onClick={handleResetDemo}
          disabled={resetting}
          className="bg-amber-100 hover:bg-amber-200 text-amber-800 border border-amber-300 px-5 py-2.5 rounded-lg text-sm font-medium transition-colors"
        >
          {resetting ? '…' : '🔄 Use Demo Data'}
        </button>
        <span className="text-xs text-gray-400 italic">
          Your data is stored locally on the server for this session.
          Do not enter confidential or personal information.
        </span>
      </div>
    </div>
  )
}
