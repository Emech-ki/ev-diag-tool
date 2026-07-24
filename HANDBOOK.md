# EV-Diag-Tool Handoff

## 项目信息
- **远程仓库:** https://github.com/Emech-ki/ev-diag-tool
- **当前版本:** v1.3.0 — 相关码点击跳转 bug 修复
- **技术栈:** Python 3.14 + PyQt6 + SQLite + Ollama API
- **入口:** `python src/main.py`
- **测试:** `python -m pytest tests/ -v`

## 最近完成的工作（本次会话）

### 1. DtcTextBrowser 子类（阻止 Qt 默认导航）
- `result_panel.py` — 新增 `DtcTextBrowser(QTextBrowser)` 子类，覆写 `setSource()`
- 拦截 `dtc://` scheme，不调 `super().setSource()`，阻止 Qt 报 "No document for dtc://..."
- `knowledge_browser` 从 `QTextBrowser()` 改为 `DtcTextBrowser()`

### 2. QTimer.singleShot 延迟信号发射（修复竞争条件）
- **根因：** Qt 的 `QTextBrowser` 在 `anchorClicked` 信号处理器内部仍在执行 `setSource`，此时 `show_lookup_result()` 调用 `clear()` 会破坏 Qt 内部状态机，导致 "No document" 警告 + 相关码信息不显示
- `result_panel.py:_on_anchor_clicked` — `diagnose_requested.emit(code)` 改为 `QTimer.singleShot(0, ...)` 延迟发射
- `main_window.py:_on_related_code_clicked` — 拆分为两部分：
  - `_on_related_code_clicked(code)` — worker 清理 + 设置输入框（同步）
  - `_do_related_code_lookup(code)` — kb.lookup + show_lookup_result（延迟）

### 3. ⚠️ 当前状态：bug 仍未完全解决
- `QTimer.singleShot` 延迟方案已实现，但实际运行中 "No document for dtc://..." 仍然出现
- 可能需要更深层的方案：子类化覆写 `mouseReleaseEvent` 或改用 `QLabel` + `linkActivated`
- **下一步重点排查方向：** PyQt6 中 `setSource` 虚方法覆写是否真正生效（C++ 层面可能直接调用基类）

## 已知未完成项
1. **🔴 dtc:// 点击跳转 bug** — "No document for dtc://..." 仍然出现，相关码信息不显示，需继续排查
2. **相关码点击后完整诊断联动** — 当前只做同步 KB 查询，需要决定是否触发 AI 诊断
3. **打包 exe** — 需要更新 `EV-Diag-Tool_v1.0.0.spec` 文件以包含新增文件
4. **诊断历史导出** — 支持导出为 PDF/HTML
5. **"Streaming response failed" bug** — 排查中，待确认根因

## 项目结构

```
ev-diag-tool/
├── src/
│   ├── main.py            ← 程序入口
│   ├── config.py          ← .env 配置管理（新增）
│   ├── version.py         ← 版本号
│   ├── ui/
│   │   ├── main_window.py ← 主窗口（含模型选择器）
│   │   ├── result_panel.py← 诊断结果面板
│   │   ├── agent_chat.py  ← AI 对话面板（流式响应）
│   │   ├── history_panel.py ← 历史记录面板（新增）
│   │   └── styles/        ← 样式常量
│   ├── database/
│   │   ├── db_manager.py  ← 数据库管理（含历史记录方法）
│   │   └── schema.py      ← 表结构定义（含 history 表）
│   ├── engine/
│   │   ├── diagnostic.py  ← 诊断流程控制
│   │   └── knowledge_base.py ← 知识库查询
│   └── ai/
│       ├── llm_client.py  ← Ollama API 客户端（流式+模型切换）
│       ├── prompt_templates.py ← 提示词模板
│       └── agent.py       ← AI Agent（流式对话）
├── data/
│   ├── seed/              ← 种子数据（已修复 B1100/B1101）
│   └── obd_codes.db       ← SQLite 数据库（150 条 + history 表）
├── tests/
│   ├── test_database.py   ← 数据库测试（19个）
│   ├── test_engine.py     ← 引擎测试（12个）
│   └── test_ai.py         ← AI 测试（10个）
├── scripts/
│   └── seed_db.py         ← 数据库初始化（已更新支持 history 表）
├── .env.example           ← 配置文件模板
├── .env                   ← 实际配置（已创建，git 忽略）
└── requirements.txt       ← 依赖清单（含 pytest）
```

## 运行方式

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 确保 Ollama 运行
ollama serve

# 3. 初始化数据库（如需更新）
python scripts/seed_db.py

# 4. 运行程序
python src/main.py

# 5. 运行测试
python -m pytest tests/ -v
```

## 配置文件 (.env)

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL_NAME=qwen2.5:7b
DB_PATH=
LOG_LEVEL=INFO
```

## 数据库表

### obd_codes（故障码表）
- 150 条记录（P/B/C/U 系列）
- 字段：code, system, description, detail, severity, common_causes, diagnostic_steps, related_codes, symptoms

### diagnostic_history（诊断历史表，新增）
- 自动保存每次诊断记录
- 字段：code, vehicle_info, symptoms, knowledge_found, ai_suggestion, created_at

## Git 提交历史

```
ecf2dd0 feat: streaming diagnosis + related code jump + code review fixes
e3a50f7 fix: auto-create diagnostic_history table on startup
c959ee6 docs: update handoff for v1.1.0 - phase 2 complete
4428222 fix: code review issues - streaming performance, retry, imports
5a81a02 feat: phase 2 enhancements - streaming, model selector, history, tests
4c51c84 feat: add .env config support + fix timeout + fix b_codes symptoms
5a98119 fix: simplify database check in main.py
8cbc394 Add handoff document
a3e948b Fix: resolve 42 code review issues (MEDIUM+LOW) + agent session bug
8425375 Initial commit: EV-Diag-Tool v1.0.0
```

## 下一步建议

1. **🔴 dtc:// 点击跳转 bug（最高优先级）** — "No document" 仍然出现，需尝试：
   - 方案 A：覆写 `mouseReleaseEvent`，在点击 `dtc://` 链接时自行处理并 `event.accept()`
   - 方案 B：改用 `QLabel` + `linkActivated` 信号（无 `setSource` 问题）
   - 方案 C：用 `eventFilter` 拦截 `QTextBrowser` 的鼠标事件
2. **相关码点击后完整诊断** — 点击相关码时是否触发完整诊断（含AI流式）
3. **打包 exe** — 更新 PyInstaller spec 文件，打包新功能
4. **多语言支持** — 当前只支持中文
5. **诊断报告导出** — 支持导出为 PDF/HTML
