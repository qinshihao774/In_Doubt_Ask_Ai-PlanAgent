"""
Pipeline Visualizer — Agent 执行流程可视化组件

以点线流程图形式展示多 Agent 执行进度，让用户感知每个阶段在做什么。
"""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

PIPELINE_CSS = """
<style>
/* ═══════════════════════════════════════════════════════════
   Pipeline Visualizer — 点线流程
   ═══════════════════════════════════════════════════════════ */
.pipeline-wrapper {
    padding: 16px 8px;
    margin: 12px 0;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    overflow-x: auto;
}
.pipeline-flow {
    display: flex;
    align-items: flex-start;
    justify-content: center;
    min-width: max-content;
    gap: 0;
    padding: 8px 4px;
}
.pipeline-node-wrapper {
    display: flex;
    align-items: flex-start;
    gap: 0;
}
.pipeline-node {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    min-width: 72px;
    position: relative;
}
.pipeline-node__dot {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    transition: all 0.4s ease;
    position: relative;
    z-index: 1;
}
/* 状态颜色 */
.pipeline-node__dot--pending {
    background: rgba(255, 255, 255, 0.06);
    border: 2px solid rgba(255, 255, 255, 0.12);
    opacity: 0.45;
}
.pipeline-node__dot--running {
    background: rgba(255, 209, 0, 0.18);
    border: 2px solid var(--primary, #FFD100);
    box-shadow: 0 0 14px rgba(255, 209, 0, 0.5);
    animation: pipeline-pulse 1.2s ease-in-out infinite;
}
.pipeline-node__dot--done {
    background: rgba(0, 200, 120, 0.15);
    border: 2px solid rgba(0, 200, 120, 0.55);
}
.pipeline-node__dot--error {
    background: rgba(255, 51, 102, 0.15);
    border: 2px solid rgba(255, 51, 102, 0.55);
}
@keyframes pipeline-pulse {
    0%, 100% { box-shadow: 0 0 8px rgba(255, 209, 0, 0.3); }
    50% { box-shadow: 0 0 22px rgba(255, 209, 0, 0.7); }
}
.pipeline-node__label {
    font-size: 11px;
    color: rgba(255, 255, 255, 0.7);
    text-align: center;
    white-space: nowrap;
    font-weight: 500;
    transition: color 0.3s;
}
.pipeline-node__label--active {
    color: var(--primary, #FFD100);
    font-weight: 600;
}
.pipeline-node__label--done {
    color: rgba(0, 200, 120, 0.85);
}
/* 连线 */
.pipeline-connector {
    display: flex;
    align-items: center;
    padding: 0 2px;
    margin-top: 18px;
}
.pipeline-connector__line {
    width: 32px;
    height: 2px;
    border-radius: 1px;
    background: rgba(255, 255, 255, 0.1);
    transition: background 0.5s ease;
}
.pipeline-connector__line--done {
    background: rgba(0, 200, 120, 0.35);
}
.pipeline-connector__line--active {
    background: linear-gradient(90deg, rgba(255, 209, 0, 0.4), rgba(255, 255, 255, 0.1));
    animation: connector-flash 0.8s ease-in-out infinite;
}
@keyframes connector-flash {
    0%, 100% { opacity: 0.5; }
    50% { opacity: 1; }
}
/* 当前状态横幅 */
.pipeline-status-bar {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    padding: 10px 16px;
    margin-top: 10px;
    background: rgba(255, 209, 0, 0.06);
    border-radius: 10px;
    border: 1px solid rgba(255, 209, 0, 0.12);
}
.pipeline-status-bar__icon {
    font-size: 18px;
    animation: pipeline-pulse 1.2s ease-in-out infinite;
}
.pipeline-status-bar__text {
    font-size: 13px;
    color: var(--primary, #FFD100);
    font-weight: 500;
}
/* 完成图标覆盖 */
.pipeline-check {
    position: absolute;
    font-size: 15px;
    color: rgba(0, 200, 120, 0.9);
    line-height: 1;
}
</style>
"""


class PipelineVisualizer:
    """Agent 流水线可视化组件"""

    @staticmethod
    def inject_css():
        st.markdown(PIPELINE_CSS, unsafe_allow_html=True)

    @staticmethod
    def render(stages_config: list[dict], stage_states: dict[str, str]):
        """渲染点线流程图。

        Args:
            stages_config: [{id, label, active_msg, done_msg, icon}, ...]
            stage_states: {stage_id: "pending" | "running" | "done" | "error"}
        """
        if not stages_config:
            return

        # 找到当前活跃阶段
        active_stage = None
        for s in stages_config:
            if stage_states.get(s["id"]) == "running":
                active_stage = s
                break

        nodes_html = ""
        for i, stage in enumerate(stages_config):
            sid = stage["id"]
            status = stage_states.get(sid, "pending")

            dot_class = f"pipeline-node__dot--{status}"
            label_class = ""
            if status == "running":
                label_class = "pipeline-node__label--active"
            elif status == "done":
                label_class = "pipeline-node__label--done"

            dot_content = stage.get("icon", "○")
            if status == "done":
                dot_content = "✓"
            elif status == "error":
                dot_content = "✗"

            nodes_html += f"""
            <div class="pipeline-node">
                <div class="pipeline-node__dot {dot_class}">{dot_content}</div>
                <div class="pipeline-node__label {label_class}">{stage['label']}</div>
            </div>"""

            # 连接线（最后一个不加）
            if i < len(stages_config) - 1:
                next_status = stage_states.get(stages_config[i + 1]["id"], "pending")
                line_class = ""
                if status == "done":
                    line_class = "pipeline-connector__line--done"
                elif status == "running":
                    line_class = "pipeline-connector__line--active"

                nodes_html += f"""
            <div class="pipeline-connector">
                <div class="pipeline-connector__line {line_class}"></div>
            </div>"""

        status_bar = ""
        if active_stage:
            msg = active_stage.get("active_msg", "处理中...")
            icon = active_stage.get("icon", "⚡")
            status_bar = f"""
            <div class="pipeline-status-bar">
                <span class="pipeline-status-bar__icon">{icon}</span>
                <span class="pipeline-status-bar__text">{msg}</span>
            </div>"""

        html = f"""
        <div class="pipeline-wrapper">
            <div class="pipeline-flow">
                {nodes_html}
            </div>
            {status_bar}
        </div>"""

        components.html(PIPELINE_CSS + html, height=190)
