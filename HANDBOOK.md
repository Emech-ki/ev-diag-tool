# Handoff Document — EV-Diag-Tool

**Date:** 2026-07-25
**Project:** `D:\桌面\诊断ai程序\ev-diag-tool`
**Repo:** https://github.com/Emech-ki/ev-diag-tool.git
**Version:** v3.1.0 — Streaming Tool Calling
**Tests:** 85 passed (unit) + 41 passed (verification)
**Database:** 8729 fault codes (100% 中文) + 45 vehicle models

---

## 本次会话完成的工作

### 1. 故障码数据库全量中文翻译（2026-07-25）

将 8729 条故障码的英文描述翻译为专业中文，翻译率从 3.4% 提升到 100%。

| 文件 | 总数 | 翻译前纯中文 | 翻译后纯中文 |
|------|------|-------------|-------------|
| p_codes.csv | 6553 | 130 (2%) | 6553 (100%) |
| b_codes.csv | 360 | 69 (19%) | 360 (100%) |
| c_codes.csv | 525 | 26 (5%) | 525 (100%) |
| u_codes.csv | 1231 | 34 (3%) | 1231 (100%) |
| ev_codes.csv | 60 | 39 (65%) | 60 (100%) |

**翻译方法：** 使用多个并行 Task 代理进行 AI 翻译，分批处理（每批 ~200 条），经过 3 轮翻译 + 修复：
- 第1轮：7个并行 Task 翻译 8667 条 description
- 第2轮：2个并行 Task 修复 1529 条未翻译的 C/U 系列
- 第3轮：2个并行 Task 修复 1008 条翻译损坏的条目

**翻译规则：**
- 保留标准缩写：EGR、EVAP、ABS、CAN、HO2S、O2、MAP、MAF 等
- Bank 1 = 第一排, Bank 2 = 第二排
- Circuit/Open = 电路/开路, Circuit Low = 电路电压过低
- Range/Performance = 范围/性能, Intermittent/Erratic = 间歇性/不稳定

### 2. 全链路流式 Tool Calling 实现（2026-07-25）

将 AI Agent 对话从"伪流式"（等待全部完成后一次性显示）升级为"全链路流式"（逐 token 实时显示）。

#### 改动的文件（6个）

**`src/ai/providers/__init__.py`**
- 新增 `StreamEvent` 数据类（type: "content" | "tool_calls" | "done"）
- 新增 `chat_with_tools_stream` 默认实现（回退到非流式）

**`src/ai/providers/ollama.py`**
- 实现 `chat_with_tools_stream`：Ollama NDJSON 流式解析
- Ollama 流式模式下 tool_calls 在单个 chunk 中完整返回（非增量）

**`src/ai/providers/openai_compat.py`**
- 实现 `chat_with_tools_stream`：OpenAI SSE 流式解析
- 增量 tool_calls 按 index 缓冲拼接（name + arguments 片段）
- `tool_calls_detected` 标志防止检测到 tool_calls 后继续 yield content

**`src/ai/llm_client.py`**
- 新增 `chat_with_tools_stream` 代理方法，转发到当前 provider

**`src/ai/agent.py`**
- 新增 `run_stream` 方法：流式 ReAct 循环入口
- 新增 `_run_react_loop_stream` 方法：流式版本的工具调用循环
- 重写 `chat_stream`：调用 `run_stream` 而非伪流式 `yield self.run()`

**`src/ui/agent_chat.py`**
- `AgentStreamWorker.run()` 改为消费 `StreamEvent`，逐 token emit
- `_stop_worker` 增加强制终止机制（terminate + wait）

#### 数据流

```
用户输入
    ↓
AgentStreamWorker.run()  (QThread 子线程)
    ↓
agent.run_stream(message)  →  Iterator[StreamEvent]
    ↓
llm.chat_with_tools_stream(messages, tools)
    ↓ (逐 token)
StreamEvent("content", "你")  →  chunk.emit("你")  →  _append_stream_token()
StreamEvent("content", "好")  →  chunk.emit("好")  →  _append_stream_token()
...
StreamEvent("tool_calls", [...])  →  执行工具  →  on_tool_call()  →  UI显示"🔍 查询故障码"
StreamEvent("content", "根据")  →  chunk.emit("根据")  →  _append_stream_token()
...
StreamEvent("done")  →  finished.emit()  →  _finalize_stream_message()
```

#### Bug 修复（3项）

| # | 文件 | Bug | 修复 |
|---|------|-----|------|
| 1 | `ollama.py:284` | 冗余循环导入 `from src.ai.providers import StreamEvent as SE`，与顶部导入冲突 | 删除冗余导入，统一使用 `StreamEvent` |
| 2 | `openai_compat.py:340` | `finish_reason == "tool_calls"` 的 `break` 只跳出内层 `while` 循环，外层 `for` 继续读取可能 yield 多余 content | 添加 `tool_calls_detected` 标志，双层 break |
| 3 | `openai_compat.py:288` | `content_buf` 变量累积但从未使用 | 删除未使用变量 |

### 3. Git 提交

- **Commit:** `0a42d31` — "feat: 全链路流式Tool Calling + 8729条故障码中文翻译"
- **Push:** 已推送到 `origin/master`

---

## 之前会话完成的工作

### 数据库大扩充

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

#### 3. Bug 修复
- **品牌选择栏空选项** — `main_window.py` 移除 `addItem("")` 空选项

#### 4. 打包 exe
- **输出:** `dist/EV-Diag-Tool.exe` (37.6 MB)
- **工具:** PyInstaller 6.21.0

### 阶段三：AI Agent 版（v3.0.0）

#### 1. 工具调用框架
- **新建** `src/ai/tools.py` — `ToolParam`, `Tool`, `ToolRegistry`
- **新建** `src/ai/diagnostic_tools.py` — 9 个诊断工具

#### 2. Provider 层扩展 — Tool Calling 支持
- `src/ai/providers/__init__.py` — `chat_with_tools` 抽象方法
- `src/ai/providers/openai_compat.py` — OpenAI function calling
- `src/ai/providers/ollama.py` — Ollama tool calling（0.4.0+）

#### 3. Agent 循环 — ReAct 模式
- `src/ai/agent.py` — `run()` + `_run_react_loop()` + `_run_with_prefetch()`

#### 4. Prompt 工程
- `src/ai/prompt_templates.py` — `get_tool_agent_system_prompt()`

#### 5. 搜索增强
- `src/database/db_manager.py` — `search_codes()` 扩展搜索范围
- `src/ai/diagnostic_tools.py` — 症状关键词映射

#### 6. Bug 修复（5 项）
1. Ollama 400 Bad Request — 去掉 tool_calls
2. LLM 重复调用同一工具 10 次 — 工具去重机制
3. Z9999 编造诊断 — 反幻觉铁律
4. "冷车启动抖动"搜不到 P0300 — 症状关键词映射
5. 4xx 错误重试 4 次 — 4xx 不重试

---

## 当前项目状态

- **版本：** v3.1.0 — Streaming Tool Calling
- **阶段：** 阶段三增强 — 全链路流式 + 翻译完成
- **测试：** 85 单元测试 + 41 功能验证，全部通过
- **数据库：** 8729 故障码（100% 中文） + 45 车型
- **已修复问题：** 32 项（29 + 3 流式相关）

## 核心架构

```
用户消息 → Agent.run_stream()  (流式入口)
              │
              ├── 尝试 chat_with_tools_stream（流式 Tool Calling）
              │       │
              │       ├── 有 tool_calls → 流式 ReAct 循环
              │       │       ├── 执行工具 → on_tool_call() → UI 显示中间状态
              │       │       ├── 下一轮 LLM 流式调用 → 逐 token yield
              │       │       └── 无 tool_calls → 最终回答 → done
              │       │
              │       └── 无 tool_calls → 直接 yield 最终回答 → done
              │
              └── 降级: _run_with_prefetch() + 普通流式 chat
```

## 建议的下一步工作

1. **补全故障码** — 下载 Wal33D 数据库，补全 18,805 条厂商自定义码
2. **编辑端点功能** — 右键菜单增加"编辑"
3. **多 Agent 协作** — 主 Agent + 专家子 Agent（BMS/电机/热管理）
4. **UI 优化** — Markdown 渲染增强、诊断结果导出
5. **实际运行测试** — 用 Ollama/OpenAI 测试流式输出效果

---

## 敏感信息说明

- `.env` 文件已通过 `.gitignore` 排除
- Ollama 默认配置：`http://localhost:11434`，模型 `qwen2.5:7b`
- OpenAI API Key 未配置（需用户自行填写 `.env`）
