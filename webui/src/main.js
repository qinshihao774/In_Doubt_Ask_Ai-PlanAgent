import './style.css'
import { health, initSession, streamChat } from './api'
import { state, loadState, resetState } from './state'
import { parsePlans, renderPlanCardsHtml } from './plans'
import { renderPipeline } from './pipeline'
import { getBrowserLocation, reverseGeocodeNominatim } from './location'

const esc = (s) =>
  (s || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')

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
      <button class="btn btn--primary geo-btn" id="geo-allow">启用定位</button>
      <button class="btn btn--ghost geo-btn" id="geo-skip">跳过</button>
      <button class="btn btn--icon geo-icon" id="geo-refresh" title="刷新定位" aria-label="刷新定位">
        <span class="geo-icon__dot"></span>
      </button>
    </div>
    <div class="loc-badge" id="loc-badge" style="display:none"></div>
  </div>
  <header class="hero">
    <div class="hero-icon">🍜</div>
    <h1 class="hero-title">私人规划执行助理</h1>
    <div class="hero-subtitle">INTELLIGENT PLANNING · FLUID EXPERIENCE</div>
  </header>
  <main class="layout">
    <aside class="sidebar">
      <div class="status-badge" id="status-badge">
        <span class="status-dot"></span>
        <span class="status-text">连接检测中</span>
      </div>
      <div class="divider"></div>
      <div class="session-card">
        <div class="session-card__label">当前会话</div>
        <div class="session-card__id" id="session-id"></div>
      </div>
      <div class="session-card session-card--mini" id="detected-loc-card" style="display:none"></div>
      <button class="btn btn--ghost btn--block" id="reset-session">重置会话</button>
    </aside>
    <section class="chat">
      <div class="messages" id="messages"></div>
      <div class="processing" id="processing" style="display:none">
        <div id="pipeline"></div>
        <div id="thinking"></div>
      </div>
      <form class="composer" id="composer">
        <input class="composer__input" id="prompt" placeholder="描述你的需求，例如：下午2点出发，带5岁娃，老婆减脂，帮我规划4-6小时..." autocomplete="off"/>
        <button class="btn btn--primary composer__send" type="submit" aria-label="发送">↗</button>
      </form>
    </section>
  </main>`
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
    .map((m) => {
      if (m.role === 'user') {
        return `<div class="message-row message-row--user">
          <div class="message-bubble message-bubble--user">${esc(m.content)}</div>
          <div class="avatar avatar--user">你</div>
        </div>`
      }

      const { intro, plans } = parsePlans(m.content || '')
      if (!plans.length) {
        return `<div class="message-row message-row--assistant">
          <div class="avatar avatar--ai">AI</div>
          <div class="message-bubble message-bubble--assistant">${esc(m.content).replaceAll('\n', '<br>')}</div>
        </div>`
      }

      const activeIdx = Math.min(state.activePlanIndex, plans.length - 1)
      const introHtml = intro ? `<div class="plan-intro">${esc(intro)}</div>` : ''
      const cardsHtml = renderPlanCardsHtml(plans, activeIdx)
      const dots = plans
        .map((_, i) => `<button class="dot ${i === activeIdx ? 'dot--on' : ''}" data-dot="${i}" type="button">${i === activeIdx ? '●' : '○'}</button>`)
        .join('')
      return `<div class="message-row message-row--assistant">
        <div class="avatar avatar--ai">AI</div>
        <div class="plan-wrap">
          ${introHtml}
          ${cardsHtml}
          <div class="plan-actions">
            <button class="btn btn--primary btn--block" data-pick="${activeIdx}" type="button">就选它！</button>
          </div>
          <div class="plan-dots">${dots}</div>
          <div class="plan-caption">方案 ${activeIdx + 1} / ${plans.length}</div>
        </div>
      </div>`
    })
    .join('')

  box.querySelectorAll('[data-dot]').forEach((el) => {
    el.addEventListener('click', () => {
      state.activePlanIndex = Number(el.getAttribute('data-dot') || '0') || 0
      renderMessages()
    })
  })
  box.querySelectorAll('[data-pick]').forEach((el) => {
    el.addEventListener('click', () => {
      const idx = Number(el.getAttribute('data-pick') || '0') || 0
      sendMessage(`确认 方案${idx + 1}`)
    })
  })
  box.querySelectorAll('[data-nav]').forEach((el) => {
    el.addEventListener('click', () => {
      const dir = el.getAttribute('data-nav')
      const n = Number(el.getAttribute('data-count') || '0') || 0
      if (n <= 1) return
      if (dir === 'prev') state.activePlanIndex = (state.activePlanIndex - 1 + n) % n
      else state.activePlanIndex = (state.activePlanIndex + 1) % n
      renderMessages()
    })
  })

  box.scrollTop = box.scrollHeight
}

const setLocationUi = () => {
  const badge = document.querySelector('#loc-badge')
  const loc = state.detectedLocation
  if (!loc) {
    badge.style.display = 'none'
  } else {
    badge.style.display = 'flex'
    badge.innerHTML = `<span class="loc-dot"></span><span class="loc-text" title="${esc(loc.label)}">${esc(loc.label)}</span>`
    const card = document.querySelector('#detected-loc-card')
    card.style.display = 'block'
    card.innerHTML = `<div class="session-card__label">探测位置</div><div class="session-card__id">📌 ${esc(loc.label)}</div>`
  }

  const showPerm = !state.locationPermissionDecided
  document.querySelector('#geo-allow').style.display = showPerm ? 'inline-flex' : 'none'
  document.querySelector('#geo-skip').style.display = showPerm ? 'inline-flex' : 'none'
  document.querySelector('#geo-refresh').style.display = state.locationPermission === 'granted' ? 'inline-flex' : 'none'
}

const showProcessing = (on) => {
  document.querySelector('#processing').style.display = on ? 'block' : 'none'
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

  state.messages.push({ role: 'assistant', content: accumulated || '抱歉，服务暂时不可用。' })
  state.isProcessing = false
  showProcessing(false)
  renderMessages()
}

const bind = () => {
  document.querySelector('#session-id').textContent = state.sessionId

  document.querySelector('#composer').addEventListener('submit', (e) => {
    e.preventDefault()
    const input = document.querySelector('#prompt')
    const v = (input.value || '').trim()
    input.value = ''
    sendMessage(v)
  })

  document.querySelector('#reset-session').addEventListener('click', async () => {
    resetState()
    document.querySelector('#session-id').textContent = state.sessionId
    state.messages = []
    renderMessages()
    try {
      await initSession(state.apiBase, state.sessionId)
    } catch {
      setStatus('offline')
    }
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
      setLocationUi()
    } catch {
      setLocationUi()
    }
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
    await initSession(state.apiBase, state.sessionId)
  } catch {
    setStatus('offline')
  }
}

boot()
