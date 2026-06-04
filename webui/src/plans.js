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

export const plansFromPayload = (payload) => {
  const plans = Array.isArray(payload) ? payload : []
  return plans.map((plan, idx) => {
    const total = typeof plan.total_minutes === 'number' ? `总时长约${(plan.total_minutes / 60).toFixed(1)}小时` : ''
    const validation = plan.validation || {}
    const satisfied = Array.isArray(validation.satisfied) && validation.satisfied.length
      ? `已满足：${validation.satisfied.slice(0, 3).join('；')}`
      : ''
    const rationale = [total, plan.rationale || '', satisfied].filter(Boolean).join('；')
    return {
      title: `方案${idx + 1}`,
      rawTitle: plan.title || `方案${idx + 1}`,
      rationale,
      items: (plan.items || []).map((it) => {
        const poi = it.poi || {}
        const time = it.start && it.end ? `${it.start}-${it.end} ` : ''
        const cat = poi.category ? ` [${poi.category}]` : ''
        const leg = it.travel_from_prev ? ` · ${it.travel_from_prev.mode} ${it.travel_from_prev.minutes}min/${it.travel_from_prev.distance_km}km` : ''
        const dist = typeof poi.distance_from_user === 'number' ? ` · 距约${poi.distance_from_user}km` : ''
        const area = poi.business_area ? ` · 商圈/场馆：${poi.business_area}` : ''
        const address = poi.address ? ` · ${poi.address}` : ''
        const note = it.notes ? ` · ${it.notes}` : ''
        return `${time}${poi.name || '待定地点'}${cat}${dist}${area}${address}${leg}${note}`
      }),
      sourceId: plan.id,
    }
  })
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

export const renderPlanCardsHtml = (plans, activeIdx, planKey = '') => {
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
  </div>
  <div class="plan-actions" style="text-align:center;margin-top:14px">
    <button class="btn btn--primary" data-map-key="${esc(planKey)}" type="button">🗺️ 查看路线地图</button>
  </div>`
}
