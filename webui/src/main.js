import './style.css'
import { deleteSession, fetchMessages, fetchSessions, fetchState, fetchWeather, health, initSession, setPinned, streamChat } from './api'
import { state, loadState, resetState } from './state'
import { parsePlans, plansFromPayload, renderPlanCardsHtml } from './plans'
import { renderPipeline } from './pipeline'
import { getBrowserLocation, reverseGeocodeNominatim } from './location'
import { renderMap } from './map'

const esc = (s) =>
  (s || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')

let asrRecognizer = null
let asrListening = false
let asrWarnedUnsupported = false

const setAsrUi = (on) => {
  const btn = document.querySelector('#asr-btn')
  if (!btn) return
  btn.classList.toggle('composer__asr--on', !!on)
  btn.setAttribute('aria-pressed', on ? 'true' : 'false')
  btn.setAttribute('title', on ? '停止语音输入' : '语音转文字')
}

const appendToPrompt = (text) => {
  const input = document.querySelector('#prompt')
  const t = (text || '').trim()
  if (!input || !t) return
  const cur = input.value || ''
  const sep = cur && !/\s$/.test(cur) ? ' ' : ''
  input.value = cur + sep + t
  input.focus()
  input.setSelectionRange(input.value.length, input.value.length)
}

const ensureAsr = () => {
  if (asrRecognizer) return asrRecognizer
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SpeechRecognition) return null

  const r = new SpeechRecognition()
  r.lang = 'zh-CN'
  r.interimResults = true
  r.continuous = true
  r.maxAlternatives = 1

  r.onresult = (e) => {
    let out = ''
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const res = e.results[i]
      if (res && res.isFinal && res[0] && res[0].transcript) {
        out += res[0].transcript
      }
    }
    appendToPrompt(out)
  }

  r.onerror = (e) => {
    stopAsr()
    const err = (e && e.error) || ''
    if (err === 'not-allowed' || err === 'service-not-allowed') {
      window.alert('未授予麦克风权限，无法进行语音转文字。请在浏览器地址栏权限设置中允许麦克风后重试。')
    } else if (err === 'no-speech') {
      window.alert('没有检测到语音输入，请重试。')
    }
  }

  r.onend = () => {
    asrListening = false
    setAsrUi(false)
  }

  asrRecognizer = r
  return r
}

const startAsr = () => {
  const r = ensureAsr()
  if (!r) {
    if (!asrWarnedUnsupported) {
      asrWarnedUnsupported = true
      window.alert('当前浏览器不支持语音识别（SpeechRecognition）。建议使用最新版 Chrome。')
    }
    return
  }

  try {
    r.start()
    asrListening = true
    setAsrUi(true)
  } catch {
    asrListening = false
    setAsrUi(false)
  }
}

const stopAsr = () => {
  if (!asrListening) {
    setAsrUi(false)
    return
  }
  asrListening = false
  setAsrUi(false)
  try {
    asrRecognizer && asrRecognizer.stop()
  } catch {
  }
}

const toggleAsr = () => {
  if (asrListening) stopAsr()
  else startAsr()
}

const mount = () => {
  const root = document.querySelector('#app')
  root.innerHTML = `
  <div class="bg">
    <div class="aurora a1"></div>
    <div class="aurora a2"></div>
    <div class="noise"></div>
  </div>
  <div class="top-right">
    <div class="geo-actions">
      <div class="status-badge status-badge--mini" id="status-badge">
        <span class="status-dot"></span>
        <span class="status-text">连接检测中</span>
      </div>
      <button class="btn btn--primary geo-btn" id="geo-allow">启用定位</button>
      <button class="btn btn--ghost geo-btn" id="geo-skip">跳过</button>
      <button class="btn btn--icon geo-icon" id="geo-refresh" title="刷新定位" aria-label="刷新定位">
        <span class="geo-icon__dot"></span>
      </button>
    </div>
    <div class="loc-badge" id="loc-badge" style="display:none"></div>
  </div>
  <header class="hero">
    <h1 class="hero-title">私人规划执行助理</h1>
    <div class="hero-subtitle">INTELLIGENT PLANNING · FLUID EXPERIENCE</div>
  </header>
  <main class="layout">
    <aside class="sidebar">
      <button class="btn btn--ghost btn--block" id="new-session">新建对话</button>
      <div class="divider"></div>
      <div class="session-card">
        <div class="session-card__label">当前会话</div>
        <div class="session-card__id" id="session-id"></div>
      </div>
      <div class="session-card session-card--mini" id="detected-loc-card" style="display:none"></div>
      <div class="divider"></div>
      <div class="session-card session-card--mini">
        <div class="session-card__label">历史对话</div>
        <div class="session-list" id="session-list"></div>
      </div>
    </aside>
    <section class="chat">
      <div class="messages" id="messages"></div>
      <div class="processing" id="processing" style="display:none">
        <div id="pipeline"></div>
        <div id="thinking"></div>
      </div>
      <form class="composer" id="composer">
        <input class="composer__input" id="prompt" placeholder="描述你的需求，例如：下午2点出发，带5岁娃，老婆减脂，帮我规划4-6小时..." autocomplete="off"/>
        <button class="btn btn--ghost composer__asr" type="button" id="asr-btn" aria-label="语音转文字" aria-pressed="false" title="语音转文字">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 14c1.66 0 3-1.34 3-3V6a3 3 0 0 0-6 0v5c0 1.66 1.34 3 3 3Z" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M19 11a7 7 0 0 1-14 0" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>
            <path d="M12 18v3" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>
            <path d="M8 21h8" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>
          </svg>
        </button>
        <button class="btn btn--primary composer__send" type="submit" aria-label="发送">↗</button>
      </form>
    </section>
  </main>

  <!-- Persistent map overlay (outside messages to survive re-renders) -->
  <div id="map-panel" class="map-panel" style="display:none">
    <div class="map-panel__header">
      <span class="map-panel__title">🗺️ 行程路线地图</span>
      <button class="btn btn--ghost map-panel__close" id="map-close-btn" type="button" aria-label="关闭地图">✕</button>
    </div>
    <div id="map-container" class="map-panel__body"></div>
  </div>`
}

const setStatus = (mode) => {
  const badge = document.querySelector('#status-badge')
  const dot = badge.querySelector('.status-dot')
  const text = badge.querySelector('.status-text')
  badge.classList.remove('status-badge--online', 'status-badge--offline')
  dot.classList.remove('status-dot--live', 'status-dot--dead')
  if (mode === 'online') {
    badge.classList.add('status-badge--online')
    dot.classList.add('status-dot--live')
    text.textContent = '服务在线'
  } else if (mode === 'offline') {
    badge.classList.add('status-badge--offline')
    dot.classList.add('status-dot--dead')
    text.textContent = '服务离线'
  } else {
    text.textContent = '连接检测中'
  }
}

const renderMessages = () => {
  const box = document.querySelector('#messages')
  box.innerHTML = state.messages
    .map((m, msgIdx) => {
      if (m.role === 'user') {
        return `<div class="message-row message-row--user">
          <div class="message-bubble message-bubble--user">${esc(m.content)}</div>
          <div class="avatar avatar--user">我</div>
        </div>`
      }

      const structuredPlans = state.planPayloadByMessage?.[m.planKey]
      const parsed = structuredPlans ? { intro: null, plans: plansFromPayload(structuredPlans) } : parsePlans(m.content || '')
      const { intro, plans } = parsed
      if (!plans.length) {
        return `<div class="message-row message-row--assistant">
          <div class="avatar avatar--ai">AI</div>
          <div class="message-bubble message-bubble--assistant">${esc(m.content).replaceAll('\n', '<br>')}</div>
        </div>`
      }

      const activeIdx = Math.min(state.activePlanIndexByMessage?.[m.planKey] ?? 0, plans.length - 1)
      const introHtml = intro ? `<div class="plan-intro">${esc(intro)}</div>` : ''
      const cardsHtml = renderPlanCardsHtml(plans, activeIdx, m.planKey || '')
      const dots = plans
        .map((_, i) => `<button class="dot ${i === activeIdx ? 'dot--on' : ''}" data-dot="${i}" data-plan-key="${esc(m.planKey || '')}" type="button">${i === activeIdx ? '●' : '○'}</button>`)
        .join('')
      return `<div class="message-row message-row--assistant" data-message-idx="${msgIdx}">
        <div class="avatar avatar--ai">AI</div>
        <div class="plan-wrap">
          ${introHtml}
          ${cardsHtml}
          <div class="plan-actions">
            <button class="btn btn--primary btn--block" data-pick="${activeIdx}" data-plan-key="${esc(m.planKey || '')}" type="button">就选它！</button>
          </div>
          <div class="plan-dots">${dots}</div>
          <div class="plan-caption">方案 ${activeIdx + 1} / ${plans.length}</div>
        </div>
      </div>`
    })
    .join('')

  box.querySelectorAll('[data-dot]').forEach((el) => {
    el.addEventListener('click', () => {
      const key = el.getAttribute('data-plan-key') || ''
      const idx = Number(el.getAttribute('data-dot') || '0') || 0
      setActivePlanIndex(key, idx)
      renderMessages()
    })
  })
  box.querySelectorAll('[data-pick]').forEach((el) => {
    el.addEventListener('click', () => {
      const idx = Number(el.getAttribute('data-pick') || '0') || 0
      const key = el.getAttribute('data-plan-key') || ''
      setActivePlanIndex(key, idx)
      sendMessage(`确认 方案${idx + 1}`)
    })
  })
  box.querySelectorAll('[data-nav]').forEach((el) => {
    el.addEventListener('click', () => {
      const dir = el.getAttribute('data-nav')
      const n = Number(el.getAttribute('data-count') || '0') || 0
      const key = el.closest('.plan-wrap')?.querySelector('[data-map-key]')?.getAttribute('data-map-key') || ''
      if (n <= 1) return
      const cur = getActivePlanIndex(key)
      if (dir === 'prev') setActivePlanIndex(key, (cur - 1 + n) % n)
      else setActivePlanIndex(key, (cur + 1) % n)
      renderMessages()
    })
  })

  // Touch swipe for plan carousel
  box.querySelectorAll('.plan-carousel').forEach((carousel) => {
    let startX = 0
    carousel.addEventListener('touchstart', (e) => {
      startX = e.touches[0].clientX
    }, { passive: true })
    carousel.addEventListener('touchend', (e) => {
      const endX = e.changedTouches[0].clientX
      const diff = startX - endX
      const n = Number(carousel.getAttribute('data-count') || '0') || 0
      const key = carousel.closest('.plan-wrap')?.querySelector('[data-map-key]')?.getAttribute('data-map-key') || ''
      if (n <= 1) return
      if (Math.abs(diff) < 50) return
      const cur = getActivePlanIndex(key)
      if (diff > 0) setActivePlanIndex(key, (cur + 1) % n)
      else setActivePlanIndex(key, (cur - 1 + n) % n)
      renderMessages()
    })
  })

  // Map toggle button (re-attached each render since DOM is recreated)
  box.querySelectorAll('[data-map-key]').forEach((mapBtn) => {
    mapBtn.addEventListener('click', () => {
      const key = mapBtn.getAttribute('data-map-key') || ''
      const plans = state.planPayloadByMessage?.[key] || null
      const idx = getActivePlanIndex(key)
      if (state.sessionId) renderMap(state.sessionId, idx, plans)
    })
  })

  box.scrollTop = box.scrollHeight
}

const getActivePlanIndex = (planKey) => {
  if (!planKey) return state.activePlanIndex || 0
  return state.activePlanIndexByMessage?.[planKey] ?? 0
}

const setActivePlanIndex = (planKey, idx) => {
  const next = Number(idx || 0) || 0
  state.activePlanIndex = next
  if (!planKey) return
  state.activePlanIndexByMessage[planKey] = next
}

const setLocationUi = () => {
  const badge = document.querySelector('#loc-badge')
  const loc = state.detectedLocation
  if (!loc) {
    badge.style.display = 'none'
  } else {
    badge.style.display = 'flex'
    const w = state.weather
    const wx =
      w && (typeof w.temperature_c === 'number' || typeof w.precipitation_mm === 'number')
        ? `<span class="loc-weather">${typeof w.temperature_c === 'number' ? `${Math.round(w.temperature_c)}°C` : ''}${typeof w.precipitation_mm === 'number' ? ` · ${w.precipitation_mm.toFixed(1)}mm` : ''}</span>`
        : ''
    badge.innerHTML = `<span class="loc-dot"></span><span class="loc-text" title="${esc(loc.label)}">${esc(loc.label)}</span>${wx}`
    const card = document.querySelector('#detected-loc-card')
    card.style.display = 'block'
    const wline =
      w && (typeof w.temperature_c === 'number' || typeof w.precipitation_mm === 'number' || typeof w.wind_kph === 'number')
        ? `<div class="session-card__id">🌦️ ${typeof w.temperature_c === 'number' ? `${Math.round(w.temperature_c)}°C` : ''}${typeof w.precipitation_mm === 'number' ? ` · 降水${w.precipitation_mm.toFixed(1)}mm` : ''}${typeof w.wind_kph === 'number' ? ` · 风${Math.round(w.wind_kph)}km/h` : ''}</div>`
        : ''
    card.innerHTML = `<div class="session-card__label">位置定位</div><div class="session-card__id">📍 ${esc(loc.label)}</div>${wline}`
  }

  const showPerm = !state.locationPermissionDecided
  document.querySelector('#geo-allow').style.display = showPerm ? 'inline-flex' : 'none'
  document.querySelector('#geo-skip').style.display = showPerm ? 'inline-flex' : 'none'
  document.querySelector('#geo-refresh').style.display = state.locationPermission === 'granted' ? 'inline-flex' : 'none'
}

const showProcessing = (on) => {
  document.querySelector('#processing').style.display = on ? 'block' : 'none'
}

let openMenuSid = null

const renderSessionList = () => {
  const box = document.querySelector('#session-list')
  const items = state.sessions || []
  if (!items.length) {
    box.innerHTML = `<div class="session-empty">暂无历史</div>`
    return
  }
  box.innerHTML = items
    .map((s) => {
      const sid = s.session_id
      const active = sid === state.sessionId
      const pinned = Number(s.pinned || 0) === 1
      const raw = (s.last_content || '').trim()
      const preview = raw ? esc(raw).slice(0, 26) : '（空会话）'
      const menuOpen = openMenuSid === sid
      return `<div class="session-item ${active ? 'session-item--on' : ''} ${menuOpen ? 'session-item--menu-open' : ''}" data-sid="${esc(sid)}" role="button" tabindex="0">
        <div class="session-item__top">
          <div class="session-item__id">${pinned ? '📌 ' : ''}${esc(sid)}</div>
          <button class="session-more" data-more="${esc(sid)}" type="button" aria-label="更多">⋯</button>
        </div>
        <div class="session-item__preview">${preview}</div>
        <div class="session-menu ${menuOpen ? 'session-menu--on' : ''}" data-menu="${esc(sid)}">
          <button class="session-menu__item" data-act="pin" data-sid="${esc(sid)}" type="button">
            <span class="session-menu__icon">📌</span>
            <span>${pinned ? '取消固定' : '固定置顶'}</span>
          </button>
          <button class="session-menu__item session-menu__item--danger" data-act="del" data-sid="${esc(sid)}" type="button">
            <span class="session-menu__icon">🗑️</span>
            <span>删除对话</span>
          </button>
        </div>
      </div>`
    })
    .join('')

  box.querySelectorAll('.session-item[data-sid]').forEach((el) => {
    el.addEventListener('click', async () => {
      const sid = el.getAttribute('data-sid')
      if (!sid || sid === state.sessionId || state.isProcessing) return
      await loadSession(sid)
    })
    el.addEventListener('keydown', async (e) => {
      if (e.key !== 'Enter' && e.key !== ' ') return
      e.preventDefault()
      const sid = el.getAttribute('data-sid')
      if (!sid || sid === state.sessionId || state.isProcessing) return
      await loadSession(sid)
    })
  })

  box.querySelectorAll('[data-more]').forEach((el) => {
    el.addEventListener('click', (e) => {
      e.preventDefault()
      e.stopPropagation()
      const sid = el.getAttribute('data-more')
      openMenuSid = openMenuSid === sid ? null : sid
      renderSessionList()
    })
  })

  box.querySelectorAll('[data-act]').forEach((el) => {
    el.addEventListener('click', async (e) => {
      e.preventDefault()
      e.stopPropagation()
      const sid = el.getAttribute('data-sid')
      const act = el.getAttribute('data-act')
      if (!sid || !act) return
      if (act === 'del') {
        try {
          await deleteSession(state.apiBase, sid)
        } catch {}
        openMenuSid = null
        await refreshSessions()
        if (sid === state.sessionId) {
          const next = (state.sessions || []).find((x) => x.session_id !== sid)
          if (next) await loadSession(next.session_id)
          else {
            resetState()
            document.querySelector('#session-id').textContent = state.sessionId
            state.messages = []
            renderMessages()
            setLocationUi()
            await refreshSessions()
          }
        }
        return
      }
      if (act === 'pin') {
        const cur = (state.sessions || []).find((x) => x.session_id === sid)
        const pinned = !(cur && Number(cur.pinned || 0) === 1)
        try {
          await setPinned(state.apiBase, sid, pinned)
        } catch {}
        openMenuSid = null
        await refreshSessions()
      }
    })
  })
}

const refreshSessions = async () => {
  try {
    state.sessions = await fetchSessions(state.apiBase, 30, 0)
  } catch {
    state.sessions = []
  }
  renderSessionList()
}

const loadSession = async (sid) => {
  openMenuSid = null
  state.sessionId = sid
  localStorage.setItem('meituan_session_id', state.sessionId)
  document.querySelector('#session-id').textContent = state.sessionId
  state.messages = []
  state.activePlanIndex = 0
  state.activePlanIndexByMessage = {}
  state.pendingPlans = null
  showProcessing(false)
  renderPipeline(document.querySelector('#pipeline'), [], {})
  updateThinking('正在加载历史对话...')
  try {
    await initSession(state.apiBase, state.sessionId)
  } catch {}
  try {
    const st = await fetchState(state.apiBase, state.sessionId)
    if (st && st.location) state.detectedLocation = st.location
    state.weather = (st && st.scratch && st.scratch.weather) || null
  } catch {}
  try {
    const msgs = await fetchMessages(state.apiBase, state.sessionId, 200)
    state.messages = (msgs || []).map((m, idx) => ({ role: m.role, content: m.content, planKey: `${sid}_${idx}` }))
  } catch {
    state.messages = []
  }
  setLocationUi()
  renderMessages()
  await refreshSessions()
}

const thinkingHtml = (text) => `
<div class="thinking">
  <div class="thinking-ring"></div>
  <div class="thinking-text">${esc(text || '正在理解你的需求...')}</div>
  <div class="thinking-progress"><div class="thinking-progress-bar"></div></div>
  <div class="thinking-dots"><span></span><span></span><span></span></div>
  <div class="thinking-long-wait">Agent 正在深度思考中，请耐心等待...</div>
</div>`

const updateThinking = (text) => {
  const box = document.querySelector('#thinking')
  box.innerHTML = thinkingHtml(text)
}

const sendMessage = async (text) => {
  if (!text || state.isProcessing) return
  state.messages.push({ role: 'user', content: text })
  state.isProcessing = true
  showProcessing(true)
  updateThinking('正在理解你的需求...')
  renderMessages()

  let accumulated = ''
  let streamedPlans = null
  state.pipelineConfig = []
  state.pipelineStates = {}
  renderPipeline(document.querySelector('#pipeline'), [], {})

  const payload = { session_id: state.sessionId, message: text }
  if (state.detectedLocation) payload.user_location = state.detectedLocation

  try {
    await streamChat(state.apiBase, payload, (ev) => {
      const t = ev.type
      if (t === 'pipeline_config') {
        state.pipelineConfig = ev.stages || []
        state.pipelineStates = Object.fromEntries(state.pipelineConfig.map((s) => [s.id, 'pending']))
        renderPipeline(document.querySelector('#pipeline'), state.pipelineConfig, state.pipelineStates)
        return
      }
      if (t === 'pipeline_stage') {
        if (ev.stage_id && state.pipelineStates[ev.stage_id] !== undefined) {
          state.pipelineStates[ev.stage_id] = ev.status || 'pending'
          renderPipeline(document.querySelector('#pipeline'), state.pipelineConfig, state.pipelineStates)
        }
        return
      }
      if (t === 'status') {
        updateThinking(ev.content || '处理中...')
        return
      }
      if (t === 'plans') {
        streamedPlans = ev.plans || []
        state.pendingPlans = streamedPlans
        updateThinking('方案已生成，正在整理说明...')
        return
      }
      if (t === 'delta') {
        accumulated += ev.content || ''
        updateThinking('正在生成回复...')
        const safe = esc(accumulated).replaceAll('\n', '<br>')
        const box = document.querySelector('#messages')
        const last = box.querySelector('.streaming')
        if (last) last.remove()
        box.insertAdjacentHTML(
          'beforeend',
          `<div class="message-row message-row--assistant streaming">
            <div class="avatar avatar--ai">AI</div>
            <div class="message-bubble message-bubble--assistant">${safe}<span class="typing-cursor"></span></div>
          </div>`,
        )
        box.scrollTop = box.scrollHeight
        return
      }
      if (t === 'done') {
        return
      }
    })
  } catch {
    accumulated = '连接出现问题，请稍后重试。'
  }

  const box = document.querySelector('#messages')
  const last = box.querySelector('.streaming')
  if (last) last.remove()

  const planKey = `msg_${Date.now()}_${state.messages.length}`
  if (streamedPlans && streamedPlans.length) {
    state.planPayloadByMessage[planKey] = streamedPlans
    state.activePlanIndexByMessage[planKey] = 0
  }
  state.messages.push({ role: 'assistant', content: accumulated || '抱歉，服务暂时不可用。', planKey })
  state.pendingPlans = null
  state.isProcessing = false
  showProcessing(false)
  renderMessages()
  await refreshSessions()
}

const bind = () => {
  document.querySelector('#session-id').textContent = state.sessionId

  document.addEventListener('click', () => {
    if (!openMenuSid) return
    openMenuSid = null
    renderSessionList()
  })

  document.querySelector('#composer').addEventListener('submit', (e) => {
    e.preventDefault()
    stopAsr()
    const input = document.querySelector('#prompt')
    const v = (input.value || '').trim()
    input.value = ''
    sendMessage(v)
  })

  const asrBtn = document.querySelector('#asr-btn')
  if (asrBtn) {
    asrBtn.addEventListener('click', () => {
      toggleAsr()
    })
  }

  document.querySelector('#new-session').addEventListener('click', async () => {
    if (state.isProcessing) return
    if (!state.messages.length) return
    resetState()
    document.querySelector('#session-id').textContent = state.sessionId
    state.messages = []
    renderMessages()
    setLocationUi()
    await refreshSessions()
  })

  document.querySelector('#geo-skip').addEventListener('click', () => {
    state.locationPermission = 'denied'
    state.locationPermissionDecided = true
    setLocationUi()
  })

  document.querySelector('#geo-allow').addEventListener('click', async () => {
    state.locationPermission = 'granted'
    state.locationPermissionDecided = true
    setLocationUi()
    try {
      const loc = await getBrowserLocation()
      try {
        const label = await reverseGeocodeNominatim(loc.lat, loc.lng)
        state.detectedLocation = { ...loc, label }
      } catch {
        state.detectedLocation = loc
      }
      try {
        state.weather = await fetchWeather(state.apiBase, state.detectedLocation.lat, state.detectedLocation.lng)
      } catch {
        state.weather = null
      }
      setLocationUi()
    } catch {
      state.locationPermission = 'denied'
      setLocationUi()
    }
  })

  document.querySelector('#geo-refresh').addEventListener('click', async () => {
    try {
      const loc = await getBrowserLocation()
      state.detectedLocation = loc
      try {
        state.weather = await fetchWeather(state.apiBase, state.detectedLocation.lat, state.detectedLocation.lng)
      } catch {
        state.weather = null
      }
      setLocationUi()
    } catch {
      setLocationUi()
    }
  })

  // Map panel close button
  document.querySelector('#map-close-btn').addEventListener('click', () => {
    const panel = document.querySelector('#map-panel')
    if (panel) panel.style.display = 'none'
  })
}

const boot = async () => {
  loadState()
  mount()
  bind()
  setLocationUi()
  renderMessages()
  setStatus('checking')
  try {
    await health(state.apiBase)
    setStatus('online')
    await refreshSessions()
    const exist = (state.sessions || []).some((x) => x.session_id === state.sessionId)
    if (exist) {
      await loadSession(state.sessionId)
    } else {
      document.querySelector('#session-id').textContent = state.sessionId
      state.messages = []
      renderMessages()
      setLocationUi()
      renderSessionList()
    }
  } catch {
    setStatus('offline')
  }
}

boot()
