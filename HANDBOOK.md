# Handoff Document — EV-Diag-Tool

**Date:** 2026-07-26
**Project:** `D:\桌面\诊断ai程序\ev-diag-tool`
**Repo:** https://github.com/Emech-ki/ev-diag-tool.git
**Version:** v3.1.0 — Streaming Tool Calling
**Tests:** 85 passed (unit) + 42 passed (verification)
**Database:** 8729 fault codes (100% 中文) + 45 vehicle models

---

## 本次会话完成的工作

### 1. 数据库验证与分析（2026-07-26）

对现有数据库进行全面验证，确认数据完整性。

#### 关键发现

| 项目 | 之前假设 | 实际数据 |
|------|---------|----------|
| Wal33D 数据库 | 28,220+ 条 | **8,581 条** |
| 当前数据库 | 8,729 条 | 8,729 条 ✅ |
| 需要补全 | ~19,000+ 条 | **0 条**（已合并） |
| 翻译状态 | 需要翻译 | **100% 已完成** |

#### 数据完整性检查

| 检查项 | 状态 | 详情 |
|--------|------|------|
| 单元测试 | ✅ 85/85 通过 | 全部通过 |
| 功能验证 | ✅ 42/42 通过 | 修复1个测试bug |
| 必填字段 | ✅ 通过 | 无空 code 或 description |
| 严重程度值 | ✅ 通过 | low/medium/high/critical |
| JSON 字段 | ✅ 通过 | 所有 JSON 字段有效 |
| 车型数据 | ✅ 45款/18品牌 | 数据完整 |

#### EV 码存储说明

ev_codes.csv 的60个故障码与 p_codes.csv 重叠（P0Axx/P0Bxx/P0Cxx）。导入时 ev_codes 会覆盖 p_codes 的同名条目，因为 ev_codes 有更详细的信息（common_causes、diagnostic_steps 等）。这是**设计如此**，不是 bug。

### 2. 测试 Bug 修复（2026-07-26）

**文件：** `scripts/verify_features.py`

**修改：** `test_tool_vehicle_info` 函数

- **修复前：** 期望车型表为空（`assert r["found"] is False`）
- **修复后：** 期望车型表有数据（`assert r["found"] is True`），并验证 `common_codes` 字段存在

### 3. 数据质量分析（2026-07-26）

分析现有8729条故障码的数据质量：

| 字段 | 填充率 | 说明 |
|------|--------|------|
| description | 100% | ✅ 全部中文 |
| detail | 3.3% | ⚠️ 只有284条 |
| common_causes | 3.3% | ⚠️ 只有284条 |
| diagnostic_steps | 3.3% | ⚠️ 只有284条 |
| related_codes | 3.3% | ⚠️ 只有284条 |
| symptoms | 2.4% | ⚠️ 只有212条 |

### 4. 高频码数据增强（2026-07-26）

为24个高频故障码补充详细的诊断信息。

#### 增强的故障码

**EV/BMS 系统（13个）：**
- P0A00-P0A06：冷却系统相关（温度传感器、水泵）
- P0A09：DC/DC转换器
- P0A0E/P0A0F：高压联锁电路
- P0A16/P0A1F：电池能量控制模块
- P0A30：电机温度传感器

**发动机系统（11个）：**
- P0420/P0430：催化器效率
- P0440-P0455：EVAP系统（蒸发排放）
- P0500：车速传感器
- P0505：怠速控制
- P0562：系统电压
- P0600/P0606：ECU故障

#### 增强内容

每个故障码新增：
- `detail`：详细说明（系统原理、故障含义）
- `severity`：严重程度（已更新为更准确的级别）
- `common_causes`：常见原因（5-6个）
- `diagnostic_steps`：诊断步骤（5-7步）
- `related_codes`：相关故障码
- `symptoms`：可观测症状（3-4个）

#### 增强效果

| 项目 | 增强前 | 增强后 | 变化 |
|------|--------|--------|------|
| detail | 284 (3.3%) | 308 (3.5%) | +24 |
| common_causes | 284 (3.3%) | 308 (3.5%) | +24 |
| diagnostic_steps | 284 (3.3%) | 308 (3.5%) | +24 |
| related_codes | 284 (3.3%) | 308 (3.5%) | +24 |
| symptoms | 212 (2.4%) | 236 (2.7%) | +24 |

#### 新增文件

- `data/seed/priority_enhancement.json` — 增强数据源（24个故障码的详细信息）
- `scripts/enhance_priority_codes.py` — 增强脚本（读取JSON并更新数据库）

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

### 全链路流式 Tool Calling（v3.1.0）

#### 改动的文件（6个）

**`src/ai/providers/__init__.py`**
- 新增 `StreamEvent` 数据类
- 新增 `chat_with_tools_stream` 默认实现

**`src/ai/providers/ollama.py`**
- 实现 `chat_with_tools_stream`：Ollama NDJSON 流式解析

**`src/ai/providers/openai_compat.py`**
- 实现 `chat_with_tools_stream`：OpenAI SSE 流式解析
- 增量 tool_calls 按 index 缓冲拼接

**`src/ai/llm_client.py`**
- 新增 `chat_with_tools_stream` 代理方法

**`src/ai/agent.py`**
- 新增 `run_stream` 方法：流式 ReAct 循环入口
- 新增 `_run_react_loop_stream` 方法

**`src/ui/agent_chat.py`**
- `AgentStreamWorker.run()` 改为消费 `StreamEvent`

#### Bug 修复（3项）
1. Ollama 冗余循环导入
2. OpenAI `finish_reason == "tool_calls"` break 问题
3. 未使用变量 `content_buf`

---

## 当前项目状态

- **版本：** v3.1.0 — Streaming Tool Calling
- **阶段：** 阶段三增强 — 全链路流式 + 翻译完成 + 数据增强
- **测试：** 85 单元测试 + 42 功能验证，全部通过
- **数据库：** 8729 故障码（100% 中文） + 45 车型
- **数据质量：** 308 条有详细诊断信息（+24 本次增强）
- **已修复问题：** 33 项（32 + 1 测试 bug）

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

1. **继续数据增强** — 为更多故障码补充详细信息（当前只有308/8729有详细信息）
2. **AI批量生成** — 使用AI批量生成剩余故障码的详细信息
3. **编辑端点功能** — 右键菜单增加"编辑"
4. **多 Agent 协作** — 主 Agent + 专家子 Agent（BMS/电机/热管理）
5. **UI 优化** — Markdown 渲染增强、诊断结果导出
6. **实际运行测试** — 用 Ollama/OpenAI 测试流式输出效果

---

## 敏感信息说明

- `.env` 文件已通过 `.gitignore` 排除
- Ollama 默认配置：`http://localhost:11434`，模型 `qwen2.5:7b`
- OpenAI API Key 未配置（需用户自行填写 `.env`）

## 关键文件

| 文件 | 说明 |
|------|------|
| `HANDBOOK.md` | 本文档（交接文档） |
| `CLAUDE.md` | Claude Code 项目规范 |
| `README.md` | 项目完整蓝图和设计决策 |
| `data/seed/priority_enhancement.json` | 高频码增强数据源 |
| `scripts/enhance_priority_codes.py` | 数据增强脚本 |
| `scripts/verify_features.py` | 功能验证脚本（42个用例） |
| `scripts/merge_official_codes.py` | 官方故障码合并脚本 |
| `scripts/translate_codes_v2.py` | 故障码翻译脚本 |
