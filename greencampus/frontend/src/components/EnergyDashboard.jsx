import { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, LineChart, Line
} from 'recharts'
import { fetchEnergy } from '../api.js'
import { MONTHS, fmtNum } from '../utils/formatters.js'

export default function EnergyDashboard({ dataMode, dataVersion }) {
  const [data, setData] = useState(null)
  const isUserMode = dataMode === 'user'

  // Re-fetch whenever the active dataset changes (mode switch or new user submission).
  // dataVersion ensures re-fetch even if dataMode stays the same (e.g., user re-submits).
  useEffect(() => { fetchEnergy().then(setData).catch(console.error) }, [dataMode, dataVersion])

  if (!data) return <div className="text-gray-400 text-sm p-4">Loading energy data…</div>

  const hasBuildings = Array.isArray(data.buildings) && data.buildings.length > 0
  const hasMonthly = data.has_monthly !== false && hasBuildings

  const monthlyTotal = hasMonthly
    ? MONTHS.map((m, i) => ({
        month: m,
        total: data.buildings.reduce((s, b) => s + (b.monthly?.[i] ?? 0), 0),
      }))
    : []

  const buildingTotals = hasBuildings
    ? data.buildings.map(b => ({
        name: b.name,
        annual: (b.monthly || []).reduce((s, v) => s + v, 0),
      }))
    : []

  return (
    <div>
      <div className="flex items-start justify-between mb-1 flex-wrap gap-2">
        <h2 className="text-xl font-bold text-green-800">⚡ Energy Consumption</h2>
        <span className={`text-xs px-3 py-1 rounded-full border font-medium ${
          isUserMode
            ? 'bg-green-100 border-green-300 text-green-800'
            : 'bg-amber-100 border-amber-300 text-amber-800'
        }`}>
          {isUserMode ? '✅ User Campus Data' : '⚠️ Demo Synthetic Data'}
        </span>
      </div>
      <p className="text-xs text-gray-500 mb-4 italic">{data.note}</p>

      {/* Annual total if no monthly breakdown */}
      {isUserMode && !hasMonthly && data.annual_kwh && (
        <div className="mb-4 bg-blue-50 border border-blue-200 rounded-xl p-4">
          <div className="text-sm font-semibold text-blue-800">Annual Electricity Consumption</div>
          <div className="text-2xl font-bold text-blue-700 mt-1">{fmtNum(data.annual_kwh, 0)} kWh</div>
          <div className="text-xs text-blue-500 mt-1 italic">
            Monthly trend data unavailable — only annual total was provided.
          </div>
        </div>
      )}

      {hasMonthly ? (
        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h3 className="font-semibold text-gray-700 mb-3">Monthly Total (kWh)</h3>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={monthlyTotal}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={v => `${(v/1000).toFixed(0)}k`} tick={{ fontSize: 11 }} />
                <Tooltip formatter={v => [`${fmtNum(v)} kWh`, 'Total']} />
                <Line type="monotone" dataKey="total" stroke="#16a34a" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h3 className="font-semibold text-gray-700 mb-3">Annual by Building (kWh)</h3>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={buildingTotals} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" tickFormatter={v => `${(v/1000).toFixed(0)}k`} tick={{ fontSize: 11 }} />
                <YAxis dataKey="name" type="category" width={120} tick={{ fontSize: 10 }} />
                <Tooltip formatter={v => [`${fmtNum(v)} kWh`, 'Annual']} />
                <Bar dataKey="annual" fill="#22c55e" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      ) : !isUserMode ? (
        // Demo mode should always have buildings — show anyway
        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h3 className="font-semibold text-gray-700 mb-3">Monthly Total (kWh)</h3>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={monthlyTotal}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={v => `${(v/1000).toFixed(0)}k`} tick={{ fontSize: 11 }} />
                <Tooltip formatter={v => [`${fmtNum(v)} kWh`, 'Total']} />
                <Line type="monotone" dataKey="total" stroke="#16a34a" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h3 className="font-semibold text-gray-700 mb-3">Annual by Building (kWh)</h3>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={buildingTotals} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" tickFormatter={v => `${(v/1000).toFixed(0)}k`} tick={{ fontSize: 11 }} />
                <YAxis dataKey="name" type="category" width={120} tick={{ fontSize: 10 }} />
                <Tooltip formatter={v => [`${fmtNum(v)} kWh`, 'Annual']} />
                <Bar dataKey="annual" fill="#22c55e" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      ) : null}
    </div>
  )
}
