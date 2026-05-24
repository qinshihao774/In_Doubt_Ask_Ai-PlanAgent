const esc = (s) =>
  (s || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')

export const parsePlans = (content) => {
  const first = content.match(/方案(\d+)[：:]/)
  if (!first) return { intro: null, plans: [] }
  const startIdx = content.indexOf(first[0])
  const intro = content.slice(0, startIdx).trim() || null
  const parts = content.slice(startIdx).split(/(方案\d+[：:])/).filter(Boolean)

  const plans = []
  let cur = ''
  for (const part of parts) {
    const m = part.match(/^方案(\d+)[：:]$/)
    if (m) {
      cur = `方案${m[1]}`
      continue
    }
    if (!cur) continue
    const parsed = parseSinglePlan(cur, part.trim())
    if (parsed) plans.push(parsed)
    cur = ''
  }
  return { intro, plans }
}

export const parseSinglePlan = (title, text) => {
  const lines = (text || '').split('\n').map((x) => x.trim()).filter(Boolean)
  let rationale = ''
  const items = []
  let inRationale = false
  for (const line of lines) {
    if (line.startsWith('理由：') || line.startsWith('理由:')) {
      rationale = line.slice(3).trim()
      inRationale = true
      continue
    }
    if (inRationale && !line.startsWith('-') && !line.startsWith('方案')) continue
    inRationale = false
    if (line.startsWith('-')) items.push(line)
  }
  const rawTitle = lines[0] || title
  return {
    title,
    rawTitle,
    rationale,
    items: items.length ? items : [text.trim()],
  }
}

export const renderPlanCardsHtml = (plans, activeIdx) => {
  const n = plans.length
  if (!n) return ''
  let cards = ''
  for (let idx = 0; idx < n; idx += 1) {
    const plan = plans[idx]
    let diff = idx - activeIdx
    if (n > 1) {
      diff = ((diff % n) + n) % n
      if (diff > n / 2) diff -= n
    }
    const abs = Math.abs(diff)
    const cls = abs === 0 ? 'plan-card--active' : abs === 1 ? (diff < 0 ? 'plan-card--left' : 'plan-card--right') : 'plan-card--back'
    const itemsHtml = (plan.items || [])
      .map((it) => `<div class="plan-card__item">${esc(it)}</div>`)
      .join('')
    const rationaleHtml = plan.rationale ? `<div class="plan-card__rationale">${esc(plan.rationale)}</div>` : ''
    const z = 50 - abs
    cards += `<div class="plan-card ${cls}" data-plan-idx="${idx}" style="--offset:${diff};--abs:${abs};--z:${z}">
      <div class="plan-card__title">
        <span class="plan-index">${idx + 1}</span>
        <span>${esc(plan.rawTitle || plan.title)}</span>
      </div>
      ${rationaleHtml}
      <div class="plan-card__items">${itemsHtml}</div>
    </div>`
  }
  return `<div class="plan-carousel" data-count="${n}">
    <button class="plan-arrow plan-arrow--left" data-nav="prev" data-count="${n}" type="button" aria-label="上一张">‹</button>
    <div class="plan-carousel__stage">${cards}</div>
    <button class="plan-arrow plan-arrow--right" data-nav="next" data-count="${n}" type="button" aria-label="下一张">›</button>
  </div>`
}
