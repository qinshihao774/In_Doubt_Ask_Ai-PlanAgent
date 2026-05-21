"""
Inspire UI 流体设计 — 聊天页面 v2.0
独立页面入口，与 streamlit_app.py 保持一致的设计语言
"""

from __future__ import annotations

import json
import os
import re
import sys
import uuid

import httpx
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from styles.inspire_ui import inject_css

API_BASE = os.getenv("MEITUAN_AGENT_API_BASE", "http://127.0.0.1:8000")


class ChatInterface:
    """Inspire UI 聊天界面"""

    def __init__(self):
        self._init_session()
        self._ensure_connection()

    def _init_session(self):
        if "session_id" not in st.session_state:
            st.session_state.session_id = f"sess_{uuid.uuid4().hex[:10]}"
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "is_typing" not in st.session_state:
            st.session_state.is_typing = False
        if "connection_status" not in st.session_state:
            st.session_state.connection_status = "checking"

    def _ensure_connection(self):
        try:
            r = httpx.get(f"{API_BASE}/health", timeout=5)
            if r.status_code == 200:
                st.session_state.connection_status = "online"
                self._post_init(st.session_state.session_id)
            else:
                st.session_state.connection_status = "offline"
        except Exception:
            st.session_state.connection_status = "offline"

    def _post_init(self, session_id: str):
        try:
            with httpx.Client(timeout=10) as c:
                c.post(f"{API_BASE}/init", json={"session_id": session_id})
        except Exception:
            pass

    def _iter_chat_stream(self, session_id: str, message: str):
        with httpx.Client(timeout=None) as client:
            with client.stream(
                "POST",
                f"{API_BASE}/chat/stream",
                json={"session_id": session_id, "message": message},
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data:
                        continue
                    yield json.loads(data)

    # ═══════════════════════════════════════════
    # 渲染
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

    def _compute_plan_count(self) -> int:
        for msg in reversed(st.session_state.messages):
            if msg["role"] == "assistant":
                matches = re.findall(r'方案(\d+)[：:]', msg["content"])
                if matches:
                    return max(int(m) for m in matches)
        return 0

    def render_sidebar(self):
        with st.sidebar:
            # 面板标题
            st.markdown("""
            <div style="padding:0.5rem 0;margin-bottom:0.5rem;">
                <h3 style="color:#FFD100;margin:0;font-size:1.15rem;">⚙️ 控制面板</h3>
            </div>
            """, unsafe_allow_html=True)

            # 连接状态
            status = st.session_state.get("connection_status", "checking")
            if status == "online":
                st.markdown("""
                <div class="status-badge status-badge--online" style="margin-bottom:12px;">
                    <span class="status-dot status-dot--live"></span>
                    <span>服务在线</span>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="status-badge status-badge--offline" style="margin-bottom:12px;">
                    <span class="status-dot status-dot--dead"></span>
                    <span>服务离线</span>
                </div>
                """, unsafe_allow_html=True)

            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

            # 会话 ID
            sid = st.session_state.session_id
            st.markdown(f"""
            <div class="session-card">
                <div class="session-card__label">会话 ID</div>
                <div class="session-card__id">{sid}</div>
            </div>
            """, unsafe_allow_html=True)

            if st.button("🔄 重置会话", use_container_width=True, type="secondary"):
                for k in list(st.session_state.keys()):
                    del st.session_state[k]
                st.rerun()

            # 动态快捷确认
            plan_count = self._compute_plan_count()
            if plan_count > 0:
                st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

                st.markdown("""
                <div style="margin-bottom:10px;">
                    <span style="font-size:0.82rem;color:rgba(255,255,255,0.6);">🚀 快捷确认（点击执行所选方案）</span>
                </div>
                """, unsafe_allow_html=True)

                cols = st.columns(plan_count)
                for i in range(plan_count):
                    with cols[i]:
                        if st.button(f"✅ 方案{i+1}", use_container_width=True, key=f"chat_confirm_{i+1}"):
                            st.session_state.pending_send = f"确认 方案{i+1}"
                            st.rerun()

    def render_chat(self):
        # 历史消息
        for msg in st.session_state.messages:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                st.markdown(f"""
                <div class="message-row message-row--user">
                    <div class="message-bubble message-bubble--user">{content}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="message-row message-row--assistant">
                    <div class="message-bubble message-bubble--assistant">{content}</div>
                </div>
                """, unsafe_allow_html=True)

        # 思考状态
        if st.session_state.get("is_typing"):
            st.markdown("""
            <div class="message-row message-row--assistant">
                <div class="message-bubble message-bubble--assistant">
                    <div class="thinking-dots">
                        <span></span><span></span><span></span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # 输入
        prompt = st.chat_input("✨ 描述你的需求，例如：下午2点出发，带5岁娃，老婆减脂，帮我规划4-6小时...")

        pending = st.session_state.get("pending_send")
        if pending and not prompt:
            prompt = pending
            st.session_state.pending_send = None

        if prompt:
            self._handle_user_message(prompt)

    def _handle_user_message(self, prompt: str):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.is_typing = True
        st.rerun()

    def process_ai_response(self):
        if not st.session_state.get("is_typing"):
            return

        last_user = None
        for msg in reversed(st.session_state.messages):
            if msg["role"] == "user":
                last_user = msg["content"]
                break

        if not last_user:
            st.session_state.is_typing = False
            return

        try:
            full = ""
            for chunk in self._iter_chat_stream(
                st.session_state.session_id, last_user
            ):
                if chunk.get("type") == "delta":
                    full += chunk.get("content", "")
                elif chunk.get("type") == "done":
                    break

            if full:
                st.session_state.messages.append(
                    {"role": "assistant", "content": full}
                )
        except Exception as e:
            st.session_state.messages.append(
                {"role": "assistant", "content": f"抱歉，出现了一些问题：{str(e)}"}
            )
        finally:
            st.session_state.is_typing = False
            st.rerun()


# ═══════════════════════════════════════════════════════════
# 页面入口
# ═══════════════════════════════════════════════════════════

def render_page():
    inject_css()

    st.set_page_config(
        page_title="私人规划执行助理",
        page_icon="🍜",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    ui = ChatInterface()

    ui.render_header()
    ui.process_ai_response()

    col1, col2 = st.columns([1, 3])
    # 先渲染聊天区（处理 AI 响应），再渲染侧边栏（读取最新方案数）
    with col2:
        ui.render_chat()
    with col1:
        ui.render_sidebar()
