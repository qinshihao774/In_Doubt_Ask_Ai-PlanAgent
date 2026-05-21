"""
Inspire UI — 流体设计风格 v2.0
设计灵感: inspira-ui.com
核心理念: 流动渐变 · 极光背景 · 流光边框 · 3D变换 · 粒子特效
主色调: 美团黄 #FFD100
"""

import streamlit as st

CSS_STYLES = """
<style>
/* ═══════════════════════════════════════════════════════════
   设计令牌 (Design Tokens)
   ═══════════════════════════════════════════════════════════ */
:root {
    /* 主色系 */
    --primary: #FFD100;
    --primary-light: #FFE44D;
    --primary-glow: rgba(255, 209, 0, 0.45);
    --primary-ghost: rgba(255, 209, 0, 0.08);

    /* 点缀色 */
    --accent-purple: #7B2CBF;
    --accent-purple-glow: rgba(123, 44, 191, 0.4);
    --accent-cyan: #00D4FF;
    --accent-cyan-glow: rgba(0, 212, 255, 0.35);
    --accent-pink: #FF3366;
    --accent-pink-glow: rgba(255, 51, 102, 0.3);

    /* 背景 */
    --bg-deep: #06060E;
    --bg-elevated: rgba(16, 16, 32, 0.7);
    --bg-card: rgba(22, 22, 44, 0.55);

    /* 玻璃态 */
    --glass-bg: rgba(255, 255, 255, 0.04);
    --glass-border: rgba(255, 255, 255, 0.08);
    --glass-border-hover: rgba(255, 255, 255, 0.16);

    /* 文字 */
    --text-primary: #FFFFFF;
    --text-secondary: rgba(255, 255, 255, 0.7);
    --text-muted: rgba(255, 255, 255, 0.45);

    /* 阴影 */
    --shadow-glow-yellow: 0 0 60px rgba(255, 209, 0, 0.25);
    --shadow-glow-purple: 0 0 60px rgba(123, 44, 191, 0.2);
    --shadow-card: 0 8px 32px rgba(0, 0, 0, 0.5);

    /* 圆角 */
    --radius-sm: 10px;
    --radius-md: 16px;
    --radius-lg: 24px;
    --radius-xl: 32px;

    /* 过渡 */
    --ease-smooth: cubic-bezier(0.4, 0, 0.2, 1);
    --ease-bounce: cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* ═══════════════════════════════════════════════════════════
   全局重置
   ═══════════════════════════════════════════════════════════ */
* { box-sizing: border-box; }

.stApp {
    background: var(--bg-deep) !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    overflow-x: hidden;
}

#MainMenu, footer, header { visibility: hidden; }

/* ═══════════════════════════════════════════════════════════
   极光流体背景 — 多层变形光球
   ═══════════════════════════════════════════════════════════ */
.aurora-layer {
    position: fixed;
    top: 0; left: 0;
    width: 100%; height: 100%;
    pointer-events: none;
    z-index: -1;
    overflow: hidden;
}

.aurora-orb {
    position: absolute;
    border-radius: 50%;
    filter: blur(100px);
    opacity: 0.55;
    will-change: transform;
}

.aurora-orb--yellow {
    width: 700px; height: 700px;
    background: radial-gradient(circle, rgba(255, 209, 0, 0.5) 0%, transparent 70%);
    top: -15%; left: -10%;
    animation: auroraFloat1 18s ease-in-out infinite;
}

.aurora-orb--purple {
    width: 600px; height: 600px;
    background: radial-gradient(circle, rgba(123, 44, 191, 0.45) 0%, transparent 70%);
    top: 40%; right: -12%;
    animation: auroraFloat2 22s ease-in-out infinite;
}

.aurora-orb--cyan {
    width: 500px; height: 500px;
    background: radial-gradient(circle, rgba(0, 212, 255, 0.35) 0%, transparent 70%);
    bottom: -10%; left: 30%;
    animation: auroraFloat3 20s ease-in-out infinite;
}

.aurora-orb--pink {
    width: 450px; height: 450px;
    background: radial-gradient(circle, rgba(255, 51, 102, 0.25) 0%, transparent 70%);
    top: 10%; right: 25%;
    animation: auroraFloat4 24s ease-in-out infinite;
}

@keyframes auroraFloat1 {
    0%, 100% { transform: translate(0, 0) scale(1) rotate(0deg); }
    25% { transform: translate(8%, 6%) scale(1.12) rotate(3deg); }
    50% { transform: translate(-3%, 10%) scale(0.94) rotate(-2deg); }
    75% { transform: translate(-6%, -4%) scale(1.08) rotate(1deg); }
}

@keyframes auroraFloat2 {
    0%, 100% { transform: translate(0, 0) scale(1) rotate(0deg); }
    33% { transform: translate(-7%, -5%) scale(1.1) rotate(-3deg); }
    66% { transform: translate(5%, 8%) scale(0.92) rotate(2deg); }
}

@keyframes auroraFloat3 {
    0%, 100% { transform: translate(0, 0) scale(1) rotate(0deg); }
    33% { transform: translate(6%, -8%) scale(0.88) rotate(2deg); }
    66% { transform: translate(-4%, 5%) scale(1.14) rotate(-1deg); }
}

@keyframes auroraFloat4 {
    0%, 100% { transform: translate(0, 0) scale(1) rotate(0deg); }
    25% { transform: translate(-5%, 7%) scale(1.06) rotate(-2deg); }
    50% { transform: translate(8%, -3%) scale(0.9) rotate(3deg); }
    75% { transform: translate(-3%, -6%) scale(1.1) rotate(-1deg); }
}

/* ═══════════════════════════════════════════════════════════
   细微网格纹理
   ═══════════════════════════════════════════════════════════ */
.grid-texture {
    position: fixed;
    top: 0; left: 0;
    width: 100%; height: 100%;
    pointer-events: none;
    z-index: -1;
    opacity: 0.03;
    background-image:
        linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px);
    background-size: 60px 60px;
}

/* ═══════════════════════════════════════════════════════════
   浮动粒子
   ═══════════════════════════════════════════════════════════ */
.particle-field {
    position: fixed;
    top: 0; left: 0;
    width: 100%; height: 100%;
    pointer-events: none;
    z-index: -1;
}

.particle {
    position: absolute;
    width: 3px; height: 3px;
    border-radius: 50%;
    background: var(--primary);
    box-shadow: 0 0 6px var(--primary-glow);
    animation: particleDrift linear infinite;
}

.particle:nth-child(1)  { left: 10%; top: 20%; animation-duration: 14s; animation-delay: 0s; }
.particle:nth-child(2)  { left: 25%; top: 60%; animation-duration: 18s; animation-delay: -2s; width: 2px; height: 2px; }
.particle:nth-child(3)  { left: 40%; top: 15%; animation-duration: 16s; animation-delay: -4s; }
.particle:nth-child(4)  { left: 55%; top: 70%; animation-duration: 20s; animation-delay: -6s; width: 2px; height: 2px; }
.particle:nth-child(5)  { left: 70%; top: 30%; animation-duration: 15s; animation-delay: -8s; }
.particle:nth-child(6)  { left: 85%; top: 50%; animation-duration: 22s; animation-delay: -3s; width: 2px; height: 2px; }
.particle:nth-child(7)  { left: 15%; top: 85%; animation-duration: 17s; animation-delay: -5s; }
.particle:nth-child(8)  { left: 50%; top: 40%; animation-duration: 19s; animation-delay: -7s; width: 2px; height: 2px; }
.particle:nth-child(9)  { left: 75%; top: 10%; animation-duration: 21s; animation-delay: -9s; }
.particle:nth-child(10) { left: 35%; top: 45%; animation-duration: 13s; animation-delay: -1s; }

@keyframes particleDrift {
    0%   { transform: translateY(0) translateX(0); opacity: 0; }
    10%  { opacity: 0.8; }
    90%  { opacity: 0.8; }
    100% { transform: translateY(-100vh) translateX(40px); opacity: 0; }
}

/* ═══════════════════════════════════════════════════════════
   标题区域
   ═══════════════════════════════════════════════════════════ */
.hero-wrapper {
    text-align: center;
    padding: 2.5rem 1rem 1.5rem;
    position: relative;
}

.hero-glow {
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    width: 500px; height: 160px;
    background: radial-gradient(ellipse, rgba(255,209,0,0.15) 0%, transparent 70%);
    filter: blur(40px);
    pointer-events: none;
    animation: heroGlowPulse 4s ease-in-out infinite;
}

@keyframes heroGlowPulse {
    0%, 100% { opacity: 0.7; transform: translate(-50%, -50%) scale(1); }
    50% { opacity: 1; transform: translate(-50%, -50%) scale(1.15); }
}

.hero-icon {
    font-size: 3.5rem;
    margin-bottom: 0.5rem;
    animation: iconFloat 3s ease-in-out infinite;
    display: inline-block;
}

@keyframes iconFloat {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-8px); }
}

.hero-title {
    font-size: 2.8rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    margin: 0 0 0.3rem;
    background: linear-gradient(
        135deg,
        #FFD100 0%,
        #FFA500 25%,
        #FF6B35 50%,
        #7B2CBF 75%,
        #FFD100 100%
    );
    background-size: 200% auto;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: shimmerText 4s linear infinite;
    text-shadow: none;
    filter: drop-shadow(0 0 20px rgba(255, 209, 0, 0.3));
}

@keyframes shimmerText {
    0% { background-position: 0% center; }
    100% { background-position: 200% center; }
}

.hero-subtitle {
    font-size: 0.95rem;
    color: var(--text-muted);
    letter-spacing: 0.2em;
    text-transform: uppercase;
    font-weight: 500;
}

/* ═══════════════════════════════════════════════════════════
   流光玻璃卡片
   ═══════════════════════════════════════════════════════════ */
.glass-card {
    position: relative;
    background: var(--glass-bg);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    border-radius: var(--radius-lg);
    padding: 24px;
    overflow: hidden;
    transition: all 0.4s var(--ease-smooth);
}

.glass-card::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: inherit;
    padding: 1px;
    background: conic-gradient(
        from 0deg,
        transparent,
        rgba(255, 209, 0, 0.3),
        transparent,
        rgba(123, 44, 191, 0.3),
        transparent
    );
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor;
    mask-composite: exclude;
    animation: rotateBorder 6s linear infinite;
}

.glass-card:hover {
    transform: translateY(-4px);
    background: rgba(255, 255, 255, 0.06);
    box-shadow:
        0 20px 50px rgba(0, 0, 0, 0.5),
        0 0 40px rgba(255, 209, 0, 0.08);
}

.glass-card:hover::before {
    animation-duration: 3s;
}

@keyframes rotateBorder {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

/* 无边框变体 */
.glass-card--plain {
    position: relative;
    background: var(--glass-bg);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg);
    padding: 24px;
    transition: all 0.35s var(--ease-smooth);
}

.glass-card--plain:hover {
    transform: translateY(-2px);
    border-color: var(--glass-border-hover);
    box-shadow: var(--shadow-card);
    background: rgba(255, 255, 255, 0.06);
}

/* ═══════════════════════════════════════════════════════════
   3D 透视卡片
   ═══════════════════════════════════════════════════════════ */
.card-3d-container {
    perspective: 1000px;
}

.card-3d {
    transition: transform 0.5s var(--ease-smooth);
    transform-style: preserve-3d;
}

.card-3d:hover {
    transform: rotateX(2deg) rotateY(-3deg) translateY(-6px);
    box-shadow:
        20px 20px 60px rgba(0, 0, 0, 0.6),
        -5px -5px 30px rgba(255, 209, 0, 0.05);
}

/* ═══════════════════════════════════════════════════════════
   消息气泡
   ═══════════════════════════════════════════════════════════ */
.message-row {
    display: flex;
    margin: 14px 0;
    animation: messageSlideIn 0.45s var(--ease-bounce);
}

.message-row--user {
    justify-content: flex-end;
}

.message-row--assistant {
    justify-content: flex-start;
}

.message-bubble {
    max-width: 78%;
    padding: 16px 22px;
    border-radius: var(--radius-md);
    font-size: 0.95rem;
    line-height: 1.65;
    position: relative;
}

.message-bubble--user {
    background: linear-gradient(135deg, #FFD100 0%, #FF8C00 100%);
    color: #1A1A2E;
    font-weight: 500;
    border-bottom-right-radius: 6px;
    box-shadow: 0 4px 20px rgba(255, 209, 0, 0.2);
}

.message-bubble--assistant {
    background: var(--glass-bg);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid var(--glass-border);
    color: var(--text-primary);
    border-bottom-left-radius: 6px;
}

.message-bubble--assistant::after {
    content: '';
    position: absolute;
    inset: -1px;
    border-radius: inherit;
    padding: 1px;
    background: linear-gradient(
        135deg,
        rgba(255, 255, 255, 0.08),
        rgba(255, 255, 255, 0.02)
    );
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor;
    mask-composite: exclude;
    pointer-events: none;
}

/* ═══════════════════════════════════════════════════════════
   聊天头像
   ═══════════════════════════════════════════════════════════ */
.chat-avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    object-fit: cover;
    flex-shrink: 0;
    margin: 2px 8px;
}

.chat-avatar--ai {
    order: -1;
    box-shadow: 0 0 10px rgba(255, 209, 0, 0.25);
}

.chat-avatar--user {
    order: 1;
    box-shadow: 0 0 10px rgba(0, 180, 216, 0.2);
}

@keyframes messageSlideIn {
    from {
        opacity: 0;
        transform: translateY(16px) scale(0.96);
    }
    to {
        opacity: 1;
        transform: translateY(0) scale(1);
    }
}

/* ═══════════════════════════════════════════════════════════
   打字机光标
   ═══════════════════════════════════════════════════════════ */
.typing-cursor::after {
    content: '◌';
    color: var(--primary);
    animation: cursorFlash 1s step-end infinite;
}

@keyframes cursorFlash {
    0%, 50% { opacity: 1; }
    51%, 100% { opacity: 0; }
}

/* ═══════════════════════════════════════════════════════════
   思考指示器（三点跳跃）
   ═══════════════════════════════════════════════════════════ */
.thinking-dots {
    display: inline-flex;
    gap: 4px;
    align-items: center;
    padding: 4px 0;
}

.thinking-dots span {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--primary);
    animation: dotBounce 1.4s ease-in-out infinite;
}

.thinking-dots span:nth-child(1) { animation-delay: 0s; }
.thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes dotBounce {
    0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
    40% { transform: scale(1); opacity: 1; }
}

/* ═══════════════════════════════════════════════════════════
   思考中指示器（旋转光环 + 状态文字 + 跳点）
   ═══════════════════════════════════════════════════════════ */
.thinking-indicator {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 14px;
    padding: 22px 26px;
    background: var(--glass-bg);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-md);
    max-width: 78%;
    animation: messageSlideIn 0.45s var(--ease-bounce);
}

.thinking-ring {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    background: conic-gradient(
        from 0deg,
        var(--primary) 0%,
        var(--accent-purple) 33%,
        var(--accent-cyan) 66%,
        var(--primary) 100%
    );
    animation: thinkRingSpin 1.1s linear infinite;
    mask: radial-gradient(
        farthest-side,
        transparent calc(100% - 4px),
        #fff calc(100% - 4px)
    );
    -webkit-mask: radial-gradient(
        farthest-side,
        transparent calc(100% - 4px),
        #fff calc(100% - 4px)
    );
}

@keyframes thinkRingSpin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

.thinking-indicator .thinking-text {
    color: var(--text-secondary);
    font-size: 0.92rem;
    font-weight: 500;
    line-height: 1.4;
}

.thinking-indicator .thinking-dots {
    display: inline-flex;
    gap: 5px;
    align-items: center;
    padding: 2px 0;
}

.thinking-indicator .thinking-dots span {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--primary);
    animation: dotBounce 1.4s ease-in-out infinite;
}

.thinking-indicator .thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
.thinking-indicator .thinking-dots span:nth-child(3) { animation-delay: 0.4s; }

/* 进度条 — 与旋转光环同色系（黄→紫→青 conic-gradient） */
.thinking-progress {
    width: 100%;
    height: 4px;
    background: rgba(255, 255, 255, 0.06);
    border-radius: 2px;
    overflow: hidden;
}

.thinking-progress-bar {
    height: 100%;
    border-radius: 2px;
    background: linear-gradient(90deg,
        var(--primary) 0%,
        var(--accent-purple) 50%,
        var(--accent-cyan) 100%
    );
    animation: progressFill 15s ease-out forwards;
    transform-origin: left center;
    width: 0%;
}

@keyframes progressFill {
    0%   { width: 0%; }
    15%  { width: 18%; }
    35%  { width: 40%; }
    55%  { width: 62%; }
    75%  { width: 80%; }
    90%  { width: 92%; }
    100% { width: 98%; }
}

/* 2 秒超时提示 */
.thinking-long-wait {
    font-size: 0.78rem;
    color: var(--text-muted);
    opacity: 0;
    animation: fadeInDelay 0.5s ease-in 2s forwards;
}

@keyframes fadeInDelay {
    from { opacity: 0; }
    to   { opacity: 1; }
}

/* ═══════════════════════════════════════════════════════════
   方案卡片堆叠 — 活跃在前清晰，非活跃在后模糊
   ═══════════════════════════════════════════════════════════ */
.plan-stack {
    position: relative;
    width: 100%;
}

.plan-card {
    position: absolute;
    top: 0; left: 0;
    width: 100%;
    background: var(--glass-bg);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg);
    padding: 22px 26px;
    transition: all 0.5s var(--ease-smooth);
    overflow: hidden;
}

/* 活跃卡片 — 清晰前置，金色流光 */
.plan-card--active {
    z-index: 3;
    filter: none;
    opacity: 1;
    transform: translateY(0) scale(1);
    border-color: rgba(255, 209, 0, 0.5);
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5), 0 0 30px rgba(255, 209, 0, 0.15);
    background: rgba(255, 255, 255, 0.06);
}

.plan-card--active::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: inherit;
    padding: 1px;
    background: conic-gradient(from 0deg, transparent, rgba(255,209,0,0.5), transparent, rgba(123,44,191,0.35), transparent);
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor;
    mask-composite: exclude;
    animation: rotateBorder 8s linear infinite;
    pointer-events: none;
}

/* 非活跃卡片 — 藏于后方，模糊不可交互 */
.plan-card--behind-1 {
    z-index: 2;
    filter: blur(3px) brightness(0.6);
    opacity: 0.45;
    transform: translateY(12px) scale(0.94);
    pointer-events: none;
}

.plan-card--behind-2 {
    z-index: 1;
    filter: blur(5px) brightness(0.45);
    opacity: 0.3;
    transform: translateY(24px) scale(0.88);
    pointer-events: none;
}

.plan-card__title {
    font-size: 1rem;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 10px;
}

.plan-index {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 26px;
    height: 26px;
    border-radius: 50%;
    background: linear-gradient(135deg, #FFD100, #FF8C00);
    color: #1A1A2E;
    font-size: 0.8rem;
    font-weight: 700;
    flex-shrink: 0;
}

.plan-card__rationale {
    font-size: 0.82rem;
    color: var(--text-muted);
    margin-bottom: 8px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--glass-border);
    font-style: italic;
}

.plan-card__items {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.plan-card__item {
    font-size: 0.85rem;
    color: var(--text-secondary);
    padding: 6px 10px;
    background: rgba(255, 255, 255, 0.03);
    border-radius: var(--radius-sm);
    border: 1px solid rgba(255, 255, 255, 0.04);
}

/* ═══════════════════════════════════════════════════════════
   骨架屏
   ═══════════════════════════════════════════════════════════ */
.skeleton {
    background: linear-gradient(
        110deg,
        rgba(255, 255, 255, 0.04) 0%,
        rgba(255, 255, 255, 0.1) 50%,
        rgba(255, 255, 255, 0.04) 100%
    );
    background-size: 200% 100%;
    animation: skeletonFlow 1.6s ease-in-out infinite;
    border-radius: 8px;
}

@keyframes skeletonFlow {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}

/* ═══════════════════════════════════════════════════════════
   按钮系统
   ═══════════════════════════════════════════════════════════ */

/* 主要按钮 */
.btn-primary {
    position: relative;
    background: linear-gradient(135deg, #FFD100 0%, #FF8C00 100%);
    color: #1A1A2E;
    border: none;
    padding: 12px 28px;
    border-radius: var(--radius-sm);
    font-weight: 700;
    font-size: 0.9rem;
    cursor: pointer;
    overflow: hidden;
    transition: all 0.3s var(--ease-smooth);
    box-shadow: 0 4px 16px rgba(255, 209, 0, 0.25);
}

.btn-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 28px rgba(255, 209, 0, 0.4);
}

.btn-primary:active {
    transform: translateY(0);
}

/* 涟漪效果 */
.btn-primary::after {
    content: '';
    position: absolute;
    top: 50%; left: 50%;
    width: 0; height: 0;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.3);
    transform: translate(-50%, -50%);
    transition: width 0.6s, height 0.6s, opacity 0.6s;
}

.btn-primary:active::after {
    width: 300px; height: 300px;
    opacity: 0;
}

/* 幽灵按钮 */
.btn-ghost {
    position: relative;
    background: transparent;
    color: var(--primary);
    border: 1px solid rgba(255, 209, 0, 0.3);
    padding: 10px 24px;
    border-radius: var(--radius-sm);
    font-weight: 600;
    font-size: 0.85rem;
    cursor: pointer;
    overflow: hidden;
    transition: all 0.3s var(--ease-smooth);
}

.btn-ghost:hover {
    background: rgba(255, 209, 0, 0.08);
    border-color: var(--primary);
    box-shadow: 0 0 24px rgba(255, 209, 0, 0.15);
}

/* 流光按钮 */
.btn-glow {
    position: relative;
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-primary);
    border: none;
    padding: 10px 24px;
    border-radius: var(--radius-sm);
    font-weight: 600;
    font-size: 0.85rem;
    cursor: pointer;
    overflow: hidden;
    transition: all 0.3s var(--ease-smooth);
    z-index: 0;
}

.btn-glow::before {
    content: '';
    position: absolute;
    inset: -2px;
    z-index: -1;
    border-radius: calc(var(--radius-sm) + 2px);
    background: conic-gradient(
        from 0deg,
        var(--primary),
        var(--accent-purple),
        var(--accent-cyan),
        var(--primary)
    );
    animation: rotateBorder 4s linear infinite;
    opacity: 0;
    transition: opacity 0.3s;
}

.btn-glow:hover::before {
    opacity: 1;
}

.btn-glow::after {
    content: '';
    position: absolute;
    inset: 1px;
    z-index: -1;
    border-radius: var(--radius-sm);
    background: var(--bg-deep);
}

/* ═══════════════════════════════════════════════════════════
   状态指示器
   ═══════════════════════════════════════════════════════════ */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 600;
}

.status-badge--online {
    background: rgba(0, 255, 128, 0.1);
    border: 1px solid rgba(0, 255, 128, 0.2);
    color: #00FF80;
}

.status-badge--offline {
    background: rgba(255, 80, 80, 0.1);
    border: 1px solid rgba(255, 80, 80, 0.2);
    color: #FF5050;
}

.status-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
}

.status-dot--live {
    background: #00FF80;
    box-shadow: 0 0 10px #00FF80;
    animation: statusPulse 2s ease-in-out infinite;
}

.status-dot--dead {
    background: #FF5050;
}

@keyframes statusPulse {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.3); opacity: 0.6; }
}

/* ═══════════════════════════════════════════════════════════
   会话 ID 卡片
   ═══════════════════════════════════════════════════════════ */
.session-card {
    background: linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-md);
    padding: 18px;
    margin-bottom: 16px;
}

.session-card__label {
    font-size: 0.7rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.15em;
    margin-bottom: 8px;
}

.session-card__id {
    font-family: 'SF Mono', 'Consolas', 'Fira Code', monospace;
    font-size: 0.85rem;
    color: var(--primary);
    background: rgba(255, 209, 0, 0.08);
    padding: 10px 14px;
    border-radius: var(--radius-sm);
    border: 1px solid rgba(255, 209, 0, 0.15);
    word-break: break-all;
}

/* ═══════════════════════════════════════════════════════════
   分割线
   ═══════════════════════════════════════════════════════════ */
.divider {
    margin: 16px 0;
    border: none;
    height: 1px;
    background: linear-gradient(
        90deg,
        transparent,
        rgba(255, 255, 255, 0.1),
        transparent
    );
}

.divider--glow {
    background: linear-gradient(
        90deg,
        transparent,
        rgba(255, 209, 0, 0.3),
        transparent
    );
}

/* ═══════════════════════════════════════════════════════════
   滚动条
   ═══════════════════════════════════════════════════════════ */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}

::-webkit-scrollbar-track {
    background: rgba(255, 255, 255, 0.02);
    border-radius: 3px;
}

::-webkit-scrollbar-thumb {
    background: rgba(255, 209, 0, 0.35);
    border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
    background: rgba(255, 209, 0, 0.6);
}

/* ═══════════════════════════════════════════════════════════
   Streamlit 组件覆盖
   ═══════════════════════════════════════════════════════════ */

/* 聊天输入框 */
.stChatInput > div > div > input {
    background: rgba(255, 255, 255, 0.04) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: var(--radius-md) !important;
    color: var(--text-primary) !important;
    padding: 14px 20px !important;
    font-size: 0.95rem !important;
    transition: all 0.3s var(--ease-smooth) !important;
}

.stChatInput > div > div > input:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px rgba(255, 209, 0, 0.15) !important;
}

.stChatInput > div > div > input::placeholder {
    color: rgba(255, 255, 255, 0.3) !important;
}

/* Streamlit 默认按钮 */
.stButton > button {
    position: relative;
    background: linear-gradient(135deg, #FFD100 0%, #FF8C00 100%) !important;
    color: #1A1A2E !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    padding: 10px 22px !important;
    font-weight: 700 !important;
    font-size: 0.88rem !important;
    transition: all 0.3s var(--ease-smooth) !important;
    overflow: hidden !important;
}

.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 28px rgba(255, 209, 0, 0.4) !important;
}

.stButton > button:active {
    transform: translateY(0) !important;
}

/* 次级按钮 */
.stButton > button[kind="secondary"] {
    background: rgba(255, 255, 255, 0.05) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--glass-border) !important;
}

.stButton > button[kind="secondary"]:hover {
    background: rgba(255, 255, 255, 0.08) !important;
    border-color: var(--glass-border-hover) !important;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3) !important;
}

/* 侧边栏 */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg,
        rgba(12, 12, 28, 0.95) 0%,
        rgba(16, 16, 36, 0.9) 100%
    ) !important;
    backdrop-filter: blur(24px) !important;
    -webkit-backdrop-filter: blur(24px) !important;
    border-right: 1px solid var(--glass-border) !important;
}

/* 侧边栏内容 */
section[data-testid="stSidebar"] .stMarkdown {
    color: var(--text-primary) !important;
}

/* Expander */
.stExpander {
    background: rgba(255, 255, 255, 0.03) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: var(--radius-sm) !important;
}

/* ═══════════════════════════════════════════════════════════
   响应式
   ═══════════════════════════════════════════════════════════ */
@media (max-width: 768px) {
    .hero-title {
        font-size: 1.8rem;
    }

    .hero-subtitle {
        font-size: 0.75rem;
        letter-spacing: 0.12em;
    }

    .message-bubble {
        max-width: 90%;
        padding: 12px 16px;
        font-size: 0.9rem;
    }

    .glass-card,
    .glass-card--plain {
        padding: 16px;
        border-radius: var(--radius-md);
    }

    .aurora-orb {
        filter: blur(60px);
    }

    .aurora-orb--yellow { width: 400px; height: 400px; }
    .aurora-orb--purple { width: 350px; height: 350px; }
    .aurora-orb--cyan   { width: 300px; height: 300px; }
    .aurora-orb--pink   { width: 280px; height: 280px; }
}

/* ═══════════════════════════════════════════════════════════
   动画减弱（偏好设置）
   ═══════════════════════════════════════════════════════════ */
@media (prefers-reduced-motion: reduce) {
    .aurora-orb,
    .particle,
    .hero-glow,
    .hero-icon {
        animation: none !important;
    }

    .glass-card::before {
        animation: none !important;
    }
}
</style>
"""

# ═══════════════════════════════════════════════════════════
# 极光背景 HTML（注入页面）
# ═══════════════════════════════════════════════════════════
AURORA_HTML = """
<div class="aurora-layer">
    <div class="aurora-orb aurora-orb--yellow"></div>
    <div class="aurora-orb aurora-orb--purple"></div>
    <div class="aurora-orb aurora-orb--cyan"></div>
    <div class="aurora-orb aurora-orb--pink"></div>
</div>
"""

# ═══════════════════════════════════════════════════════════
# 粒子场 HTML
# ═══════════════════════════════════════════════════════════
PARTICLE_HTML = """
<div class="particle-field">
    <div class="particle"></div>
    <div class="particle"></div>
    <div class="particle"></div>
    <div class="particle"></div>
    <div class="particle"></div>
    <div class="particle"></div>
    <div class="particle"></div>
    <div class="particle"></div>
    <div class="particle"></div>
    <div class="particle"></div>
</div>
"""

# ═══════════════════════════════════════════════════════════
# 网格纹理 HTML
# ═══════════════════════════════════════════════════════════
GRID_HTML = """
<div class="grid-texture"></div>
"""

# ═══════════════════════════════════════════════════════════
# WebGL 流体烟雾光标
# ═══════════════════════════════════════════════════════════
CURSOR_TRAIL_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body {
    width: 100%;
    height: 100%;
    overflow: hidden;
    background: transparent !important;
  }
  #fluid-canvas {
    display: block;
    position: fixed;
    inset: 0;
    width: 100%;
    height: 100%;
    background: transparent !important;
  }
</style>
</head>
<body>
<canvas id="fluid-canvas"></canvas>
<script type="module">
const canvas = document.getElementById('fluid-canvas');

function forwardToParent(event) {
  try {
    const parentDoc = window.parent.document;
    const x = event.clientX || 0;
    const y = event.clientY || 0;
    const target = parentDoc.elementFromPoint(x, y);
    if (!target) return;

    if ((event.type === 'mousedown' || event.type === 'click') && typeof target.focus === 'function') {
      target.focus();
    }

    const common = {
      bubbles: true,
      cancelable: true,
      view: window.parent,
      clientX: x,
      clientY: y,
      screenX: event.screenX || 0,
      screenY: event.screenY || 0,
      ctrlKey: !!event.ctrlKey,
      shiftKey: !!event.shiftKey,
      altKey: !!event.altKey,
      metaKey: !!event.metaKey,
      button: event.button || 0,
    };

    let cloned;
    if (event instanceof WheelEvent) {
      cloned = new WheelEvent(event.type, {
        ...common,
        deltaX: event.deltaX || 0,
        deltaY: event.deltaY || 0,
        deltaMode: event.deltaMode || 0,
      });
    } else if (event instanceof KeyboardEvent) {
      cloned = new KeyboardEvent(event.type, {
        bubbles: true,
        cancelable: true,
        key: event.key,
        code: event.code,
        ctrlKey: !!event.ctrlKey,
        shiftKey: !!event.shiftKey,
        altKey: !!event.altKey,
        metaKey: !!event.metaKey,
      });
    } else {
      cloned = new MouseEvent(event.type, common);
    }
    target.dispatchEvent(cloned);
  } catch (err) {
    // ignore
  }
}

function wireInteractions() {
  [
    'click', 'dblclick', 'contextmenu', 'mousedown', 'mouseup', 'wheel',
    'keydown', 'keyup', 'input', 'change'
  ].forEach((name) => {
    document.addEventListener(name, (event) => {
      event.stopPropagation();
      if (name !== 'wheel' && name !== 'contextmenu') {
        event.preventDefault();
      }
      forwardToParent(event);
    }, true);
  });
  document.addEventListener('dragstart', (event) => event.preventDefault(), true);
}

function startFallbackTrail() {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const dpr = Math.max(window.devicePixelRatio || 1, 1);
  let width = 0;
  let height = 0;
  const points = [];
  const palette = ['255,209,0', '255,107,53', '157,78,221', '34,197,94', '0,180,216'];

  function resize() {
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function addPoint(x, y) {
    points.push({
      x, y,
      life: 1,
      radius: 110 + Math.random() * 70,
      color: palette[Math.floor(Math.random() * palette.length)],
    });
  }

  function render() {
    ctx.clearRect(0, 0, width, height);
    ctx.globalCompositeOperation = 'lighter';
    for (let i = points.length - 1; i >= 0; i -= 1) {
      const p = points[i];
      p.life -= 0.012;
      p.radius *= 0.992;
      if (p.life <= 0.02) {
        points.splice(i, 1);
        continue;
      }
      const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.radius);
      g.addColorStop(0, `rgba(${p.color}, ${0.23 * p.life})`);
      g.addColorStop(0.45, `rgba(${p.color}, ${0.11 * p.life})`);
      g.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
      ctx.fill();
    }
    requestAnimationFrame(render);
  }

  window.addEventListener('resize', resize);
  window.addEventListener('mousemove', (event) => addPoint(event.clientX, event.clientY));
  window.addEventListener('touchmove', (event) => {
    const touch = event.touches && event.touches[0];
    if (touch) addPoint(touch.clientX, touch.clientY);
  }, { passive: true });

  resize();
  render();
}

async function startFluid() {
  try {
    const module = await import('https://cdn.jsdelivr.net/npm/webgl-fluid-enhanced@0.8.0/+esm');
    const webGLFluidEnhanced = module.default || module;

    webGLFluidEnhanced.simulation(canvas, {
      COLOR_PALETTE: ['#9d4edd', '#22c55e', '#ff6b35', '#00b4d8', '#ec4899', '#ffd100'],
      HOVER: true,
      TRIGGER: 'hover',
      SIM_RESOLUTION: 128,
      DYE_RESOLUTION: 1024,
      SPLAT_RADIUS: 0.28,
      SPLAT_FORCE: 6000,
      DENSITY_DISSIPATION: 0.978,
      VELOCITY_DISSIPATION: 0.985,
      PRESSURE: 0.8,
      PRESSURE_ITERATIONS: 20,
      CURL: 36,
      SHADING: true,
      COLORFUL: true,
      COLOR_UPDATE_SPEED: 4,
      BLOOM: true,
      BLOOM_INTENSITY: 0.9,
      BLOOM_ITERATIONS: 4,
      BLOOM_RESOLUTION: 256,
      BLOOM_THRESHOLD: 0.55,
      BLOOM_SOFT_KNEE: 0.7,
      SUNRAYS: true,
      SUNRAYS_RESOLUTION: 196,
      SUNRAYS_WEIGHT: 0.55,
      TRANSPARENT: true,
      PAUSED: false,
    });
  } catch (error) {
    console.warn('Fluid effect fallback:', error);
    startFallbackTrail();
  }
}

wireInteractions();
startFluid();
</script>
</body>
</html>
"""


def inject_css():
    """注入 Inspire UI 全部样式和背景层"""
    st.markdown(CSS_STYLES, unsafe_allow_html=True)

    # 注入背景层（顺序：网格 → 极光 → 粒子）
    st.markdown(GRID_HTML, unsafe_allow_html=True)
    st.markdown(AURORA_HTML, unsafe_allow_html=True)
    st.markdown(PARTICLE_HTML, unsafe_allow_html=True)

    # 注入 WebGL 流体光标
    inject_cursor_trail()


def inject_cursor_trail():
    """注入 Inspira 风格 WebGL 流体烟雾光标"""
    import streamlit.components.v1 as components

    st.markdown("""
    <style>
    div[data-testid="stHtml"] iframe {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        min-width: 100vw !important;
        min-height: 100vh !important;
        border: none !important;
        z-index: 99990 !important;
        background: transparent !important;
        pointer-events: auto !important;
    }
    </style>
    """, unsafe_allow_html=True)

    components.html(CURSOR_TRAIL_HTML, height=0)
