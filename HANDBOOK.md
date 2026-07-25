# Handoff Document — EV-Diag-Tool

**Date:** 2026-07-25
**Project:** `D:\桌面\诊断ai程序\ev-diag-tool`
**Repo:** https://github.com/Emech-ki/ev-diag-tool.git
**Version:** v2.1.0 + 第三方模型 UI 管理
**Tests:** 76 passed

---

## 本次会话完成的工作

### 阶段二：AI 增强版（v2.0.0）

#### 1. 配置外置化
- `src/config.py` + `.env.example` 新增 AI_PROVIDER、OPENAI_*、AI_TEMPERATURE 等配置项
- 支持多 OpenAI 兼容 API 端点（索引格式 `OPENAI_ENDPOINT_1_NAME/URL/KEY/MODEL`）

#### 2. LLM 抽象层重构
- **新建** `src/ai/providers/__init__.py` — `LLMProvider` 抽象基类
- **新建** `src/ai/providers/ollama.py` — `OllamaProvider`
- **新建** `src/ai/providers/openai_compat.py` — `OpenAICompatProvider`
- **重构** `src/ai/llm_client.py` — 改为代理层，`threading.Lock` 保护 `_provider` 切换

#### 3. Prompt 优化
- few-shot 示例（P0300 缺火诊断推理过程）
- CoT 推理链引导
- 严重程度自适应（critical/high 自动增加高压安全警告）
- 新能源安全提醒（绝缘手套、高压维修开关等）

#### 4. 新能源故障码
- **新建** `data/seed/ev_codes.csv` — 45 条 EV 专属码（BMS/电机/OBC/DC-DC/热管理/高压/再生制动/充电/网络通信）

#### 5. 车型数据库
- **新建** `data/seed/vehicle_models.csv` — 30 款主流新能源车型
- `src/database/schema.py` 新增 `vehicle_models` 表（含 `UNIQUE(make, model)` 约束）
- `src/database/db_manager.py` 新增 `execute_query()` + 自动迁移
- `src/engine/knowledge_base.py` 新增车型查询方法

#### 6. UI 适配
- 品牌栏新增 Provider 选择器（"本地模型" / 远程端点名）
- 模型选择器随 provider 动态刷新
- 车型输入改为品牌→车型两级联动 `QComboBox`

### 本地/调用模型切换（v2.1.0）

- 品牌栏下拉框：`[ 本地模型 ▼ ]  [ qwen2.5:7b ▼ ]`
- 切换到远程后：`[ DeepSeek ▼ ]  [ deepseek-chat ▼ ]`
- 异步检查 AI 可用性（`_AICheckWorker`），不阻塞 UI
- 检查结果带 `_check_target` 标记，不覆盖用户已切换的 provider

### Code Review 修复（10 项）

1. `result_panel.py:383,480,503` — `result.code` 加 `html.escape()` 防 XSS
2. `llm_client.py:52` — 单例恢复 `threading.Lock()` 防竞态
3. `main_window.py:406` — `_update_remote_status` 改为异步 `_do_check_ai_async`
4. `main_window.py:436` — 检查结果不覆盖已切换的 provider
5. `llm_client.py:100` — `switch_provider()` 设置 `_endpoint_name`
6. `config.py:67` — 删除未使用的 `seen_names`
7. `schema.py:42` — `vehicle_models` 加 `UNIQUE(make, model)` 约束
8. `prompt_templates.py:113` — `.format()` 改为 f-string
9. `seed_db.py:165` — `int()` 加 `_safe_int()` 容错
10. `main_window.py:426` — `_refresh_model_list` 异常显示状态栏消息

### Debug 修复（9 项）

1. `main_window.py` — Worker 超时后 `terminate()` 强制终止
2. `main_window.py` — 相关码点击后恢复按钮状态
3. `main_window.py` — 停止旧的 `_AICheckWorker` 再创建新的
4. `llm_client.py` — `_provider` 切换全部加 `threading.Lock`
5. `llm_client.py` — 防止重复插入系统提示词
6. `ollama.py` + `openai_compat.py` — `range(max(AI_MAX_RETRIES, 0) + 1)` 防负值
7. `openai_compat.py` — SSE 用 `raw_buffer` 累积字节再解码
8. `seed_db.py` — `_open_csv` 关闭前一个文件句柄
9. `seed_db.py` — `_safe_int` 移到循环外

### 第三方模型 UI 管理（v2.1.0+）

#### 1. 添加远程端点 UI
- **新建** `src/ui/add_endpoint_dialog.py` — `AddEndpointDialog(QDialog)`，字段：显示名称、API 地址、API Key（明文）、模型名称，全部必填
- **新增** `src/config.py` — `get_next_endpoint_index()` + `append_endpoint_to_env()`，写入 .env 后 `load_dotenv(override=True)` 刷新

#### 2. 删除远程端点 UI
- **新增** `src/config.py` — `remove_endpoint_from_env(endpoint_name)`，正则匹配删除 4 行，清 `os.environ`
- **新建** `_RightClickComboBox(QComboBox)` — 重写 `showPopup()` 在 `view().viewport()` 安装事件过滤器
- **新建** `_ViewRightClickFilter(QObject)` — 拦截 viewport 右键事件，发射 `right_clicked` 信号
- Provider 下拉框右键远程端点 → QMenu "删除" → 确认框 → 删除 + 切回本地模型

#### 3. Bug 修复（4 项）
1. **添加模型取消后重复弹框** — `blockSignals` 不嵌套，`_init_provider_selector` 内部 `blockSignals(False)` 覆盖外层。改用 `was_blocked = signalsBlocked()` 恢复机制
2. **右键删除不生效** — QComboBox 弹出框是独立顶层窗口，事件过滤器装在 `view()` 上无效。改用 `_RightClickComboBox` 子类 + `view().viewport()` 安装
3. **删除端点后模型选择器未刷新** — `_delete_endpoint` 缺少 `switch_to_local()` + `_refresh_model_list()`
4. **添加后新端点未自动选中** — 索引 `new_count - 2` 指向分隔线，应为 `new_count - 3`

#### 4. DeepSeek API 适配
- `openai_compat.py` — URL 自动补全 `/v1` 后缀
- `openai_compat.py` + `ollama.py` — `_check_availability` 模型名比较改为 `.lower()` 大小写不敏感
- `.env` — 模型名修正为全小写 `deepseek-v4-flash`

---

## 当前项目状态

- **版本：** v2.1.0 + 第三方模型 UI 管理
- **阶段：** 阶段二（AI增强版）完成 + 多端点切换 + 2 轮 code review 修复 + 第三方模型 UI 管理
- **功能：** 故障码查询(含EV码)、知识库展示、AI 诊断建议(few-shot/CoT/流式)、AI 对话、诊断历史、相关码跳转、多 Provider 支持(Ollama+多OpenAI端点)、**UI 添加/删除远程端点**、车型数据库(30款)、品牌车型联动
- **测试：** 76 个全部通过
- **已修复问题：** 23 项（10 code review + 9 debug + 4 第三方模型 UI）

---

## 建议的下一步工作

1. **编辑端点功能** — 右键菜单增加"编辑"选项，修改已有端点的 URL/Key/Model
2. **阶段三：AI Agent 版** — MCP/A2A 架构，工具调用，多 Agent 协作
3. **打包 exe** — PyInstaller 打包、`scripts/build_exe.py` 完善
4. **数据扩充** — 更多新能源故障码、更多车型数据
5. **UI 优化** — Markdown 渲染增强（当前只支持加粗）、诊断结果导出

---

## 敏感信息说明

- `.env` 文件已通过 `.gitignore` 排除
- Ollama 默认配置：`http://localhost:11434`，模型 `qwen2.5:7b`
- OpenAI API Key 未配置（需用户自行填写 `.env`）
