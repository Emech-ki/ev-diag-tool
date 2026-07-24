# EV-Diag-Tool Handoff

## 项目信息
- **远程仓库:** https://github.com/Emech-ki/ev-diag-tool
- **当前版本:** v1.2.0 — 流式诊断 + 相关码跳转 + bug 修复
- **技术栈:** Python 3.14 + PyQt6 + SQLite + Ollama API
- **入口:** `python src/main.py`
- **测试:** `python -m pytest tests/ -v`

## 最近完成的工作（本次会话）

### 1. Code Review 修复 (8 issues, 已全部修复)
- 🔴 **HIGH (2):**
  - `main_window.py:319` — 添加 `LLMClient.reset_availability()` 方法，替换外部直接改 `_available`
  - `main.py:99` — `check_database()` 返回 False 时 `sys.exit(1)`
- 🟡 **MEDIUM (6):**
  - `result_panel.py:256` — 删除未使用的 `detail` 重复赋值
  - `main.py:28` — `check_database()` 改用 `DatabaseManager._resolve_db_path()` 统一路径
  - `db_manager.py:134/300` — `search_codes()` 和 `search_history()` 中 LIKE 通配符 `%` `_` 加 `ESCAPE '\'` 转义
  - `main_window.py:386` — `except: pass` 改为显示错误信息
  - `llm_client.py:289` — `create_llm_client()` 默认模型名从 config 读取
  - `scripts/seed_db.py:135` — 新增 `-f/--force` 参数，支持 `argparse`

### 2. 历史记录时间修复
- `db_manager.py:save_history()` — 改用 `datetime.now()` 显式写入本地时间，替代 SQLite 的 UTC `CURRENT_TIMESTAMP`

### 3. 流式诊断 (改进了诊断 UX)
- `llm_client.py` — 新增 `_call_ollama_stream()` + `get_diagnostic_suggestion_stream()`
- `main_window.py` — `DiagnoseWorker` 拆为两阶段: KB 查询 → `kb_ready` 信号 → AI 流式 → `ai_token`/`ai_finished` 信号
- `result_panel.py` — 新增 `show_kb_result()`、`append_ai_text()`、`finalize_ai_suggestion()` 分步渲染
- 效果: 点击"诊断"后 **<0.1s 显示知识库结果**，AI 建议逐 token 追加

### 4. 相关故障码修复 + 点击跳转
- `kb.get("related_codes")` JSON 字符串未解析为列表的 bug 修复
- `kb.get("common_causes")` / `kb.get("diagnostic_steps")` JSON 字符串同样修复
- 相关码 chip 间距修复: `QTextBrowser` 不支持 `display:inline-block`，改用 `" ".join` 加空格
- 新增点击跳转: `<a href="dtc://CODE">` → `_on_related_code_clicked` → 同步 `kb.lookup()` → `show_lookup_result()` → 切 tab

### 5. 未完成
- 相关码点击后的完整诊断联动（含 AI）尚未处理

## 已知未完成项
1. **相关码点击后完整诊断联动** — 当前只做同步 KB 查询，需要决定是否触发 AI 诊断
2. **打包 exe** — 需要更新 `EV-Diag-Tool_v1.0.0.spec` 文件以包含新增文件
3. **诊断历史导出** — 支持导出为 PDF/HTML
4. **"Streaming response failed" bug** — 排查中，待确认根因

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
4428222 fix: code review issues - streaming performance, retry, imports
5a81a02 feat: phase 2 enhancements - streaming, model selector, history, tests
4c51c84 feat: add .env config support + fix timeout + fix b_codes symptoms
5a98119 fix: simplify database check in main.py
8cbc394 Add handoff document
a3e948b Fix: resolve 42 code review issues (MEDIUM+LOW) + agent session bug
8425375 Initial commit: EV-Diag-Tool v1.0.0
```

## 下一步建议

1. **相关码点击后完整诊断** — 点击相关码时是否触发完整诊断（含AI流式）
2. **打包 exe** — 更新 PyInstaller spec 文件，打包新功能
3. **多语言支持** — 当前只支持中文
4. **诊断报告导出** — 支持导出为 PDF/HTML
5. **离线模式** — 支持不联网时只使用知识库查询
