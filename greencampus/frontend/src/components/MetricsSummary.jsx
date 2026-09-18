import { fmtINR, fmtNum, fmtPct } from '../utils/formatters.js'

const KPI_CONFIG = [
  { key: 'annual_energy_kwh',  label: 'Annual Energy',   unit: 'kWh', icon: '⚡', color: 'bg-yellow-50 border-yellow-300', tab: 'energy' },
  { key: 'annual_water_m3',    label: 'Annual Water',    unit: 'm³',  icon: '💧', color: 'bg-blue-50 border-blue-300',   tab: 'water' },
  { key: 'annual_waste_kg',    label: 'Annual Waste',    unit: 'kg',  icon: '♻️', color: 'bg-orange-50 border-orange-300', tab: 'waste' },
  { key: 'annual_co2_kg',      label: 'CO₂ Equivalent',  unit: 'kg',  icon: '🌿', color: 'bg-green-50 border-green-300', tab: 'co2'   },
  { key: 'recycling_rate_pct', label: 'Recycling Rate',  unit: '%',   icon: '🔄', color: 'bg-teal-50 border-teal-300',   tab: 'waste' },
]

function KPICard({ config, value, onNavigate }) {
  const display = config.unit === '%'
    ? fmtPct(value)
    : config.unit === 'kg' && value > 999
    ? `${fmtNum(value, 0)} ${config.unit}`
    : `${fmtNum(value, 0)} ${config.unit}`

  return (
    <button
      onClick={() => onNavigate(config.tab)}
      className={`border-2 rounded-xl p-5 text-left hover:shadow-md transition-shadow w-full ${config.color}`}
    >
      <div className="text-2xl mb-1">{config.icon}</div>
      <div className="text-xs text-gray-500 uppercase tracking-wide">{config.label}</div>
      <div className="text-2xl font-bold text-gray-800 mt-1">{display}</div>
      <div className="text-xs text-green-600 mt-2">→ View details</div>
    </button>
  )
}

export default function MetricsSummary({ metrics, onNavigate, dataMode, dataLabel }) {
  const isUserMode = dataMode === 'user'

  if (!metrics) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {KPI_CONFIG.map(c => (
          <div key={c.key} className={`border-2 rounded-xl p-5 animate-pulse ${c.color}`}>
            <div className="h-16 bg-gray-200 rounded" />
          </div>
        ))}
      </div>
    )
  }

  return (
    <div>
      <div className="mb-4 flex items-start justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-xl font-bold text-green-800">Campus Overview</h2>
          <p className="text-sm text-gray-500 mt-1">
            Annual sustainability metrics across all campus buildings.
            Click any card to explore details.
          </p>
        </div>
        {/* Data source badge */}
        <div className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border font-medium ${
          isUserMode
            ? 'bg-green-100 border-green-300 text-green-800'
            : 'bg-amber-100 border-amber-300 text-amber-800'
        }`}>
          {isUserMode ? '✅' : '⚠️'}
          {dataLabel || (isUserMode ? 'User Campus Data' : 'Demo Synthetic Data')}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        {KPI_CONFIG.map(c => (
          <KPICard key={c.key} config={c} value={metrics[c.key]} onNavigate={onNavigate} />
        ))}
      </div>

      {/* Completeness notice for user data */}
      {isUserMode && metrics.completeness && (
        <div className="mb-4 bg-blue-50 border border-blue-200 rounded-xl p-4">
          <div className="text-sm font-semibold text-blue-800 mb-2">📊 Dataset Completeness</div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(metrics.completeness).map(([k, v]) => (
              <span
                key={k}
                className={`text-xs px-2 py-0.5 rounded-full border ${
                  v ? 'bg-green-100 border-green-300 text-green-700' : 'bg-gray-100 border-gray-300 text-gray-500'
                }`}
              >
                {v ? '✓' : '—'} {k.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-green-200 p-5">
        <h3 className="font-semibold text-green-800 mb-3">Quick Actions</h3>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => onNavigate('ecosimopt')}
            className="bg-green-700 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-green-800 transition-colors"
          >
            🔬 Run EcoSim-Opt
          </button>
          <button
            onClick={() => onNavigate('assistant')}
            className="bg-blue-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
          >
            🤖 Ask AI Assistant
          </button>
          {!isUserMode && (
            <button
              onClick={() => onNavigate('campusdata')}
              className="bg-emerald-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-emerald-700 transition-colors"
            >
              📋 Enter Campus Data
            </button>
          )}
          <button
            onClick={() => onNavigate('responsible')}
            className="bg-gray-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-gray-700 transition-colors"
          >
            ⚖️ Responsible AI
          </button>
        </div>
      </div>

      <p className="text-xs text-gray-400 mt-4 italic">{metrics.note}</p>
    </div>
  )
}
