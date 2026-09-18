import { fmtNum } from '../utils/formatters.js'

const FACTORS = [
  { label: 'Grid emission factor', value: '0.716 kg CO₂/kWh', note: 'CEA India average (prototype)' },
  { label: 'Water treatment factor', value: '0.344 kg CO₂/m³', note: 'Pumping + treatment (prototype)' },
  { label: 'Landfill factor', value: '0.50 kg CO₂e/kg', note: 'Methane + transport (prototype)' },
]

export default function CO2Dashboard({ metrics, dataMode }) {
  const isUserMode = dataMode === 'user'
  if (!metrics) return <div className="text-gray-400 text-sm p-4">Loading CO₂ data…</div>

  const co2 = metrics.annual_co2_kg
  const energy_co2 = metrics.annual_energy_kwh * 0.716
  const water_co2  = metrics.annual_water_m3  * 0.344
  const waste_co2  = co2 - energy_co2 - water_co2

  const breakdown = [
    { label: 'Energy (grid)', kg: energy_co2, color: 'bg-yellow-400' },
    { label: 'Water (treatment)', kg: water_co2, color: 'bg-blue-400' },
    { label: 'Waste (landfill)', kg: waste_co2, color: 'bg-red-400' },
  ]

  return (
    <div>
      <div className="flex items-start justify-between mb-1 flex-wrap gap-2">
        <h2 className="text-xl font-bold text-green-800">🌿 CO₂ Equivalent Emissions</h2>
        <span className={`text-xs px-3 py-1 rounded-full border font-medium ${
          isUserMode
            ? 'bg-green-100 border-green-300 text-green-800'
            : 'bg-amber-100 border-amber-300 text-amber-800'
        }`}>
          {isUserMode ? '✅ User Campus Data' : '⚠️ Demo Synthetic Data'}
        </span>
      </div>
      <p className="text-xs text-gray-500 mb-4 italic">{metrics.note}</p>

      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <div className="text-4xl font-bold text-gray-800">{fmtNum(co2, 0)} kg CO₂e/year</div>
        <p className="text-sm text-gray-500 mt-1">Total estimated annual emissions</p>
      </div>

      <div className="grid md:grid-cols-3 gap-4 mb-6">
        {breakdown.map(b => (
          <div key={b.label} className="bg-white rounded-xl border border-gray-200 p-4">
            <div className={`w-3 h-3 rounded-full ${b.color} inline-block mr-2`} />
            <span className="text-sm font-medium text-gray-700">{b.label}</span>
            <div className="text-2xl font-bold text-gray-800 mt-2">{fmtNum(b.kg, 0)} kg</div>
            <div className="text-xs text-gray-400">{((b.kg / co2) * 100).toFixed(1)}% of total</div>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <h3 className="font-semibold text-gray-700 mb-3">Emission Factors Used</h3>
        <p className="text-xs text-amber-700 bg-amber-50 p-2 rounded mb-3">
          ⚠️ Prototype assumptions – not a certified emissions audit. Validate with campus energy accounts.
        </p>
        <table className="text-sm w-full">
          <thead>
            <tr className="text-left text-gray-500 border-b">
              <th className="pb-2">Factor</th><th className="pb-2">Value</th><th className="pb-2">Source</th>
            </tr>
          </thead>
          <tbody>
            {FACTORS.map(f => (
              <tr key={f.label} className="border-b last:border-0">
                <td className="py-2 text-gray-700">{f.label}</td>
                <td className="py-2 font-mono text-gray-800">{f.value}</td>
                <td className="py-2 text-gray-400 text-xs">{f.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
