"""
私人规划执行助理 — Inspire UI 流体设计 v2.0
设计灵感: inspira-ui.com
核心理念: 极光背景 · 流光边框 · 3D变换 · 粒子特效 · 流动渐变
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import uuid
from typing import Generator

import httpx
import streamlit as st
from dotenv import load_dotenv

try:
    from streamlit_geolocation import streamlit_geolocation
except ImportError:
    streamlit_geolocation = None

sys.path.insert(0, os.path.dirname(__file__))
from styles.inspire_ui import inject_css

load_dotenv()

API_BASE = os.getenv("MEITUAN_AGENT_API_BASE", "http://127.0.0.1:8000")


def _img_b64(path: str) -> str:
    """将本地图片转为 base64 data URI"""
    try:
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        mime = "image/png" if ext == "png" else "image/jpeg"
        return f"data:{mime};base64,{data}"
    except Exception:
        return ""


# 头像 base64
_MEDIA = os.path.join(os.path.dirname(__file__), "..", "..", "比赛设计文档_media")
AI_AVATAR = _img_b64(os.path.join(_MEDIA, "ai.png"))
USER_AVATAR = _img_b64(os.path.join(_MEDIA, "OIP_m.png"))

_AI_AVATAR_HTML = f'<img class="chat-avatar chat-avatar--ai" src="{AI_AVATAR}" alt="AI">'
_USER_AVATAR_HTML = f'<img class="chat-avatar chat-avatar--user" src="{USER_AVATAR}" alt="User">'

THINKING_SKELETON_HTML = f"""
<div class="message-row message-row--assistant">
  {_AI_AVATAR_HTML}
  <div class="thinking-indicator">
    <div class="thinking-ring"></div>
    <div class="thinking-text">正在理解你的需求...</div>
    <div class="thinking-progress"><div class="thinking-progress-bar"></div></div>
    <div class="thinking-dots"><span></span><span></span><span></span></div>
    <div class="thinking-long-wait">Agent 正在深度思考中，请耐心等待...</div>
  </div>
</div>
"""

THINKING_STATUS_HTML = f"""
<div class="message-row message-row--assistant">
  {_AI_AVATAR_HTML}
  <div class="thinking-indicator">
    <div class="thinking-ring"></div>
    <div class="thinking-text">{{status_text}}</div>
    <div class="thinking-progress"><div class="thinking-progress-bar"></div></div>
    <div class="thinking-dots"><span></span><span></span><span></span></div>
    <div class="thinking-long-wait">Agent 正在深度思考中，请耐心等待...</div>
  </div>
</div>
"""


class InspireChatApp:
    """私人规划执行助理"""

    def __init__(self):
        self._init_page_config()
        self._inject_styles()
        self.session_id = self._ensure_session()
        self._check_connection()

    def _init_page_config(self):
        st.set_page_config(
            page_title="私人规划执行助理",
            page_icon="🍜",
            layout="wide",
            initial_sidebar_state="expanded",
        )

    def _inject_styles(self):
        inject_css()

    def _ensure_session(self) -> str:
        if "session_id" not in st.session_state:
            st.session_state.session_id = f"sess_{uuid.uuid4().hex[:10]}"
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "connection_status" not in st.session_state:
            st.session_state.connection_status = "checking"
        if "is_processing" not in st.session_state:
            st.session_state.is_processing = False
        if "detected_location" not in st.session_state:
            st.session_state.detected_location = None
        if "active_plan_index" not in st.session_state:
            st.session_state.active_plan_index = 0
        return st.session_state.session_id

    def _check_connection(self):
        try:
            response = httpx.get(f"{API_BASE}/health", timeout=5)
            if response.status_code == 200:
                st.session_state.connection_status = "online"
                self._detect_user_location()
                self._init_backend_session()
            else:
                st.session_state.connection_status = "offline"
        except Exception:
            st.session_state.connection_status = "offline"

    def _detect_user_location(self):
        if st.session_state.get("detected_location"):
            return

        params = st.query_params
        lat_str = params.get("lat")
        lng_str = params.get("lng")
        label = params.get("label")
        if lat_str and lng_str:
            try:
                st.session_state.detected_location = {
                    "lat": float(lat_str),
                    "lng": float(lng_str),
                    "label": label or "浏览器定位",
                }
                st.query_params.clear()
                return
            except (ValueError, TypeError):
                pass

        if not st.session_state.get("_geo_requested"):
            st.session_state._geo_requested = True
            import streamlit.components.v1 as components
            components.html("""
            <script>
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    function(pos) {
                        var lat = pos.coords.latitude.toFixed(6);
                        var lng = pos.coords.longitude.toFixed(6);
                        var url = new URL(window.parent.location);
                        url.searchParams.set('lat', lat);
                        url.searchParams.set('lng', lng);
                        url.searchParams.set('label', '浏览器定位 (~' + Math.round(pos.coords.accuracy) + 'm)');
                        window.parent.location.href = url.toString();
                    },
                    function(err) { console.log('Geolocation: ' + err.message); },
                    { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
                );
            }
            </script>
            """, height=0)

        if not st.session_state.get("detected_location"):
            try:
                with httpx.Client(timeout=6) as client:
                    resp = client.get("https://ipwho.is/")
                    resp.raise_for_status()
                    data = resp.json()
                if data.get("success"):
                    lat = data.get("latitude")
                    lng = data.get("longitude")
                    if lat is not None and lng is not None:
                        label_parts = [data.get("city"), data.get("region"), data.get("country")]
                        label = " · ".join([x for x in label_parts if x]) or "IP 定位"
                        st.session_state.detected_location = {
                            "lat": float(lat), "lng": float(lng), "label": label,
                        }
            except Exception:
                pass

    def _init_backend_session(self):
        try:
            with httpx.Client(timeout=10) as client:
                client.post(f"{API_BASE}/init", json={"session_id": self.session_id})
        except Exception:
            pass

    def _stream_chat(self, message: str) -> Generator[dict, None, None]:
        payload = {"session_id": self.session_id, "message": message}
        detected_location = st.session_state.get("detected_location")
        if detected_location:
            payload["user_location"] = detected_location
        try:
            with httpx.Client(timeout=None) as client:
                with client.stream("POST", f"{API_BASE}/chat/stream", json=payload) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if not data_str:
                            continue
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        event_type = data.get("type", "")
                        if event_type == "session":
                            continue
                        if event_type == "status":
                            yield {"type": "status", "content": data.get("content", ""), "is_done": False}
                        elif event_type == "delta":
                            yield {"type": "delta", "content": data.get("content", ""), "is_done": False}
                        elif event_type == "done":
                            yield {"type": "done", "content": "", "is_done": True}
                            return
        except Exception:
            yield {"type": "error", "content": "连接出现问题，请稍后重试。", "is_done": True}

    # ═══════════════════════════════════════════
    # 方案解析
    # ═══════════════════════════════════════════

    @staticmethod
    def _parse_plans(content: str) -> tuple[str | None, list[dict]]:
        plans: list[dict] = []
        intro: str | None = None
        first = re.search(r'方案(\d+)[：:]', content)
        if not first:
            return None, []
        intro = content[:first.start()].strip() or None
        parts = re.split(r'(方案\d+[：:])', content[first.start():])
        current_title = ""
        for part in parts:
            m = re.match(r'方案(\d+)[：:]', part)
            if m:
                current_title = f"方案{m.group(1)}"
            elif current_title and part.strip():
                plan_dict = InspireChatApp._parse_single_plan(current_title, part.strip())
                if plan_dict:
                    plans.append(plan_dict)
                current_title = ""
        return intro, plans

    @staticmethod
    def _parse_single_plan(title: str, text: str) -> dict | None:
        lines = text.strip().split('\n')
        rationale = ""
        items: list[str] = []
        in_rationale = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith('理由：') or stripped.startswith('理由:'):
                rationale = stripped[3:].strip()
                in_rationale = True
                continue
            if in_rationale and not stripped.startswith('-') and not stripped.startswith('方案'):
                continue
            in_rationale = False
            if stripped.startswith('-'):
                items.append(stripped)
        if not items:
            items = [text.strip()]
        return {
            "title": title,
            "raw_title": text.split('\n')[0].strip() if text else title,
            "rationale": rationale,
            "items": items,
        }

    # ═══════════════════════════════════════════
    # 方案卡片渲染
    # ═══════════════════════════════════════════

    def _render_plan_cards(self, plans: list[dict], intro: str | None, message_index: int):
        plan_count = len(plans)
        if plan_count == 0:
            return

        active_idx = st.session_state.get("active_plan_index", 0)
        if active_idx >= plan_count:
            active_idx = 0
            st.session_state.active_plan_index = 0

        if intro:
            st.markdown(
                f"""<div style="color:var(--text-secondary);font-size:0.86rem;margin-bottom:14px;line-height:1.6;">{intro}</div>""",
                unsafe_allow_html=True,
            )

        # 构建 DOM 顺序：活跃卡片排第一，其余按距离排后面
        ordered = []
        for dist in range(plan_count):
            idx = (active_idx + dist) % plan_count
            ordered.append((idx, plans[idx]))

        # 单次 st.markdown 渲染全部卡片 → DOM 兄弟节点 → 叠层 CSS 生效
        all_cards_html = '<div class="plan-stack" style="min-height:320px;">'
        for order_pos, (orig_idx, plan) in enumerate(ordered):
            if order_pos == 0:
                card_class = "plan-card--active"
            elif order_pos == 1:
                card_class = "plan-card--behind-1"
            else:
                card_class = "plan-card--behind-2"

            raw_title = plan.get("raw_title", plan["title"])
            rationale = plan.get("rationale", "")
            items = plan.get("items", [])
            plan_num = orig_idx + 1

            items_html = ""
            for item in items:
                safe_item = item.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                items_html += f'<div class="plan-card__item">{safe_item}</div>'

            rationale_html = ""
            if rationale:
                safe_rationale = rationale.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                rationale_html = f'<div class="plan-card__rationale">{safe_rationale}</div>'

            all_cards_html += f"""<div class="plan-card {card_class}">
              <div class="plan-card__title">
                <span class="plan-index">{plan_num}</span>
                <span>{raw_title}</span>
              </div>
              {rationale_html}
              <div class="plan-card__items">{items_html}</div>
            </div>"""
        all_cards_html += '</div>'

        st.markdown(all_cards_html, unsafe_allow_html=True)

        # 只有活跃卡片显示「就选它！」
        _, btn_col, _ = st.columns([3, 2, 3])
        with btn_col:
            if st.button(
                "就选它！",
                key=f"pick_{message_index}_{active_idx}",
                use_container_width=True,
                type="primary",
            ):
                st.session_state.pending_message = f"确认 方案{active_idx + 1}"
                st.rerun()

        # 导航圆点
        _, nav_center, _ = st.columns([2, 1, 2])
        with nav_center:
            dots = st.columns(plan_count)
            for i in range(plan_count):
                with dots[i]:
                    if st.button(
                        "●" if i == active_idx else "○",
                        key=f"dot_{message_index}_{i}",
                    ):
                        st.session_state.active_plan_index = i
                        st.rerun()

        st.caption(f"方案 {active_idx + 1} / {plan_count}")

    # ═══════════════════════════════════════════
    # 渲染方法
    # ═══════════════════════════════════════════

    def render_header(self):
        st.markdown("""
        <div class="hero-wrapper">
            <div class="hero-glow"></div>
            <div class="hero-icon">🍜</div>
            <h1 class="hero-title">私人规划执行助理</h1>
            <p class="hero-subtitle">Intelligent Planning · Fluid Experience</p>
        </div>
        """, unsafe_allow_html=True)

    def render_sidebar(self):
        with st.sidebar:
            self._render_connection_status()
            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
            self._render_session_card()

    def _render_connection_status(self):
        status = st.session_state.get("connection_status", "checking")
        if status == "online":
            st.markdown("""
            <div class="status-badge status-badge--online">
                <span class="status-dot status-dot--live"></span>
                <span>服务在线</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="status-badge status-badge--offline">
                <span class="status-dot status-dot--dead"></span>
                <span>服务离线</span>
            </div>
            """, unsafe_allow_html=True)
            st.error("无法连接到后端服务，请确保后端已启动并刷新页面")

    def _render_session_card(self):
        sid = st.session_state.session_id
        st.markdown(f"""
        <div class="session-card">
            <div class="session-card__label">当前会话</div>
            <div class="session-card__id">{sid}</div>
        </div>
        """, unsafe_allow_html=True)

        detected_location = st.session_state.get("detected_location")
        if detected_location:
            st.markdown(
                f"""
                <div class="session-card" style="margin-top:12px;">
                    <div class="session-card__label">探测位置</div>
                    <div class="session-card__id" style="font-size:0.8rem;">📌 {detected_location.get('label', '未知')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if st.button("重置会话", use_container_width=True, type="secondary"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    def render_chat_interface(self):
        for idx, msg in enumerate(st.session_state.messages):
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                st.markdown(f"""
                <div class="message-row message-row--user">
                    <div class="message-bubble message-bubble--user">{content}</div>
                    {_USER_AVATAR_HTML}
                </div>
                """, unsafe_allow_html=True)
            else:
                intro, plans = self._parse_plans(content)
                if plans:
                    st.markdown(
                        f'<div class="message-row message-row--assistant">{_AI_AVATAR_HTML}</div>',
                        unsafe_allow_html=True,
                    )
                    self._render_plan_cards(plans, intro, idx)
                else:
                    st.markdown(f"""
                    <div class="message-row message-row--assistant">
                        {_AI_AVATAR_HTML}
                        <div class="message-bubble message-bubble--assistant">{content}</div>
                    </div>
                    """, unsafe_allow_html=True)

        if st.session_state.get("is_processing"):
            self._process_ai_response()

        prompt = st.chat_input("描述你的需求，例如：下午2点出发，带5岁娃，老婆减脂，帮我规划4-6小时...")

        pending = st.session_state.get("pending_message")
        if pending and not prompt:
            prompt = pending
            st.session_state.pending_message = None

        if prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.session_state.is_processing = True
            st.rerun()

    def _process_ai_response(self):
        if not st.session_state.get("is_processing"):
            return

        last_message = None
        for msg in reversed(st.session_state.messages):
            if msg["role"] == "user":
                last_message = msg["content"]
                break
        if not last_message:
            st.session_state.is_processing = False
            return

        placeholder = st.empty()
        accumulated = ""
        placeholder.markdown(THINKING_SKELETON_HTML, unsafe_allow_html=True)

        try:
            for event in self._stream_chat(last_message):
                et = event["type"]

                if et == "status":
                    placeholder.markdown(
                        THINKING_STATUS_HTML.format(status_text=event["content"]),
                        unsafe_allow_html=True,
                    )

                elif et == "delta":
                    accumulated += event["content"]
                    safe = accumulated.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
                    placeholder.markdown(
                        f"""<div class="message-row message-row--assistant">
                          {_AI_AVATAR_HTML}
                          <div class="message-bubble message-bubble--assistant">
                            {safe}<span class="typing-cursor"></span>
                          </div>
                        </div>""",
                        unsafe_allow_html=True,
                    )

                elif et == "done":
                    if accumulated:
                        st.session_state.messages.append({"role": "assistant", "content": accumulated})
                        st.session_state.is_processing = False
                        st.rerun()  # 立即重渲染 → 方案卡片即刻呈现

                elif et == "error":
                    st.session_state.messages.append({"role": "assistant", "content": event["content"]})
                    st.session_state.is_processing = False
                    st.rerun()

        except Exception as e:
            st.session_state.messages.append(
                {"role": "assistant", "content": f"抱歉，处理消息时出现问题：{str(e)}"}
            )
            st.session_state.is_processing = False
            st.rerun()


def main():
    app = InspireChatApp()

    if "location_permission" not in st.session_state:
        st.session_state.location_permission = "unknown"
    if "location_permission_decided" not in st.session_state:
        st.session_state.location_permission_decided = False

    if not st.session_state.location_permission_decided:
        st.markdown("""
        <div style="max-width:720px;margin:14px auto 0 auto;padding:18px 22px;border-radius:12px;
                    border:1px solid #30363d;background:#161b22;">
          <div style="font-size:0.94rem;font-weight:600;color:#e6edf3;margin-bottom:6px;">位置授权</div>
          <div style="font-size:0.84rem;color:#8b949e;line-height:1.5;">
            以你当前所在位置为中心检索真实商铺与路线。也可先拒绝，系统会回退到 IP 粗定位。
          </div>
        </div>
        """, unsafe_allow_html=True)
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("启用精确定位（推荐）", use_container_width=True, type="primary"):
                st.session_state.location_permission = "granted"
                st.session_state.location_permission_decided = True
                st.rerun()
        with c2:
            if st.button("暂不授权", use_container_width=True, type="secondary"):
                st.session_state.location_permission = "denied"
                st.session_state.location_permission_decided = True
                st.rerun()

    if st.session_state.location_permission == "granted" and not st.session_state.get("browser_location_fetched"):
        if streamlit_geolocation is not None:
            try:
                geo_data = streamlit_geolocation()
            except Exception:
                geo_data = None
                st.session_state.location_permission = "denied"
                st.warning("精确定位组件加载失败，已回退到 IP 粗定位。")
            if geo_data:
                lat = geo_data.get("latitude")
                lng = geo_data.get("longitude")
                if lat is not None and lng is not None:
                    try:
                        r = httpx.get(
                            "https://nominatim.openstreetmap.org/reverse",
                            params={"lat": lat, "lon": lng, "format": "jsonv2", "accept-language": "zh-CN,zh"},
                            headers={"User-Agent": "meituan-competition-agent/1.0"},
                            timeout=5.0,
                        )
                        label = r.json().get("display_name", f"{lat:.4f}, {lng:.4f}")
                    except Exception:
                        label = f"{lat:.4f}, {lng:.4f}"
                    st.session_state.detected_location = {
                        "lat": float(lat), "lng": float(lng), "label": label,
                    }
                    st.session_state.browser_location_fetched = True
                    st.rerun()

    app.render_header()

    loc = st.session_state.get("detected_location")
    if loc:
        st.markdown(f"""
        <div style="position:fixed;top:1rem;right:1rem;z-index:99999;background:#161b22;
                    border:1px solid #30363d;padding:6px 14px;border-radius:20px;color:#e6edf3;
                    font-size:0.8rem;display:flex;align-items:center;gap:6px;box-shadow:0 4px 12px rgba(0,0,0,0.3);">
          <div style="width:7px;height:7px;border-radius:50%;background:#3fb950;"></div>
          <span style="max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="{loc['label']}">
            {loc['label']}
          </span>
        </div>
        """, unsafe_allow_html=True)

    col1, col2 = st.columns([1, 3])
    with col2:
        app.render_chat_interface()
    with col1:
        app.render_sidebar()


if __name__ == "__main__":
    main()
