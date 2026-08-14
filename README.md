# EV-Diag-Tool | 新能源汽车智能诊断工具

面向维修技师的 **OBD-II 智能故障码诊断工具**：本地知识库给"标准答案"，AI 给"排查建议"，两者明确区分，帮助快速定位新能源汽车故障点。

---

## 功能特性

| 功能 | 说明 |
|------|------|
| **故障码查询** | 支持 P/B/C/U 系列 + EV 系统码，共 9129 条 |
| **AI 诊断建议** | 支持 Ollama 本地模型 + OpenAI 兼容 API |
| **AI Agent 对话** | 流式 Tool Calling，对话式排查引导 |
| **专家路由** | 电池/电机/电控/通用 多 Agent 协作 |
| **多故障码分析** | 自动识别多个故障码，综合分析 |
| **三电诊断** | 电池/电机/电控领域向导 + 系统覆盖概览 |
| **深色模式** | 主题切换，持久化到 .env |
| **诊断结果导出** | txt / html / pdf |
| **诊断历史** | 记录、搜索、导出历史诊断 |

## 项目状态

| 指标 | 数值 |
|------|------|
| 版本 | v3.6.1 |
| 测试 | 620 个全部通过 |
| 故障码 | 9129 条（100% 中文），EV 系统码 400 条 100% 有详情 |
| 车型数据 | 45 款 / 18 品牌 |

---

## 快速开始

### 前置条件

- Python 3.10+
- [Ollama](https://ollama.com/)，并拉取推荐模型：

```bash
ollama pull qwen2.5:7b
```

### 安装与运行

```bash
git clone https://github.com/Emech-ki/ev-diag-tool.git
cd ev-diag-tool

python -m venv venv
# Windows: .\venv\Scripts\activate

pip install -r requirements.txt
python scripts/seed_db.py   # 初始化数据库
python src/main.py          # 运行程序
```

### 常用命令

```bash
python scripts/seed_db.py    # 初始化数据库
python src/main.py           # 运行程序
pytest tests/                # 运行测试（620 个）
```

### 打包成 exe

```bash
pip install pyinstaller
pyinstaller EV-Diag-Tool.spec --noconfirm
```

生成的 exe 在 `dist/` 目录下。打包前请把 `EV-Diag-Tool.spec` 中的 `name` 改为当前版本号。

## 配置说明

程序读取根目录 `.env`（参考 `.env.example`）：

- **服务商**：`AI_PROVIDER=ollama|openai`
- **本地模型**：`OLLAMA_BASE_URL`、`OLLAMA_MODEL_NAME`
- **多端点**：`OPENAI_ENDPOINT_1_NAME/URL/KEY/MODEL`，可配置多个端点，品牌栏一键切换
- **主题**：`THEME=light|dark`（界面内切换会持久化到 .env）

---

## 技术栈

| 技术 | 用途 |
|-----|------|
| Python 3.10+ | 编程语言 |
| PyQt6 | 桌面 GUI |
| SQLite | 本地数据库（零配置、单文件） |
| Ollama | 本地大模型推理 |
| PyInstaller | 打包 exe |

## OBD-II 故障码结构

```
P 0 300
│ │ └── 具体故障编号
│ └── 0=通用故障码, 1=厂商自定义
└── 系统类别: P=动力总成 B=车身 C=底盘 U=网络通讯
```

另支持新能源系统码 `EV-XXX-NNN`（如 `EV-BMS-001`）。当前覆盖：P 6553 / U 1231 / C 525 / B 360 / EV 60 / EV 系统码 400。

---

## 项目目录结构

```
ev-diag-tool/
├── README.md             # 项目文档
├── CONTRIBUTING.md       # 贡献指南与代码规范
├── CHANGELOG.md          # 版本历史
├── requirements.txt
├── .env.example          # 环境变量模板
├── data/seed/            # 种子数据（CSV + 三电向导 JSON）
├── src/
│   ├── main.py           # 程序入口
│   ├── ui/               # PyQt6 界面层
│   ├── database/         # SQLite 数据层
│   ├── engine/           # 诊断引擎（含三电领域）
│   └── ai/               # AI 服务层（Provider/Agent/工具）
├── scripts/              # 工具脚本（建库、增强、验证）
└── tests/                # 单元测试
```

---

## 贡献

欢迎提交 Issue、补充故障码数据、改进诊断逻辑。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 更新日志

各版本变更详见 [CHANGELOG.md](CHANGELOG.md)。

## 开源协议

本项目采用 MIT 协议。