# 遇事不决问ai-规划执行助理（美团竞赛 Agent）

基于 **Plan-and-Execute（规划-执行）** 架构的多 Agent 协作系统，输入自然语言需求，自动完成语义理解 → 位置解析 → POI 搜索 → 方案规划 → 用户确认 → 执行落地 → 邮件通知的全闭环流程。

## 启动指南

### 环境要求

- Python 3.11+
- Windows / macOS / Linux

### 1) 进入项目目录

```powershell
cd e:\PythonProject\Private_planning_agent\meituan_competition_agent
```

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

### 4) 安装依赖

```powershell
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r backend\requirements.txt --no-cache-dir
```

### 5) 配置环境变量

项目提供 `.env.example` 作为模板，复制并填写：

```powershell
copy .env.example .env
```

关键配置项：

| 变量 | 说明 | 默认值 |
|---|---|---|
| `MEITUAN_AGENT_LLM_PROVIDER` | LLM 提供商（deepseek / openai / none） | `none` |
| `MEITUAN_AGENT_OPENAI_API_KEY` | API Key | 空 |
| `MEITUAN_AGENT_OPENAI_MODEL` | 模型名 | `gpt-4o-mini` |
| `MEITUAN_AGENT_MAP_PROVIDER` | 地图数据源（auto / osm / amap / mock） | `auto` |
| `MEITUAN_AGENT_AMAP_API_KEY` | 高德 Key（可选） | 空 |
| `MEITUAN_AGENT_ASR_PROVIDER` | 语音识别（qwen / none） | `none` |
| `MEITUAN_AGENT_MAX_QUEUE_MINUTES` | 排队容忍阈值（分钟） | `60` |

**不需要任何商业 Key 即可运行**：系统默认使用 OSM 真实数据 + 启发式规划，Demo 可用。

### 6) 启动后端（FastAPI）

```powershell
cd backend
..\.venv\Scripts\python run_api.py
```

验证：

```powershell
..\.venv\Scripts\python -c "import httpx; print(httpx.get('http://127.0.0.1:8000/health').json())"
# 输出: {"ok": true}
```

### 7) 构建并访问前端（Web UI）

前端使用 JavaScript/HTML/CSS（Vite 构建），不依赖 Streamlit。

先构建静态资源：

```powershell
cd e:\PythonProject\Private_planning_agent\meituan_competition_agent\webui
npm install
npm run build
```

然后启动后端并访问（后端会自动提供静态页面）：

- http://127.0.0.1:8000/ui

### 8) 运行测试

```powershell
cd e:\PythonProject\Private_planning_agent\meituan_competition_agent\backend
..\.venv\Scripts\python -m pytest -q
```

## 后端 API

### 业务 API

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/health` | 健康检查 |
| `POST` | `/init` | 初始化会话 `{ session_id?: str }` |
| `POST` | `/chat` | 对话 `{ session_id?, message, user_location? }` |
| `POST` | `/chat/stream` | 流式对话（SSE，事件 delta / done） |
| `GET` | `/state/{session_id}` | 获取会话状态 |
| `GET` | `/messages/{session_id}?limit=50` | 获取历史消息 |
| `POST` | `/asr/transcribe` | 语音转文字（需启用 ASR） |

### Mock API（模拟交易接口）

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/mock/search_poi?tag=亲子` | 搜索 POI |
| `GET` | `/mock/menu/{poi_id}?fat_content=true` | 查询菜单 |
| `GET` | `/mock/availability/{poi_id}?size=4` | 排队检查 |
| `POST` | `/mock/order/{poi_id}` | 模拟下单 |

## 前端交互

Web UI（JavaScript/HTML/CSS）特性：

- **自动定位**：浏览器定位授权 → 获取经纬度 → 右上角位置徽标展示
- **打字机输出**：SSE 流式接收后端响应，逐步呈现
- **方案卡片**：多候选方案可视化展示（支持左右切换 + 一键"就选它！"确认）
- **决策流程可见**：点线流程图展示各 Agent 阶段执行进度
- **等待动画**：彩色旋转等待 + 彩色线条进度条，降低长等待焦虑

## 接入 LLM 增强规划

在 `.env` 中配置 LLM 后，两处能力自动升级：

1. **SemanticAgent**：从简单意图分类升级为深度结构化需求提取（> 20 个字段）
2. **Planner**：从固定模式升级为 LLM 动态组合方案，能理解更复杂的约束关系

以 DeepSeek 为例：

```env
MEITUAN_AGENT_LLM_PROVIDER=deepseek
MEITUAN_AGENT_OPENAI_BASE_URL=https://api.deepseek.com
MEITUAN_AGENT_OPENAI_API_KEY=sk-your-key
MEITUAN_AGENT_OPENAI_MODEL=deepseek-v4-flash
```

当 LLM 输出非法 JSON 或不满足 schema 时，自动回退启发式规划，保证系统可用。

## 扩展指南

项目已将执行层强解耦。要接入真实能力：

- **地图数据**：新增实现类实现 `POISearchTool` + `MapTool`，在 `Container` 中替换注入
- **交易接口**：新增实现类实现 `MenuInfoTool` / `AvailabilityTool` / `OrderTool`，在 `Container` 中替换注入
- **RPA**：新增实现类实现 `RPAExecutor`，接入 Playwright / Appium 等自动化框架
- **记忆存储**：新增实现类实现 `MemoryStore`，如 Redis / PostgreSQL
- **LLM**：任何 OpenAI 兼容 API 均可，修改 `.env` 中的 `base_url` 和 `model` 即可

所有 API Key / Token 等敏感信息必须仅存在于 `.env`（或更严格的 secrets 管理系统）中，禁止硬编码。


### 下面给你一套 在 Windows + PowerShell 下最稳的启动步骤（全程显式使用这个 venv 的 python，避免用错解释器）。

方式 A：只启动后端，用后端直接提供 Web UI（推荐验收用）

1. 打开 PowerShell，进入项目根目录：
```
cd e:\PythonProject\Private_planning_agent
```
2. 安装/更新后端依赖（安装到你的 .venv 里）：
```
e:\PythonProject\Private_planning_agent\meituan_competition_agent\.venv\Scripts\python.exe -m pip install -r meituan_competition_agent\backend\requirements.txt
```
3. 构建 WebUI（这是 Node 依赖，不会装进 .venv ）：
```
cd e:\PythonProject\Private_planning_agent\meituan_competition_agent\webui
npm install
npm run build
```
4. 启动后端（用你的 .venv python 启动）：
```
cd e:\PythonProject\Private_planning_agent
e:\PythonProject\Private_planning_agent\meituan_competition_agent\.venv\Scripts\python.exe meituan_competition_agent\backend\run_api.py
```
5. 浏览器打开：
- http://127.0.0.1:8000/ui
方式 B：前后端分开启动（用于前端调试/HMR）

- 终端 1（后端）：
```
cd e:\PythonProject\Private_planning_agent
e:\PythonProject\Private_planning_agent\meituan_competition_agent\.venv\Scripts\python.exe meituan_competition_agent\backend\run_api.py
```
- 终端 2（前端 dev server）：
```
cd 
cd e:\PythonProject\Private_planning_agent\meituan_competition_agent\webui
npm install
npm run dev
```
依赖是否安装在虚拟环境中？

- pip install ... ：会安装到你这个 .venv （只要你像上面那样用 .venv\Scripts\python.exe -m pip ... 或先激活 venv）。
- npm install ... ：安装的是前端依赖到 meituan_competition_agent\webui\node_modules ， 与 Python 虚拟环境无关 。
