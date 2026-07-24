# Handoff Document — EV-Diag-Tool

**Date:** 2026-07-25
**Project:** `D:\桌面\诊断ai程序\ev-diag-tool`
**Repo:** https://github.com/Emech-ki/ev-diag-tool.git
**Latest commit:** `589d666` (master)

---

## 本次会话完成的工作

### 1. Handbook 阅读 + 问题发现

读取了 `README.md`（项目记忆/蓝图）、`文件清单.txt`、`项目整体架构图.txt`，以及 `.opencode/skills/` 下的 prototype、diagnosing-bugs、code-review 等技能文档。通过 2 个并行 agent 扫描全部源码，发现 6 个初始问题。

### 2. 初始 6 项修复（已提交）

| # | 文件 | 修复 |
|---|------|------|
| 1 | `result_panel.py:431` | 诊断步骤永远不显示 — HTML 生成嵌套在 `isinstance(steps, str)` 块内 |
| 2 | `agent_chat.py:251` | 流式消息替换不可靠 — 改用消息列表 + 重建方案 |
| 3 | `result_panel.py` | 局部变量 `html` 遮蔽 `html` 模块 → 重命名为 `kb_html` |
| 4 | `agent.py:103,145` | `CONTEXT_WINDOW_SIZE=10` 定义但未使用 |
| 5 | `llm_client.py:255,274` | 硬编码 temperature/num_predict → 使用模块常量 |
| 6 | `schema.py:48-63` | 删除 5 个从未使用的 SQL 查询常量 |

### 3. 代码审查（9 个 agent × 10 个角度）

对修改后的 5 个文件进行全面审查，发现 15 个额外问题。

### 4. 全部 15 项修复（已提交）

**agent_chat.py（10 项）：**
- 线程安全：添加 `_stop_worker()` 辅助方法，`_on_new_diagnosis`/`_on_clear_chat`/`sync_diagnosis` 先停止 worker 再操作 session
- `wait(1000)` → `wait(5000)`
- `_append_message_html` 添加 `html.escape()` 转义
- `_on_agent_error` 记录部分 `_stream_content` 到 `_messages`
- `_clear_display` 重置 `_stream_content`
- `__init__` 初始化 `_stream_content = ""`
- 预编译 `_BOLD_RE`
- `_rebuild_display` 添加 `setUpdatesEnabled(False/True)` 减少闪烁

**result_panel.py（3 项）：**
- `desc`/`detail`/causes/steps 全部 `html.escape()`
- `sys` 变量重命名为 `sys_name`，防空处理
- 相关码点击修复：`url.path()` → `url.host().upper()`

**llm_client.py（1 项）：**
- 流式重试改为仅连接阶段重试，避免重复内容

**knowledge_base.py（1 项）：**
- `related_codes` 解析兼容 JSON 数组格式

**main_window.py（1 项）：**
- Ollama 可用性检查移到后台线程（`_OllamaCheckWorker`），解决启动卡顿 1-2 秒

---

## 当前项目状态

- **版本：** v1.3.0 "相关码跳转修复"
- **阶段：** 阶段一（基础查询版）基本完成
- **功能：** 故障码查询、知识库展示、AI 诊断建议（流式）、AI 对话、诊断历史、相关码跳转、模型切换
- **已知遗留：** `_messages` 列表无上限（当前会话规模无需限制）

---

## 建议的下一步工作

1. **阶段二：AI 增强版** — 优化 LLM prompt、支持更多模型、添加车型数据库
2. **测试补充** — `tests/` 目录下目前无测试文件，建议添加 `test_database.py`、`test_engine.py`、`test_ai.py`
3. **打包 exe** — PyInstaller 打包、`scripts/build_exe.py` 完善
4. **性能优化** — `_messages` 添加上限、流式渲染频率优化

---

## Suggested Skills

- `/diagnosing-bugs` — 如果遇到新 bug，使用 6 阶段诊断流程
- `/code-review` — 下次大规模修改后进行全面代码审查
- `/tdd` — 为 `tests/` 目录补充单元测试
- `/improve-codebase-architecture` — 阶段二开始前审视架构

---

## 敏感信息说明

- `.env` 文件已通过 `.gitignore` 排除，不包含在提交中
- Ollama 默认配置：`http://localhost:11434`，模型 `qwen2.5:7b`
- 无 API 密钥或其他敏感凭证
