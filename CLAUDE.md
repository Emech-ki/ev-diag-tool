# EV-Diag-Tool

新能源汽车 OBD-II 智能故障码诊断工具，PyQt6 桌面应用。

## 项目结构

- `src/ui/` — PyQt6 界面层（主窗口、结果面板、AI 对话面板）
- `src/database/` — SQLite 数据库管理
- `src/engine/` — 诊断引擎和知识库查询
- `src/ai/` — LLM 客户端（Ollama + OpenAI 兼容 API）
- `src/ai/providers/` — LLM Provider 抽象层（OllamaProvider, OpenAICompatProvider）
- `data/seed/` — 故障码种子数据 CSV（含新能源 EV 码 + 车型数据）
- `scripts/` — 工具脚本（数据库初始化、打包）

## 技术栈

Python 3.10+ / PyQt6 / aiosqlite / Ollama (本地 LLM) / OpenAI 兼容 API

## 常用命令

```bash
python scripts/seed_db.py    # 初始化数据库（含新能源码+车型数据）
python src/main.py           # 运行程序
pytest tests/                # 运行测试（76个测试）
```

## 代码规范

- 中文注释和文档
- 线程安全：UI 更新必须在主线程，耗时操作用 QThread
- HTML 转义：所有用户/知识库数据插入 HTML 前必须 `html.escape()`
- 流式渲染：token 级 HTML 处理需考虑跨 token 边界的 markdown 标记
- Provider 切换：必须持有 `threading.Lock` 保护 `_provider` 赋值
- Worker 生命周期：`quit()` + `wait()` 超时后必须 `terminate()`

## AI 架构

- **Provider 抽象层**: `src/ai/providers/` — LLMProvider 接口 + OllamaProvider + OpenAICompatProvider
- **LLMClient 代理**: `src/ai/llm_client.py` — 根据配置选择 provider，`threading.Lock` 保护切换
- **多端点**: `.env` 中配置 `OPENAI_ENDPOINT_1_NAME/URL/KEY/MODEL`，支持多个
- **UI 切换**: 品牌栏下拉框"本地模型 / DeepSeek / OpenAI"一键切换
- **Prompt**: 支持 few-shot 示例、CoT 推理、严重程度自适应、新能源安全提醒
