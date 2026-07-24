# EV-Diag-Tool Handoff

## 项目信息
- **远程仓库:** https://github.com/Emech-ki/ev-diag-tool
- **当前版本:** v1.1.0 — 流式响应 + 模型切换 + 历史记录
- **技术栈:** Python 3.14 + PyQt6 + SQLite + Ollama API
- **入口:** `python src/main.py`
- **测试:** `python -m pytest tests/ -v`

## 最近完成的工作（本次会话）

### 1. 阶段一遗留修复
- ✅ `.env` 配置集成 — 新建 `src/config.py`，统一管理配置
- ✅ Ollama 超时修复 — `REQUEST_TIMEOUT` 30s → 90s，`MAX_RETRIES` 2 → 3
- ✅ `b_codes.csv` 数据修复 — B1100/B1101 症状从 P 码改为车身系统正确症状

### 2. 阶段二增强
- ✅ **流式响应** — AI 回复逐字显示（打字机效果）
  - `llm_client.py` 新增 `chat_stream()` 方法
  - `agent.py` 新增 `chat_stream()` 方法
  - `agent_chat.py` 使用 `AgentStreamWorker` 实现实时显示
- ✅ **模型切换 UI** — 品牌栏可编辑下拉框
  - `llm_client.py` 新增 `get_available_models()` + `set_model()`
  - `main_window.py` 添加 QComboBox，自动列出已安装模型
- ✅ **诊断历史记录** — 新增"历史记录"Tab
  - `schema.py` 新增 `diagnostic_history` 表
  - `db_manager.py` 新增 `save_history()` / `get_history()` / `search_history()` / `clear_history()`
  - `history_panel.py` 新建，支持搜索和清空
  - 每次诊断自动保存记录

### 3. 测试
- ✅ 41 个单元测试全部通过
  - `tests/test_database.py` — 19 个数据库测试
  - `tests/test_engine.py` — 12 个引擎测试
  - `tests/test_ai.py` — 10 个 AI 测试

### 4. Code Review 修复
- ✅ 动态 import 改为顶部导入
- ✅ 流式请求增加重试机制
- ✅ 流式 UI 性能优化（不重写整个 HTML）
- ✅ 模型切换增加验证提示

## 已知未完成项
1. **打包 exe** — 需要更新 `EV-Diag-Tool_v1.0.0.spec` 文件以包含新增文件
2. **流式 UI 完善** — 当前流式完成后会用 HTML 替换，可进一步优化格式化
3. **诊断历史导出** — 计划中的功能，暂未实现
4. **Git 系统 PATH** — 当前需通过 `$env:PATH` 临时添加

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

1. **打包 exe** — 更新 PyInstaller spec 文件，打包新功能
2. **流式诊断建议** — 当前只在 Agent 对话中使用流式，诊断结果页面的 AI 建议也可以改为流式
3. **多语言支持** — 当前只支持中文
4. **诊断报告导出** — 支持导出为 PDF/HTML
5. **离线模式** — 支持不联网时只使用知识库查询
