export const fmtINR = (v) => {
  if (v >= 1e7) return `₹${(v / 1e7).toFixed(1)} Cr`
  if (v >= 1e5) return `₹${(v / 1e5).toFixed(1)} L`
  return `₹${Number(v).toLocaleString('en-IN')}`
}

export const fmtNum = (v, decimals = 0) =>
  Number(v).toLocaleString('en-IN', { maximumFractionDigits: decimals })

export const fmtPct = (v) => `${Number(v).toFixed(1)}%`

export const fmtKwh = (v) => {
  if (v >= 1e6) return `${(v / 1e6).toFixed(2)} MWh`
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)} MWh`
  return `${fmtNum(v)} kWh`
}

export const fmtM3 = (v) => `${fmtNum(v)} m³`

export const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
