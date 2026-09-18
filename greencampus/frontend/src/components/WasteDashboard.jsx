import { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, PieChart, Pie, Cell
} from 'recharts'
import { fetchWaste } from '../api.js'
import { fmtNum } from '../utils/formatters.js'

const PIE_COLORS = ['#22c55e', '#86efac', '#ef4444']

export default function WasteDashboard({ dataMode, dataVersion }) {
  const [data, setData] = useState(null)
  const isUserMode = dataMode === 'user'

  // Re-fetch whenever the active dataset changes (mode switch or new user submission).
  // dataVersion ensures re-fetch even if dataMode stays the same (e.g., user re-submits).
  useEffect(() => { fetchWaste().then(setData).catch(console.error) }, [dataMode, dataVersion])

  if (!data) return <div className="text-gray-400 text-sm p-4">Loading waste data…</div>

  const totals = data.monthly.reduce(
    (acc, m) => {
      acc.recycled  += m.recycled
      acc.compost   += m.compost
      acc.landfill  += m.landfill
      return acc
    },
    { recycled: 0, compost: 0, landfill: 0 }
  )

  const pieData = [
    { name: 'Recycled',  value: totals.recycled },
    { name: 'Compost',   value: totals.compost },
    { name: 'Landfill',  value: totals.landfill },
  ]

  return (
    <div>
      <div className="flex items-start justify-between mb-1 flex-wrap gap-2">
        <h2 className="text-xl font-bold text-green-800">♻️ Waste Management</h2>
        <span className={`text-xs px-3 py-1 rounded-full border font-medium ${
          isUserMode
            ? 'bg-green-100 border-green-300 text-green-800'
            : 'bg-amber-100 border-amber-300 text-amber-800'
        }`}>
          {isUserMode ? '✅ User Campus Data' : '⚠️ Demo Synthetic Data'}
        </span>
      </div>
      <p className="text-xs text-gray-500 mb-4 italic">{data.note}</p>
      {isUserMode && !data.has_monthly && (
        <p className="text-xs text-blue-500 italic mb-2">
          Waste chart uses annual data distributed evenly across months — actual monthly data not provided.
        </p>
      )}

      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h3 className="font-semibold text-gray-700 mb-3">Monthly Waste Composition (kg)</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={data.monthly}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={v => `${(v/1000).toFixed(1)}t`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={v => [`${fmtNum(v)} kg`]} />
              <Legend />
              <Bar dataKey="recycled" stackId="a" fill="#22c55e" name="Recycled" />
              <Bar dataKey="compost"  stackId="a" fill="#86efac" name="Compost" />
              <Bar dataKey="landfill" stackId="a" fill="#ef4444" name="Landfill" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h3 className="font-semibold text-gray-700 mb-3">Annual Waste Split</h3>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label={({ name, percent }) => `${name} ${(percent*100).toFixed(0)}%`}>
                {pieData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i]} />)}
              </Pie>
              <Tooltip formatter={v => `${fmtNum(v)} kg`} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
