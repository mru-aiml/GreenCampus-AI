import { useState } from 'react'
import { fmtINR, fmtPct, fmtNum } from '../utils/formatters.js'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
  ResponsiveContainer, RadarChart, Radar, PolarGrid, PolarAngleAxis
} from 'recharts'

function Badge({ text, color = 'bg-green-100 text-green-800' }) {
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${color}`}>{text}</span>
}

function ScoreBar({ label, value, weight }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-20 text-gray-500 capitalize">{label}</span>
      <div className="flex-1 bg-gray-100 rounded-full h-2">
        <div
          className="bg-green-500 h-2 rounded-full transition-all"
          style={{ width: `${Math.min(value * 100, 100)}%` }}
        />
      </div>
      <span className="w-10 text-right text-gray-700 font-mono">{(value * 100).toFixed(0)}%</span>
      {weight != null && (
        <span className="w-10 text-right text-gray-400 font-mono text-xs">×{(weight * 100).toFixed(0)}%</span>
      )}
    </div>
  )
}

// Impact comparison across all 5 dimensions for each selected intervention
function ImpactComparison({ interventions }) {
  if (!interventions || interventions.length === 0) return null
  const data = interventions.map(iv => ({
    name: iv.name.length > 16 ? iv.name.slice(0, 14) + '…' : iv.name,
    'Energy %':  iv.energy_saving_pct,
    'Water %':   iv.water_saving_pct,
    'Waste %':   iv.waste_reduction_pct,
    'CO₂ kg/yr': Math.round(iv.co2_reduction_kg_year / 1000),  // display in tonnes for readability
    'Savings ₹L': Math.round(iv.annual_savings_inr / 100000),
  }))
  return (
    <div className="mb-4">
      <h4 className="text-xs font-semibold text-gray-600 mb-1 uppercase tracking-wide">
        Impact Comparison per Intervention
      </h4>
      <p className="text-xs text-gray-400 mb-2">
        CO₂ in tonnes/yr · Financial savings in ₹ lakh/yr · all other values in %
      </p>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} barCategoryGap="25%">
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" tick={{ fontSize: 9 }} />
          <YAxis tick={{ fontSize: 9 }} />
          <Tooltip />
          <Legend iconSize={9} wrapperStyle={{ fontSize: 10 }} />
          <Bar dataKey="Energy %"   fill="#eab308" />
          <Bar dataKey="Water %"    fill="#3b82f6" />
          <Bar dataKey="Waste %"    fill="#f97316" />
          <Bar dataKey="CO₂ kg/yr"  fill="#22c55e" />
          <Bar dataKey="Savings ₹L" fill="#8b5cf6" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

// Objective formula panel — shown collapsed by default
function ObjectiveFormulaPanel({ formula }) {
  const [open, setOpen] = useState(false)
  if (!formula || !formula.weights) return null
  const w = formula.weights
  const bounds = formula.normalisation_bounds || {}
  return (
    <div className="mb-4 border border-gray-200 rounded-lg">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs font-semibold text-gray-600 hover:bg-gray-50 rounded-lg"
      >
        <span>📐 Objective Formula &amp; Weights</span>
        <span>{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="px-3 pb-3 text-xs text-gray-600">
          <p className="font-mono bg-gray-50 rounded p-2 mb-2 text-xs">
            composite = Σ w<sub>k</sub> × min(metric<sub>k</sub> / max<sub>k</sub>, 1)
          </p>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-gray-400 border-b">
                <th className="pb-1">Dimension</th>
                <th className="pb-1">Weight</th>
                <th className="pb-1">Upper bound</th>
                <th className="pb-1">Unit</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(w).map(([dim, wt]) => (
                <tr key={dim} className="border-b last:border-0">
                  <td className="py-1 capitalize font-medium">{dim}</td>
                  <td className="py-1 font-mono">{(wt * 100).toFixed(0)}%</td>
                  <td className="py-1 font-mono">{bounds[dim]?.max ?? '—'}</td>
                  <td className="py-1 text-gray-400">{bounds[dim]?.unit ?? ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-gray-400 italic">
            Savings combination: projected = baseline × Π (1 − r<sub>i</sub>) — compounded, not additive.
          </p>
        </div>
      )}
    </div>
  )
}

export default function SimulationResult({ result, rank }) {
  if (!result) return null

  const ivs          = result.interventions_applied || []
  const interactions = result.interactions_applied  || []
  const breakdown    = result.score_breakdown       || {}
  const formula      = result.objective_formula     || {}
  const weights      = formula.weights              || {}

  const comparisonData = [
    { name: 'Energy', baseline: 100, projected: 100 - result.energy_saving_pct },
    { name: 'Water',  baseline: 100, projected: 100 - result.water_saving_pct  },
    { name: 'Waste',  baseline: 100, projected: 100 - result.waste_reduction_pct },
    { name: 'CO₂',   baseline: 100, projected: 100 - result.co2_reduction_pct },
  ]

  const isOptimized = result.mode === 'optimized'

  return (
    <div className="bg-white rounded-xl border border-green-200 p-5 mb-4">
      {/* Header badges */}
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        {rank && <span className="text-lg font-bold text-green-700">#{rank}</span>}
        {isOptimized && <Badge text={`Score: ${result.score?.toFixed(4)}`} />}
        <Badge text={result.mode === 'manual' ? 'Manual' : 'Optimized'} color="bg-blue-100 text-blue-800" />
        {result.remaining_budget_inr < 0 && (
          <Badge text="⚠ Budget Exceeded" color="bg-red-100 text-red-700" />
        )}
        <Badge text="⚙️ DEMO MODE" color="bg-gray-100 text-gray-500" />
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        {[
          { label: 'Total Cost',        val: fmtINR(result.total_cost_inr),        sub: `Remaining: ${fmtINR(result.remaining_budget_inr)}` },
          { label: 'Annual Savings',    val: fmtINR(result.total_annual_savings_inr), sub: '' },
          { label: 'Payback Period',    val: isFinite(result.avg_payback_years) ? `${result.avg_payback_years} yr` : '∞', sub: '' },
          { label: 'CO₂ Reduction',     val: fmtPct(result.co2_reduction_pct),    sub: `${fmtNum(result.projected_co2_kg, 0)} kg projected` },
        ].map(k => (
          <div key={k.label} className="bg-green-50 rounded-lg p-3">
            <div className="text-xs text-gray-500">{k.label}</div>
            <div className="text-xl font-bold text-gray-800">{k.val}</div>
            {k.sub && <div className="text-xs text-gray-400">{k.sub}</div>}
          </div>
        ))}
      </div>

      {/* Savings comparison */}
      <div className="grid md:grid-cols-2 gap-4 mb-4">
        <div>
          <h4 className="text-xs font-semibold text-gray-600 mb-2 uppercase tracking-wide">
            Projected vs Baseline (%)
          </h4>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={comparisonData} barSize={18}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} />
              <YAxis domain={[0, 110]} tick={{ fontSize: 10 }} />
              <Tooltip formatter={v => `${v.toFixed(1)}%`} />
              <Legend iconSize={10} />
              <Bar dataKey="baseline"  fill="#d1d5db" name="Baseline" />
              <Bar dataKey="projected" fill="#22c55e" name="Projected" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {isOptimized && Object.keys(breakdown).length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-gray-600 mb-2 uppercase tracking-wide">
              Objective Score Breakdown
              <span className="ml-1 text-gray-400 font-normal normal-case">
                (normalised × weight → contribution)
              </span>
            </h4>
            <div className="space-y-2 pt-2">
              {Object.entries(breakdown).map(([k, v]) => (
                <ScoreBar key={k} label={k} value={v} weight={weights[k]} />
              ))}
              <div className="flex items-center gap-2 text-xs pt-1 border-t">
                <span className="w-20 font-semibold text-gray-700">Composite</span>
                <div className="flex-1 bg-gray-100 rounded-full h-2">
                  <div className="bg-green-600 h-2 rounded-full" style={{ width: `${result.score * 100}%` }} />
                </div>
                <span className="w-10 text-right font-bold text-green-700">{(result.score * 100).toFixed(1)}%</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Impact comparison across interventions */}
      <ImpactComparison interventions={ivs} />

      {/* Objective formula (collapsible) */}
      {isOptimized && <ObjectiveFormulaPanel formula={formula} />}

      {/* Interventions list */}
      <div className="mb-4">
        <h4 className="text-xs font-semibold text-gray-600 mb-2 uppercase tracking-wide">
          Interventions Applied ({ivs.length})
        </h4>
        <div className="space-y-1">
          {ivs.map(iv => (
            <div key={iv.id} className="flex items-center justify-between text-xs bg-gray-50 rounded px-3 py-2">
              <span className="font-medium text-gray-700">{iv.name}</span>
              <div className="flex gap-3 text-gray-500">
                <span>{fmtINR(iv.cost_inr)}</span>
                {iv.energy_saving_pct > 0 && <span>⚡ -{iv.energy_saving_pct}%</span>}
                {iv.water_saving_pct > 0 && <span>💧 -{iv.water_saving_pct}%</span>}
                {iv.waste_reduction_pct > 0 && <span>♻️ -{iv.waste_reduction_pct}%</span>}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Interactions */}
      {interactions.length > 0 && (
        <div className="mb-4 bg-blue-50 rounded-lg p-3">
          <h4 className="text-xs font-semibold text-blue-700 mb-1">🔗 Synergy Effects Applied</h4>
          {interactions.map((l, i) => <p key={i} className="text-xs text-blue-600">{l}</p>)}
        </div>
      )}

      {/* AI Explanation */}
      {result.explanation && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-3">
          <h4 className="text-xs font-semibold text-green-700 mb-2">🤖 AI Explanation</h4>
          <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
            {result.explanation}
          </div>
        </div>
      )}

      {/* Disclaimer */}
      <p className="text-xs text-gray-400 italic">{result.disclaimer}</p>
    </div>
  )
}
