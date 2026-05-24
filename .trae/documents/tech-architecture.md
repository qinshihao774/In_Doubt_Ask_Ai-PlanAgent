 # 私人规划执行助理 Web 前端重构（技术架构）
 
 ## 1. 目标
 - 使用 JavaScript/HTML/CSS 实现全新的 Web UI
 - 复用现有 FastAPI 后端能力（不改接口）
 - 复刻并延续现有 UI 的动效与视觉语言
 
 ## 2. 总体架构
 - **后端**：FastAPI（现有）
 - **前端**：纯 Web 前端（建议采用 Vite 管理开发与构建，但产物为 HTML/CSS/JS）
 - **通信**：
   - REST：`/health`、`/init`
   - SSE：`/chat/stream`（EventSource 或 fetch+ReadableStream）
 
 ## 3. 前端技术选型
 ### 3.1 选型原则
 - 视觉/动效优先（CSS 动画 + 少量 Canvas）
 - 低依赖、易部署（静态资源即可运行）
 - 易于复刻现有 UI：将现有 CSS 体系迁移为 CSS 变量与模块化样式
 
 ### 3.2 建议方案
 - 构建工具：Vite（vanilla）
 - UI 形态：单页应用（SPA），不引入重型框架也可实现
 - 状态管理：轻量 store（模块内状态 + DOM 更新）
 - SSE：
   - 优先：`fetch('/chat/stream')` + `ReadableStream` 解析 `data:` 行（兼容 POST）
   - 备选：后端新增 GET SSE（可选，但当前 PRD 不要求）
 
 ## 4. 模块划分
 - `src/api/`：后端 API 封装
   - `initSession()`
   - `streamChat(payload, onEvent)`
 - `src/state/`：会话状态
   - `sessionId`
   - `messages[]`
   - `pipelineConfig[]`
   - `pipelineStates{}`
   - `locationPermission`
   - `detectedLocation`
 - `src/ui/`：UI 组件（纯 DOM）
   - `renderHero()`
   - `renderChat(messages)`
   - `renderPlanCards(plans)`
   - `renderPipeline(config, states)`
   - `renderThinking(statusText?)`
   - `renderLocationControls()`
 - `src/styles/`：
   - `tokens.css`（颜色/变量）
   - `effects.css`（极光/噪点/流光边框/阴影）
   - `components.css`（卡片/气泡/流程/等待动画）
 
 ## 5. 关键实现细节
 ### 5.1 SSE（POST）解析
 - 使用 `fetch` 发起 POST，读取 `response.body.getReader()`，按 `\n\n` 分帧，解析以 `data:` 开头的 JSON。
 - pipeline 事件：
   - `pipeline_config`：初始化 stages 与 states
   - `pipeline_stage`：更新当前 stage 状态（pending/running/done/error）
 - delta 事件：拼接文本到 assistant 当前回复气泡
 
 ### 5.2 方案卡片解析
 - 复用现有文本协议（“方案1：… 理由：… - item …”）
 - 在前端解析为：
   - `intro`
   - `plans[] = {title, rawTitle, rationale, items[]}`
 - UI：叠层卡片 + 圆点导航 + “就选它”按钮（发送 `确认 方案X`）
 
 ### 5.3 定位与右上角徽标
 - 授权：前端弹出轻量按钮（启用/跳过）
 - 获取：`navigator.geolocation.getCurrentPosition`
 - 逆地理编码：
   - 复用现有逻辑：调用 Nominatim reverse（可选）或仅展示 “浏览器定位(~xxm)”
 - 结果：右上角 badge（ellipsis）
 - payload：把 `user_location` 传入 `/chat/stream`
 
 ### 5.4 视觉复刻策略
 - 将现有 `ui/styles/inspire_ui.py` 中的 CSS 抽取/迁移为 `.css` 文件
 - Canvas 背景（可选）：粒子/光晕层（低频刷新）
 - 组件动效：尽量 CSS-only（减少 JS 负担）
 
 ## 6. 部署方案
 - **开发**：
   - 前端：Vite dev server
   - 后端：现有 FastAPI
 - **生产**（推荐）：
   - 前端 build 为静态文件，放入后端 `static/`，FastAPI 挂载静态资源并提供 `index.html`
   - API_BASE 默认同源（避免 CORS）
 
 ## 7. 风险与对策
 - SSE 兼容性：采用 fetch stream（POST）而不是 EventSource（GET-only）
 - 动效性能：背景动效降级策略（低端设备关掉粒子层）
 - 样式复刻偏差：以 CSS tokens + 组件拆分逐步校准
 
