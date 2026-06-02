# 成员功能贡献记录

---

## qinshihao

| 新增什么功能？ | 为什么要增加？ | 修改了哪些文件？ | 时间 |
| --- | --- | --- | --- |
| WebUI 聊天输入框新增语音转文字按钮（浏览器 SpeechRecognition），识别结果自动回填到输入框 | 提升移动端/不便打字场景的输入效率，降低用户输入成本 | `webui/src/main.js`；`webui/src/style.css` | 2026-05-26 23:11 |

---

## yuanqisong

| 新增什么功能？ | 为什么要增加？ | 修改了哪些文件？ | 时间 |
| --- | --- | --- | --- |
| 语义分析模块支持 DashScope Agent API，替代原有 LLM 直调 | 原 LLM 直调单次耗时约 46 秒（占总流程 92%），切换为 DashScope App API 后 prompt/指令封装在平台侧，仅发送原始数据，显著降低响应耗时；未配置 DashScope 时自动回退原有 LLM 路径 | `backend/src/meituan_agent/agents/semantic_agent.py`；`backend/src/meituan_agent/config.py`；`backend/src/meituan_agent/container.py`；`.env` | 2026-05-28 |
| 新增行程路线地图可视化（高德地图 JSAPI v2.0） | 原行程方案仅以文字/卡片展示，用户无法直观看到各活动地点的空间分布与步行路线；新增地图面板后可一键查看从当前位置出发、按时间顺序串联所有 POI 的真实步行路径，并标注出行序号，提升行程规划的可理解性和实用性 | `webui/src/map.js`（新增）；`webui/src/main.js`；`webui/src/plans.js`；`webui/src/style.css`；`backend/src/meituan_agent/api/main.py`；`backend/src/meituan_agent/config.py`；`.env.example` | 2026-06-02 |

---

## yuanxing

- feature1
- feature2
- feature3
