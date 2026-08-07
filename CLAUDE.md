# EV-Diag-Tool — AI 交接文档

新能源汽车 OBD-II 智能故障码诊断工具（PyQt6 桌面应用），面向维修技师。定位：知识库给"标准答案"，AI 给"排查建议"，AI 不武断下结论。

## 项目结构

```
src/
├── main.py              # 程序入口
├── config.py            # .env 配置读取 + 多端点管理（模块级常量 import 时缓存）
├── version.py           # 版本号（v3.5.0）
├── ui/                  # PyQt6 界面层
│   ├── main_window.py   # 主窗口（含 QThread worker 定义）
│   ├── result_panel.py  # 单/多码诊断结果展示
│   ├── agent_chat.py    # AI Agent 对话面板
│   ├── three_electric_panel.py  # 三电诊断面板（概览/向导/多码诊断）
│   ├── history_panel.py # 诊断历史
│   ├── export_utils.py  # 报告导出（txt/html/pdf，PDF 用 reportlab）
│   ├── markdown_renderer.py  # Markdown→HTML（含跨 token 粗体缓冲）
│   └── styles/          # 主题令牌（深色/浅色）
├── database/
│   ├── db_manager.py    # SQLite 管理（WAL + busy_timeout + 表自动迁移）
│   └── schema.py        # 表结构
├── engine/
│   ├── diagnostic.py    # 单/多码诊断流程 + parse_fault_codes
│   ├── three_electric.py # 三电领域映射 + 向导加载 + 覆盖概览（纯逻辑无 PyQt）
│   └── knowledge_base.py
└── ai/
    ├── llm_client.py    # 单例代理，_provider_lock 保护 provider 切换
    ├── agent.py         # ReAct Agent（流式 Tool Calling）
    ├── diagnostic_tools.py  # 诊断工具集（9+ 工具）
    └── providers/       # LLMProvider 抽象 + Ollama + OpenAI兼容
```

## 常用命令

```bash
python scripts/seed_db.py    # 初始化数据库（9129 码 + 45 车型）
python scripts/synthesize_ev_details.py   # EV 码详情确定性生成（无需 Ollama）
python scripts/generate_ev_system_codes.py --sync-db   # DB 详情回写 CSV
python src/main.py           # 运行程序
pytest tests/                # 567 个测试
pytest tests/ --cov=src --cov-report=term-missing  # 覆盖率 75%（逻辑层 85%+）
python scripts/verify_features.py   # 端到端验证（需 Ollama 在线，45 项）
```

## 核心架构要点

- **三层架构**：UI (PyQt6) → 业务逻辑（引擎 + AI）→ 数据（SQLite + Ollama/OpenAI）
- **AI Provider 抽象**：`LLMProvider` 接口，`OllamaProvider` / `OpenAICompatProvider`，`LLMClient` 单例按配置选择
- **方案B**：LLM 增强诊断（故障码+车型+描述 → 结构化建议）
- **方案C**：AI Agent，ReAct 循环 + Tool Calling，专家路由（电池/电机/电控/通用）
- **多端点**：`.env` 中 `OPENAI_ENDPOINT_N_{NAME,URL,KEY,MODEL}`，品牌栏一键切换

## 代码规范（必须遵守）

- 中文注释和文档
- **UI 更新必须在主线程**：耗时操作用 QThread + 信号回传；worker 停止必须 `quit()` + `wait()`，超时后 `terminate()`；关闭窗口走 `closeEvent` 停止 worker
- **HTML 转义**：所有用户/知识库数据插入 HTML 前必须 `html.escape()`（历史上有过 XSS 漏洞）
- **流式渲染**：token 级处理需考虑跨 token 边界的 markdown 标记（`**粗体**` 用 `_pending_bold_buf` 缓冲）
- **Provider 切换**：必须持有 `threading.Lock` 保护 `_provider` 赋值
- **故障码格式**：P/B/C/U 后 4 位可含十六进制字母（`P0A00`、`B001A`），解析用 `[0-9A-Fa-f]{4}`，**不要**用 `\d{4}`；另支持 EV 系统码 `EV-XXX-NNN`（如 `EV-BMS-001`），解析见 `parse_fault_codes`
- **数据库**：所有 SQL 必须参数化（`?` 占位符）；并发写用 `_write_lock` 串行化

## 关键陷阱（踩过坑）

1. **Ollama 不支持消息历史中的 `tool_calls` 字段**（返回 400）。`agent.py` 用 `_build_tool_assistant_msg()` 按 provider 区分：Ollama 剥离 tool_calls，OpenAI 必须携带
2. **availability 缓存有 TTL**（30s）：`_available` + `_available_at`，服务恢复后不会永久显示不可用
3. **`LLMClient.is_available()`** 网络调用在锁外执行（避免长持锁冻结 UI）
4. **多码诊断**：UI 走 `diagnose_multiple`（`main_window._diagnose_multiple`），无关联性分析（correlation 模块已移除）
5. **模型选择器初始化**：`_model_selector_updating` 保护标志防止误触发 `_on_model_changed`
6. `.env` 写入用 `_sanitize_env_value()` 防注入；数值配置有默认值容错

## 当前状态

- **版本**：v3.5.0（三电诊断）
- **测试**：567 个全部通过（含 UI 测试、export_as_pdf 4 个）
- **数据库**：9129 故障码（EV 系统码 400 条 100% 有详情，各系统 50 条；P/B/C/U 详情部分覆盖）+ 45 车型
- **AI 配置**：`.env` 指向本地 Ollama `qwen2.5:7b`
- **打包**：`pyinstaller EV-Diag-Tool.spec --noconfirm`（spec 内改 name 为当前版本号）
- **EV 详情生成**：`scripts/synthesize_ev_details.py`（确定性模板，无需 Ollama）回填 DB 后，用 `scripts/generate_ev_system_codes.py --sync-db` 回写 CSV

## 已修复的高危问题（v3.4.2 已提交）

| 严重度 | 问题 | 修复 |
|--------|------|------|
| 🔴 | `parse_fault_codes` 正则丢弃 63.7% 含十六进制字母的码 | 改为 `[0-9A-Fa-f]{4}` |
| 🔴 | 多码结果 HTML 未转义（XSS） | `_build_multi_code_kb_html` 全部 `html.escape` |
| 🔴 | ReAct 非流式循环缺下一轮 LLM 调用 | 补上 `chat_with_tools` |
| 🟠 | Ollama/OpenAI 协议不一致导致 OpenAI 400 | `_build_tool_assistant_msg` 按 provider 分支 |
| 🟠 | availability 永久缓存 | 加 30s TTL |
| 🟠 | worker 生命周期（wait 超时无 terminate、无 closeEvent） | 补 terminate + `closeEvent` |
| 🟠 | `_ensure_tables` 不建 obd_codes 表 | 补幂等建表 |
| 🟠 | 流式粗体跨 token 泄漏字面 `**` | `StreamMarkdownRenderer` 状态机（粗体延迟到闭合渲染） |
| 🟢 | 死代码 `diagnose_multi`/correlation/context 等 | 全部删除（无调用点，167 测试验证） |
