const clamp = (v, a, b) => (v < a ? a : v > b ? b : v)

const hash = (x, y) => {
  const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453123
  return s - Math.floor(s)
}

const noise2 = (x, y) => {
  const xi = Math.floor(x)
  const yi = Math.floor(y)
  const xf = x - xi
  const yf = y - yi
  const u = xf * xf * (3 - 2 * xf)
  const v = yf * yf * (3 - 2 * yf)
  const n00 = hash(xi, yi)
  const n10 = hash(xi + 1, yi)
  const n01 = hash(xi, yi + 1)
  const n11 = hash(xi + 1, yi + 1)
  const nx0 = n00 + (n10 - n00) * u
  const nx1 = n01 + (n11 - n01) * u
  return nx0 + (nx1 - nx0) * v
}

const fbm = (x, y) => {
  let f = 0
  let a = 0.5
  let fx = x
  let fy = y
  for (let i = 0; i < 4; i += 1) {
    f += a * noise2(fx, fy)
    fx *= 2
    fy *= 2
    a *= 0.5
  }
  return f
}

export const initSmoke = (canvas, opts = {}) => {
  if (!canvas) return () => {}

  const dpr = Math.max(1, window.devicePixelRatio || 1)
  const scale = clamp(opts.scale ?? 0.75, 0.35, 1)
  const cfg = {
    max: opts.max ?? 900,
    emit: opts.emit ?? 12,
    fade: clamp(opts.fade ?? 0.09, 0.02, 0.22),
    speed: clamp(opts.speed ?? 1.1, 0.4, 2.2),
    curl: clamp(opts.curl ?? 2.1, 0.6, 4.0),
    size: clamp(opts.size ?? 26, 10, 64),
    jitter: clamp(opts.jitter ?? 0.8, 0, 2.5),
    hue: opts.hue ?? 140,
    zoom: clamp(opts.zoom ?? 1.012, 1.0, 1.05),
  }

  const ctx = canvas.getContext('2d', { alpha: true })
  const prev = document.createElement('canvas')
  const prevCtx = prev.getContext('2d', { alpha: true })
  let w = 0
  let h = 0
  let raf = 0

  const particles = []
  const mouse = { x: 0, y: 0, vx: 0, vy: 0, down: false, seen: false }
  let last = performance.now()

  const resize = () => {
    const rw = Math.floor(window.innerWidth * dpr * scale)
    const rh = Math.floor(window.innerHeight * dpr * scale)
    w = rw
    h = rh
    canvas.width = w
    canvas.height = h
    prev.width = w
    prev.height = h
    canvas.style.width = `${window.innerWidth}px`
    canvas.style.height = `${window.innerHeight}px`
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.imageSmoothingEnabled = true
    prevCtx.setTransform(1, 0, 0, 1, 0, 0)
    prevCtx.imageSmoothingEnabled = true
  }

  const toLocal = (clientX, clientY) => {
    const x = (clientX * dpr * scale)
    const y = (clientY * dpr * scale)
    return { x, y }
  }

  const emit = (x, y, dx, dy) => {
    const sp = Math.sqrt(dx * dx + dy * dy)
    const base = clamp(sp * 0.08, 0.2, 2.0)
    const count = cfg.emit + Math.floor(base * 12)
    for (let i = 0; i < count; i += 1) {
      if (particles.length >= cfg.max) particles.shift()
      const a = Math.random() * Math.PI * 2
      const r = (Math.random() ** 0.35) * 10
      const sx = x + Math.cos(a) * r
      const sy = y + Math.sin(a) * r
      const v = (0.22 + Math.random() * 0.78) * (cfg.speed * (0.75 + base))
      const vx = dx * 0.006 + Math.cos(a) * v
      const vy = dy * 0.006 + Math.sin(a) * v
      const life = 1.2 + Math.random() * 1.6
      const size = cfg.size * (0.55 + Math.random() * 0.85)
      const hue = cfg.hue + (Math.random() * 24 - 12)
      const sat = 65 + Math.random() * 18
      const lum = 55 + Math.random() * 10
      particles.push({ x: sx, y: sy, vx, vy, life, size, hue, sat, lum, age: 0 })
    }
  }

  const step = (t) => {
    raf = requestAnimationFrame(step)
    const now = t
    const dt = clamp((now - last) / 1000, 0.008, 0.05)
    last = now

    ctx.globalCompositeOperation = 'source-over'
    ctx.globalAlpha = 1
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.clearRect(0, 0, w, h)

    ctx.save()
    ctx.translate(w / 2, h / 2)
    ctx.scale(cfg.zoom, cfg.zoom)
    ctx.translate(-w / 2, -h / 2)
    ctx.globalAlpha = 1 - cfg.fade
    ctx.drawImage(prev, 0, 0)
    ctx.restore()

    ctx.globalAlpha = 1
    ctx.fillStyle = `rgba(0,0,0,${cfg.fade})`
    ctx.fillRect(0, 0, w, h)
    ctx.globalCompositeOperation = 'lighter'

    const time = now * 0.00012
    const fx = 0.0026
    const fy = 0.0026

    for (let i = particles.length - 1; i >= 0; i -= 1) {
      const p = particles[i]
      p.age += dt
      if (p.age >= p.life) {
        particles.splice(i, 1)
        continue
      }

      const nx = p.x * fx + time
      const ny = p.y * fy - time * 0.9
      const n = fbm(nx, ny)
      const n2 = fbm(nx + 19.7, ny + 7.3)
      const ang = (n * 2 - 1) * Math.PI * cfg.curl
      const ax = Math.cos(ang) * 26
      const ay = Math.sin(ang) * 26
      const curlx = (n2 - n) * 180
      const curly = (n - n2) * 180

      p.vx += (ax + curlx) * dt
      p.vy += (ay + curly) * dt
      p.vx *= 0.975
      p.vy *= 0.975
      p.x += p.vx * 60 * dt
      p.y += p.vy * 60 * dt

      const k = 1 - p.age / p.life
      const alpha = clamp(0.26 * k * k, 0, 0.26)
      const s = p.size * (0.55 + 1.35 * (1 - k))
      const gx = p.x
      const gy = p.y

      const grad = ctx.createRadialGradient(gx, gy, 0, gx, gy, s)
      grad.addColorStop(0, `hsla(${p.hue},${p.sat}%,${p.lum}%,${alpha})`)
      grad.addColorStop(0.55, `hsla(${p.hue + 6},${p.sat}%,${p.lum - 6}%,${alpha * 0.55})`)
      grad.addColorStop(1, `hsla(${p.hue + 18},${p.sat - 10}%,${p.lum - 16}%,0)`)
      ctx.fillStyle = grad
      ctx.beginPath()
      ctx.arc(gx, gy, s, 0, Math.PI * 2)
      ctx.fill()
    }

    prevCtx.globalCompositeOperation = 'source-over'
    prevCtx.globalAlpha = 1
    prevCtx.setTransform(1, 0, 0, 1, 0, 0)
    prevCtx.clearRect(0, 0, w, h)
    prevCtx.drawImage(canvas, 0, 0)

    if (mouse.seen) {
      if (Math.abs(mouse.vx) + Math.abs(mouse.vy) > 0.1) {
        emit(mouse.x, mouse.y, mouse.vx, mouse.vy)
      }
      mouse.vx *= 0.82
      mouse.vy *= 0.82
      if (cfg.jitter > 0.01 && particles.length < cfg.max) {
        const j = cfg.jitter
        emit(mouse.x, mouse.y, (Math.random() - 0.5) * 40 * j, (Math.random() - 0.5) * 40 * j)
      }
    }
  }

  const onMove = (e) => {
    const pt = toLocal(e.clientX, e.clientY)
    if (!mouse.seen) {
      mouse.x = pt.x
      mouse.y = pt.y
      mouse.seen = true
      return
    }
    mouse.vx += (pt.x - mouse.x) * 0.65
    mouse.vy += (pt.y - mouse.y) * 0.65
    mouse.x = pt.x
    mouse.y = pt.y
  }

  resize()
  ctx.clearRect(0, 0, w, h)
  prevCtx.clearRect(0, 0, w, h)
  raf = requestAnimationFrame(step)

  window.addEventListener('resize', resize, { passive: true })
  window.addEventListener('mousemove', onMove, { passive: true })

  return () => {
    cancelAnimationFrame(raf)
    window.removeEventListener('resize', resize)
    window.removeEventListener('mousemove', onMove)
  }
}
