# EV-Diag-Tool | 新能源汽车智能诊断工具

> **"不武断下结论，而是帮你一步步排查"**

一个面向维修技师的 **OBD-II 智能故障码诊断工具**，结合本地知识库 + AI 大模型，帮助快速定位新能源汽车故障点。

---

## 📋 项目记忆 | Project Memory

> 本文档记录了项目的所有重要决策和设计思路，相当于项目的"长期记忆"。

### 🎯 项目定位

| 项目维度 | 决策内容 |
|---------|---------|
| **目标用户** | 新能源汽车维修技师 |
| **解决问题** | 通过 OBD-II 故障码快速定位故障原因，给出排查步骤 |
| **核心原则** | 知识库信息是确定的，AI 建议是辅助参考，两者明确区分 |
| **发布方式** | Windows exe + GitHub 开源 |
| **交付形态** | PyQt6 桌面应用 |

### 🧠 核心理念

> 就像一位经验丰富的维修老师傅：
> 1. 你先告诉我故障码（症状）
> 2. 我查手册告诉你标准答案（知识库）
> 3. 我再结合经验给你一些排查建议（AI 辅助）
> 4. 但我不会直接说"换某某零件"——而是告诉你"先检查这个，再测试那个"

### 🏗️ 系统架构（三层）

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

### 🗺️ 四阶段开发计划

| 阶段 | 名称 | 核心功能 | 预计时间 |
|------|------|---------|---------|
| 🟢 **阶段一** | **基础查询版** | PyQt6界面 + SQLite知识库查询 + 打包exe | 2-3周 |
| 🔵 **阶段二** | **AI增强版** | 接入Ollama LLM，生成AI诊断建议 | 1-2周 |
| 🟣 **阶段三** | **AI Agent版** | MCP/A2A架构，对话式交互引导排查 | 2-3周 |
| ⚫ **阶段四** | **开源完善** | 文档、CI/CD、社区贡献 | 持续 |

### 🔧 技术栈

| 技术 | 用途 | 备注 |
|-----|------|------|
| **Python 3.10+** | 编程语言 | 主流版本 |
| **PyQt6** | 桌面 GUI | 功能强大，原生质感 |
| **SQLite (aiosqlite)** | 本地数据库 | 零配置，单文件 |
| **Ollama** | 本地大模型推理 | 免费，隐私保障 |
| **qwen2.5:7b / llama3.2:3b** | LLM 模型 | 推荐模型，3060可跑 |
| **PyInstaller** | 打包 exe | 最终分发 |

### 💻 开发环境

| 硬件 | 配置 |
|-----|------|
| CPU | AMD Ryzen 5 5800H (8C/16T) |
| GPU | NVIDIA RTX 3060 (6GB VRAM) |
| RAM | 16GB |
| OS | Windows 11 |

### 🤖 AI 方案说明

**方案B — LLM 增强诊断：**
- 输入故障码 + 车型 + 附加描述
- LLM 生成结构化的诊断建议
- 界面清晰标注"AI建议，仅供参考"

**方案C — AI Agent 交互诊断：**
- 基于 MCP (Model Context Protocol) 让 Agent 访问数据库
- 基于 A2A (Agent-to-Agent) 可扩展多 Agent 协作
- 维护诊断会话上下文，主动提问引导排查

---

## 🚀 快速开始

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
git clone https://github.com/你的用户名/ev-diag-tool.git
cd ev-diag-tool

# 2. 创建虚拟环境
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/Mac:
# source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 初始化数据库（导入种子数据）
python scripts/seed_db.py

# 5. 运行程序
python src/main.py
```

### 打包成 exe

```bash
# 安装 PyInstaller
pip install pyinstaller

# 打包
pyinstaller --onefile --windowed --icon=docs/icon.ico src/main.py

# 生成的 exe 在 dist/ 目录下
```

---

## 📁 项目目录结构

```
ev-diag-tool/
├── README.md                 # 项目文档（就是本文件）
├── requirements.txt          # Python 依赖清单
├── .env.example             # 环境变量模板
│
├── data/                     # 数据文件
│   ├── seed/                 # 种子数据
│   │   ├── p_codes.csv       # P系列故障码（动力总成）
│   │   ├── b_codes.csv       # B系列故障码（车身）
│   │   ├── c_codes.csv       # C系列故障码（底盘）
│   │   └── u_codes.csv       # U系列故障码（网络通讯）
│   └── obd_codes.db          # SQLite数据库（运行时生成）
│
├── src/                      # 源代码
│   ├── main.py               # 程序入口
│   ├── ui/                   # 界面层
│   │   ├── main_window.py    # 主窗口
│   │   ├── result_panel.py   # 结果展示面板
│   │   └── agent_chat.py     # AI Agent对话面板
│   ├── database/             # 数据库层
│   │   ├── db_manager.py     # 数据库管理
│   │   └── schema.py         # 表结构定义
│   ├── engine/               # 诊断引擎
│   │   ├── diagnostic.py     # 诊断流程控制
│   │   └── knowledge_base.py # 知识库查询
│   └── ai/                   # AI服务层
│       ├── llm_client.py     # LLM API客户端
│       ├── prompt_templates.py # 提示词模板
│       └── agent.py          # AI Agent实现
│
├── scripts/                  # 工具脚本
│   ├── seed_db.py            # 数据库初始化
│   └── build_exe.py          # 打包脚本
│
├── tests/                    # 单元测试
│   ├── test_database.py
│   ├── test_engine.py
│   └── test_ai.py
│
└── docs/                     # 文档资源
```

---

## 🧩 OBD-II 故障码结构说明

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

| 类别 | 数量 | 示例 |
|-----|------|------|
| P0xxx 发动机 | 30个 | P0300缺火, P0420催化器 |
| P1xxx 厂商自定义 | 5个 | P1A00电池组故障 |
| B0xxx 车身电器 | 5个 | B1420安全气囊 |
| C0xxx 底盘 | 5个 | C0035轮速传感器 |
| U0xxx 网络通讯 | 5个 | U0100通讯丢失 |
| **合计** | **50个** | 核心常用码 |

---

## 🤝 贡献指南

欢迎贡献！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详情。

**你可以这样贡献：**
- 🐛 提交 Issue 报告 bug
- 📝 补充新的故障码数据
- 💡 改进诊断逻辑
- 🌐 增加多语言支持

---

## 📄 开源协议

本项目采用 MIT 协议。

---

## 🙏 致谢

- OBD-II 标准参考自 SAE J2012
- 数据整理参考自多个公开维修资料
- 感谢所有开源贡献者

---

> **最后的话：** 这个项目始于一个简单的想法——让 AI 辅助维修技师，而不是取代他们。技术应该赋能人，而不是替代人。
