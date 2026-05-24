const makeId = () => `sess_${Math.random().toString(16).slice(2, 10)}${Math.random().toString(16).slice(2, 6)}`

export const state = {
  apiBase: import.meta.env.VITE_API_BASE || '',
  sessionId: '',
  messages: [],
  isProcessing: false,
  pipelineConfig: [],
  pipelineStates: {},
  locationPermissionDecided: false,
  locationPermission: 'unknown',
  detectedLocation: null,
  weather: null,
  activePlanIndex: 0,
}

export const loadState = () => {
  const sid = localStorage.getItem('meituan_session_id')
  state.sessionId = sid || makeId()
  localStorage.setItem('meituan_session_id', state.sessionId)
}

export const resetState = () => {
  localStorage.removeItem('meituan_session_id')
  state.sessionId = makeId()
  localStorage.setItem('meituan_session_id', state.sessionId)
  state.messages = []
  state.isProcessing = false
  state.pipelineConfig = []
  state.pipelineStates = {}
  state.detectedLocation = null
  state.weather = null
  state.activePlanIndex = 0
}
