"""
SemanticAgent — 深度语义分析

LLM 驱动，从用户消息中深度提取结构化需求。
输出 SemanticSchema JSON，供下游专业 agent 消费。
无任何硬编码规则或正则 —— 完全由模型动态理解。
"""

from __future__ import annotations

import json
import logging
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
            return self._parse(raw)
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
