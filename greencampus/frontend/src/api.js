import axios from 'axios'

const api = axios.create({ baseURL: '/api', withCredentials: true })

export const fetchMetrics      = ()       => api.get('/metrics').then(r => r.data)
export const fetchEnergy       = ()       => api.get('/energy').then(r => r.data)
export const fetchWater        = ()       => api.get('/water').then(r => r.data)
export const fetchWaste        = ()       => api.get('/waste').then(r => r.data)
export const fetchInterventions= ()       => api.get('/interventions').then(r => r.data)
export const fetchHealth       = ()       => api.get('/health').then(r => r.data)

export const postSimulate      = (body)   => api.post('/simulate', body).then(r => r.data)
export const postOptimize      = (body)   => api.post('/optimize', body).then(r => r.data)
export const postWhatIf        = (body)   => api.post('/what-if', body).then(r => r.data)
export const postAssistant     = (body)   => api.post('/assistant', body).then(r => r.data)
export const postExplain       = (body)   => api.post('/explain', body).then(r => r.data)

// ── Campus Data Management ────────────────────────────────────────────────────
export const fetchCampusDataStatus = ()   => api.get('/campus-data/status').then(r => r.data)
export const fetchCampusData       = ()   => api.get('/campus-data').then(r => r.data)
export const fetchDemoData         = ()   => api.get('/campus-data/demo').then(r => r.data)
export const postCampusData        = (body) => api.post('/campus-data', body).then(r => r.data)
export const deleteCampusData      = ()   => api.delete('/campus-data').then(r => r.data)
export const uploadCampusCSV       = (file) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/campus-data/csv', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)
}
export const fetchCSVTemplate      = ()   =>
  api.get('/campus-data/csv-template', { responseType: 'text' }).then(r => r.data)
