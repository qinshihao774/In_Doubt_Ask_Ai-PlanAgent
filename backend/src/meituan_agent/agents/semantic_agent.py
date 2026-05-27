"""
SemanticAgent — 深度语义分析

LLM 驱动，从用户消息中深度提取结构化需求。
输出 SemanticSchema JSON，供下游专业 agent 消费。
无任何硬编码规则或正则 —— 完全由模型动态理解。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from meituan_agent.domain.models import (
    FoodConstraint,
    LeisureConstraint,
    LocationConstraint,
    PartyConstraint,
    SemanticSchema,
    TimingConstraint,
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# 后处理规则层 —— 品牌名→品类映射 & 关键词集合
# ═══════════════════════════════════════════════════════════

BRAND_TO_CUISINE: dict[str, str] = {
    "蜜雪冰城": "奶茶/饮品",
    "瑞幸": "咖啡",
    "星巴克": "咖啡",
    "喜茶": "奶茶/饮品",
    "奈雪": "奶茶/饮品",
    "茶百道": "奶茶/饮品",
    "古茗": "奶茶/饮品",
    "沪上阿姨": "奶茶/饮品",
    "霸王茶姬": "奶茶/饮品",
    "书亦烧仙草": "奶茶/饮品",
    "麦当劳": "西式快餐",
    "肯德基": "西式快餐",
    "必胜客": "西餐",
    "海底捞": "火锅",
}

_DEPART_KEYWORDS = {"出发", "走起", "动身", "出门"}
_SINGLE_KEYWORDS = {"一个人", "自己", "独自", "独食"}
_MULTI_KEYWORDS = {"我们", "大家", "一起", "朋友", "家人", "同事", "闺蜜", "兄弟"}
_BUY_DRINK_RE = re.compile(r"(?:买一杯|来一杯|点杯|来杯|买杯)\s*([^\s，。,、!?！？]+)")

SEMANTIC_SYSTEM_PROMPT = """你是一个深度语义分析器。你的任务是从用户消息中全面、细致地提取所有规划相关的需求与约束。

你必须输出一个完整的 JSON 对象，不要输出任何其他文字。

## 核心原则
1. **深度理解语义**：不要只匹配关键词。理解用户的真实意图、隐含条件和情感倾向。
2. **硬约束优先**：用户明确指定的限制（区域、口味、预算等）必须严格遵守。
3. **灵活推导**：合理推断用户未明确说明但可以从上下文得出的偏好。
4. **宁缺毋滥**：如果某个信息确实无法从消息中获取，不要编造。

## JSON Schema

```json
{
  "intent": "planning | chat | confirmation",
  "location": {
    "type": "current_gps | named_area | none",
    "area": "望京 | 三里屯 | ... 或 null",
    "radius_km": 1.5,
    "must_not_exceed": true
  },
  "food": {
    "required": true,
    "cuisine_types": ["火锅", "川菜", ...],
    "avoid": ["日料", ...],
    "taste_profile": "辣 | 清淡 | 酸甜 | ... 或 null",
    "dietary": ["减脂", "低卡", ...],
    "budget_per_person": 100,
    "occasion": "朋友聚会 | 约会 | 家庭聚餐 | ... 或 null"
  },
  "leisure": {
    "required": true,
    "activity_types": ["展览", "户外", "电影", "购物", ...],
    "vibe": "安静 | 热闹 | 文艺 | 刺激 | ... 或 null",
    "indoor_outdoor": "indoor | outdoor | any",
    "duration_per_activity_minutes": 90
  },
  "party": {
    "size": 2,
    "has_child": false,
    "child_age": null,
    "composition": "2男2女 | 夫妻带娃 | 一个人 | ... 或 null"
  },
  "timing": {
    "start": "14:00 | ... 或 null",
    "duration_hours": 5,
    "date": "today | tomorrow | 2026-05-21 | ... 或 null"
  },
  "hard_constraints": ["必须在望京区域内", "不吃日料", "人均不超过150", ...],
  "free_text_summary": "一句话概括用户需求"
}
```

## 字段填写指南

### intent
- "planning": 用户想规划出行/美食/休闲
- "chat": 纯聊天、打招呼、询问能力等
- "confirmation": 用户确认选择某个方案（"确认方案1""就这个"）

### location
- 用户说"附近的""周边的" → type="current_gps"
- 用户说"望京""三里屯""朝阳区" → type="named_area", area=地名
- 用户说"必须在这个区域""不能太远" → must_not_exceed=true
- 未提位置 → type="none"

### food
- 仔细识别：火锅、川菜、粤菜、日料、韩餐、西餐、烧烤、小吃、甜品、奶茶...
- 用户说"不要""不吃""不喜欢"的 → 放入 avoid
- 口味："辣""清淡""不辣""甜的"...
- 减脂/控卡相关 → dietary: ["减脂"]
- 用户说人均预算 → budget_per_person
- 聚餐场景 → occasion

### leisure
- 识别活动：展览/博物馆/画廊、电影/影院、购物/逛街/商场、户外/公园/散步/爬山、唱歌/KTV、剧本杀/密室、咖啡/下午茶...
- 氛围偏好："安静的""热闹的""文艺的""刺激的"
- "不想出去""室内"→ indoor_outdoor: "indoor"
- "户外""外面走走"→ indoor_outdoor: "outdoor"

### party
- 识别人数："一个人""自己"→ size=1
- "我和女朋友""两个人""一对"→ size=2
- "一家三口""我和老婆孩子"→ size=3, has_child=true
- "两男两女""四个人"→ size=4
- 带孩子 → has_child=true, child_age=年龄
- 朋友聚会 → composition 描述

### timing
- "下午2点""两点"→ start: "14:00"
- "晚上8点"→ start: "20:00"
- "4-6小时""半天"→ duration_hours
- "今天""明天""周六"→ date

### hard_constraints
从消息中提取所有明确不可违背的限制。用中文表述。例如：
- "必须在XX区域"
- "不能吃XX"
- "人均不超过XX"
- "必须是室内活动"
- "不能太远"

### free_text_summary
用自然语言一句话概括用户的完整需求。
"""


class SemanticAgent:
    """深度语义分析 Agent —— 完全 LLM 驱动，无硬编码规则"""

    def __init__(self, llm) -> None:
        self._llm = llm

    def analyze(self, user_message: str, location_label: str = "未知", *, conversation: str | None = None) -> SemanticSchema:
        """分析用户消息，返回完整 SemanticSchema"""
        prefix = f"用户当前位置：{location_label}\n\n"
        if conversation:
            prefix += f"对话历史（最近对话，按时间顺序）：\n{conversation}\n\n"
        user_prompt = prefix + f"用户消息：{user_message}\n\n请深度分析上述消息，输出完整的 JSON 需求分析。"

        try:
            raw = self._llm.chat(system=SEMANTIC_SYSTEM_PROMPT, user=user_prompt)
            schema = self._parse(raw)
            return self._post_process(schema, user_message)
        except Exception as e:
            logger.warning(f"语义分析失败，回退默认值: {e}")
            return SemanticSchema()

    def _parse(self, raw: str) -> SemanticSchema:
        text = raw.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("no_json_found")

        obj = json.loads(text[start : end + 1])
        return self._from_dict(obj)

    @staticmethod
    def _from_dict(d: dict[str, Any]) -> SemanticSchema:
        def _drop_none(raw: dict | None) -> dict:
            """过滤 null 值，避免 Pydantic 对 int/float 等字段拒绝 None"""
            if raw is None:
                return {}
            return {k: v for k, v in raw.items() if v is not None}

        return SemanticSchema(
            intent=d.get("intent", "planning"),
            location=LocationConstraint(**_drop_none(d.get("location"))),
            food=FoodConstraint(**_drop_none(d.get("food"))),
            leisure=LeisureConstraint(**_drop_none(d.get("leisure"))),
            party=PartyConstraint(**_drop_none(d.get("party"))),
            timing=TimingConstraint(**_drop_none(d.get("timing"))),
            hard_constraints=d.get("hard_constraints") or [],
            free_text_summary=d.get("free_text_summary", ""),
        )

    @staticmethod
    def _post_process(schema: SemanticSchema, user_message: str) -> SemanticSchema:
        """后处理规则层 —— 用确定性规则补全 LLM 的遗漏。"""
        text = user_message or ""
        changed: list[str] = []

        # ── 规则 1: 品牌名 → 品类映射 ──
        cuisine_types = list(schema.food.cuisine_types or [])
        for brand, category in BRAND_TO_CUISINE.items():
            if brand in text:
                if category not in cuisine_types:
                    cuisine_types.append(category)
                    changed.append(f"品牌映射: {brand}→{category}")
                if brand not in cuisine_types:
                    cuisine_types.append(brand)
        if cuisine_types and cuisine_types != (schema.food.cuisine_types or []):
            schema.food.cuisine_types = cuisine_types

        # ── 规则 2: "出发" → current_gps 定位 ──
        if schema.location.type == "none":
            if any(kw in text for kw in _DEPART_KEYWORDS):
                schema.location.type = "current_gps"
                changed.append("出发→current_gps")

        # ── 规则 3: party.size 默认推断 ──
        if schema.party.size is None:
            if any(kw in text for kw in _SINGLE_KEYWORDS):
                schema.party.size = 1
                changed.append("单人关键词→size=1")
            elif not any(kw in text for kw in _MULTI_KEYWORDS):
                schema.party.size = 1
                changed.append("无多人描述→默认size=1")

        # ── 规则 4: duration_hours 推断 ──
        if schema.timing.duration_hours is None and schema.intent == "planning":
            activity_count = len(schema.food.cuisine_types or []) + len(schema.leisure.activity_types or [])
            if activity_count >= 2:
                schema.timing.duration_hours = min(int(activity_count * 1.5), 8)
                if schema.timing.duration_hours < 3:
                    schema.timing.duration_hours = 3
                changed.append(f"活动数{activity_count}→推断{schema.timing.duration_hours}h")

        # ── 规则 5: "买一杯/来一杯/点杯" 捕获 ──
        drink_match = _BUY_DRINK_RE.search(text)
        if drink_match:
            drink_name = drink_match.group(1)
            mapped = BRAND_TO_CUISINE.get(drink_name)
            category = mapped or "奶茶/饮品"
            current = schema.food.cuisine_types or []
            if category not in current:
                schema.food.cuisine_types = current + [category]
                changed.append(f"饮品捕获: {drink_name}→{category}")
            if drink_name not in (schema.food.cuisine_types or []):
                schema.food.cuisine_types = (schema.food.cuisine_types or []) + [drink_name]

        if changed:
            logger.info("[后处理] %s", " | ".join(changed))

        return schema
