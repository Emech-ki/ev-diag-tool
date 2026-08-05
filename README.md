# EV-Diag-Tool | 新能源汽车智能诊断工具

> **"不武断下结论，而是帮你一步步排查"**

一个面向维修技师的 **OBD-II 智能故障码诊断工具**，结合本地知识库 + AI 大模型，帮助快速定位新能源汽车故障点。

---

## 项目状态

| 指标 | 数值 |
|------|------|
| **版本** | v3.4.3 |
| **测试** | 493 个全部通过 |
| **覆盖率** | 75%（逻辑层 85%+） |
| **故障码** | 8729 条（100% 中文） |
| **详细信息覆盖** | 100%（8729 条） |
| **车型数据** | 45 款 / 18 品牌 |

---

## 项目定位

| 项目维度 | 决策内容 |
|---------|---------|
| **目标用户** | 新能源汽车维修技师 |
| **解决问题** | 通过 OBD-II 故障码快速定位故障原因，给出排查步骤 |
| **核心原则** | 知识库信息是确定的，AI 建议是辅助参考，两者明确区分 |
| **发布方式** | Windows exe + GitHub 开源 |
| **交付形态** | PyQt6 桌面应用 |

### 核心理念

> 就像一位经验丰富的维修老师傅：
> 1. 你先告诉我故障码（症状）
> 2. 我查手册告诉你标准答案（知识库）
> 3. 我再结合经验给你一些排查建议（AI 辅助）
> 4. 但我不会直接说"换某某零件"——而是告诉你"先检查这个，再测试那个"

---

## 快速开始

### 前置条件

```bash
# 1. 安装 Python 3.10+
#    下载: https://www.python.org/downloads/

# 2. 安装 Ollama
#    下载: https://ollama.com/
#    拉取推荐模型:
ollama pull qwen2.5:7b

# 3. 验证 Ollama 可用:
ollama run qwen2.5:7b
# 输入: "你好" 测试是否正常工作
```

### 安装与运行

```bash
# 1. 克隆项目
git clone https://github.com/Emech-ki/ev-diag-tool.git
cd ev-diag-tool

# 2. 创建虚拟环境
python -m venv venv
# Windows:
.\venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 初始化数据库（导入种子数据）
python scripts/seed_db.py

# 5. 运行程序
python src/main.py
```

### 常用命令

```bash
python scripts/seed_db.py    # 初始化数据库（含新能源码+车型数据）
python src/main.py           # 运行程序
pytest tests/                # 运行测试（493个测试）
```

### 打包成 exe

```bash
pip install pyinstaller
pyinstaller EV-Diag-Tool.spec --noconfirm
# 生成的 exe 在 dist/ 目录下（名称含版本号，如 EV-Diag-Tool_v3.4.2.exe）
# 打包前请修改 EV-Diag-Tool.spec 中的 name 字段为当前版本
```

---

## 技术栈

| 技术 | 用途 | 备注 |
|-----|------|------|
| **Python 3.10+** | 编程语言 | 主流版本 |
| **PyQt6** | 桌面 GUI | 功能强大，原生质感 |
| **SQLite** | 本地数据库 | 零配置，单文件 |
| **Ollama** | 本地大模型推理 | 免费，隐私保障 |
| **qwen2.5:7b / llama3.2:3b** | LLM 模型 | 推荐模型，3060可跑 |
| **PyInstaller** | 打包 exe | 最终分发 |

### 开发环境

| 硬件 | 配置 |
|-----|------|
| CPU | AMD Ryzen 5 5800H (8C/16T) |
| GPU | NVIDIA RTX 3060 (6GB VRAM) |
| RAM | 16GB |
| OS | Windows 11 |

---

## 系统架构（三层）

```
┌─────────────────────────────────────────────┐
│            用户界面层 (PyQt6)                 │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ 故障码输入 │  │ 诊断结果显示│  │ AI对话面板│  │
│  └─────┬────┘  └─────┬────┘  └─────┬─────┘  │
├────────┼──────────────┼──────────────┼──────┤
│        ▼              ▼              ▼       │
│           业务逻辑层                          │
│  ┌────────────────┐  ┌──────────────────┐   │
│  │  诊断引擎       │  │  AI 服务层       │   │
│  │  (知识库查询 +  │  │  (方案B LLM增强  │   │
│  │   推理排序)     │  │  + 方案C Agent)  │   │
│  └────────┬───────┘  └────────┬─────────┘   │
├───────────┼───────────────────┼────────────┤
│           ▼                   ▼              │
│             数据层                            │
│  ┌──────────────────┐  ┌───────────────┐    │
│  │  SQLite 本地数据库 │  │  Ollama 本地   │    │
│  │  (OBD故障码知识库) │  │  大模型       │    │
│  └──────────────────┘  └───────────────┘    │
└──────────────────────────────────────────────┘
```

---

## AI 架构

### Provider 抽象层

- **Provider 接口**: `src/ai/providers/__init__.py` — `LLMProvider` 抽象基类
- **OllamaProvider**: `src/ai/providers/ollama.py` — Ollama HTTP API（支持 tool calling）
- **OpenAICompatProvider**: `src/ai/providers/openai_compat.py` — OpenAI 兼容 API
- **LLMClient 代理**: `src/ai/llm_client.py` — 根据配置选择 provider，`threading.Lock` 保护切换

### 多端点配置

`.env` 中配置 `OPENAI_ENDPOINT_1_NAME/URL/KEY/MODEL`，支持多个端点。品牌栏下拉框"本地模型 / DeepSeek / OpenAI"一键切换。

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
- 专家角色声明（BMS/电机/热管理专家路由）

---

## 功能特性

| 功能 | 说明 |
|------|------|
| **故障码查询** | 支持 P/B/C/U 系列 8729 条故障码 |
| **AI 诊断建议** | 支持 Ollama 本地模型 + OpenAI 兼容 API |
| **AI Agent 对话** | 流式 Tool Calling，对话式排查引导 |
| **多 Agent 协作** | 专家路由系统（BMS/电机/热管理/通用） |
| **多故障码分析** | 自动识别多个故障码，综合分析因果关系 |
| **深色模式** | 主题切换，持久化到 .env |
| **诊断结果导出** | 支持 txt/html/pdf 格式（PDF 用 reportlab） |
| **诊断历史** | 记录历史诊断，支持搜索和导出 |
| **批量数据增强** | AI 批量生成故障码详细诊断信息 |

---

## OBD-II 故障码结构说明

```
     P    0     300
     │    │     └── 具体故障编号
     │    └── 0=通用故障码, 1=厂商自定义
     └── 系统类别:
         P = Powertrain (动力总成/发动机)
         B = Body (车身)
         C = Chassis (底盘)
         U = Network (网络通讯)
```

### 当前覆盖的故障码范围

| 类别 | 数量 | 说明 |
|-----|------|------|
| P-codes (动力总成) | 6553 | 标准英文 + 中文详细 |
| U-codes (网络通讯) | 1231 | 标准英文 + 中文详细 |
| C-codes (底盘) | 525 | 标准英文 + 中文详细 |
| B-codes (车身) | 360 | 标准英文 + 中文详细 |
| EV-codes (新能源) | 60 | 中文详细 |
| **合计** | **8729** | 100% 有详细诊断信息 |

---

## 项目目录结构

```
ev-diag-tool/
├── README.md                 # 项目文档（本文件）
├── requirements.txt          # Python 依赖清单
├── .env.example             # 环境变量模板
│
├── data/                     # 数据文件
│   ├── seed/                 # 种子数据
│   │   ├── p_codes.csv       # P系列故障码（动力总成）
│   │   ├── b_codes.csv       # B系列故障码（车身）
│   │   ├── c_codes.csv       # C系列故障码（底盘）
│   │   ├── u_codes.csv       # U系列故障码（网络通讯）
│   │   └── ev_codes.csv      # 新能源专用故障码
│   └── obd_codes.db          # SQLite数据库（运行时生成）
│
├── src/                      # 源代码
│   ├── main.py               # 程序入口
│   ├── config.py             # 配置管理
│   ├── version.py            # 版本信息
│   ├── ui/                   # 界面层
│   │   ├── main_window.py    # 主窗口
│   │   ├── result_panel.py   # 结果展示面板
│   │   ├── agent_chat.py     # AI Agent对话面板
│   │   ├── history_panel.py  # 诊断历史面板
│   │   ├── export_utils.py   # 诊断结果导出（txt/html/pdf）
│   │   ├── markdown_renderer.py # Markdown渲染器
│   │   ├── theme_helper.py   # 主题辅助模块
│   │   ├── styles/           # 设计令牌（深色/浅色主题）
│   │   └── add_endpoint_dialog.py # 添加端点对话框
│   ├── database/             # 数据库层
│   │   ├── db_manager.py     # 数据库管理
│   │   └── schema.py         # 表结构定义
│   ├── engine/               # 诊断引擎
│   │   ├── diagnostic.py     # 诊断流程控制
│   │   └── knowledge_base.py # 知识库查询
│   └── ai/                   # AI服务层
│       ├── llm_client.py     # LLM API客户端
│       ├── prompt_templates.py # 提示词模板
│       ├── agent.py          # AI Agent实现
│       ├── tools.py          # 工具调用框架
│       ├── diagnostic_tools.py # 诊断工具集
│       └── providers/        # LLM Provider抽象层
│
├── scripts/                  # 工具脚本
│   ├── seed_db.py            # 数据库初始化
│   ├── batch_enhance_codes.py # 批量增强脚本
│   └── ...
│
└── tests/                    # 单元测试（477个）
    ├── test_database.py
    ├── test_engine.py
    ├── test_ai.py
    ├── test_providers.py
    └── test_export_and_markdown.py
```

---

## 代码规范

- 中文注释和文档
- 线程安全：UI 更新必须在主线程，耗时操作用 QThread
- HTML 转义：所有用户/知识库数据插入 HTML 前必须 `html.escape()`
- 流式渲染：token 级 HTML 处理需考虑跨 token 边界的 markdown 标记
- Provider 切换：必须持有 `threading.Lock` 保护 `_provider` 赋值
- Worker 生命周期：`quit()` + `wait()` 超时后必须 `terminate()`

---

## 版本历史

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

---

## 贡献指南

欢迎贡献！

**你可以这样贡献：**
- 提交 Issue 报告 bug
- 补充新的故障码数据
- 改进诊断逻辑
- 增加多语言支持

---

## 开源协议

本项目采用 MIT 协议。

---

## 致谢

- OBD-II 标准参考自 SAE J2012
- 数据整理参考自多个公开维修资料
- 感谢所有开源贡献者

---

> **最后的话：** 这个项目始于一个简单的想法——让 AI 辅助维修技师，而不是取代他们。技术应该赋能人，而不是替代人。
