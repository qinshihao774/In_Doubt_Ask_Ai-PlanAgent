# 遇事不决问ai-规划执行助理（美团竞赛 Agent）

基于 **Plan-and-Execute（规划-执行）** 架构的多 Agent 协作系统，输入自然语言需求，自动完成语义理解 → 位置解析 → POI 搜索 → 方案规划 → 用户确认 → 执行落地 → 邮件通知的全闭环流程。

## 架构概览

```
用户输入（自然语言 / 语音）
       │
       ▼
┌─────────────────────────────────────────────────┐
│                  ManagerAgent                    │
│              （编排调度 & 状态机驱动）              │
│                                                  │
│  SemanticAgent ──→ MapAgent ──→ FoodAgent        │
│                         │            │            │
│                         └──→ LeisureAgent         │
│                                  │               │
│                                  ▼               │
│                              Planner             │
│                                  │               │
│                       用户确认方案后              │
│                                  │               │
│                                  ▼               │
│                          ExecutionAgent          │
│                     （失败则自动重规划）           │
└─────────────────────────────────────────────────┘
       │
       ▼
  前端 Streamlit（Inspire UI 流体设计）
  · 打字机流式输出 · 3D 卡片方案选择 · 浏览器定位
```

## 核心特性

- **Plan-and-Execute 闭环**：自然语言需求 → 多候选方案规划 → 用户确认 → 逐店执行（排队检查/菜单查询/下单）→ 失败自动重规划
- **深度语义分析**：LLM 一次性完成意图分类 + 餐饮约束 + 休闲偏好 + 人员组成 + 时间预算 + 位置约束 + 硬性限制的结构化提取，零硬编码规则
- **多 Agent 协作**：7 个专业化 Agent 各司其职，通过 `SessionState` 共享上下文，`ManagerAgent` 统一编排
- **强解耦设计**：领域模型、MemoryStore、工具接口（POI/菜单/排队/下单/地图/RPA）均通过抽象基类注入，新增数据源只需实现接口
- **多地图数据源**：高德 → OpenStreetMap → Mock 三级自动降级，无商业 Key 也能使用真实 POI 和路线
- **LLM 双轨规划**：LLM 可用时输出结构化 JSON 规划方案（Pydantic 校验）；不可用时自动回退启发式规划
- **语音输入**：可选接入千问 ASR（OpenAI 兼容），支持中/英/粤语
- **邮件投递**：执行完成后将完整行程 HTML 邮件发送至用户邮箱

## 目录结构

```
meituan_competition_agent/
  .env                        # 环境变量（不含真实秘钥，已 gitignore）
  .env.example                # 环境变量模板
  .gitignore
  README.md
  backend/
    requirements.txt
    pyproject.toml
    run_api.py                # FastAPI 启动入口
    data/
      mock_pois.json          # Mock 数据（离线演示用）
    src/meituan_agent/
      agents/                 # Agent 层
        base.py               # Agent 抽象基类
        manager_agent.py      # 编排调度 & 状态机
        semantic_agent.py     # LLM 深度语义分析
        map_agent.py          # 位置解析 & POI 预搜索
        food_agent.py         # 餐饮搜索
        leisure_agent.py      # 休闲娱乐搜索
        execution_agent.py    # 方案执行落地
      planning/               # 规划层
        planner.py            # HeuristicPlanner / LLMPlanner / FallbackPlanner
        schema.py             # LLM 规划输出 Schema
      domain/
        models.py             # 领域模型（SessionState / POI / ItineraryPlan / SemanticSchema 等）
      memory/                 # 记忆 & 状态持久化
        base.py               # MemoryStore 抽象接口
        sqlite_store.py       # SQLite 实现
        inmemory.py           # 内存实现（测试用）
        factory.py            # 工厂方法
      tools/                  # 工具层（全部通过接口注入）
        base.py               # POISearchTool / MapTool / MenuInfoTool / AvailabilityTool / OrderTool / RPAExecutor 抽象
        amap_tools.py         # 高德地图实现
        osm_tools.py          # OpenStreetMap 实现（Nominatim + Overpass + OSRM）
        mock_map.py           # Mock 地图
        mock_meituan.py       # Mock 美团交易工具
        mock_rpa.py           # Mock RPA
      services/
        session_service.py    # 会话服务（协调 Memory + Manager）
      api/
        main.py               # FastAPI 路由（/init /chat /chat/stream /asr/transcribe 等）
      asr/
        qwen_asr.py           # 千问语音识别
      llm/
        openai_compat.py      # OpenAI 兼容 LLM 客户端
      config.py               # 配置加载（pydantic-settings）
      container.py            # 依赖注入容器
      email_sender.py         # 邮件发送
      location_parser.py      # 用户消息中的位置实体提取
    tests/                    # 测试
      conftest.py
      test_manager_flow.py
      test_llm_planner_flow.py
      test_location_planning_guardrails.py
      test_map_provider_fallback.py
      test_osm_overpass_resilience.py
  ui/
    requirements.txt
    streamlit_app.py          # Streamlit 前端主入口
    app_inspire.py
    components/
      animations.py           # 骨架屏 / 脉冲 / 打字机动画
      geolocation.py          # 浏览器定位
    pages/
      chat_page.py
    styles/
      inspire_ui.py           # Inspire UI CSS 注入
```

## Agent 职责详解

### 1. SemanticAgent — 深度语义分析

**职责**：将用户的自然语言需求一次性转换为结构化约束，供下游所有 Agent 消费。

- 调用 LLM（OpenAI 兼容接口）进行深度语义理解
- 输出 `SemanticSchema` JSON，字段覆盖：
  - `intent`：意图分类（planning / chat / confirmation）
  - `location`：位置约束（区域、半径、是否可超出）
  - `food`：餐饮约束（菜系、避讳、口味、预算、就餐场景）
  - `leisure`：休闲约束（活动类型、氛围、室内/室外、单活动时长）
  - `party`：同行人员（人数、是否带娃、娃年龄、人员组成）
  - `timing`：时间约束（出发时间、总时长、日期）
  - `hard_constraints`：不可违背的硬性限制列表
  - `free_text_summary`：需求一句话摘要
- 零硬编码规则——所有推理由 LLM 动态完成
- LLM 不可用时回退为默认 `SemanticSchema`，系统仍可工作

**源码位置**：[semantic_agent.py](backend/src/meituan_agent/agents/semantic_agent.py)

### 2. MapAgent — 位置解析 & POI 预搜索

**职责**：确定用户位置，预搜索周边 POI，为后续 Agent 提供数据基础。

- 从 `SemanticSchema` 的位置约束中提取区域信息
- 三级位置解析策略：
  1. 语义分析中的命名区域（"望京"、"三里屯"）
  2. 用户消息中的位置实体（正则提取）
  3. IP 地理位置（`ipwho.is` 免费 API）
  4. 兜底：北京天安门（默认坐标）
- 在多数据源之间自动选择（高德 → OSM → Mock）
- 预搜索周边餐饮和休闲 POI，写入 `state.scratch` 供后续 Agent 复用
- 支持路线计算（`enrich_routes`）：为行程方案填充各 POI 之间的交通方式、耗时、距离

**源码位置**：[map_agent.py](backend/src/meituan_agent/agents/map_agent.py)

### 3. FoodAgent — 餐饮搜索

**职责**：根据语义分析中的餐饮约束，搜索和过滤餐厅候选。

- 搜索标签完全由 `SemanticSchema.food` 驱动：
  - `cuisine_types`（菜系）优先 → `dietary`（饮食偏好）次之 → 兜底标签"餐饮"
- 增量半径搜索（3km → 6km → 10km），保证就近优先且数据充足
- 约束过滤：
  - 避讳过滤（`food.avoid` 中的关键词匹配 POI 名称和标签）
  - 预算过滤（人均消费 ≤ 预算 × 1.2 的弹性上限）
- 去重 + 仅保留餐饮类 POI
- 搜索结果不足时回退到 MapAgent 预搜索的 `nearby_food`

**源码位置**：[food_agent.py](backend/src/meituan_agent/agents/food_agent.py)

### 4. LeisureAgent — 休闲娱乐搜索

**职责**：根据语义分析中的休闲约束，搜索和过滤休闲娱乐候选。

- 搜索标签完全由 `SemanticSchema.leisure` 驱动：
  - `activity_types`（活动类型）优先 → 带娃时默认"亲子/展览" → 兜底"展览/休闲"
- 增量半径搜索（同 FoodAgent）
- 排除"餐饮"类 POI（由 FoodAgent 专责）
- 按评分降序排列，取 Top 10 候选项

**源码位置**：[leisure_agent.py](backend/src/meituan_agent/agents/leisure_agent.py)

### 5. Planner（规划层）— 方案生成

**职责**：将 FoodAgent 和 LeisureAgent 的候选 POI 组合为 2-3 个差异化行程方案。

采用 **LLM + 启发式双轨 + 回退** 架构：

| Planner | 触发条件 | 策略 |
|---|---|---|
| `LLMPlanner` | LLM 可用 | LLM 输出 `PlanningOutput` JSON（含 title / rationale / items），Pydantic 校验 |
| `HeuristicPlanner` | LLM 不可用或 LLM 输出非法 | 基于 profile（亲子/朋友/混合）用不同餐厅+休闲组合 |
| `FallbackPlanner` | 始终作为包装器 | `LLMPlanner` 失败或结果为空时自动回退 `HeuristicPlanner` |

- 每个方案内的 POI 组合**必须完全不同**（不只是顺序变化），通过逐轮排除已用 POI ID 实现
- 自动为方案内的 POI 序列计算路线（`enrich_routes`）
- 每个方案包含 `id` / `title` / `rationale` / `items`（含路线信息）

**源码位置**：[planner.py](backend/src/meituan_agent/planning/planner.py) / [schema.py](backend/src/meituan_agent/planning/schema.py)

### 6. ExecutionAgent — 方案执行落地

**职责**：将用户确认的方案逐店执行，失败时通知 ManagerAgent 触发重规划。

执行流程（按方案中的 POI 顺序）：

1. **非餐饮 POI**：直接标记"已安排到访"
2. **餐饮 POI**：
   - 排队检查（`check_table_availability`）—— 超过 `max_queue_minutes` 阈值则失败
   - 菜单查询（`get_menu_info`）—— 减脂模式下返回轻食菜单
   - 自动选菜（根据人数选推荐菜品）
   - 模拟下单（`place_order`）—— 返回订单号
3. 任一环节失败则设置 `state.last_error`，由 ManagerAgent 捕获并触发重规划
4. 全部成功则设置 `state.status = completed`

执行完成后通过 `build_itinerary` 构建完整行程数据（含路线和执行状态），供邮件和前端展示使用。

**源码位置**：[execution_agent.py](backend/src/meituan_agent/agents/execution_agent.py)

### 7. ManagerAgent — 编排调度 & 状态机

**职责**：多 Agent 流水线的总调度，驱动状态机，处理确认和重规划。

状态机流转：

```
planning → awaiting_confirmation → executing → completed
                ↑                        │
                │  执行失败自动重规划      │
                └────────────────────────┘
```

核心流水线（`step` 方法）：

```
阶段 0: SemanticAgent 深度分析
阶段 1: 意图路由
  ├── intent=chat         → 闲聊回复（LLM 可用时）
  ├── intent=confirmation → 用户确认方案 → ExecutionAgent 执行 → 成功发邮件
  │                         └── 失败 → _replan_after_failure → 重新 awaiting_confirmation
  └── intent=planning     → MapAgent → FoodAgent → LeisureAgent → Planner
                            → 方案去重（_dedup_plans） → 输出候选方案
```

方案去重逻辑（`_dedup_plans`）：
- 以 POI ID 指纹判断方案是否实质相同
- 发现重复时迭代重规划（最多 3 次），每次排除已用的 POI
- 确保用户看到的是真正不同的选择

**源码位置**：[manager_agent.py](backend/src/meituan_agent/agents/manager_agent.py)

## Agent 协作流程

### 完整时序

```
用户: "下午2点出发，带5岁娃，老婆减脂，帮我规划4-6小时，人均不超过150"
  │
  ├─ [1] SemanticAgent.analyze()
  │     └─→ SemanticSchema {
  │           intent: "planning",
  │           party: { size: 3, has_child: true, child_age: 5, composition: "夫妻带娃" },
  │           food: { dietary: ["减脂"], budget_per_person: 150, cuisine_types: null },
  │           leisure: { activity_types: ["亲子", "展览"], indoor_outdoor: "any" },
  │           timing: { start: "14:00", duration_hours: 5 },
  │           hard_constraints: ["人均不超过150", "适合5岁孩子"]
  │         }
  │     写入 state.planning_context
  │
  ├─ [2] MapAgent.run()
  │     从 schema 中读取位置约束 → IP 定位 → 确定用户坐标
  │     搜索半径 = schema.location.radius_km（默认 3km）
  │     预搜索附近餐饮/休闲 POI → 写入 state.scratch
  │
  ├─ [3] FoodAgent.run()
  │     从 schema.food 读取搜索标签（cuisine_types || dietary || "餐饮"）
  │     增量半径搜索 POI → 去重 → 避讳过滤 → 预算过滤
  │     写入 state.scratch["food_candidates"]
  │
  ├─ [4] LeisureAgent.run()
  │     从 schema.leisure 读取搜索标签（activity_types || 默认 "亲子/展览"）
  │     增量半径搜索 POI → 去重 → 排除餐饮类
  │     按评分排序 → 写入 state.scratch["leisure_candidates"]
  │
  ├─ [5] Planner.plan()
  │     LLM 可用 → LLMPlanner：发送 candidate POI + 约束 → 结构化 JSON → Pydantic 校验
  │     LLM 不可用 → HeuristicPlanner：亲子优先方案A/B（不同餐厅+不同休闲组合）
  │     失败回退 → FallbackPlanner 自动切换
  │     输出 2-3 个 ItineraryPlan（含路线）
  │
  ├─ [6] _dedup_plans()
  │     检查方案间 POI 指纹 → 重复则重规划 → 确保差异化
  │
  ├─ [7] 输出方案文本 → state.status = awaiting_confirmation
  │     前端渲染 3D 卡片供用户选择
  │
  │     ═══════════ 用户点击"就选它！"或输入"确认 方案1" ═══════════
  │
  ├─ [8] intent=confirmation → 提取方案 ID
  │     state.status = executing
  │
  ├─ [9] ExecutionAgent.execute_plan()
  │     for item in plan.items:
  │       if 非餐饮: 标记"已安排到访"
  │       if 餐饮:
  │         ① check_table_availability → 排队 > 阈值? → failed
  │         ② get_menu_info → 获取菜单
  │         ③ place_order → 模拟下单
  │     全部通过 → state.status = completed
  │
  ├─ [10] 构建行程 HTML → send_itinerary_email → 用户邮箱
  │
  └─ 输出执行摘要 → 前端展示完整行程
```

### 失败重规划流程

```
ExecutionAgent 执行失败（排队超时 / 下单失败）
  │
  ├─ state.last_error = "排队检查失败: XX餐厅"
  │
  ├─ ManagerAgent._replan_after_failure()
  │     ① 定位失败餐厅 ID
  │     ② 从 food_candidates 中剔除该餐厅
  │     ③ 调用 Planner.plan(excluded_poi_ids={失败餐厅ID})
  │     ④ state.status = awaiting_confirmation
  │
  └─ 输出新方案 → 用户重新确认 → 重新执行
```

### Agent 间数据传递

所有 Agent 间通信通过 `SessionState` 这一个共享数据结构完成：

| 字段 | 写入方 | 读取方 |
|---|---|---|
| `planning_context` (SemanticSchema) | SemanticAgent | MapAgent / FoodAgent / LeisureAgent / Planner |
| `location` | MapAgent | FoodAgent / LeisureAgent / Planner / ExecutionAgent |
| `scratch["food_candidates"]` | FoodAgent | Planner / ManagerAgent（重规划时剔除） |
| `scratch["leisure_candidates"]` | LeisureAgent | Planner |
| `scratch["nearby_food"]` / `scratch["nearby_leisure"]` | MapAgent | FoodAgent / LeisureAgent（搜索不足时回退） |
| `candidate_plans` | Planner | ManagerAgent / ExecutionAgent |
| `selected_plan_id` | ManagerAgent（用户确认后） | ExecutionAgent |
| `executions` | ExecutionAgent | ManagerAgent（汇总展示） |
| `last_error` | ExecutionAgent | ManagerAgent（触发重规划） |

## 领域模型

```
SessionState                    # 会话级状态（核心数据结构）
├── session_id: str             # 会话唯一标识
├── status: SessionStatus       # 状态机：planning | awaiting_confirmation | executing | completed
├── profile: UserProfile        # 用户画像（人数/亲子/减脂/预算/风格）
├── location: Location          # 用户位置（lat/lng/label）
├── planning_context: SemanticSchema  # LLM 语义分析结果
├── candidate_plans: [ItineraryPlan]  # 候选方案列表
├── selected_plan_id: str       # 用户选择的方案 ID
├── executions: [ExecutionResult]     # 执行日志
├── last_error: str             # 最近一次错误（触发重规划）
└── scratch: dict               # Agent 间临时数据交换区

SemanticSchema                  # LLM 深度语义分析输出
├── intent: "planning" | "chat" | "confirmation"
├── location: LocationConstraint  # 区域/半径/是否可超出
├── food: FoodConstraint          # 菜系/避讳/口味/预算/场景
├── leisure: LeisureConstraint    # 活动类型/氛围/室内外/时长
├── party: PartyConstraint        # 人数/是否带娃/娃年龄/组成
├── timing: TimingConstraint       # 出发时间/总时长/日期
├── hard_constraints: [str]        # 不可违背的硬限制
└── free_text_summary: str         # 需求摘要

ItineraryPlan                   # 单个行程方案
├── id: str                     # plan_uuid
├── title: str                  # 方案标题
├── rationale: str              # 推荐理由
└── items: [ItineraryItem]      # 行程条目列表
    ├── poi: POI                # 地点信息
    ├── start/end: str          # 时间段
    ├── travel_from_prev: RouteLeg  # 从上个 POI 的交通方式/耗时/距离
    └── notes: str              # 备注

POI                             # 兴趣点
├── id / name / category        # 标识与分类
├── location / lat / lng        # 坐标
├── tags / rating / price       # 标签/评分/人均
├── address / open_hours / tel  # 地址/营业时间/电话
├── distance_from_user: float   # 距用户的直线距离
└── menu / image_url            # 菜单/图片
```

## 工具接口与数据源

所有外部能力均通过抽象基类定义，通过 `Container` 注入具体实现：

```python
class POISearchTool(ABC):       # POI 搜索接口
class MapTool(ABC):             # 地图接口（路线/逆地理编码）
class MenuInfoTool(ABC):        # 菜单查询接口
class AvailabilityTool(ABC):    # 排队/可订状态接口
class OrderTool(ABC):           # 下单接口
class RPAExecutor(ABC):         # RPA 执行接口
```

### 地图数据源优先级

| 优先级 | Provider | 条件 | 说明 |
|---|---|---|---|
| 1 | 高德 AmapTools | `map_provider=amap` 且有 Key | 商业级精度，POI/地理编码/路线 |
| 2 | OpenStreetMapTools | `map_provider=osm` 或 `auto` 且无高德 Key | 免费，Nominatim 地理编码 + Overpass POI + OSRM 路线 |
| 3 | Mock | `map_provider=mock` | 本地 JSON，离线演示 |

OSM 实现（[osm_tools.py](backend/src/meituan_agent/tools/osm_tools.py)）特色：
- **多公共实例容灾**：主 Overpass 实例不可用时自动切换 kumi.systems / private.coffee
- **降级半径搜索**：大半径超时时自动缩小半径（4000m → 2500m）
- **Nominatim 回退**：Overpass 完全不可用时切换 Nominatim 搜索
- **免费 IP 定位**：通过 `ipwho.is` 获取城市级位置

### 交易工具

当前阶段使用模拟实现（`Container` 中的 `SimMenu` / `SimAvailability` / `SimOrder` / `SimRPA`），均返回成功信号。要接入真实能力，只需新增实现类并在 `Container` 中替换注入即可。

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
