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

---

## yuanxing

| 新增什么功能？ | 为什么要增加？ | 修改了哪些文件？ | 时间 |
| --- | --- | --- | --- |
| 移动端布局溢出修复：逐层添加 overflow-x 约束，修复 Pipeline 流程图撑屏问题 | 移动端横向溢出需左右拖动，且处理流程出现时页面被拉长导致输入框不可见 | `webui/src/style.css` | 2026-05-29 00:52 |
