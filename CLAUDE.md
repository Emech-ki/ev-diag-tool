# EV-Diag-Tool

新能源汽车 OBD-II 智能故障码诊断工具，PyQt6 桌面应用。

## 项目结构

- `src/ui/` — PyQt6 界面层（主窗口、结果面板、AI 对话面板）
- `src/database/` — SQLite 数据库管理
- `src/engine/` — 诊断引擎和知识库查询
- `src/ai/` — Ollama LLM 客户端和 AI Agent
- `data/seed/` — 故障码种子数据 CSV
- `scripts/` — 工具脚本（数据库初始化、打包）

## 技术栈

- Python 3.10+ / PyQt6 / aiosqlite / Ollama (本地 LLM)

## 常用命令

```bash
python scripts/seed_db.py    # 初始化数据库
python src/main.py           # 运行程序
```

## 代码规范

- 中文注释和文档
- 线程安全：UI 更新必须在主线程，耗时操作用 QThread
- HTML 转义：所有用户/知识库数据插入 HTML 前必须 `html.escape()`
- 流式渲染：token 级 HTML 处理需考虑跨 token 边界的 markdown 标记
