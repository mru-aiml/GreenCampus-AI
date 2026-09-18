const SECTIONS = [
  {
    icon: '🔍',
    title: 'Transparency',
    content: `GreenCampus AI uses a documented, rule-based objective function for intervention scoring. All weights, emission factors, and simulation parameters are visible in the application and source code. The active data source (Demo or User Campus Data) is clearly labelled on every dashboard. No hidden models influence recommendations.`,
  },
  {
    icon: '💡',
    title: 'Explainability',
    content: `Every simulation result includes a detailed explanation covering: which interventions were selected, why (objective score breakdown), financial and environmental impact projections, and any synergy effects applied. Users can inspect each scoring dimension individually.`,
  },
  {
    icon: '🔒',
    title: 'Privacy',
    content: `This prototype does not collect, store, or transmit personal data. No student names, IDs, phone numbers, or email addresses are required — only campus sustainability and operational data (energy kWh, water m³, waste kg). User-submitted campus data is isolated per browser session using a cryptographically random session ID stored in an HttpOnly cookie. Sessions are not tied to any personal identifier. If Granite mode is enabled, API calls go to IBM watsonx.ai — review IBM's data processing terms before using in production.`,
  },
  {
    icon: '👤',
    title: 'Human Oversight',
    content: `GreenCampus AI is a decision-support tool, not a decision-making system. All intervention recommendations require human review and validation against real campus conditions. Campus sustainability officers retain full authority over all decisions. The system provides information; it does not act.`,
  },
  {
    icon: '📋',
    title: 'User Data',
    content: `Users may provide campus sustainability data manually through a form or by uploading a CSV file. No student names, student IDs, phone numbers, or email addresses should be entered — only operational sustainability data is needed. User data is not independently verified or certified by this prototype. All calculations remain deterministic. AI explanations are grounded in calculated results. Missing values are never silently invented or fabricated.`,
  },
  {
    icon: '📊',
    title: 'Data Limitations',
    content: `In Demo mode, this prototype uses synthetic campus data generated for demonstration purposes only. It does not represent any real campus. Intervention parameters are approximations and have not been calibrated against real installations. Do not use any data (demo or user-provided) for financial or regulatory decisions without independent verification. When user data is active, the system uses it as-is — no validation against external sources is performed.`,
  },
  {
    icon: '〰️',
    title: 'Uncertainty',
    content: `Projected savings are estimates based on simplified models. Actual results depend on occupancy patterns, equipment age, maintenance quality, seasonal variation, and local grid conditions. Payback periods use simple payback (cost / annual savings) and exclude financing costs, inflation, and degradation over time. If monthly data is unavailable, charts may show evenly-distributed estimates rather than real monthly profiles.`,
  },
  {
    icon: '🧪',
    title: 'Synthetic Data Disclosure',
    content: `The Demo dataset (all campus figures: energy kWh, water m³, waste kg) is synthetic and randomly generated. Intervention costs and savings percentages are prototype assumptions loosely based on published ranges for Indian campuses. They are labelled "Prototype assumptions" throughout the application. The Demo dataset is not derived from any real institution.`,
  },
  {
    icon: '🤖',
    title: 'AI Model Disclosure',
    content: `The AI explanation engine defaults to deterministic templates — no LLM is used unless GRANITE_MODE=1 is set explicitly. When Granite mode is active, IBM Granite is used. Prompts are designed to ground responses in provided calculated data and explicitly instruct the model not to invent numerical values. Granite mode is opt-in. The LLM never performs CO₂ or sustainability calculations — all numbers come from deterministic Python code.`,
  },
]

const EMISSION_FACTORS = [
  { factor: 'Grid emission factor', value: '0.716 kg CO₂/kWh', source: 'CEA India average (prototype approximation)' },
  { factor: 'Water treatment factor', value: '0.344 kg CO₂/m³', source: 'Pumping + treatment (prototype)' },
  { factor: 'Landfill waste factor', value: '0.50 kg CO₂e/kg', source: 'Methane + transport (prototype)' },
]

const OPT_WEIGHTS = [
  { dim: 'Energy', weight: '25%' },
  { dim: 'Water', weight: '15%' },
  { dim: 'Waste', weight: '10%' },
  { dim: 'CO₂', weight: '25%' },
  { dim: 'Financial ROI', weight: '25%' },
]

export default function ResponsibleAI() {
  return (
    <div>
      <h2 className="text-xl font-bold text-green-800 mb-1">⚖️ Responsible AI</h2>
      <p className="text-sm text-gray-600 mb-6 max-w-2xl">
        GreenCampus AI is built with transparency, human oversight, and honest uncertainty disclosure as first-class requirements — not afterthoughts.
      </p>

      <div className="grid md:grid-cols-2 gap-4 mb-6">
        {SECTIONS.map(s => (
          <div key={s.title} className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-2xl">{s.icon}</span>
              <h3 className="font-bold text-gray-800">{s.title}</h3>
            </div>
            <p className="text-sm text-gray-600 leading-relaxed">{s.content}</p>
          </div>
        ))}
      </div>

      {/* Emission factors table */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
        <h3 className="font-bold text-gray-800 mb-2">📐 Emission Factors (Prototype Assumptions)</h3>
        <p className="text-xs text-amber-700 bg-amber-50 p-2 rounded mb-3">
          These factors are prototype approximations. For compliance or financial reporting, engage a certified auditor.
        </p>
        <table className="text-sm w-full">
          <thead>
            <tr className="text-left text-gray-500 border-b">
              <th className="pb-2">Factor</th><th className="pb-2">Value</th><th className="pb-2">Source Note</th>
            </tr>
          </thead>
          <tbody>
            {EMISSION_FACTORS.map(f => (
              <tr key={f.factor} className="border-b last:border-0">
                <td className="py-2 text-gray-700">{f.factor}</td>
                <td className="py-2 font-mono text-gray-800">{f.value}</td>
                <td className="py-2 text-gray-400 text-xs">{f.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Optimization weights table */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
        <h3 className="font-bold text-gray-800 mb-2">⚖️ EcoSim-Opt Objective Weights (Default)</h3>
        <div className="flex flex-wrap gap-3">
          {OPT_WEIGHTS.map(w => (
            <div key={w.dim} className="bg-green-50 border border-green-200 rounded-lg px-3 py-2 text-center text-sm">
              <div className="font-bold text-green-700">{w.weight}</div>
              <div className="text-gray-600 text-xs">{w.dim}</div>
            </div>
          ))}
        </div>
        <p className="text-xs text-gray-400 mt-2">
          Composite score = Σ weight_k × min(metric_k / max_k, 1.0). Weights can be customised per run.
        </p>
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-4">
        <h3 className="font-bold text-amber-800 mb-1">🔐 Session Isolation Notice</h3>
        <p className="text-sm text-amber-700">
          Prototype session isolation is provided for demonstration purposes and is <strong>not equivalent
          to production-grade authentication</strong>. Sessions are identified by a random cookie stored
          in the browser. Data is held in server memory (not a database) and is lost on server restart.
          Do not store sensitive, confidential, or personally identifiable information in this prototype.
        </p>
      </div>
      <div className="bg-green-50 border border-green-200 rounded-xl p-5">
        <h3 className="font-bold text-green-800 mb-2">📋 Summary of Limitations</h3>
        <ul className="text-sm text-gray-700 space-y-1 list-disc list-inside">
          <li>Demo data is synthetic. Do not use for financial, regulatory, or audit purposes.</li>
          <li>User-provided data is not independently verified by this prototype.</li>
          <li>Intervention parameters are prototype assumptions, not certified measurements.</li>
          <li>Simple payback does not account for financing costs or degradation.</li>
          <li>CO₂ estimates use prototype emission factors — engage a certified auditor for compliance.</li>
          <li>Monthly trend charts show evenly-distributed estimates if actual monthly data is not provided.</li>
          <li>Simulation results should be validated against real campus metering and audits.</li>
          <li>The AI assistant is grounded in provided data and does not invent values, but may misinterpret ambiguous questions.</li>
          <li>Do not upload personally identifiable information or confidential records. No student names, IDs, or personal data are required.</li>
          <li>Session isolation is prototype-grade only — not enterprise-secure or production-authenticated.</li>
        </ul>
      </div>
    </div>
  )
}
