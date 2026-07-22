# EV-Diag-Tool Handoff

## 项目信息
- **远程仓库:** https://github.com/Emech-ki/ev-diag-tool
- **当前版本:** v1.0.0 基础查询版
- **技术栈:** Python 3.14 + PyQt6 + SQLite + Ollama API
- **入口:** `python src/main.py`

## 最近完成的工作
1. v1.0.1（玻璃拟态仪表盘）→ 完全回退到 v1.0.0
2. 代码审计修复：42 个问题（8 HIGH + 18 MEDIUM + 16 LOW）全部修复
3. 核心修复：AI Agent 会话永不初始化 bug、HTML 注入、信号泄漏、DB 线程安全
4. Git 初始化并推送至 GitHub

## 已知未完成项
1. **.env 集成** — `.env.example` 定义了配置变量，但代码未读取。需安装 `python-dotenv` 并实现 `os.getenv`
2. **data/seed/b_codes.csv** — B1100/B1101 的症状数据是 P 码症状，与车身系统不符
3. **git 系统 PATH** — 当前需通过 `$env:PATH` 临时添加

## 可执行文件
`dist/EV-Diag-Tool_v1.0.0.exe` — 已包含全部修复的最新打包

## 数据库
`data/obd_codes.db` — 150 条记录，由 `python scripts/seed_db.py` 初始化
