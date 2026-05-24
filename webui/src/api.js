export const health = async (apiBase) => {
  const r = await fetch(`${apiBase}/health`, { method: 'GET' })
  if (!r.ok) throw new Error('health_failed')
  return r.json()
}

export const initSession = async (apiBase, sessionId) => {
  const r = await fetch(`${apiBase}/init`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
  if (!r.ok) throw new Error('init_failed')
  return r.json()
}

export const fetchMessages = async (apiBase, sessionId, limit = 200) => {
  const base = apiBase || ''
  const url = `${base}/messages/${encodeURIComponent(sessionId)}?limit=${encodeURIComponent(String(limit))}`
  const r = await fetch(url, { method: 'GET' })
  if (!r.ok) throw new Error('messages_failed')
  return r.json()
}

export const fetchState = async (apiBase, sessionId) => {
  const base = apiBase || ''
  const url = `${base}/state/${encodeURIComponent(sessionId)}`
  const r = await fetch(url, { method: 'GET' })
  if (!r.ok) throw new Error('state_failed')
  return r.json()
}

export const fetchSessions = async (apiBase, limit = 30, offset = 0) => {
  const base = apiBase || ''
  const url = `${base}/sessions?limit=${encodeURIComponent(String(limit))}&offset=${encodeURIComponent(String(offset))}`
  const r = await fetch(url, { method: 'GET' })
  if (!r.ok) throw new Error('sessions_failed')
  return r.json()
}

export const deleteSession = async (apiBase, sessionId) => {
  const base = apiBase || ''
  const url = `${base}/sessions/${encodeURIComponent(sessionId)}`
  const r = await fetch(url, { method: 'DELETE' })
  if (!r.ok) throw new Error('delete_failed')
  return r.json()
}

export const setPinned = async (apiBase, sessionId, pinned) => {
  const base = apiBase || ''
  const url = `${base}/sessions/${encodeURIComponent(sessionId)}/pin`
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pinned: !!pinned }),
  })
  if (!r.ok) throw new Error('pin_failed')
  return r.json()
}

export const streamChat = async (apiBase, payload, onEvent) => {
  const r = await fetch(`${apiBase}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error('stream_failed')
  if (!r.body) throw new Error('stream_no_body')

  const reader = r.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buf = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const frames = buf.split('\n\n')
    buf = frames.pop() || ''
    for (const frame of frames) {
      const line = frame.split('\n').find((x) => x.startsWith('data:'))
      if (!line) continue
      const dataStr = line.slice(5).trim()
      if (!dataStr) continue
      let obj
      try {
        obj = JSON.parse(dataStr)
      } catch {
        continue
      }
      onEvent(obj)
    }
  }
}

export const fetchWeather = async (apiBase, lat, lng) => {
  const base = apiBase || ''
  const url = `${base}/weather/current?lat=${encodeURIComponent(String(lat))}&lng=${encodeURIComponent(String(lng))}`
  const r = await fetch(url, { method: 'GET' })
  if (!r.ok) throw new Error('weather_failed')
  return r.json()
}
