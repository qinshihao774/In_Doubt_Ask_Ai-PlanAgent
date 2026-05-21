"""
Inspire UI - 私人规划执行助理
流体玻璃态设计风格主入口
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from typing import Any, Generator

import httpx
import streamlit as st
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from components.animations import (
    add_custom_css,
    PulseEffect,
    SkeletonLoader,
    TypewriterEffect,
)

# API 基础 URL
API_BASE = os.getenv("MEITUAN_AGENT_API_BASE", "http://127.0.0.1:8000")


class InspireChatApp:
    """Inspire UI 聊天应用主类"""
    
    def __init__(self):
        self.session_id = self._ensure_session()
        self._init_styles()
        self._check_backend_connection()
    
    def _init_styles(self):
        """初始化样式"""
        add_custom_css()
        
        # 页面配置
        st.set_page_config(
            page_title="私人规划执行助理",
            page_icon="🍜",
            layout="wide",
            initial_sidebar_state="expanded"
        )
    
    def _ensure_session(self) -> str:
        """确保会话存在"""
        if "session_id" not in st.session_state:
            st.session_state.session_id = f"sess_{uuid.uuid4().hex[:10]}"
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "connection_status" not in st.session_state:
            st.session_state.connection_status = "checking"
        if "is_processing" not in st.session_state:
            st.session_state.is_processing = False
        return st.session_state.session_id
    
    def _check_backend_connection(self):
        """检查后端连接状态"""
        try:
            response = httpx.get(f"{API_BASE}/health", timeout=5)
            if response.status_code == 200:
                st.session_state.connection_status = "online"
                # 初始化会话
                self._init_backend_session()
            else:
                st.session_state.connection_status = "offline"
        except Exception:
            st.session_state.connection_status = "offline"
    
    def _init_backend_session(self):
        """初始化后端会话"""
        try:
            with httpx.Client(timeout=10) as client:
                client.post(
                    f"{API_BASE}/init",
                    json={"session_id": self.session_id}
                )
        except Exception:
            pass
    
    def _stream_chat(self, message: str) -> Generator[tuple[str, bool], None, None]:
        """流式聊天生成器"""
        accumulated = ""
        is_first = True
        
        try:
            with httpx.Client(timeout=None) as client:
                with client.stream(
                    "POST",
                    f"{API_BASE}/chat/stream",
                    json={"session_id": self.session_id, "message": message}
                ) as response:
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
                        
                        # 处理会话信息
                        if data.get("type") == "session":
                            new_session_id = data.get("session_id")
                            if new_session_id:
                                st.session_state.session_id = new_session_id
                                self.session_id = new_session_id
                        
                        # 处理增量内容
                        elif data.get("type") == "delta":
                            content = data.get("content", "")
                            if content:
                                accumulated += content
                                yield accumulated, False
                        
                        # 处理完成
                        elif data.get("type") == "done":
                            yield accumulated, True
                            return
        
        except Exception as e:
            if not accumulated:
                accumulated = f"连接出现问题，请稍后重试。"
            yield accumulated, True
    
    def _process_pending_message(self):
        """处理待处理的消息"""
        if not st.session_state.get("is_processing"):
            return
        
        # 获取最后一条用户消息
        last_message = None
        for msg in reversed(st.session_state.messages):
            if msg["role"] == "user":
                last_message = msg["content"]
                break
        
        if not last_message:
            st.session_state.is_processing = False
            return
        
        # 创建占位符用于流式输出
        assistant_placeholder = st.empty()
        accumulated_text = ""
        
        try:
            for text, is_done in self._stream_chat(last_message):
                accumulated_text = text
                if not is_done:
                    # 显示带光标的流式输出
                    assistant_placeholder.markdown(
                        f"<div class='message-bubble message-assistant'>{accumulated_text}<span class='typing-cursor'></span></div>",
                        unsafe_allow_html=True
                    )
                else:
                    # 完成，移除光标
                    assistant_placeholder.markdown(
                        f"<div class='message-bubble message-assistant'>{accumulated_text}</div>",
                        unsafe_allow_html=True
                    )
        
        except Exception as e:
            assistant_placeholder.markdown(
                f"<div class='message-bubble message-assistant'>抱歉，处理消息时出现问题：{str(e)}</div>",
                unsafe_allow_html=True
            )
        
        finally:
            # 添加到消息历史
            if accumulated_text:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": accumulated_text
                })
            
            st.session_state.is_processing = False
    
    def render_header(self):
        """渲染页面头部"""
        st.markdown("""
        <div style="text-align: center; padding: 2rem 0 1rem 0; position: relative;">
            <!-- 装饰性光晕 -->
            <div style="
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                width: 300px;
                height: 100px;
                background: radial-gradient(ellipse, rgba(255,209,0,0.2) 0%, transparent 70%);
                filter: blur(20px);
                pointer-events: none;
            "></div>
            
            <h1 style="
                font-size: 2.8rem;
                font-weight: 800;
                background: linear-gradient(135deg, #FFD100 0%, #FF8C00 30%, #FF6B35 60%, #7B2CBF 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                margin-bottom: 0.5rem;
                letter-spacing: -0.02em;
                position: relative;
                z-index: 1;
            ">🍜 私人规划执行助理</h1>
            
            <p style="
                font-size: 1rem;
                color: rgba(255,255,255,0.6);
                font-weight: 400;
                letter-spacing: 0.05em;
                position: relative;
                z-index: 1;
            ">INTELLIGENT PLANNING · FLUID EXPERIENCE</p>
        </div>
        """, unsafe_allow_html=True)
    
    def render_sidebar(self):
        """渲染侧边栏"""
        # 连接状态指示器
        self._render_connection_status()
        
        # 会话信息卡片
        self._render_session_card()
        
        # 快捷操作
        self._render_quick_actions()
        
        # 系统状态
        self._render_system_status()
    
    def _render_connection_status(self):
        """渲染连接状态"""
        status = st.session_state.get("connection_status", "checking")
        
        if status == "online":
            st.markdown("""
            <div style="
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 8px 12px;
                border-radius: 20px;
                background: linear-gradient(135deg, rgba(0,255,128,0.15) 0%, rgba(0,255,128,0.05) 100%);
                border: 1px solid rgba(0,255,128,0.2);
                margin-bottom: 16px;
            ">
                <div style="
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                    background: #00FF80;
                    box-shadow: 0 0 8px #00FF80;
                    animation: pulse-ring 2s infinite;
                "></div>
                <span style="font-size: 0.85rem; color: #00FF80; font-weight: 500;">服务在线</span>
            </div>
            <style>
                @keyframes pulse-ring {
                    0%, 100% { opacity: 1; transform: scale(1); }
                    50% { opacity: 0.6; transform: scale(1.1); }
                }
            </style>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 8px 12px;
                border-radius: 20px;
                background: linear-gradient(135deg, rgba(255,80,80,0.15) 0%, rgba(255,80,80,0.05) 100%);
                border: 1px solid rgba(255,80,80,0.2);
                margin-bottom: 16px;
            ">
                <div style="
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                    background: #FF5050;
                "></div>
                <span style="font-size: 0.85rem; color: #FF5050; font-weight: 500;">服务离线</span>
            </div>
            """, unsafe_allow_html=True)
            
            st.error("⚠️ 无法连接到后端服务，请确保后端已启动")
    
    def _render_session_card(self):
        """渲染会话信息卡片"""
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.03) 100%);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 16px;
        ">
            <div style="
                font-size: 0.75rem;
                color: rgba(255,255,255,0.5);
                text-transform: uppercase;
                letter-spacing: 0.1em;
                margin-bottom: 8px;
            ">当前会话</div>
            <div style="
                font-family: 'SF Mono', 'Consolas', monospace;
                font-size: 0.85rem;
                color: #FFD100;
                background: rgba(255,209,0,0.1);
                padding: 8px 12px;
                border-radius: 8px;
                border: 1px solid rgba(255,209,0,0.2);
            ">{}</div>
        </div>
        """.format(st.session_state.session_id), unsafe_allow_html=True)
        
        # 重置按钮
        if st.button("🔄 重置会话", use_container_width=True, type="secondary"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    def _render_quick_actions(self):
        """渲染快捷操作区"""
        st.markdown("""
        <div style="
            margin-top: 8px;
            padding-top: 16px;
            border-top: 1px solid rgba(255,255,255,0.1);
        ">
            <div style="
                font-size: 0.8rem;
                color: rgba(255,255,255,0.6);
                margin-bottom: 12px;
                display: flex;
                align-items: center;
                gap: 6px;
            ">
                <span>🚀</span>
                <span>快捷操作</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ 确认方案1", use_container_width=True, type="primary"):
                st.session_state.pending_message = "确认 方案1"
                st.rerun()
        with col2:
            if st.button("✅ 确认方案2", use_container_width=True, type="primary"):
                st.session_state.pending_message = "确认 方案2"
                st.rerun()
    
    def _render_system_status(self):
        """渲染系统状态信息"""
        # 获取后端状态
        state = self._get_state()
        
        if state:
            status = state.get("status", "unknown")
            status_color = {
                "idle": "#00FF80",
                "planning": "#FFD100",
                "awaiting_confirmation": "#00D4FF",
                "executing": "#FF8C00",
                "completed": "#00FF80",
                "failed": "#FF5050"
            }.get(status, "#888888")
            
            status_text = {
                "idle": "空闲",
                "planning": "规划中",
                "awaiting_confirmation": "等待确认",
                "executing": "执行中",
                "completed": "已完成",
                "failed": "失败"
            }.get(status, status)
            
            st.markdown(f"""
            <div style="
                margin-top: 16px;
                padding-top: 16px;
                border-top: 1px solid rgba(255,255,255,0.1);
            ">
                <div style="
                    font-size: 0.8rem;
                    color: rgba(255,255,255,0.6);
                    margin-bottom: 12px;
                ">📊 系统状态</div>
                <div style="
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    padding: 10px 14px;
                    border-radius: 10px;
                    background: rgba(255,255,255,0.05);
                    border: 1px solid {status_color}40;
                ">
                    <div style="
                        width: 10px;
                        height: 10px;
                        border-radius: 50%;
                        background: {status_color};
                        box-shadow: 0 0 8px {status_color};
                    "></div>
                    <span style="color: {status_color}; font-weight: 500; font-size: 0.9rem;">{status_text}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    def _get_state(self) -> dict | None:
        """获取后端状态"""
        try:
            with httpx.Client(timeout=5) as client:
                r = client.get(f"{API_BASE}/state/{self.session_id}")
                if r.status_code == 200:
                    return r.json()
        except Exception:
            pass
        return None


def main():
    """主入口函数"""
    # 创建应用实例
    app = InspireChatApp()
    
    # 渲染头部
    app.render_header()
    
    # 创建两列布局
    col1, col2 = st.columns([1, 3])
    
    with col1:
        app.render_sidebar()
    
    with col2:
        # 这里将渲染聊天界面
        st.markdown("""
        <div style="
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 20px;
            padding: 24px;
            min-height: 500px;
        ">
            <div style="text-align: center; padding: 60px 0;">
                <div style="font-size: 4rem; margin-bottom: 16px;">💬</div>
                <div style="color: rgba(255,255,255,0.6); font-size: 1.1rem;">
                    开始你的智能规划之旅<br>
                    <span style="font-size: 0.9rem; opacity: 0.7;">在下方输入你的需求</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # 聊天输入框
        prompt = st.chat_input("✨ 描述你的需求...")
        
        # 处理快捷发送
        pending = st.session_state.get("pending_message")
        if pending and not prompt:
            prompt = pending
            st.session_state.pending_message = None
        
        # 处理用户输入
        if prompt:
            # 添加到消息历史
            st.session_state.messages.append({
                "role": "user",
                "content": prompt
            })
            
            # 标记正在处理
            st.session_state.is_processing = True
            
            # 重新加载以显示用户消息
            st.rerun()


if __name__ == "__main__":
    main()