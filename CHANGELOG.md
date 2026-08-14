# 更新日志

本文件记录 EV-Diag-Tool 各版本的变更。最新版本置顶。

---

### v3.6.1 — 真实频次融合与三电深色模式修复（2026-08-14）

| # | 新增项 | 文件 |
|---|------|------|
| 1 | 概览频次融合：`real_frequency`（近 90 天诊断历史计数归一化，20 次记满，多码逗号串拆开各计 1）作为真实信号，与 seed `frequency` 按 0.7×real + 0.3×seed 融合排序；`save_history` 增量刷新受影响码真实频次（重算先归零再累加，历史删除后不 stale）；`recalc_frequencies(codes=None)` 支持全量/增量，老库自动补列 | `src/database/schema.py`, `src/database/db_manager.py`, `src/engine/three_electric.py`, `tests/` |
| 2 | 概览配额均衡：子系统总配额（battery 5 / motor 3 / vcu 2）+ 每系统前缀额度（默认 1 席）双约束；修复保证 EV-OBC/DCDC/THERMAL 不被 EV-BMS/HV critical 挤掉 | `src/engine/three_electric.py`, `tests/` |
| 3 | 三电深色模式修复：外层/内层 tab 基础样式补 `color`（深底黑字）、启动即应用主题、向导动态控件取色；结果面板现象「保存」按钮禁用态改主题令牌 `symptom_disabled`（消除深色下浅色残留）；三电页面/内层 tab 页/内嵌结果面板底色补 `CARD_BG`（消除深色下白底留白） | `src/ui/main_window.py`, `src/ui/three_electric_panel.py`, `src/ui/result_panel.py`, `src/ui/theme_helper.py`, `tests/` |
| 4 | 测试 598 → 620；版本/文档同步 v3.6.1 | `tests/`, `src/version.py`, `README.md`, `CLAUDE.md` |

### v3.6.0 — 三电置信度与频次排序增强（2026-08-12）

| # | 新增项 | 文件 |
|---|------|------|
| 1 | 向导候选码显式置信度 `weight`：`three_electric_guide.json` 候选码改为对象式 `{code, weight}`（0-100），新增 `get_option_codes`/`get_option_weights` 单一解析；weight 贯穿 worker(`priority_weights`) → `diagnose_multiple` → `MultiCodeDiagnosticResult.priority_weights` → AI prompt（渲染「置信度 x%」）→ 结果面板「🎯 高疑似 x%」徽标。顺序仅作 tie-breaker | `data/seed/three_electric_guide.json`, `src/engine/three_electric.py`, `src/ui/three_electric_panel.py`, `src/engine/diagnostic.py`, `src/ai/llm_client.py`, `src/ai/prompt_templates.py`, `src/ui/result_panel.py` |
| 2 | `obd_codes` 新增 `frequency` 列（0-100 确定性 seed，EV 系统码由生成脚本稳定哈希填充，老库 `_migrate_add_column` 自动补列）；`build_overview` 高频码排序 = severity 主键 + frequency 次键 | `src/database/schema.py`, `src/database/db_manager.py`, `scripts/generate_ev_system_codes.py`, `scripts/seed_db.py`, `data/seed/ev_system_codes.csv`, `src/engine/three_electric.py` |
| 3 | P0Axx/消息关键词收敛单一真源：`THREE_ELECTRIC` 各子系统 `keywords` + `get_expert_keywords`/`match_keywords`；`_select_expert` 删除硬编码 battery/motor/vcu 关键词与 P0A 电机描述词 | `src/engine/three_electric.py`, `src/ai/agent.py` |
| 4 | `dist/` 历史 exe 归档：旧版本移入 `dist/archive/`，仅保留最新版 | `dist/` |
| 5 | 测试 587 → 598（weight 解析/透传/渲染、frequency 迁移/排序、关键词收敛）；文档/spec/版本同步 v3.6.0 | `tests/`, `src/version.py`, `EV-Diag-Tool.spec`, `README.md`, `CLAUDE.md` |
| 6 | 在线验证 + 打包：`verify_features.py` 45/45 全绿（Ollama qwen2.5:7b）；`pyinstaller` 生成 v3.6.0 exe 冒烟启动通过 | `scripts/verify_features.py`, `EV-Diag-Tool.spec`, `dist/` |

### v3.5.1 — 三电诊断增强（2026-08-10）

| # | 新增项 | 文件 |
|---|------|------|
| 1 | 向导候选码 → 「🎯 高疑似」标记：`three_electric_guide.json` 的候选码顺序作为高疑似提示，贯穿 worker → `diagnose_multiple` → AI prompt（新增「高疑似候选码」段）→ 结果面板（高疑似码排前并带标记，不依赖 AI 也有合理排序） | `src/ui/three_electric_panel.py`, `src/ui/result_panel.py`, `src/engine/diagnostic.py`, `src/ai/prompt_templates.py`, `src/ai/llm_client.py` |
| 2 | 三电报告导出增强：symptom_context（诊断对象/现象/排查提示）进入 PDF/HTML/txt 报告的「症状描述」；聚合逻辑收敛为 `export_utils.aggregate_multi_knowledge`（主窗口与三电面板共用，修复原面板版丢严重度/原因/步骤的问题） | `src/ui/export_utils.py`, `src/ui/main_window.py`, `src/ui/three_electric_panel.py` |
| 3 | 修复 `do_sync_db` 注释与实现不符：DB 无详情时不再用空值覆盖 CSV 原有详情（提取 `_merge_sync_rows` 纯函数） | `scripts/generate_ev_system_codes.py`, `tests/test_generate_ev_codes.py` |
| 4 | Ollama 在线验证：`build_multi_diagnostic_prompt` 排序指令在 qwen2.5:7b 实测有效（高疑似码排前）；`verify_features.py` 45/45 全绿 | 文档同步 |
| 5 | 打包验证：`pyinstaller` 生成 v3.5.1 exe 并可正常启动；文档/测试数同步（567 → 582） | `EV-Diag-Tool.spec`, `README.md`, `CLAUDE.md` |
| 6 | 域映射单一真源：`THREE_ELECTRIC` 收敛专家路由（`get_subsystem_for_system`/`get_expert_name`/`get_expert_domains`），`_select_expert` 删除硬编码 EV 系统码 if 链；`expert_context.json` domains 与之一致性测试兜底。新增 EV 系统码只需改一处 | `src/engine/three_electric.py`, `src/ai/agent.py`, `tests/test_three_electric.py`, `tests/test_ev_codes.py` |
| 7 | `build_overview` 收窄异常：`except Exception` → `except (KeyError, TypeError, AttributeError)`（不再吞 KB 结构错误） | `src/engine/three_electric.py` |

### v3.5.0 — 三电诊断（2026-08-07）

| # | 新增项 | 文件 |
|---|------|------|
| 1 | 新增 EV-VCU 电控系统码 50 条（上电时序/通信/扭矩仲裁/高压许可等），EV 系统码 350→400，故障码总数 9079→9129；`--upsert-db` 改为先删后插保证幂等 | `data/seed/ev_system_codes.csv`, `scripts/generate_ev_system_codes.py`, `scripts/synthesize_ev_details.py` |
| 2 | 三电领域引擎：battery（BMS/HV/OBC/DC-DC/热管理 250 码）/ motor（电机/再生制动 100 码）/ vcu（电控 50 码），含向导加载 + 覆盖概览统计 | `src/engine/three_electric.py` |
| 3 | 手写三电向导 JSON：3 子系统 × 4 症状流 × 3 选项，候选码全部命中真实码 | `data/seed/three_electric_guide.json` |
| 4 | 三电诊断 UI：独立 Tab + 子系统切换 + 每页概览/向导/内嵌 ResultPanel 多码诊断 + 导出 | `src/ui/three_electric_panel.py`, `src/ui/main_window.py` |
| 5 | AI 专家重构为三电体系：battery/motor/vcu/general，EV-THERMAL→电池域，EV-VCU→电控域 | `data/seed/expert_context.json`, `src/ai/agent.py`, `src/ai/prompt_templates.py`, `src/ai/diagnostic_tools.py` |
| 6 | 数据/专家路由测试同步，新增三电引擎/向导/UI 测试 | `tests/test_ev_codes.py`, `tests/test_ai.py`, `tests/test_diagnostic_tools.py`, `tests/test_three_electric.py`, `tests/test_ui_three_electric.py` |

### v3.4.4 — EV 码扩充至 350（2026-08-07）

| # | 修复/新增项 | 文件 |
|---|------|------|
| 1 | EV 系统码 146 → 350（每系统 50，7 系统），故障码总数 8875→9079 | `data/seed/ev_system_codes.csv`, `scripts/generate_ev_system_codes.py` |
| 2 | 新增确定性详情生成脚本（纯模板，取代卡死的 Ollama 批量增强）：为新增 204 条 EV 码回填 `detail/common_causes/diagnostic_steps/symptoms`，已存在 AI 详情保留不动 | `scripts/synthesize_ev_details.py` |
| 3 | `generate_ev_system_codes.py` 新增 `--merge`（幂等追加新码）/ `--sync-db`（DB 详情回写 CSV）模式 | `scripts/generate_ev_system_codes.py` |
| 4 | 更新 EV 码测试：每系统 ≥20 → ≥50，新增 `test_total_codes_ge_300` | `test_ev_codes.py` |

### v3.4.3 — EV 码知识库扩充（2026-08-05）

| # | 修复/新增项 | 文件 |
|---|------|------|
| 1 | 新增 146 条 EV 系统码（BMS 22 / MOTOR 22 / OBC 22 / DC-DC 20 / THERMAL 20 / HV 20 / REGEN 20），全部 AI 增强含中文详情，故障码总数 8729→8875 | `data/seed/ev_system_codes.csv`, `scripts/generate_ev_system_codes.py` |
| 2 | `parse_fault_codes` 支持 `EV-XXX-NNN` 格式输入解析（与历史导出拆分一致），补 7 个回归测试 | `diagnostic.py`, `test_bug_fixes.py` |
| 3 | 专家路由扩充：EV-OBC/EV-DCDC → BMS 专家，EV-REGEN → 电机专家（域名 + `_select_expert`） | `expert_context.json`, `agent.py` |
| 4 | `seed_db.py` 接入 ev_system_codes.csv | `seed_db.py` |
| 5 | 修复 5 个导出/症状区/死代码 bug（多码导出崩溃、历史导出 EV 码、症状区重置、死代码）+ 16 回归测试 | `main_window.py`, `result_panel.py`, `agent_chat.py`, `test_bug_fixes.py` |
| 6 | 新增 EV 码数据完整性测试（CSV 格式/可导入/查询链路/专家路由） | `test_ev_codes.py` |

### v3.4.2 — 死代码清理 + 流式渲染修复 + CI（2026-08-04）

| # | 修复项 | 文件 |
|---|--------|------|
| 1 | 清理死代码：`diagnose_multi`/`MultiCodeResult`/`CorrelationAnalyzer`/`CorrelationResult`/`export_multi_as_text`/`export_multi_as_html`/`get_multi_code_suggestion`/`DiagnosticContext`（均无调用点） | `diagnostic.py`, `correlation.py`(删), `export_utils.py`, `llm_client.py`, `context.py`(删) |
| 2 | 流式粗体跨 token 泄漏字面 `**`（逐字符/分段到达时）→ 新增 `StreamMarkdownRenderer` 状态机，粗体内容延迟到闭合后渲染 | `markdown_renderer.py`, `agent_chat.py` |
| 3 | GitHub Actions CI（Python 3.10/3.11/3.12 + pytest + 覆盖率门限 30%） | `.github/workflows/ci.yml` |
| 4 | 数据覆盖 98.2% → 100%（8729 条全部有详情） | 文档同步 |
| 5 | 补 ReAct 主循环测试（直接回答/工具循环/Ollama 剥离/OpenAI 保留/去重/超限/降级） | `test_ai.py` |
| 6 | 更新打包 spec：移除已删模块 hiddenimports、exe 名 → v3.4.2 | `EV-Diag-Tool.spec` |
| 7 | 测试总数 151 → 477（新增流式 provider 测试、verify_features 流式端到端、PDF 导出测试、UI 测试） | `test_export_and_markdown.py`, `test_ai.py`, `test_providers.py`, `verify_features.py`, `test_ui_*.py` |
| 8 | PDF 诊断报告导出（reportlab，中文字体自动回退），UI 导出对话框新增 PDF 选项 | `export_utils.py`, `main_window.py`, `EV-Diag-Tool.spec` |

### v3.4.2 — 安全与健壮性修复（2026-08-04）

| # | 严重度 | 修复项 | 文件 |
|---|--------|--------|------|
| 1 | 🔴 CRITICAL | `parse_fault_codes` 正则丢弃 63.7% 含十六进制字母的故障码（P0A00/B001A 等），改为 `[0-9A-Fa-f]{4}` | `diagnostic.py` |
| 2 | 🔴 HIGH | 多码知识库结果 HTML 未转义（XSS 注入） | `result_panel.py` |
| 3 | 🔴 HIGH | AI 完成提示中故障码未转义（XSS 注入） | `result_panel.py` |
| 4 | 🔴 HIGH | ReAct 非流式循环缺少下一轮 LLM 调用，多轮推理失效 | `agent.py` |
| 5 | 🟠 MEDIUM | Ollama/OpenAI Tool Calling 协议不一致导致 OpenAI 端 400 | `agent.py`（`_build_tool_assistant_msg`） |
| 6 | 🟠 MEDIUM | availability 永久缓存，服务恢复后仍显示不可用（加 30s TTL） | `ollama.py`, `openai_compat.py` |
| 7 | 🟠 MEDIUM | worker 生命周期：wait 超时无 terminate、窗口关闭不停止线程 | `main_window.py`（`closeEvent`） |
| 8 | 🟠 MEDIUM | `_ensure_tables` 不创建 obd_codes 表（空库/清库时查询失败） | `db_manager.py` |
| 9 | 🟠 MEDIUM | `is_available()` 网络调用持有 provider 锁阻塞 UI | `llm_client.py` |
| 10 | 🟠 MEDIUM | Agent 预查询正则把英文单词误判为故障码（PLEASE→PLEA） | `agent.py` |
| 11 | 🟡 LOW | markdown 链接未校验协议（`javascript:` 注入） | `markdown_renderer.py` |
| 12 | 🟡 LOW | 导出严重程度拼接 class 属性未转义、格式判断仅靠扩展名 | `export_utils.py`, `main_window.py` |
| 13 | 🟡 LOW | `.env` 写入未净化、数值配置解析无容错 | `config.py` |
| 14 | 🟡 LOW | `record_symptoms` 读改写竞态、多码历史导出查询失败 | `db_manager.py`, `main_window.py` |
| 15 | 🟡 LOW | AI 流式出错界面卡在"生成中"占位 | `result_panel.py`（`show_ai_error`） |

### v3.4.1 — Bug 修复（2026-08-04）

| # | 修复项 | 文件 | 说明 |
|---|--------|------|------|
| 1 | model_name setter 去重 | `ollama.py`, `openai_compat.py` | 模型名不变时不重置 availability 缓存 |
| 2 | 多码诊断方法名修正 | `llm_client.py` | `build_multi_code_diagnostic_prompt` → `build_multi_diagnostic_prompt` |
| 3 | 多码诊断参数修正 | `llm_client.py` | `knowledge_list` → `results`，补充 `correlation_summary` |
| 4 | 模型选择器保护标志 | `main_window.py` | 防止初始化时误触发 `_on_model_changed` |

### v3.4.0 — 代码审查修复（2026-07-29）

| # | 修复项 | 文件 | 说明 |
|---|--------|------|------|
| 1 | 线程安全修复 | `llm_client.py` | `_provider_lock` 初始化移到 `__new__` |
| 2 | 提取重复逻辑 | `agent.py` | 新增 `_execute_tool_calls` 共享方法 |
| 3 | 异常处理改善 | `agent.py` | 替换 5 处 `except Exception: pass` |
| 4 | HTML 转义统一 | `result_panel.py` | 统一转义逻辑 |
| 5 | DiagnosticContext | `context.py` | 新建数据类封装参数 |
| 6 | 方法重命名 | `agent.py` | `_prefetch_tools` → `_prefetch_knowledge_for_message` |

### v3.4.0 — 多故障码分析（2026-07-28）

- 新增 `correlation.py` 故障码关联性分析
- 修复 EV 系统码关联判断过宽
- 修复多码 AI 流式显示清空问题

### v3.1.0 — 全链路流式 Tool Calling（2026-07-27）

- 新增 `StreamEvent` 数据类
- Ollama/OpenAI 流式 Tool Calling 实现
- Agent `run_stream` 方法

### v3.0.0 — 阶段三：AI Agent 版

- 新增 `tools.py` 工具调用框架 + `diagnostic_tools.py` 9 个诊断工具
- ReAct 模式 Agent 循环
- 症状关键词映射增强搜索