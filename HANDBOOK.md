# Handoff Document — EV-Diag-Tool

**Date:** 2026-07-25
**Project:** `D:\桌面\诊断ai程序\ev-diag-tool`
**Repo:** https://github.com/Emech-ki/ev-diag-tool.git
**Version:** v3.0.0 — AI Agent (Tool Calling)
**Tests:** 85 passed (unit) + 41 passed (verification)
**Database:** 8729 fault codes + 45 vehicle models

---

## 本次会话完成的工作

### 数据库大扩充（2026-07-25）

#### 1. 从开源数据库抓取标准故障码
- **来源:** [Wal33D/dtc-database](https://github.com/Wal33D/dtc-database) (GitHub 开源)
- **抓取脚本:** `scripts/merge_official_codes.py`
- **数据量:** 从 ~200 条扩充至 **8729 条**

| 类别 | 数量 | 说明 |
|------|------|------|
| P-codes (动力总成) | 6553 | 标准英文 + 部分中文详细 |
| U-codes (网络通讯) | 1231 | 标准英文 + 部分中文详细 |
| C-codes (底盘) | 525 | 标准英文 + 部分中文详细 |
| B-codes (车身) | 360 | 标准英文 + 部分中文详细 |
| EV-codes (新能源) | 60 | 中文详细 |
| 车型数据 | 45 | 国内主流新能源品牌 |

#### 2. 新增车型数据
新增 12 个品牌：长安深蓝、阿维塔、岚图、昊铂、小米、极狐、smart 等

#### 3. 故障码描述翻译
- **翻译脚本:** `scripts/translate_codes_v2.py`
- **当前状态:** 约 8.9% 完全中文，91% 中英混合
- **待办:** 翻译质量需进一步优化

#### 4. Bug 修复
- **品牌选择栏空选项** — `main_window.py` 移除 `addItem("")` 空选项

#### 5. 打包 exe
- **输出:** `dist/EV-Diag-Tool.exe` (37.6 MB)
- **工具:** PyInstaller 6.21.0

#### 6. Git 提交
- **Commit:** `eb30494` — "feat: 扩充故障码数据库至 8729 条 + 修复品牌选择栏"
- **Push:** 待手动执行 `git push origin master`

---

### 阶段三：AI Agent 版（v3.0.0）

#### 1. 工具调用框架
- **新建** `src/ai/tools.py` — `ToolParam`, `Tool`, `ToolRegistry`
  - `Tool.to_openai_schema()` — 转为 OpenAI function calling JSON Schema 格式
  - `ToolRegistry` — 工具注册/查找/执行，类比中断向量表
  - `ToolRegistry.to_openai_format()` — 批量导出为 LLM API 的 tools 参数

#### 2. 9 个诊断工具
- **新建** `src/ai/diagnostic_tools.py` — `register_diagnostic_tools()`

| 工具 | 功能 |
|------|------|
| `lookup_code` | 查知识库获取故障码详情 |
| `search_by_symptom` | 按症状搜索故障码（含关键词映射） |
| `get_vehicle_info` | 查车型信息和已知通病 |
| `get_related_codes` | 获取相关故障码 |
| `get_diagnostic_steps` | 获取标准诊断步骤 |
| `get_wiring_info` | 获取电路/针脚信息 |
| `record_symptom` | 记录技师观察到的现象 |
| `get_common_fixes` | 获取常见修复方案 |
| `search_codes_by_system` | 按系统分类浏览故障码 |

#### 3. Provider 层扩展 — Tool Calling 支持
- **修改** `src/ai/providers/__init__.py` — LLMProvider 新增 `chat_with_tools` 抽象方法
- **修改** `src/ai/providers/openai_compat.py` — 实现 OpenAI function calling
- **修改** `src/ai/providers/ollama.py` — 实现 Ollama tool calling（0.4.0+）
- **修改** `src/ai/llm_client.py` — 新增 `chat_with_tools` 代理方法

#### 4. Agent 循环重写 — ReAct 模式
- **重写** `src/ai/agent.py` — DiagnosticAgent 升级为带工具调用的 ReAct 循环
  - `run()` — Agent 主循环：LLM 思考 → 调用工具 → 获取结果 → 继续思考 → 最终回答
  - `_run_react_loop()` — Tool Calling 可用时的完整 ReAct 循环
  - `_run_with_prefetch()` — 降级模式：预查询数据注入 prompt + 普通 chat
  - `_prefetch_tools()` — 根据用户消息自动预查询相关工具

#### 5. Prompt 工程
- **修改** `src/ai/prompt_templates.py` — 新增 `get_tool_agent_system_prompt()`
  - 工具使用原则（何时调用哪个工具）
  - 反幻觉铁律（工具说没有=没有，不知道就说不知道）
  - 未收录故障码的严格处理规则

#### 6. UI 适配
- **修改** `src/ui/agent_chat.py` — 工具调用过程展示
  - 新增 `tool_call_signal` 和 `tool_result_signal` 信号
  - 工具调用时显示"🔍 查询故障码"等中间状态

#### 7. 搜索增强
- **修改** `src/database/db_manager.py` — `search_codes()` 扩展搜索范围
  - 新增 `detail` 和 `symptoms` 字段的 LIKE 匹配
- **修改** `src/ai/diagnostic_tools.py` — `search_by_symptom` 症状关键词映射
  - "抖动" → "缺火"、"启动抖动" → "缺火" 等技术术语转换

#### 8. Bug 修复（5 项）
1. **Ollama 400 Bad Request** — 消息历史中的 `tool_calls` 字段导致 Ollama 拒绝请求 → 去掉 tool_calls
2. **LLM 重复调用同一工具 10 次** — 去掉 tool_calls 后 LLM 不知道调用过什么 → 工具去重机制
3. **Z9999 编造诊断** — Prompt 无反幻觉规则 → 加"工具说没有=没有"铁律
4. **"冷车启动抖动"搜不到 P0300** — LLM 用口语搜索，数据库用技术术语 → 症状关键词映射
5. **4xx 错误重试 4 次** — `_http_request` 对所有 HTTP 错误重试 → 4xx 不重试

#### 9. 测试
- **修改** `tests/test_ai.py` — 新增 9 个测试
  - ToolRegistry 注册/查找/执行/Schema
  - DiagnosticTools 全部 9 个工具注册
  - Agent 初始化/诊断/重置/摘要/工具注册
- **新建** `scripts/verify_features.py` — 41 个功能验证用例（6 组）

---

## 当前项目状态

- **版本：** v3.0.0 — AI Agent (Tool Calling)
- **阶段：** 阶段三完成 — Tool Calling + ReAct 循环 + 降级模式
- **测试：** 85 单元测试 + 41 功能验证，全部通过
- **数据库：** 8729 故障码 + 45 车型
- **已修复问题：** 29 项（10 code review + 9 debug + 4 第三方模型 UI + 5 Agent + 1 品牌选择栏）

## 核心架构

```
用户消息 → Agent.run()
              │
              ├── 尝试 chat_with_tools（原生 Tool Calling）
              │       │
              │       ├── 有 tool_calls → ReAct 循环（调工具→拿结果→继续）
              │       │
              │       └── 无 tool_calls → 降级模式
              │
              └── 降级: _run_with_prefetch()
                      ├── 分析用户消息，预查询相关工具
                      ├── 注入结果到 prompt
                      └── 普通 chat 调用 LLM
```

## 建议的下一步工作

1. **翻译优化** — 故障码描述翻译质量需提升（当前 8.9% 完全中文）
2. **编辑端点功能** — 右键菜单增加"编辑"
3. **流式 Tool Calling** — 当前 `chat_stream` 用非流式实现，可优化
4. **多 Agent 协作** — 主 Agent + 专家子 Agent（BMS/电机/热管理）
5. **UI 优化** — Markdown 渲染增强、诊断结果导出
6. **Git Push** — 手动执行 `git push origin master`

---

## 敏感信息说明

- `.env` 文件已通过 `.gitignore` 排除
- Ollama 默认配置：`http://localhost:11434`，模型 `qwen2.5:7b`
- OpenAI API Key 未配置（需用户自行填写 `.env`）
