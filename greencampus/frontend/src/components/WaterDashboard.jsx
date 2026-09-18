import { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LineChart, Line
} from 'recharts'
import { fetchWater } from '../api.js'
import { MONTHS, fmtNum } from '../utils/formatters.js'

export default function WaterDashboard({ dataMode, dataVersion }) {
  const [data, setData] = useState(null)
  const isUserMode = dataMode === 'user'

  // Re-fetch whenever the active dataset changes (mode switch or new user submission).
  // dataVersion ensures re-fetch even if dataMode stays the same (e.g., user re-submits).
  useEffect(() => { fetchWater().then(setData).catch(console.error) }, [dataMode, dataVersion])

  if (!data) return <div className="text-gray-400 text-sm p-4">Loading water data…</div>

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
        <h2 className="text-xl font-bold text-green-800">💧 Water Consumption</h2>
        <span className={`text-xs px-3 py-1 rounded-full border font-medium ${
          isUserMode
            ? 'bg-green-100 border-green-300 text-green-800'
            : 'bg-amber-100 border-amber-300 text-amber-800'
        }`}>
          {isUserMode ? '✅ User Campus Data' : '⚠️ Demo Synthetic Data'}
        </span>
      </div>
      <p className="text-xs text-gray-500 mb-4 italic">{data.note}</p>

      {isUserMode && !hasMonthly && data.annual_m3 && (
        <div className="mb-4 bg-blue-50 border border-blue-200 rounded-xl p-4">
          <div className="text-sm font-semibold text-blue-800">Annual Water Consumption</div>
          <div className="text-2xl font-bold text-blue-700 mt-1">{fmtNum(data.annual_m3, 0)} m³</div>
          <div className="text-xs text-blue-500 mt-1 italic">
            Monthly trend data unavailable — only annual total was provided.
          </div>
        </div>
      )}

      {hasMonthly && (
        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h3 className="font-semibold text-gray-700 mb-3">Monthly Total (m³)</h3>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={monthlyTotal}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={v => [`${fmtNum(v)} m³`, 'Total']} />
                <Line type="monotone" dataKey="total" stroke="#2563eb" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h3 className="font-semibold text-gray-700 mb-3">Annual by Building (m³)</h3>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={buildingTotals} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis dataKey="name" type="category" width={120} tick={{ fontSize: 10 }} />
                <Tooltip formatter={v => [`${fmtNum(v)} m³`, 'Annual']} />
                <Bar dataKey="annual" fill="#3b82f6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {!hasMonthly && !isUserMode && (
        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h3 className="font-semibold text-gray-700 mb-3">Monthly Total (m³)</h3>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={monthlyTotal}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={v => [`${fmtNum(v)} m³`, 'Total']} />
                <Line type="monotone" dataKey="total" stroke="#2563eb" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h3 className="font-semibold text-gray-700 mb-3">Annual by Building (m³)</h3>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={buildingTotals} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis dataKey="name" type="category" width={120} tick={{ fontSize: 10 }} />
                <Tooltip formatter={v => [`${fmtNum(v)} m³`, 'Annual']} />
                <Bar dataKey="annual" fill="#3b82f6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  )
}
