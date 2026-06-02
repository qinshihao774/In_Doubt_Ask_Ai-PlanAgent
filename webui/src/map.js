// map.js - Amap route visualization (dynamic SDK loading)
import { state } from './state.js';

let sdkReady = false;
let sdkLoading = null;
let mapInstance = null;   // 跟踪地图实例，销毁旧实例防止 WebGL 泄漏

// ── 坐标提取工具 ──
// 兼容两种 POI 结构：
//   A) { lat, lng }  扁平字段
//   B) { location: { lat, lng } }  嵌套对象
function getLatLng(poi) {
  if (!poi) return null;
  // 优先从 location 子对象取（amap_tools / osm_tools 均显式写入）
  if (poi.location && typeof poi.location.lat === 'number' && typeof poi.location.lng === 'number'
      && !isNaN(poi.location.lat) && !isNaN(poi.location.lng)
      && (poi.location.lat !== 0 || poi.location.lng !== 0)) {
    return { lat: poi.location.lat, lng: poi.location.lng };
  }
  // 回退到扁平字段
  if (typeof poi.lat === 'number' && typeof poi.lng === 'number'
      && !isNaN(poi.lat) && !isNaN(poi.lng)
      && (poi.lat !== 0 || poi.lng !== 0)) {
    return { lat: poi.lat, lng: poi.lng };
  }
  return null;
}

// ── SDK 加载（使用 AMapLoader，符合高德 v2.0 规范）──
function loadAmapSDK() {
  if (sdkReady) return Promise.resolve();
  if (sdkLoading) return sdkLoading;
  sdkLoading = new Promise(async (resolve, reject) => {
    try {
      const resp = await fetch((state.apiBase || location.origin) + '/config/map');
      if (!resp.ok) throw new Error('failed to fetch map config');
      const cfg = await resp.json();
      const key = cfg.amap_key;
      if (!key) throw new Error('amap_key_not_configured');
      // 安全密钥必须在加载 SDK 前配置
      window._AMapSecurityConfig = { securityJsCode: cfg.amap_security_code || '' };
      // 加载 AMapLoader（loader.js 轻量，重复加载无副作用）
      await new Promise((res, rej) => {
        const s = document.createElement('script');
        s.src = 'https://webapi.amap.com/loader.js';
        s.onload = res;
        s.onerror = () => rej(new Error('amap_loader_load_failed'));
        document.head.appendChild(s);
      });
      // 使用 AMapLoader.load 正式加载 JSAPI v2.0
      window.AMapLoader.load({
        key,
        version: '2.0',
        plugins: ['AMap.Scale', 'AMap.ToolBar', 'AMap.Walking'],
      }).then((AMap) => {
        window.AMap = AMap;  // 挂载到全局，供其他函数使用
        sdkReady = true;
        resolve();
      }).catch(reject);
    } catch (e) { reject(e); }
  });
  return sdkLoading;
}

// ── 标记与信息窗 ──
function markerHtml(idx, bg) {
  const label = String(idx + 1);
  return '<div style="width:30px;height:30px;border-radius:50%;background:' + bg +
    ';border:2.5px solid rgba(255,255,255,.92);display:grid;place-items:center;' +
    'font-size:13px;font-weight:800;color:#fff;box-shadow:0 3px 12px rgba(0,0,0,.4)">' +
    label + '</div>';
}

function infoHtml(it) {
  const poi = it.poi;
  let h = '<div style="padding:10px 14px;font-size:13px;line-height:1.6;min-width:180px">' +
    '<div style="font-weight:700;margin-bottom:6px;color:#0b0c18">📍 ' + poi.name + '</div>';
  if (poi.category) h += '<div style="color:#666;font-size:12px">' + poi.category + '</div>';
  if (it.start && it.end)
    h += '<div style="color:#888;font-size:12px;margin-top:4px">⏰ ' + it.start + ' – ' + it.end + '</div>';
  if (it.travel_from_prev)
    h += '<div style="color:#888;font-size:12px">🚶 步行 ' + it.travel_from_prev.minutes +
      ' 分钟 · ' + it.travel_from_prev.distance_km + ' km</div>';
  return h + '</div>';
}

function addMarkers(map, items) {
  const COLORS = ['#00c878','#4ECDC4','#FFD166','#FF6B6B','#A78BFA','#60A5FA','#F472B6','#34D399'];
  const overlays = [];
  items.forEach((it, i) => {
    const ll = getLatLng(it.poi);
    if (!ll) return;
    const pos = [ll.lng, ll.lat];
    const bg = COLORS[i % COLORS.length];
    try {
      const marker = new AMap.Marker({
        position: pos,
        content: markerHtml(i, bg),
        offset: new AMap.Pixel(-15, -15),
        zIndex: 120 - i
      });
      marker.on('click', () => {
        new AMap.InfoWindow({ content: infoHtml(it), offset: new AMap.Pixel(0, -20) }).open(map, pos);
      });
      map.add(marker);
      overlays.push(marker);
    } catch (_) {}
  });
  return overlays;
}

// ── 主入口 ──
export async function renderMap(sessionId, planIndex) {
  if (planIndex === undefined) planIndex = 0;
  const panel = document.getElementById('map-panel');
  const mapDiv = document.getElementById('map-container');
  if (!panel || !mapDiv) return;
  panel.style.display = 'flex';
  mapDiv.innerHTML = '<div style="display:grid;place-items:center;height:100%;color:rgba(231,233,255,.6)">⏳ 正在加载地图…</div>';

  try { await loadAmapSDK(); }
  catch (e) {
    const msg = e.message === 'amap_key_not_configured'
      ? '请在 .env 中配置 MEITUAN_AGENT_AMAP_JS_KEY'
      : '无法加载高德地图 SDK，请检查网络连接';
    mapDiv.innerHTML = '<div style="padding:24px;text-align:center;color:rgba(231,233,255,.7)">' +
      '<div style="font-size:28px;margin-bottom:12px">🗺️</div>' +
      '<div style="font-weight:700;margin-bottom:8px">地图加载失败</div>' +
      '<div style="font-size:12px;color:rgba(231,233,255,.5)">' + msg + '</div></div>';
    return;
  }

  let plans;
  try {
    const resp = await fetch((state.apiBase || location.origin) + '/plans/' + sessionId);
    if (!resp.ok) throw new Error('plans fetch failed');
    plans = await resp.json();
  } catch (e) {
    mapDiv.innerHTML = '<div style="padding:24px;text-align:center;color:rgba(231,233,255,.7)">⚠️ 无法获取行程数据</div>';
    return;
  }
  if (!plans || !plans.length) {
    mapDiv.innerHTML = '<div style="padding:24px;text-align:center;color:rgba(231,233,255,.7)">📋 暂无行程方案</div>';
    return;
  }

  const plan = plans[Math.min(planIndex, plans.length - 1)];
  console.log('[map] plan data:', JSON.stringify(plan).slice(0, 500));
  // 过滤出有有效坐标的 item
  const items = (plan.items || []).filter(it => it.poi && getLatLng(it.poi));
  console.log('[map] valid items:', items.length, '/', (plan.items || []).length);
  if (items.length < 1) {
    mapDiv.innerHTML = '<div style="padding:24px;text-align:center;color:rgba(231,233,255,.7)">📍 行程中无坐标信息</div>';
    return;
  }

  // 销毁旧地图实例，释放 WebGL 上下文
  if (mapInstance) { try { mapInstance.destroy(); } catch (_) {} mapInstance = null; }

  mapDiv.innerHTML = '';
  const first = getLatLng(items[0].poi);

  // 等待容器有实际尺寸（flex 布局需要一帧计算）
  await new Promise((resolve) => {
    let tries = 0;
    const check = () => {
      const w = mapDiv.offsetWidth;
      const h = mapDiv.offsetHeight;
      console.log('[map] container size:', w, 'x', h);
      if (w > 50 && h > 50) return resolve();
      if (++tries > 30) return resolve(); // 最多等 500ms
      requestAnimationFrame(check);
    };
    requestAnimationFrame(check);
  });

  // 埋点标识（强制）
  AMap.getConfig().appname = 'amap-jsapi-skill';

  const map = new AMap.Map('map-container', {
    viewMode: '3D',
    zoom: 14,
    center: [first.lng, first.lat],
    resizeEnable: true,
    mapStyle: 'amap://styles/normal',
  });
  mapInstance = map;
  map.on('complete', () => map.resize());

  // ── 路线序列：用户定位 → POI₁ → POI₂ → …（按时间顺序）──
  const routePts = [];   // 用于路径规划的坐标序列
  const allOverlays = [];

  // 起点：用户当前位置
  const userLoc = state.detectedLocation;
  const hasUserLoc = userLoc && typeof userLoc.lat === 'number' && typeof userLoc.lng === 'number';
  if (hasUserLoc) {
    const userPos = [userLoc.lng, userLoc.lat];
    routePts.push(userPos);
    const userMarker = new AMap.Marker({
      position: userPos,
      content: '<div style="width:32px;height:32px;border-radius:50%;background:#1677ff;' +
        'border:2.5px solid rgba(255,255,255,.92);display:grid;place-items:center;' +
        'font-size:15px;color:#fff;box-shadow:0 3px 12px rgba(0,0,0,.4)">起</div>',
      offset: new AMap.Pixel(-16, -16),
      zIndex: 130,
    });
    map.add(userMarker);
    allOverlays.push(userMarker);
  }

  // POI 标记（按时间顺序编号）
  const poiOverlays = addMarkers(map, items);
  allOverlays.push(...poiOverlays);
  items.forEach(it => {
    const ll = getLatLng(it.poi);
    if (ll) routePts.push([ll.lng, ll.lat]);
  });

  // 使用 setFitView 自动适配视口（高德 v2.0 规范 API）
  if (allOverlays.length > 0) {
    map.setFitView(allOverlays, false, [60, 60, 60, 60], 16);
  } else if (routePts.length === 1) {
    map.setZoomAndCenter(16, routePts[0]);
  }

  // 逐步绘制步行路径：定位 → POI₁ → POI₂ → …
  if (routePts.length >= 2) {
    drawWalkingRoutes(map, routePts);
  }
}

// ── 步行路径规划（调用 AMap.Walking API）──
const ROUTE_COLORS = ['#00c878','#4ECDC4','#FFD166','#FF6B6B','#A78BFA','#60A5FA'];

function drawWalkingRoutes(map, pts) {
  for (let i = 0; i < pts.length - 1; i++) {
    drawOneSegment(map, pts[i], pts[i + 1], ROUTE_COLORS[i % ROUTE_COLORS.length], i + 1);
  }
}

function addSeqLabel(map, mid, color, num) {
  new AMap.Marker({
    position: mid,
    content: '<div style="background:rgba(0,0,0,.72);color:#fff;width:22px;height:22px;' +
      'border-radius:50%;display:grid;place-items:center;font-size:11px;font-weight:800;' +
      'border:2px solid ' + color + '">' + num + '</div>',
    offset: new AMap.Pixel(-11, -11),
    zIndex: 110,
  }).setMap(map);
}

function drawOneSegment(map, origin, dest, color, num) {
  try {
    const walking = new AMap.Walking();
    walking.search(origin, dest, function (status, result) {
      if (status === 'complete' && result.routes && result.routes.length) {
        const path = [];
        result.routes[0].steps.forEach(step => { path.push(...step.path); });
        new AMap.Polyline({
          path,
          strokeColor: color,
          strokeWeight: 5,
          strokeOpacity: 0.85,
          lineJoin: 'round',
          lineCap: 'round',
        }).setMap(map);
        addSeqLabel(map, path[Math.floor(path.length / 2)] || [(origin[0]+dest[0])/2, (origin[1]+dest[1])/2], color, num);
      } else {
        console.warn('[map] Walking route failed, fallback to straight line', status);
        drawFallbackLine(map, origin, dest, color, num);
      }
    });
  } catch (e) {
    console.warn('[map] Walking API error, fallback to straight line', e);
    drawFallbackLine(map, origin, dest, color, num);
  }
}

function drawFallbackLine(map, origin, dest, color, num) {
  new AMap.Polyline({
    path: [origin, dest],
    strokeColor: color,
    strokeWeight: 3,
    strokeOpacity: 0.5,
    strokeStyle: 'dashed',
  }).setMap(map);
  addSeqLabel(map, [(origin[0]+dest[0])/2, (origin[1]+dest[1])/2], color, num);
}

