import { useState, useEffect } from 'react'
import MetricsSummary from './components/MetricsSummary.jsx'
import EnergyDashboard from './components/EnergyDashboard.jsx'
import WaterDashboard from './components/WaterDashboard.jsx'
import WasteDashboard from './components/WasteDashboard.jsx'
import CO2Dashboard from './components/CO2Dashboard.jsx'
import EcoSimOpt from './components/EcoSimOpt.jsx'
import AIAssistant from './components/AIAssistant.jsx'
import ResponsibleAI from './components/ResponsibleAI.jsx'
import CampusData from './components/CampusData.jsx'
import { fetchMetrics, fetchCampusDataStatus } from './api.js'

const TABS = [
  { id: 'overview',     label: '🏠 Overview' },
  { id: 'campusdata',   label: '📋 Campus Data' },
  { id: 'energy',       label: '⚡ Energy' },
  { id: 'water',        label: '💧 Water' },
  { id: 'waste',        label: '♻️ Waste' },
  { id: 'co2',          label: '🌿 CO₂' },
  { id: 'ecosimopt',    label: '🔬 EcoSim-Opt' },
  { id: 'assistant',    label: '🤖 AI Assistant' },
  { id: 'responsible',  label: '⚖️ Responsible AI' },
]

export default function App() {
  const [tab, setTab] = useState('overview')
  const [metrics, setMetrics] = useState(null)
  const [lastSim, setLastSim] = useState(null)
  const [dataMode, setDataMode] = useState('demo')  // 'demo' | 'user'
  const [dataLabel, setDataLabel] = useState('Demo Synthetic Data')
  // dataVersion increments each time the active dataset changes.
  // Dashboard components include it in their useEffect dependency array so they
  // re-fetch even when dataMode stays the same (e.g., user re-submits with new values).
  const [dataVersion, setDataVersion] = useState(0)

  const refreshMetrics = () => {
    fetchMetrics()
      .then(m => {
        setMetrics(m)
        setDataMode(m.data_source || 'demo')
        setDataLabel(m.data_source_label || 'Demo Synthetic Data')
      })
      .catch(console.error)
  }

  useEffect(() => {
    refreshMetrics()
    // Also load data source status
    fetchCampusDataStatus()
      .then(s => {
        setDataMode(s.mode)
        setDataLabel(s.label)
      })
      .catch(() => {})
  }, [])

  const handleDataActivated = (mode, newMetrics) => {
    if (newMetrics) {
      // Metrics provided directly from the API response — apply immediately,
      // no extra round-trip needed.  Works for both user activation and demo restore.
      setMetrics(newMetrics)
      setDataMode(mode)
      setDataLabel(
        newMetrics.data_source_label ||
        (mode === 'user' ? 'User Campus Data' : 'Demo Synthetic Data')
      )
    } else {
      // Fallback: newMetrics not available — re-fetch from backend.
      setDataMode(mode)
      refreshMetrics()
    }
    // Bump version so mounted dashboard components (Energy/Water/Waste) re-fetch
    // their raw data from the backend, even if dataMode itself hasn't changed.
    setDataVersion(v => v + 1)
  }

  const isUserMode = dataMode === 'user'

  // Badge colours
  const badgeClass = isUserMode
    ? 'bg-green-200 text-green-900'
    : 'bg-yellow-400 text-yellow-900'

  return (
    <div className="min-h-screen bg-green-50">
      {/* Header */}
      <header className="bg-green-700 text-white px-6 py-4 shadow-md">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">🌱 GreenCampus AI</h1>
            <p className="text-green-200 text-xs mt-0.5">
              Campus Sustainability Decision-Support Platform
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right hidden sm:block">
              <p className="text-green-200 text-xs">Data Source</p>
              <p className="text-white text-xs font-semibold">{dataLabel}</p>
            </div>
            <span className={`text-xs font-semibold px-3 py-1 rounded-full ${badgeClass}`}>
              {isUserMode ? 'User Campus Data' : 'Prototype · Synthetic Data'}
            </span>
          </div>
        </div>
      </header>

      {/* Nav */}
      <nav className="bg-white border-b border-green-200 shadow-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 flex overflow-x-auto gap-1 py-1">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-3 py-2 text-sm font-medium rounded whitespace-nowrap transition-colors ${
                tab === t.id
                  ? 'bg-green-700 text-white'
                  : 'text-gray-600 hover:bg-green-50'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </nav>

      {/* Data source banner */}
      {isUserMode ? (
        <div className="bg-green-50 border-b border-green-300 text-green-800 text-xs text-center py-1.5">
          ✅ Analysis based on <strong>User Campus Data</strong> · {dataLabel} ·{' '}
          <button
            onClick={() => setTab('campusdata')}
            className="underline hover:no-underline"
          >
            Edit data
          </button>
        </div>
      ) : (
        <div className="bg-amber-50 border-b border-amber-200 text-amber-800 text-xs text-center py-1.5">
          ⚠️ Using <strong>Demo Synthetic Data</strong>. All figures are illustrative only.{' '}
          <button
            onClick={() => setTab('campusdata')}
            className="underline hover:no-underline"
          >
            Enter your campus data →
          </button>
        </div>
      )}

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        {tab === 'overview'    && <MetricsSummary metrics={metrics} onNavigate={setTab} dataMode={dataMode} dataLabel={dataLabel} />}
        {tab === 'campusdata'  && <CampusData onDataActivated={handleDataActivated} />}
        {tab === 'energy'      && <EnergyDashboard dataMode={dataMode} dataVersion={dataVersion} />}
        {tab === 'water'       && <WaterDashboard dataMode={dataMode} dataVersion={dataVersion} />}
        {tab === 'waste'       && <WasteDashboard dataMode={dataMode} dataVersion={dataVersion} />}
        {tab === 'co2'         && <CO2Dashboard metrics={metrics} dataMode={dataMode} />}
        {tab === 'ecosimopt'   && <EcoSimOpt metrics={metrics} onSimResult={setLastSim} dataMode={dataMode} />}
        {tab === 'assistant'   && <AIAssistant metrics={metrics} lastSim={lastSim} dataMode={dataMode} />}
        {tab === 'responsible' && <ResponsibleAI />}
      </main>
    </div>
  )
}
