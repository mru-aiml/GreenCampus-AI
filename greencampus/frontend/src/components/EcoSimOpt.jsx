import { useState, useEffect } from 'react'
import { fetchInterventions, postSimulate, postOptimize, postWhatIf } from '../api.js'
import { fmtINR } from '../utils/formatters.js'
import SimulationResult from './SimulationResult.jsx'

const CATEGORY_COLORS = {
  energy:     'bg-yellow-100 text-yellow-700 border-yellow-300',
  water:      'bg-blue-100 text-blue-700 border-blue-300',
  waste:      'bg-orange-100 text-orange-700 border-orange-300',
  monitoring: 'bg-purple-100 text-purple-700 border-purple-300',
}

function InterventionCard({ iv, selected, onToggle }) {
  return (
    <div
      onClick={() => onToggle(iv.id)}
      className={`border-2 rounded-xl p-4 cursor-pointer transition-all ${
        selected ? 'border-green-500 bg-green-50' : 'border-gray-200 bg-white hover:border-green-300'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-semibold text-gray-800 text-sm">{iv.name}</div>
          <div className="text-xs text-gray-500 mt-0.5">{iv.description}</div>
        </div>
        <div className={`w-5 h-5 rounded-full border-2 flex-shrink-0 flex items-center justify-center mt-0.5 ${
          selected ? 'bg-green-500 border-green-500' : 'border-gray-300'
        }`}>
          {selected && <span className="text-white text-xs">✓</span>}
        </div>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-1 text-xs">
        <span className="text-gray-500">Cost: <strong className="text-gray-700">{fmtINR(iv.cost_inr)}</strong></span>
        <span className="text-gray-500">Payback: <strong className="text-gray-700">{iv.payback_years} yr</strong></span>
        {iv.energy_saving_pct > 0 && <span className="text-yellow-700">⚡ Energy -{iv.energy_saving_pct}%</span>}
        {iv.water_saving_pct > 0 && <span className="text-blue-700">💧 Water -{iv.water_saving_pct}%</span>}
        {iv.waste_reduction_pct > 0 && <span className="text-orange-700">♻️ Waste -{iv.waste_reduction_pct}%</span>}
        <span className="text-green-700">₹ Save {fmtINR(iv.annual_savings_inr)}/yr</span>
      </div>
      <div className="mt-2">
        <span className={`text-xs px-2 py-0.5 border rounded-full ${CATEGORY_COLORS[iv.category] || 'bg-gray-100'}`}>
          {iv.category}
        </span>
        <span className="ml-2 text-xs text-gray-400 italic">{iv.note}</span>
      </div>
    </div>
  )
}

export default function EcoSimOpt({ metrics, onSimResult, dataMode }) {
  const isUserMode = dataMode === 'user'
  const [mode, setMode] = useState('optimize')       // 'manual' | 'optimize'
  const [catalog, setCatalog] = useState([])
  const [selected, setSelected] = useState([])
  // Default budget from metrics if user mode, else 500000
  const defaultBudget = (metrics?.budget_inr) ? String(metrics.budget_inr) : '500000'
  const [budget, setBudget] = useState(defaultBudget)
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const [whatIfQuery, setWhatIfQuery] = useState('')
  const [whatIfResult, setWhatIfResult] = useState(null)
  const [whatIfLoading, setWhatIfLoading] = useState(false)

  useEffect(() => {
    fetchInterventions().then(setCatalog).catch(console.error)
  }, [])

  const toggleIntervention = (id) => {
    setSelected(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  const totalSelected = catalog
    .filter(iv => selected.includes(iv.id))
    .reduce((s, iv) => s + iv.cost_inr, 0)

  const budgetNum = parseFloat(budget) || 0
  const budgetExceeded = mode === 'manual' && totalSelected > budgetNum

  const handleRun = async () => {
    setError(null)
    setResults(null)
    setLoading(true)
    try {
      if (mode === 'manual') {
        if (selected.length === 0) { setError('Select at least one intervention.'); setLoading(false); return }
        const data = await postSimulate({ intervention_ids: selected, budget_inr: budgetNum })
        setResults([data])
        onSimResult?.(data)
      } else {
        const data = await postOptimize({ budget_inr: budgetNum })
        const portfolios = data.portfolios || []
        setResults(portfolios)
        if (portfolios.length > 0) onSimResult?.(portfolios[0])
      }
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Simulation failed')
    } finally {
      setLoading(false)
    }
  }

  const handleWhatIf = async () => {
    if (!whatIfQuery.trim()) return
    setWhatIfLoading(true)
    setWhatIfResult(null)
    try {
      const data = await postWhatIf({
        query: whatIfQuery,
        current_metrics: metrics,
      })
      setWhatIfResult(data)
    } catch (err) {
      setWhatIfResult({ error: err.message })
    } finally {
      setWhatIfLoading(false)
    }
  }

  return (
    <div>
      <div className="flex items-start justify-between mb-1 flex-wrap gap-2">
        <div>
          <h2 className="text-xl font-bold text-green-800">🔬 EcoSim-Opt</h2>
          <p className="text-sm text-gray-500">Intervention simulator and budget optimizer.</p>
        </div>
        <span className={`text-xs px-3 py-1 rounded-full border font-medium ${
          isUserMode
            ? 'bg-green-100 border-green-300 text-green-800'
            : 'bg-amber-100 border-amber-300 text-amber-800'
        }`}>
          {isUserMode ? '✅ User Campus Data' : '⚠️ Demo Synthetic Data'}
        </span>
      </div>
      <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-1.5 mb-4">
        ⚠️ Prototype assumptions. Estimated results based on model assumptions. Actual results should be validated using campus measurements.
      </p>

      {/* Mode toggle */}
      <div className="flex gap-2 mb-5">
        {[
          { id: 'optimize', label: '🎯 Budget Optimization', desc: 'Enter budget → system finds best portfolios' },
          { id: 'manual',   label: '🛠 Manual Simulation',  desc: 'Pick interventions → compute combined impact' },
        ].map(m => (
          <button
            key={m.id}
            onClick={() => { setMode(m.id); setResults(null); setError(null) }}
            className={`flex-1 border-2 rounded-xl p-3 text-left transition-all ${
              mode === m.id ? 'border-green-500 bg-green-50' : 'border-gray-200 bg-white hover:border-green-300'
            }`}
          >
            <div className="font-semibold text-sm text-gray-800">{m.label}</div>
            <div className="text-xs text-gray-500 mt-0.5">{m.desc}</div>
          </button>
        ))}
      </div>

      {/* Budget input */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 mb-4">
        <label className="block text-sm font-semibold text-gray-700 mb-2">
          💰 Budget (₹)
        </label>
        <div className="flex gap-2 items-center">
          <input
            type="number"
            value={budget}
            onChange={e => setBudget(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-48 focus:outline-none focus:ring-2 focus:ring-green-400"
            placeholder="e.g. 500000"
            min="0"
          />
          <span className="text-sm text-gray-500">{fmtINR(budgetNum)}</span>
          <div className="flex gap-1 ml-auto">
            {[100000, 250000, 500000, 1000000].map(v => (
              <button key={v} onClick={() => setBudget(String(v))}
                className="text-xs bg-gray-100 hover:bg-green-100 px-2 py-1 rounded text-gray-600">
                {fmtINR(v)}
              </button>
            ))}
          </div>
        </div>
        {budgetExceeded && (
          <p className="text-xs text-red-500 mt-1">
            ⚠ Selected interventions cost {fmtINR(totalSelected)}, which exceeds the budget.
          </p>
        )}
      </div>

      {/* Intervention catalogue (manual mode) */}
      {mode === 'manual' && (
        <div className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-gray-700">
              Select Interventions ({selected.length} selected · {fmtINR(totalSelected)} total)
            </h3>
            <button onClick={() => setSelected([])} className="text-xs text-red-500 hover:underline">Clear all</button>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {catalog.map(iv => (
              <InterventionCard key={iv.id} iv={iv} selected={selected.includes(iv.id)} onToggle={toggleIntervention} />
            ))}
          </div>
        </div>
      )}

      {/* Run button */}
      <button
        onClick={handleRun}
        disabled={loading}
        className="bg-green-700 hover:bg-green-800 disabled:bg-gray-400 text-white px-8 py-2.5 rounded-lg font-semibold text-sm transition-colors mb-4"
      >
        {loading ? '⏳ Running…' : mode === 'optimize' ? '🎯 Optimize Portfolio' : '▶ Run Simulation'}
      </button>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg p-3 mb-4">
          ⚠ {error}
        </div>
      )}

      {/* Results */}
      {results && results.length === 0 && (
        <div className="bg-yellow-50 border border-yellow-200 text-yellow-700 text-sm rounded-lg p-4 mb-4">
          No feasible portfolio found within this budget. Try increasing the budget.
        </div>
      )}
      {results && results.map((r, i) => (
        <SimulationResult key={i} result={r} rank={results.length > 1 ? i + 1 : null} />
      ))}

      {/* What-If */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 mt-6">
        <h3 className="font-semibold text-gray-700 mb-1">💬 What-If Scenario</h3>
        <p className="text-xs text-gray-400 mb-3">
          Examples: "What if AC energy consumption is reduced by 15%?" · "What if the budget is ₹5 lakh?" · "What if we install rooftop solar?"
        </p>
        <div className="flex gap-2">
          <input
            type="text"
            value={whatIfQuery}
            onChange={e => setWhatIfQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleWhatIf()}
            placeholder="Ask a what-if question…"
            className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
          />
          <button
            onClick={handleWhatIf}
            disabled={whatIfLoading}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            {whatIfLoading ? '…' : 'Analyse'}
          </button>
        </div>
        {whatIfResult && (
          <div className="mt-3 bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800">
            {whatIfResult.error ? (
              <span className="text-red-600">{whatIfResult.error}</span>
            ) : (
              <>
                <p><strong>Scenario:</strong> {whatIfResult.parsed_scenario?.type?.replace(/_/g, ' ')} (confidence: {whatIfResult.parsed_scenario?.parse_confidence})</p>
                <p className="mt-1">{whatIfResult.explanation}</p>
                {whatIfResult.disclaimer && (
                  <p className="mt-1 text-xs text-blue-500 italic">{whatIfResult.disclaimer}</p>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
