# 遇事不决问 AI — 私人规划执行助理 设计文档

## 1 系统概述

本系统基于 **Plan-and-Execute（规划-执行）** 架构，由多个专业 Agent 协作完成从需求理解到方案落地的全闭环流程。用户输入一句自然语言（如"下午带老婆孩子出去玩几个小时"），系统自动完成语义解析 → 位置定位 → POI 搜索 → 约束过滤 → 方案生成 → 用户确认 → 执行下单 → 邮件通知。

**核心亮点**：无需任何商业 API Key 即可完整运行（默认使用 OpenStreetMap 真实数据 + 启发式规划）。

**全流程 Pipeline**：

```
用户消息
  │
  ▼
┌──────────────┐
│ SemanticAgent│ ← LLM / DashScope / 启发式规则
│ 深度语义分析   │ → SemanticSchema（意图 + 位置/餐饮/休闲/人数/时间约束）
└──────┬───────┘
       │ intent = planning
       ▼
┌──────────────┐
│   MapAgent   │ ← 定位 + 地理编码 + 天气 + 周边 POI 预搜
└──────┬───────┘
       │
  ┌────┴────┐
  ▼         ▼
┌──────┐ ┌──────────┐
│Food  │ │Leisure   │
│Agent │ │Agent     │ ← 按语义约束搜索候选 POI
└──┬───┘ └────┬─────┘
   │          │
   ▼          ▼
┌──────────────────────┐
│ filter_candidates()  │ ← 半径 / 忌口 / 预算 / 天气硬过滤
│ enrich_availability()│ ← 餐厅排队预查
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│      Planner         │ ← LLM 动态组合 / 启发式模板 / Fallback
│ → 2-3 候选方案        │
│ schedule_plans()     │ ← 时间排期
│ validate_plan()      │ ← 约束校验
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│   用户确认方案        │ ← 方案可视化地图全览
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  ExecutionAgent      │ ← 排队检查 → 菜单 → 选菜 → 下单
│  失败自动重规划        │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 行程摘要 + 邮件通知     │
└──────────────────────┘
```

---

## 2 Planning 策略

### 2.1 需求理解：SemanticAgent

一次 LLM 调用完成全部需求提取，输出结构化 `SemanticSchema`：

| 字段 | 示例 | 说明 |
|------|------|------|
| intent | planning / chat / confirmation | 意图分类 |
| location | { type: "current_gps", radius_km: 3 } | 位置约束 |
| food | { cuisine_types: ["火锅"], dietary: ["减脂"], budget: 150 } | 餐饮偏好 |
| leisure | { activity_types: ["亲子"], indoor_outdoor: "any" } | 休闲偏好 |
| party | { size: 3, has_child: true, child_age: 5 } | 同行人员 |
| timing | { start: "14:00", duration_hours: 5 } | 时间约束 |
| hard_constraints | ["老婆减脂", "带5岁孩子"] | 硬性限制 |

**LLM 路径**（互斥）：DashScope Agent API（低延迟） → OpenAI 兼容 API → 启发式关键词规则回退。

**后处理规则层**（确定性规则补全 LLM 遗漏）：品牌名→品类映射（"蜜雪冰城"→"奶茶/饮品"）、"出发"→定位类型推断、人数默认推断、饮品捕获。

### 2.2 候选生成：Planner

采用 **FallbackPlanner** 串联两种策略：

- **LLMPlanner**：将候选 POI 列表 + 约束 + 输出 Schema 喂给 LLM，由模型自由组合 2-3 个方案，严格遵守 hard_constraints，且要求不同方案的 POI 组合完全不同。
- **HeuristicPlanner**（兜底）：按场景模板硬组合——亲子场景用"低体力消耗"模板，朋友场景用"社交聚会"模板，通用场景用"综合推荐"模板。

LLM 输出非法 JSON 或无结果时自动降级到启发式规划，保证系统始终可用。

### 2.3 约束保障：三层校验

| 阶段 | 函数 | 作用 |
|------|------|------|
| 规划前 | `filter_candidates()` | 半径超限、忌口命中、预算超支、天气不适合户外 → 剔除 |
| 规划前 | `enrich_restaurant_availability()` | 预查餐厅排队状态，不可用 → 剔除 |
| 规划后 | `validate_plan()` | 校验方案是否含餐饮、是否亲子友好、时间是否合理 |
| 规划后 | `schedule_plans()` | 为每个 POI 分配具体时间段（餐饮 75-90min、展览 100min 等） |
| 全局 | `_dedup_plans()` | 方案间 POI 指纹去重，不够则迭代重规划（排除已用 POI，最多 3 次） |

---

## 3 工具调用链路

| 工具 | 实现 | 调用阶段 | 说明 |
|------|------|---------|------|
| POISearchTool | OSM Overpass / 高德 / Mock | FoodAgent + LeisureAgent | 按标签搜索周边餐饮/休闲 POI |
| MapTool | OSM Nominatim + OSRM / 高德 | MapAgent + Planner | 地理编码 + 步行/驾车路线规划 |
| AvailabilityTool | Mock（可扩展） | 约束过滤 + 执行阶段 | 排队检查、容量校验 |
| MenuInfoTool | Mock | 执行阶段 | 查询餐厅菜单（支持减脂筛选） |
| OrderTool | Mock | 执行阶段 | 模拟下单，返回订单号 |
| WeatherService | Open-Meteo / wttr.in | MapAgent | 实时天气（温度/降水/风速），天气恶劣时自动约束为室内 |
| LLMClient | OpenAI 兼容 / DashScope | SemanticAgent + Planner | 语义分析 + 方案生成 |
| RPAExecutor | Mock（可扩展） | 执行阶段 | 预留真实 RPA 接口（Playwright / Appium） |

**三级降级链**（确保系统零 Key 可运行）：

```
地图数据：高德 API → OpenStreetMap（Overpass 多节点轮询 + 缩小半径重试 + Nominatim 降级）→ Mock 数据
语义分析：DashScope Agent API → OpenAI 兼容 API → 启发式关键词规则
方案规划：LLMPlanner → HeuristicPlanner
```

所有实现通过依赖注入（`Container`）管理，替换接口实现即可接入真实服务，无需改动业务代码。

---

## 4 异常处理机制

| 异常场景 | 触发条件 | 处理策略 |
|---------|---------|---------|
| LLM 输出异常 | JSON 解析失败 / Schema 校验不通过 | FallbackPlanner 自动降级到启发式规划，系统不中断 |
| 地图 API 不可用 | Overpass 504 / Nominatim 超时 | 多节点轮询（3 个 Overpass 实例）→ 缩小搜索半径重试 → Nominatim 搜索降级 → Mock 数据兜底 |
| 餐厅执行失败 | 排队超时 / 下单失败 / 菜单查询失败 | `_replan_after_failure`：识别失败 POI → 排除 → 重新规划 → 展示备选方案供用户再次选择 |
| 方案内容重复 | 不同方案使用相同 POI 组合 | `_dedup_plans`：提取 POI ID 指纹去重，不足 3 个则迭代重规划（排除已用 POI），最多重试 3 次 |
| 天气恶劣 | 降水 ≥ 0.2mm / 天气码 ≥ 51 / 温度 ≥ 32°C | 自动追加 hard_constraint "优先室内活动"，LeisureAgent 搜索标签切换为展览/博物馆/商场 |
| 用户定位缺失 | 浏览器拒绝定位 / IP 定位失败 | 降级链：浏览器定位 → IP 定位（ipwho.is）→ 消息中提取地名 geocode → 兜底北京天安门 |

---

*文档版本：v1.0 | 2026-05-29*
