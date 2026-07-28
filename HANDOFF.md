# Handoff Document — EV-Diag-Tool 会话交接

**Date:** 2026-07-28
**Project:** `D:\桌面\诊断ai程序\ev-diag-tool`
**Repo:** https://github.com/Emech-ki/ev-diag-tool.git
**Version:** v3.4.0 — Multi-Fault Analysis + Bug Fixes
**Tests:** 84 passed (unit)
**Database:** 8729 fault codes + 45 vehicle models

---

## 本次会话完成的工作

### 1. 多故障码分析 Bug 修复（4 项）

| # | 严重度 | Bug | 修复 | 文件 |
|---|--------|-----|------|------|
| 1 | 🟠 MEDIUM | `search_codes_by_system` 搜索不可靠 | 改用 SQL 直接查询 | `src/ai/diagnostic_tools.py` |
| 2 | 🟠 MEDIUM | EV 系统码关联判断过宽 | 用 code 前缀判断子系统 | `src/engine/correlation.py` |
| 3 | 🟡 LOW | 多码 AI 流式显示清空问题 | 重建完整内容显示 | `src/ui/result_panel.py` |
| 4 | 🟡 LOW | 综合 AI 缺少专门方法 | 添加 `append_combined_ai_token` | `src/ui/result_panel.py`, `src/ui/main_window.py` |

### 2. AI 配置问题修复（3 项）

| # | 问题 | 修复 |
|---|------|------|
| 1 | AI 灯黄色/不亮 | `.env` 中 `AI_PROVIDER=openai` 改为 `ollama` |
| 2 | 没有模型 | 下载了 `qwen2.5:7b`（4.7GB） |
| 3 | 诊断提示不详细 | 添加了详细的错误诊断信息 |

### 3. Git 提交记录

### 1. Bug 修复（8 项）

| # | 严重度 | Bug | 修复 | 文件 |
|---|--------|-----|------|------|
| 1 | 🔴 CRITICAL | `ev_codes.csv` 重复 `symptoms` 列 | 删除重复列 | `data/seed/ev_codes.csv` |
| 2 | 🟠 MEDIUM | `styles.py` 与 `styles/__init__.py` 冲突 | 删除遗留 `styles.py` | `src/ui/styles.py` (deleted) |
| 3 | 🟡 LOW | `LLMClient` 线程安全 | 所有属性加 `provider_lock` | `src/ai/llm_client.py` |
| 4 | 🟡 LOW | OpenAI URL `/v1` 追加逻辑 | `urlparse` 检测已有路径 | `src/ai/providers/openai_compat.py` |
| 5 | ⚪ COSMETIC | 流式完成后全量重建闪烁 | 移除 `_rebuild_display()` 调用 | `src/ui/agent_chat.py` |
| 6 | 🔴 HIGH | 相关故障码 XSS 注入 | 添加 `html.escape()` | `src/ui/result_panel.py` |
| 7 | 🔴 HIGH | SQLite `database is locked` 并发写入 | 独立连接策略 + busy_timeout + 重试 | `src/database/db_manager.py`, `scripts/batch_enhance_codes.py` |
| 8 | 🟡 LOW | AI 偶尔输出英文 | 系统 Prompt 强制中文要求 | `src/ai/prompt_templates.py` |

### 2. 新功能（5 项）

#### 2.1 编辑端点
- 右键菜单编辑已配置的远程 API 端点
- 改动: `add_endpoint_dialog.py`, `config.py` (新增 `update_endpoint_in_env`), `main_window.py`

#### 2.2 诊断结果导出
- 支持 txt/html 格式导出
- 当前结果导出: 结果面板"导出报告"按钮
- 历史记录导出: 历史面板右键菜单"导出此记录"
- 新建: `src/ui/export_utils.py`
- 改动: `result_panel.py`, `history_panel.py`, `main_window.py`

#### 2.3 Markdown 渲染增强
- 新建 `src/ui/markdown_renderer.py`
- 支持: 标题、粗体、斜体、删除线、行内代码、代码块、列表、引用、链接、分隔线
- 改动: `result_panel.py`, `agent_chat.py`, `export_utils.py`

#### 2.4 多 Agent 协作（专家路由系统）
- 4 个专家: BMS 电池管理、电机驱动、热管理、通用诊断
- 路由逻辑: 查询数据库 `system` 字段 + P0Axx 描述关键词细分
- 专家知识通过 `get_expert_context` 工具查询（不注入 Prompt，保护 7B 模型输出质量）
- 系统 Prompt 注入专家角色声明 + 专家名称
- 新建: `data/seed/expert_context.json`
- 改动: `src/ai/diagnostic_tools.py` (新增第 10 个工具), `src/ai/agent.py`, `src/ai/prompt_templates.py`

#### 2.5 AI 批量故障码增强脚本
- `scripts/batch_enhance_codes.py`
- 逐条调用 AI 为故障码生成详细诊断信息（detail, severity, common_causes, diagnostic_steps, symptoms）
- 支持 Ollama 和 OpenAI 兼容 API（当前使用 MiMo API: mimo-v2.5-pro）
- 并发 5 路请求，预计总时间 ~15 小时
- 断点续传，进度保存到 `data/enhancement_progress.json`

### 3. 代码清理

| 操作 | 文件 |
|------|------|
| 删除死代码 | `src/ui/animation.py`, `src/ui/styles/dark_theme.qss` |
| 清理未用导入 | `re`, `QColor`, `_BOLD_RE` |
| 修复重复信号连接 | `src/ui/add_endpoint_dialog.py` |

### 4. 实训验证

生成 5 个故障场景的实训单和答案文件（Word）：
- `EV-Diag-Tool_故障实训单.docx` — 桌面
- `EV-Diag-Tool_实训答案.docx` — 桌面

5 个场景覆盖: BMS (P0A00), 电机 (P0A17), 热管理 (P0A01), 动力总成 (P0300), 车身 (B1420)

### 5. Git 提交记录

```
292d972 feat: bug修复 + 编辑端点 + 诊断导出 + Markdown渲染 + 批量增强
96f172f feat: 多Agent协作 — 专家路由系统
cbed637 fix: SQLite并发写入 database is locked 修复
94847b0 fix: 上下文中注入专家名称
32d4832 fix: 彻底修复 database is locked — 独立连接策略
1041f0e fix: 专家路由改用数据库 system 字段
c3f1f00 fix: 强制中文输出
```

---

## 当前项目状态

- **版本：** v3.3.0 — Multi-Agent + Batch Enhancement
- **测试：** 85 单元测试全部通过
- **数据库：** 8729 故障码（100% 中文） + 45 车型
- **数据质量：** ~1100 条有详细诊断信息（批量增强持续增长中）
- **后台任务：** MiMo API 批量增强运行中（并发 5，预计 ~15 小时完成）

## 后台运行中的任务

批量增强脚本正在后台运行：
```bash
# 查看进度
python -c "import json; p=json.load(open('data/enhancement_progress.json',encoding='utf-8')); c=len(p.get('completed',[])); f=len(p.get('failed',[])); print(f'completed: {c}  failed: {f}')"

# 重新运行（断点续传）
cd D:\桌面\诊断ai程序\ev-diag-tool
python scripts/batch_enhance_codes.py
```

当前使用 MiMo API（mimo-v2.5-pro），配置在 `.env` 中：
```
AI_PROVIDER=openai
OPENAI_ENDPOINT_1_NAME=MiMo
OPENAI_ENDPOINT_1_URL=https://token-plan-cn.xiaomimimo.com/v1
OPENAI_ENDPOINT_1_KEY=REDACTED
OPENAI_ENDPOINT_1_MODEL=mimo-v2.5-pro
```

## 新建的文件

| 文件 | 说明 |
|------|------|
| `src/ui/markdown_renderer.py` | Markdown → HTML 渲染器 |
| `src/ui/export_utils.py` | 诊断结果导出工具（txt/html） |
| `scripts/batch_enhance_codes.py` | AI 批量故障码增强脚本 |
| `scripts/generate_training_docs.py` | 实训单/答案生成脚本 |
| `data/seed/expert_context.json` | 专家领域知识（BMS/电机/热管理/通用） |
| `HANDOFF.md` | 本文件 |

## 删除的文件

| 文件 | 原因 |
|------|------|
| `src/ui/animation.py` | 未被任何代码引用，动画效果有 GC 问题 |
| `src/ui/styles/dark_theme.qss` | 预留文件，从未加载 |
| `src/ui/styles.py` | 与 `styles/__init__.py` 冲突 |

## 建议的下一步工作

1. **等批量增强完成** — 数据覆盖率从 ~13% 提升到 100%
2. **深色模式** — 实现暗色主题切换
3. **诊断历史分析** — 高频故障码统计、常见车型故障分布
4. **离线体验优化** — 无 AI 时的纯知识库诊断交互
5. **测试覆盖** — 为 export_utils、markdown_renderer 编写单元测试
6. **多 Agent 协作扩展** — 主 Agent + 专家子 Agent 并行诊断

---

## 关键文件速查

| 文件 | 说明 |
|------|------|
| `CLAUDE.md` | Claude Code 项目规范 |
| `README.md` | 项目完整蓝图和设计决策 |
| `HANDOFF.md` | 本文件（会话交接） |
| `src/ai/agent.py` | AI Agent 核心（ReAct 循环 + 专家路由） |
| `src/ai/diagnostic_tools.py` | 10 个诊断工具 |
| `src/ai/prompt_templates.py` | 系统 Prompt（含专家角色声明） |
| `src/database/db_manager.py` | SQLite 数据库管理（并发安全） |
| `scripts/batch_enhance_codes.py` | 批量增强脚本（后台运行中） |
