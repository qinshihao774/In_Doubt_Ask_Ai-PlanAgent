"""
Inspire UI 动画效果组件 v2.0
—— 骨架屏 · 脉冲 · 思考指示器 · 打字机
"""

from __future__ import annotations

import time
from typing import Optional

import streamlit as st


# ═══════════════════════════════════════════════════════════
# 骨架屏加载
# ═══════════════════════════════════════════════════════════

class SkeletonLoader:
    """骨架屏加载组件"""

    @staticmethod
    def message(container):
        """消息骨架屏"""
        container.markdown("""
        <div class="message-row message-row--assistant">
            <div class="message-bubble message-bubble--assistant" style="min-width:280px;">
                <div style="display:flex;gap:8px;align-items:center;margin-bottom:10px;">
                    <div class="skeleton" style="width:80px;height:12px;"></div>
                    <div class="skeleton" style="width:60px;height:12px;"></div>
                    <div class="skeleton" style="width:100px;height:12px;"></div>
                </div>
                <div>
                    <div class="skeleton" style="width:100%;height:10px;margin-bottom:8px;"></div>
                    <div class="skeleton" style="width:80%;height:10px;margin-bottom:8px;"></div>
                    <div class="skeleton" style="width:60%;height:10px;"></div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    @staticmethod
    def card(container, count: int = 3):
        """卡片骨架屏"""
        items = []
        for _ in range(count):
            items.append("""
            <div class="glass-card--plain" style="margin-bottom:12px;">
                <div class="skeleton" style="width:60%;height:16px;margin-bottom:12px;"></div>
                <div class="skeleton" style="width:100%;height:10px;margin-bottom:8px;"></div>
                <div class="skeleton" style="width:80%;height:10px;"></div>
            </div>
            """)
        container.markdown("\n".join(items), unsafe_allow_html=True)

    @staticmethod
    def show_message_skeleton(container):
        """向后兼容别名"""
        SkeletonLoader.message(container)

    @staticmethod
    def show_card_skeleton(container, count: int = 3):
        """向后兼容别名"""
        SkeletonLoader.card(container, count)


# ═══════════════════════════════════════════════════════════
# 脉冲效果
# ═══════════════════════════════════════════════════════════

class PulseEffect:
    """脉冲动画效果"""

    @staticmethod
    def live_indicator(container, text: str = "AI 思考中..."):
        """实时活动指示器"""
        container.markdown(f"""
        <div class="status-badge status-badge--online">
            <span class="status-dot status-dot--live"></span>
            <span>{text}</span>
        </div>
        """, unsafe_allow_html=True)

    @staticmethod
    def show_live_indicator(container):
        """向后兼容"""
        PulseEffect.live_indicator(container)

    @staticmethod
    def thinking_dots(container):
        """三点思考动画"""
        container.markdown("""
        <div class="message-row message-row--assistant">
            <div class="message-bubble message-bubble--assistant">
                <div class="thinking-dots">
                    <span></span><span></span><span></span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# 打字机效果
# ═══════════════════════════════════════════════════════════

class TypewriterEffect:
    """打字机效果管理器"""

    def __init__(self, container, text: str, speed: float = 0.025):
        self.container = container
        self.text = text
        self.speed = speed
        self.current_text = ""

    def start(self) -> str:
        placeholder = self.container.empty()
        for char in self.text:
            self.current_text += char
            display = (
                f"<div class='message-row message-row--assistant'>"
                f"<div class='message-bubble message-bubble--assistant'>"
                f"{self.current_text}<span class='typing-cursor'></span>"
                f"</div></div>"
            )
            placeholder.markdown(display, unsafe_allow_html=True)
            time.sleep(self.speed)

        final = (
            f"<div class='message-row message-row--assistant'>"
            f"<div class='message-bubble message-bubble--assistant'>"
            f"{self.current_text}</div></div>"
        )
        placeholder.markdown(final, unsafe_allow_html=True)
        return self.current_text


# ═══════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════

def render_typing_cursor() -> str:
    return "<span class='typing-cursor'></span>"
