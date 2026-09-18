import { useState } from 'react'
import { postAssistant } from '../api.js'

const SUGGESTED = [
  "What is the current annual energy consumption?",
  "Which interventions give the best ROI?",
  "What is the recycling rate?",
  "How much CO₂ does the campus emit per year?",
  "What payback period does the last simulation show?",
  "Which building uses the most energy?",
]

function Message({ role, text }) {
  const isUser = role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      <div className={`max-w-lg rounded-2xl px-4 py-3 text-sm leading-relaxed ${
        isUser
          ? 'bg-green-600 text-white rounded-br-sm'
          : 'bg-white border border-gray-200 text-gray-800 rounded-bl-sm'
      }`}>
        <div className="whitespace-pre-wrap">{text}</div>
      </div>
    </div>
  )
}

export default function AIAssistant({ metrics, lastSim }) {
  const [history, setHistory] = useState([
    {
      role: 'assistant',
      text: "Hello! I'm the GreenCampus AI Assistant.\n\nI can answer questions about your campus energy, water, waste, and CO₂ data, as well as explain simulation results and intervention recommendations.\n\nAll my answers are grounded in the campus data — I will not invent numerical values.",
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)

  const send = async (question) => {
    const q = question || input.trim()
    if (!q) return
    setInput('')
    setHistory(h => [...h, { role: 'user', text: q }])
    setLoading(true)

    try {
      const context = {
        current_metrics: metrics,
        last_simulation: lastSim,
        simulation_assumptions: {
          grid_emission_factor: '0.716 kg CO₂/kWh (CEA India, prototype)',
          water_emission_factor: '0.344 kg CO₂/m³ (prototype)',
          waste_landfill_factor: '0.50 kg CO₂e/kg (prototype)',
          data_note: 'Synthetic campus data – prototype only',
        },
      }
      const data = await postAssistant({ question: q, context })
      setHistory(h => [
        ...h,
        { role: 'assistant', text: data.answer },
        {
          role: 'assistant',
          text: `ℹ️ ${data.disclaimer}`,
        },
      ])
    } catch (err) {
      setHistory(h => [...h, { role: 'assistant', text: `Error: ${err.message}` }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h2 className="text-xl font-bold text-green-800 mb-1">🤖 AI Assistant</h2>
      <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-1.5 mb-4">
        The assistant is grounded in campus data and simulation results. It does not invent numerical values.
      </p>

      {/* Chat area */}
      <div className="bg-gray-50 rounded-xl border border-gray-200 p-4 h-96 overflow-y-auto mb-4">
        {history.map((m, i) => <Message key={i} role={m.role} text={m.text} />)}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 rounded-2xl px-4 py-3 text-sm text-gray-400 rounded-bl-sm">
              Thinking…
            </div>
          </div>
        )}
      </div>

      {/* Suggestions */}
      <div className="flex flex-wrap gap-2 mb-3">
        {SUGGESTED.map((s, i) => (
          <button
            key={i}
            onClick={() => send(s)}
            disabled={loading}
            className="text-xs bg-white border border-green-300 text-green-700 px-3 py-1 rounded-full hover:bg-green-50 transition-colors disabled:opacity-50"
          >
            {s}
          </button>
        ))}
      </div>

      {/* Input */}
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && send()}
          placeholder="Ask a question about campus sustainability…"
          className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
          disabled={loading}
        />
        <button
          onClick={() => send()}
          disabled={loading || !input.trim()}
          className="bg-green-700 hover:bg-green-800 disabled:bg-gray-400 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          Send
        </button>
      </div>
    </div>
  )
}
