# 遇事不决问 AI - 规划执行助理

基于 **Plan-and-Execute（规划-执行）** 架构的多 Agent 协作系统。用户输入自然语言需求后，系统会自动完成 **语义理解 → 位置解析 → POI 搜索 → 天气/路线辅助 → 方案规划 → 用户确认 → 执行落地 → 邮件通知（可选）** 的闭环流程，把“想出去玩、吃饭、带娃、控预算、别太远”这类模糊诉求转化为可执行的本地生活行程方案。

## 项目亮点

- **多 Agent 协作**：由 ManagerAgent 统一调度 SemanticAgent、MapAgent、FoodAgent、LeisureAgent、Planner 和 ExecutionAgent。
- **规划-执行闭环**：不仅生成建议，还支持用户确认后执行排队检查、预约、菜单查询、模拟下单和活动安排。
- **可接入真实能力**：地图、交易、RPA、记忆存储、LLM 均通过接口或容器注入解耦，便于替换为生产服务。
- **前端体验完整**：支持浏览器定位、天气展示、SSE 打字机输出、方案卡片轮播、决策流程可视化、历史会话、置顶/删除会话和路线地图面板。
- **鲁棒回退机制**：LLM 输出异常、地图 Provider 不可用或执行失败时，系统会回退启发式规划、Mock 数据或触发重规划。

## 项目结构

```text
.
├── backend/
│   ├── run_api.py
│   ├── requirements.txt
│   ├── src/meituan_agent/
│   │   ├── api/              # FastAPI 入口与接口定义
│   │   ├── agents/           # 语义、地图、美食、休闲、执行、管理 Agent
│   │   ├── planning/         # 启发式/LLM 规划器、约束过滤、调度逻辑
│   │   ├── tools/            # OSM、高德、Mock 工具与工具抽象
│   │   ├── memory/           # SQLite / 内存会话存储
│   │   ├── services/         # 会话、天气等服务
│   │   ├── asr/              # 语音识别接入
│   │   ├── llm/              # OpenAI 兼容 LLM 客户端
│   │   └── container.py      # 依赖组装与 Provider 选择
│   └── tests/                # 后端测试
├── webui/
│   ├── src/                  # 原生 Web 前端模块
│   ├── public/               # 图标与静态资源
│   └── package.json
├── documents/                # PRD 与技术架构文档
├── design-doc.md
└── README.md
```

## 启动指南

### 环境要求

- Python 3.11+（`pyproject.toml` 要求 3.10+，推荐 3.11+）
- Node.js 20.19+ 或 22.12+（用于构建 Web UI，匹配当前 Vite 8 要求）
- Windows / macOS / Linux

### 1) 进入项目目录

```powershell
cd E:\PythonProject\In_Doubt_Ask_Ai-PlanAgent
```

如果你的项目在其他目录，请切换到实际 clone 下来的项目根目录。

### 2) 创建虚拟环境

```powershell
python -m venv .venv
```

### 3) 激活虚拟环境

PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
# 如果脚本执行被阻止：
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

CMD：

```bat
.\.venv\Scripts\activate.bat
```

macOS / Linux：

```bash
source .venv/bin/activate
```

### 4) 安装后端依赖

```powershell
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r backend\requirements.txt --no-cache-dir
```

macOS / Linux：

```bash
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt --no-cache-dir
```

### 5) 配置环境变量

项目会从根目录 `.env` 读取配置。如果没有 `.env.example`，可以手动创建 `.env`，只填写你需要启用的能力；不填写也能以默认配置运行。

关键配置项：

| 变量 | 说明 | 默认值 |
|---|---|---|
| `MEITUAN_AGENT_ENV` | 运行环境标识 | `dev` |
| `MEITUAN_AGENT_DATA_DIR` | 数据目录 | `backend/data` |
| `MEITUAN_AGENT_MEMORY_BACKEND` | 记忆存储后端 | `sqlite` |
| `MEITUAN_AGENT_SQLITE_PATH` | SQLite 记忆库路径 | `backend/data/memory.sqlite3` |
| `MEITUAN_AGENT_LLM_PROVIDER` | LLM 提供商（openai / deepseek / none 等，OpenAI 兼容即可） | `none` |
| `MEITUAN_AGENT_OPENAI_BASE_URL` | OpenAI 兼容接口地址 | `https://api.openai.com/v1` |
| `MEITUAN_AGENT_OPENAI_API_KEY` | LLM API Key | 空 |
| `MEITUAN_AGENT_OPENAI_MODEL` | LLM 模型名 | `gpt-4o-mini` |
| `MEITUAN_AGENT_MAP_PROVIDER` | 地图数据源（auto / osm / amap / mock） | `auto` |
| `MEITUAN_AGENT_AMAP_API_KEY` | 高德 Web 服务 Key，用于后端 POI/路线能力 | 空 |
| `MEITUAN_AGENT_AMAP_JS_KEY` | 高德 JS API Key，用于前端地图展示 | 空 |
| `MEITUAN_AGENT_AMAP_SECURITY_CODE` | 高德 JS API 安全密钥 | 空 |
| `MEITUAN_AGENT_ASR_PROVIDER` | 后端 ASR 提供商（qwen / none） | `none` |
| `MEITUAN_AGENT_ASR_MODEL` | ASR 模型名 | `qwen3-asr-flash` |
| `MEITUAN_AGENT_DASHSCOPE_APP_ID` | 可选：DashScope 应用 ID，用于语义 Agent 接入 | 空 |
| `DASHSCOPE_API_KEY` | 可选：DashScope API Key，用于 Qwen ASR 或 DashScope 语义 Agent | 空 |
| `MEITUAN_AGENT_MAX_QUEUE_MINUTES` | 排队容忍阈值（分钟） | `60` |
| `MEITUAN_AGENT_EMAIL_SENDER` | 可选：邮件发件邮箱；当前执行完成后也会把行程发送到该邮箱 | 空 |
| `MEITUAN_AGENT_EMAIL_PASSWORD` | 可选：邮箱 SMTP 授权码，如 QQ 邮箱授权码 | 空 |

最小 `.env` 示例：

```env
MEITUAN_AGENT_MAP_PROVIDER=auto
MEITUAN_AGENT_LLM_PROVIDER=none
```

**不需要任何商业 Key 即可运行**：系统默认在 `auto` 模式下优先使用 OSM 真实数据；当选择 `mock` 时会使用本地模拟数据。若配置高德 Key，则可切换到高德数据源。

### 6) 启动后端（FastAPI）

```powershell
cd backend
python run_api.py
```

默认服务地址：

- http://127.0.0.1:8000
- http://127.0.0.1:8000/docs

验证：

```powershell
..\.venv\Scripts\python -c "import httpx; print(httpx.get('http://127.0.0.1:8000/health').json())"
```

也可以在项目根目录执行：

```powershell
.\.venv\Scripts\python -c "import httpx; print(httpx.get('http://127.0.0.1:8000/health').json())"
```

期望输出：

```json
{"ok": true}
```

### 7) 构建并访问前端（Web UI）

前端使用 JavaScript/HTML/CSS（Vite 构建），不依赖 Streamlit。

先构建静态资源：

```powershell
cd webui
npm install
npm run build
```

然后启动后端并访问（后端会自动挂载 `webui/dist`）：

- http://127.0.0.1:8000/ui

开发模式也可以单独启动 Vite：

```powershell
cd webui
npm run dev
```

### 8) 运行测试

```powershell
cd backend
..\.venv\Scripts\python -m pytest -q
```

## 后端 API

### 业务 API

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/` | 后端根路径，返回服务提示 |
| `GET` | `/health` | 健康检查 |
| `POST` | `/init` | 初始化或恢复会话 `{ session_id?: str }` |
| `POST` | `/chat` | 普通对话 `{ session_id?, message, user_location? }` |
| `POST` | `/chat/stream` | 流式对话（SSE），用于前端打字机输出和流程进度 |
| `GET` | `/state/{session_id}` | 获取会话状态 |
| `GET` | `/messages/{session_id}?limit=50` | 获取历史消息 |
| `GET` | `/plans/{session_id}` | 获取当前会话候选方案 |
| `GET` | `/sessions?limit=30&offset=0` | 获取历史会话列表 |
| `DELETE` | `/sessions/{session_id}` | 删除历史会话 |
| `POST` | `/sessions/{session_id}/pin` | 置顶或取消置顶会话 `{ pinned: bool }` |
| `GET` | `/weather/current?lat=31.2&lng=121.5` | 查询当前位置天气快照 |
| `GET` | `/config/map` | 获取前端地图展示所需的高德 JS 配置 |
| `POST` | `/asr/transcribe` | 上传音频并转文字（需启用 `MEITUAN_AGENT_ASR_PROVIDER=qwen`） |

### SSE 事件

`POST /chat/stream` 会返回 `text/event-stream`，前端按 `data: {...}` 解析。主要事件包括：

| 事件类型 | 说明 |
|---|---|
| `session` | 返回当前 `session_id` |
| `pipeline_config` | 返回流程阶段配置 |
| `pipeline_stage` | 更新某个 Agent 阶段状态：`pending` / `running` / `done` / `error` |
| `plans` | 返回结构化候选方案，供前端渲染方案卡片 |
| `execution_result` | 执行阶段结果（预留/兼容事件） |
| `delta` | 分块文本，用于打字机输出 |
| `done` | 本轮响应结束 |

当前流水线阶段：

```text
语义分析 → 地图搜索 → 美食搜索 → 休闲探索 → 方案规划 → 执行落地
```

### Mock 与工具层说明

当前 `api/main.py` 中没有单独注册 `/mock/...` HTTP 路由。Mock 能力主要作为工具层注入使用：

- `MEITUAN_AGENT_MAP_PROVIDER=mock`：使用本地 `backend/data/mock_pois.json` 和 MockMapTool。
- `Container` 中的 `SimRPA` / `SimMenu` / `SimAvailability` / `SimOrder`：用于模拟 RPA、菜单查询、排队检查和下单。

如果需要对外暴露 Mock HTTP 接口，可以在 `backend/src/meituan_agent/api/main.py` 中新增路由，并复用 `MockMeituanTools` 或现有工具抽象。

## 前端交互

Web UI（JavaScript/HTML/CSS）特性：

- **自动定位**：浏览器定位授权 → 获取经纬度 → 右上角位置徽标展示，并随请求传入后端。
- **天气辅助**：定位后查询天气，后端也会在规划中优先规避恶劣天气下的户外活动。
- **方案卡片**：多候选方案可视化展示，支持左右切换、圆点导航、滑动切换和一键“就选它！”确认。
- **决策流程可见**：点线流程图展示各 Agent 阶段执行进度。
- **地图路线展示**：候选方案可打开地图面板查看路线。
- **历史会话管理**：支持加载历史会话、置顶和删除。
- **语音输入**：前端优先使用浏览器 `SpeechRecognition` 能力。
- **等待动画**：彩色旋转等待 + 彩色线条进度条，降低长等待焦虑。

## 接入 LLM 增强规划

在 `.env` 中配置 LLM 后，两处能力会自动升级：

1. **SemanticAgent**：从规则/关键词理解升级为结构化需求提取，输出位置、餐饮、休闲、同行人、时间、硬约束等字段。
2. **Planner**：从启发式组合升级为 LLM 动态组合方案，能理解更复杂的约束关系。

以 DeepSeek 为例：

```env
MEITUAN_AGENT_LLM_PROVIDER=deepseek
MEITUAN_AGENT_OPENAI_BASE_URL=https://api.deepseek.com
MEITUAN_AGENT_OPENAI_API_KEY=sk-your-key
MEITUAN_AGENT_OPENAI_MODEL=deepseek-v4-flash
```

以 OpenAI 为例：

```env
MEITUAN_AGENT_LLM_PROVIDER=openai
MEITUAN_AGENT_OPENAI_BASE_URL=https://api.openai.com/v1
MEITUAN_AGENT_OPENAI_API_KEY=sk-your-key
MEITUAN_AGENT_OPENAI_MODEL=gpt-4o-mini
```

当 LLM 输出非法 JSON 或不满足 schema 时，系统会自动回退到启发式规划，保证服务可用。

## 地图数据源

`MEITUAN_AGENT_MAP_PROVIDER` 支持：

| 值 | 说明 |
|---|---|
| `auto` | 自动选择：配置高德 Key 时优先高德，否则使用 OSM |
| `osm` | 使用 OpenStreetMap / Nominatim / Overpass / OSRM |
| `amap` | 使用高德能力，必须配置 `MEITUAN_AGENT_AMAP_API_KEY` |
| `mock` | 使用本地模拟 POI 数据，适合演示和离线调试 |

前端地图展示使用高德 JS API 时，可额外配置：

```env
MEITUAN_AGENT_AMAP_JS_KEY=your-js-key
MEITUAN_AGENT_AMAP_SECURITY_CODE=your-security-code
```

## 执行落地与邮件通知

用户确认方案后，ExecutionAgent 会按方案逐项执行：

1. 对餐饮 POI 检查排队/可订状态。
2. 模拟预约餐位。
3. 查询菜单并按人数选择菜品。
4. 模拟下单。
5. 对休闲 POI 模拟预约活动或安排到访。
6. 汇总完整行程。

如果设置了 `MEITUAN_AGENT_EMAIL_SENDER` 和 `MEITUAN_AGENT_EMAIL_PASSWORD`，执行完成后会尝试发送行程邮件。当前实现默认使用 QQ 邮箱 SMTP（`smtp.qq.com:587`），并将行程发送到 `MEITUAN_AGENT_EMAIL_SENDER` 对应邮箱；如需区分发件人与收件人，可扩展 `email_sender.py` 或执行阶段调用逻辑。

## 扩展指南

项目已将执行层、工具层和存储层解耦。要接入真实能力：

- **地图数据**：新增实现类实现 `POISearchTool` + `MapTool`，在 `Container` 中替换注入。
- **交易接口**：新增实现类实现 `MenuInfoTool` / `AvailabilityTool` / `OrderTool`，在 `Container` 中替换注入。
- **RPA**：新增实现类实现 `RPAExecutor`，接入 Playwright / Appium 等自动化框架。
- **记忆存储**：新增实现类实现 `MemoryStore`，如 Redis / PostgreSQL。
- **LLM**：任何 OpenAI 兼容 API 均可，修改 `.env` 中的 `base_url` 和 `model` 即可。
- **ASR**：当前后端预留 Qwen ASR；前端同时支持浏览器原生 `SpeechRecognition`。
- **前端 UI**：在 `webui/src` 中按模块扩展 `api.js`、`state.js`、`plans.js`、`pipeline.js`、`map.js` 和 `main.js`。

所有 API Key / Token 等敏感信息必须仅存在于 `.env`（或更严格的 secrets 管理系统）中，禁止硬编码。

## 常见问题

### 依赖是否安装在虚拟环境中？

- `pip install ...`：会安装到 Python 虚拟环境 `.venv` 中，只要你使用 `.venv\Scripts\python.exe -m pip ...` 或先激活 venv。
- `npm install ...`：会把前端依赖安装到 `webui/node_modules`，与 Python 虚拟环境无关。


### 没有高德 Key 可以运行吗？

可以。默认 `auto` 模式下，如果没有高德 Key，会使用 OSM 相关服务。若网络环境无法访问 OSM，可切换到：

```env
MEITUAN_AGENT_MAP_PROVIDER=mock
```

### `/ui` 打不开怎么办？

请先构建前端：

```powershell
cd webui
npm install
npm run build
```

然后重新启动后端。后端只会在 `webui/dist` 存在时挂载 `/ui` 静态页面。
