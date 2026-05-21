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
.\.venv\Scripts\python -m pip install -r backend\requirements.txt -r ui\requirements.txt --no-cache-dir
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

### 7) 启动前端（Streamlit）

新开一个终端：

```powershell
cd e:\PythonProject\Private_planning_agent\meituan_competition_agent
.\.venv\Scripts\python -m streamlit run ui\streamlit_app.py
```

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

基于 Streamlit 的 Inspire UI 流体设计：

- **自动定位**：浏览器 GPS → IP 定位 → 兜底坐标三级获取用户位置
- **打字机输出**：SSE 流式接收后端响应，逐字呈现
- **3D 方案卡片**：多候选方案叠层展示，点击圆点切换，一键"就选它！"确认
- **思考动画**：骨架屏 → 思考指示器 → 进度条 → 长等待提示的完整加载体验
- **会话管理**：侧栏显示会话 ID 和探测位置，支持重置

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
