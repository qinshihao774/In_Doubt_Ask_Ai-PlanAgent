# Inspire UI - 流体玻璃态设计系统

## 🎨 设计理念

Inspire UI 采用前沿的 **Glassmorphism（玻璃态）** 设计风格，结合 **流体动画** 和 **极致交互体验**，打造沉浸式的 AI 对话界面。

### 核心设计原则

1. **玻璃态 (Glassmorphism)**
   - 半透明背景
   -  backdrop-filter 模糊效果
   - 微妙的边框光泽

2. **流体动画 (Fluid Animation)**
   - 平滑的过渡效果
   - 呼吸式脉冲动画
   - 打字机效果

3. **美团黄主色调**
   - 主色: `#FFD100`
   - 辅助色: `#FF8C00`, `#7B2CBF`
   - 深色背景: `#0D0D15`

## ✨ 特性列表

### 已实现特性

- [x] **流体玻璃态 UI**
  - 半透明卡片
  - backdrop-filter 模糊
  - 渐变边框

- [x] **打字机效果**
  - 逐字显示
  - 闪烁光标
  - 流式输出

- [x] **骨架屏加载**
  - 闪烁动画
  - 响应式布局
  - 渐变光泽

- [x] **流体背景动画**
  -  radial-gradient 渐变
  - 呼吸式动画
  - 多层叠加

- [x] **脉冲动画**
  - 在线指示器
  - 呼吸效果
  - 阴影扩散

- [x] **响应式布局**
  - 移动端适配
  - 平板优化
  - 桌面端增强

### 待实现特性

- [ ] **语音输入**
  - 麦克风动画
  - 波形可视化
  - 实时转录

- [ ] **地图集成**
  - 路线规划
  - POI 标记
  - 实时导航

- [ ] **3D 效果**
  - 卡片翻转
  - 视差滚动
  - 深度感

## 🚀 快速开始

### 启动前端

```bash
# 进入 UI 目录
cd meituan_competition_agent/ui

# 激活虚拟环境
..\..\.venv\Scripts\activate

# 启动 Streamlit
streamlit run streamlit_app.py
```

### 访问应用

打开浏览器访问: http://localhost:8501

## 🎨 自定义主题

### 修改主色调

编辑 `streamlit_app.py` 中的 CSS 变量:

```css
:root {
    --primary-yellow: #FFD100;  /* 修改为主色调 */
    --accent-purple: #7B2CBF;   /* 修改为辅助色 */
}
```

### 调整动画速度

```css
@keyframes fluidMove {
    /* 修改动画时长 */
    animation: fluidMove 30s ease-in-out infinite;
}
```

## 📱 响应式断点

| 断点 | 宽度 | 布局调整 |
|------|------|----------|
| Mobile | < 768px | 单列，缩小字体 |
| Tablet | 768px - 1024px | 两列，中等字体 |
| Desktop | > 1024px | 两列，完整字体 |

## 🔧 性能优化

### 已实现
- [x] CSS 动画使用 `transform` 和 `opacity`
- [x] `will-change` 属性优化
- [x] 滚动条自定义减少重绘

### 待优化
- [ ] 图片懒加载
- [ ] 虚拟滚动
- [ ] Web Worker 处理

## 📝 更新日志

### v1.0.0 (2024)
- ✨ 初始版本发布
- 🎨 Inspire UI 设计系统
- 💫 打字机效果
- 🌊 流体动画
- 📱 响应式布局

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License