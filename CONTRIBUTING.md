# 贡献指南

欢迎贡献！你可以在以下方面帮助项目：

- 提交 Issue 报告 bug
- 补充新的故障码数据
- 改进诊断逻辑
- 增加多语言支持

## 开发环境

```bash
python -m venv venv
# Windows: .\venv\Scripts\activate
pip install -r requirements.txt
python scripts/seed_db.py   # 初始化数据库
python src/main.py          # 运行程序
```

测试：`pytest tests/`（当前 620 个测试）

## 代码规范

- 中文注释和文档
- 线程安全：UI 更新必须在主线程，耗时操作用 QThread
- HTML 转义：所有用户/知识库数据插入 HTML 前必须 `html.escape()`
- 流式渲染：token 级 HTML 处理需考虑跨 token 边界的 markdown 标记
- Provider 切换：必须持有 `threading.Lock` 保护 `_provider` 赋值
- Worker 生命周期：`quit()` + `wait()` 超时后必须 `terminate()`

## 系统架构（三层）

```
用户界面层 (PyQt6) → 业务逻辑层（诊断引擎 + AI 服务） → 数据层（SQLite + Ollama）
```

- **UI**：`src/ui/` — PyQt6 桌面界面
- **引擎**：`src/engine/` — 故障码诊断、三电领域逻辑（纯逻辑无 PyQt）
- **AI**：`src/ai/` — Provider 抽象、ReAct Agent、诊断工具集
- **数据**：`src/database/` + `data/seed/` CSV — SQLite 知识库与种子数据

## AI 架构

### Provider 抽象层

- **Provider 接口**: `src/ai/providers/__init__.py` — `LLMProvider` 抽象基类
- **OllamaProvider**: `src/ai/providers/ollama.py` — Ollama HTTP API（支持 tool calling）
- **OpenAICompatProvider**: `src/ai/providers/openai_compat.py` — OpenAI 兼容 API
- **LLMClient 代理**: `src/ai/llm_client.py` — 根据配置选择 provider，`threading.Lock` 保护切换

### 多端点配置

`.env` 中配置 `OPENAI_ENDPOINT_N_NAME/URL/KEY/MODEL`，支持多个端点。品牌栏下拉框一键切换。

### AI 方案

**方案B — LLM 增强诊断：**
- 输入故障码 + 车型 + 附加描述
- LLM 生成结构化的诊断建议
- 界面清晰标注"AI建议，仅供参考"

**方案C — AI Agent 交互诊断：**
- 基于 Tool Calling 让 Agent 访问数据库
- 多 Agent 协作（BMS/电机/热管理专家）
- 维护诊断会话上下文，主动提问引导排查

### Agent 核心架构（ReAct 模式）

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

### Prompt 特性

- 支持 few-shot 示例、CoT 推理
- 严重程度自适应（高危故障码加强安全提醒）
- 新能源安全提醒（高压系统操作警告）
- 专家角色声明（电池/电机/电控专家路由）

更完整的内部设计说明见 `CLAUDE.md`（AI 交接文档）。