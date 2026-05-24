export const getBrowserLocation = () =>
  new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error('no_geolocation'))
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        resolve({
          lat: Number(pos.coords.latitude.toFixed(6)),
          lng: Number(pos.coords.longitude.toFixed(6)),
          label: `浏览器定位 (~${Math.round(pos.coords.accuracy)}m)`,
        })
      },
      (err) => reject(err),
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 },
    )
  })

export const reverseGeocodeNominatim = async (lat, lng) => {
  const u = new URL('https://nominatim.openstreetmap.org/reverse')
  u.searchParams.set('lat', String(lat))
  u.searchParams.set('lon', String(lng))
  u.searchParams.set('format', 'jsonv2')
  const r = await fetch(u.toString(), {
    headers: { 'User-Agent': 'meituan-competition-agent/1.0' },
  })
  if (!r.ok) throw new Error('reverse_failed')
  const j = await r.json()
  return j.display_name || `${lat}, ${lng}`
}

