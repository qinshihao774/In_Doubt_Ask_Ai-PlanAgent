const esc = (s) =>
  (s || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')

export const renderPipeline = (root, stages, states) => {
  if (!root) return
  if (!stages || !stages.length) {
    root.innerHTML = ''
    return
  }

  let active = null
  for (const s of stages) {
    if (states?.[s.id] === 'running') {
      active = s
      break
    }
  }

  let nodes = ''
  for (let i = 0; i < stages.length; i += 1) {
    const stage = stages[i]
    const status = states?.[stage.id] || 'pending'
    const dotClass = `pipeline-node__dot--${status}`
    const labelClass = status === 'running' ? 'pipeline-node__label--active' : status === 'done' ? 'pipeline-node__label--done' : ''
    let dot = esc(stage.icon || '○')
    if (status === 'done') dot = '✓'
    if (status === 'error') dot = '✗'

    nodes += `<div class="pipeline-node">
      <div class="pipeline-node__dot ${dotClass}">${dot}</div>
      <div class="pipeline-node__label ${labelClass}">${esc(stage.label || stage.id)}</div>
    </div>`

    if (i < stages.length - 1) {
      const lineClass = status === 'done' ? 'pipeline-connector__line--done' : status === 'running' ? 'pipeline-connector__line--active' : ''
      nodes += `<div class="pipeline-connector"><div class="pipeline-connector__line ${lineClass}"></div></div>`
    }
  }

  const statusBar = active
    ? `<div class="pipeline-status-bar">
      <span class="pipeline-status-bar__icon">${esc(active.icon || '⚡')}</span>
      <span class="pipeline-status-bar__text">${esc(active.active_msg || '处理中...')}</span>
    </div>`
    : ''

  root.innerHTML = `<div class="pipeline-wrapper">
    <div class="pipeline-flow">${nodes}</div>
    ${statusBar}
  </div>`
}

