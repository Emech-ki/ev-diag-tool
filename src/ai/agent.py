"""
AI Agent 模块 — 阶段三：Tool Calling 版
实现 ReAct (Reasoning + Acting) 循环：
  用户消息 → LLM 思考 → 调用工具 → 获取结果 → 继续思考 → ... → 最终回答

类比单片机的 main loop:
  while(1) {
      检查中断请求 (tool_calls)
      如果有中断 → 调用处理函数 → 返回数据给 CPU
      如果没有中断 → CPU 输出最终结果
  }
"""

import json
import logging
from typing import Optional, Dict, Any, List, Callable, Iterator

logger = logging.getLogger(__name__)

from src.engine.knowledge_base import KnowledgeBase
from src.engine.three_electric import (
    get_subsystem_for_system, get_expert_name,
    get_expert_keywords, match_keywords,
)
from src.ai.llm_client import LLMClient
from src.ai.providers import StreamEvent
from src.ai.tools import ToolRegistry
from src.ai.diagnostic_tools import register_diagnostic_tools
from src.ai.prompt_templates import PromptTemplates


# Agent 单次对话最大工具调用轮数，防止无限循环
MAX_TOOL_ROUNDS = 10


class DiagnosticAgent:
    """
    诊断 AI Agent — 带工具调用能力

    核心流程 (ReAct 模式):
    1. 用户发送消息
    2. Agent 将消息 + 工具定义发给 LLM
    3. 如果 LLM 返回 tool_calls → 执行工具 → 结果追加到消息 → 回到步骤 2
    4. 如果 LLM 返回纯文本 → 结束，返回给用户

    这就是当前 AI Agent 的核心模式：
    - OpenAI 的 Function Calling
    - Claude 的 Tool Use
    - Gemini 的 Function Calling
    全部都是这个循环。
    """

    def __init__(
        self,
        kb: Optional[KnowledgeBase] = None,
        llm: Optional[LLMClient] = None,
    ):
        self.kb = kb or KnowledgeBase()
        self.llm = llm or LLMClient()
        self.templates = PromptTemplates()

        # 初始化工具注册表，注册所有诊断工具
        self.tools = ToolRegistry()
        register_diagnostic_tools(self.tools, self.kb)

        # 会话状态
        self.session_code: Optional[str] = None
        self.session_vehicle: Optional[str] = None
        self._history: List[Dict[str, Any]] = []

    def start_diagnosis(self, code: str, vehicle_info: str = "") -> Dict[str, Any]:
        """
        开始新的诊断会话（保留旧接口兼容）

        Args:
            code: 故障码
            vehicle_info: 车型信息

        Returns:
            包含知识库信息的字典
        """
        code = code.strip().upper()
        self.session_code = code
        self.session_vehicle = vehicle_info
        self._history.clear()

        knowledge = self.kb.lookup(code)

        return {
            "code": code,
            "knowledge": knowledge,
            "session_started": True,
        }

    def run(
        self,
        user_message: str,
        on_tool_call: Optional[Callable[[str, dict], None]] = None,
        on_tool_result: Optional[Callable[[str, str], None]] = None,
    ) -> str:
        """
        Agent 主循环 — ReAct 模式

        这是整个 Agent 的核心。流程：
        ┌─────────────────────────────────────────────┐
        │  用户消息                                     │
        │      ↓                                       │
        │  LLM 思考（带工具定义）                         │
        │      ↓                                       │
        │  ┌─ 有 tool_calls? ── 是 → 执行工具 → 结果    │
        │  │                      ↓                    │
        │  │                  追加到消息历史              │
        │  │                      ↓                    │
        │  └────────────── 回到 LLM 思考                │
        │      ↓                                       │
        │  否 → 返回最终文本回答                          │
        └─────────────────────────────────────────────┘

        Args:
            user_message: 用户输入
            on_tool_call: 回调函数，工具调用时通知 UI (工具名, 参数)
            on_tool_result: 回调函数，工具返回时通知 UI (工具名, 结果摘要)

        Returns:
            Agent 的最终回答文本
        """
        # 构建消息上下文
        messages = self._build_messages(user_message)

        # 先尝试 Tool Calling 模式
        # 只有返回了真正的 tool_calls（不是文本中的 JSON）才走 ReAct 循环
        test_response = None
        try:
            test_response = self.llm.chat_with_tools(
                messages=messages[:],  # 用副本测试
                tools=self.tools.to_openai_format(),
            )
        except Exception as e:
            logger.debug(f"Tool calling not supported or failed: {e}")

        if test_response and test_response.get("tool_calls"):
            # 有真正的 tool_calls → ReAct 循环（错误由其内部处理，不在此吞掉）
            return self._run_react_loop(messages, user_message, on_tool_call, on_tool_result, test_response)

        # 没有 tool_calls，但 LLM 直接给出了最终文本回答 → 直接返回，避免浪费一次调用
        if test_response and (test_response.get("content") or "").strip():
            final_answer = test_response.get("content").strip()
            self._history.append({"role": "user", "content": user_message})
            self._history.append({"role": "assistant", "content": final_answer})
            return final_answer

        # 降级模式：预先查询数据，注入上下文，用普通 chat
        # 包括两种情况：
        # 1. chat_with_tools 抛异常（不支持 tool calling）
        # 2. chat_with_tools 返回空 content 且无 tool_calls
        return self._run_with_prefetch(user_message, on_tool_call, on_tool_result)

    def run_stream(
        self,
        user_message: str,
        on_tool_call: Optional[Callable[[str, dict], None]] = None,
        on_tool_result: Optional[Callable[[str, str], None]] = None,
    ) -> Iterator[StreamEvent]:
        """
        Agent 主循环 — 流式 ReAct 模式

        与 run() 相同的逻辑，但返回 StreamEvent 流而不是最终字符串。
        UI 可以逐 token 显示 LLM 的思考和回答过程。

        Yields:
            StreamEvent: content token / tool_calls / done
        """
        messages = self._build_messages(user_message)

        # 先尝试流式 Tool Calling
        try:
            # 用流式方式发送第一轮，检测是否有 tool_calls
            first_content = ""
            first_tool_calls = None

            for event in self.llm.chat_with_tools_stream(
                messages[:], self.tools.to_openai_format()
            ):
                if event.type == "content":
                    first_content += event.content
                    yield event
                elif event.type == "tool_calls":
                    first_tool_calls = event.tool_calls
                    # 不 yield tool_calls 给 UI（由 Agent 自己处理）
                elif event.type == "done":
                    break

            if first_tool_calls:
                # 有 tool_calls → 进入流式 ReAct 循环
                # 先把已收到的 content 作为 assistant 消息
                yield from self._run_react_loop_stream(
                    messages, user_message, on_tool_call, on_tool_result,
                    first_content, first_tool_calls,
                )
                return
            else:
                # 没有 tool_calls → 已经是最终回答（content 已经 yield 过了）
                self._history.append({"role": "user", "content": user_message})
                self._history.append({"role": "assistant", "content": first_content})
                yield StreamEvent("done")
                return

        except Exception as e:
            # 流式调用失败 — 如果已经 yield 了部分 content 给 UI，
            # 不能再走 fallback（否则 UI 会显示"部分内容 + 完整回复"的拼接）。
            # 只有在没有 yield 过任何 content 时才降级。
            if not first_content:
                try:
                    result = self._run_with_prefetch(user_message, on_tool_call, on_tool_result)
                    yield StreamEvent("content", content=result)
                    yield StreamEvent("done")
                except Exception as e:
                    logger.warning(f"Fallback chat failed: {e}")
                    yield StreamEvent("content", content=f"⚠️ AI 调用失败: {e}")
                    yield StreamEvent("done")
            else:
                # 已经 yield 了部分内容，无法回退 — 报错结束
                yield StreamEvent("content", content=f"\n\n⚠️ 流式中断: {e}")
                yield StreamEvent("done")
            return

    def _build_tool_assistant_msg(self, content: str, tool_calls: list) -> dict:
        """
        构建携带工具调用的 assistant 消息。

        Ollama 不支持消息历史中的 tool_calls 字段（会返回 400），因此剥离；
        OpenAI 兼容 API 要求 assistant 消息携带 tool_calls 才能承接 role="tool" 结果。
        """
        if not tool_calls:
            return {"role": "assistant", "content": content or ""}
        try:
            is_local = self.llm.is_local
        except Exception:
            is_local = False
        if is_local:
            return {"role": "assistant", "content": content or ""}
        return {
            "role": "assistant",
            "content": content or "",
            "tool_calls": [
                {
                    "id": tc.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": tc.get("function", {}).get("name", ""),
                        "arguments": tc.get("function", {}).get("arguments", "{}"),
                    },
                }
                for tc in tool_calls
            ],
        }

    def _execute_tool_calls(
        self,
        tool_calls: list,
        messages: list,
        called_tools: set,
        on_tool_call: Optional[Callable] = None,
        on_tool_result: Optional[Callable] = None,
    ) -> bool:
        """
        执行工具调用列表，返回是否有新调用

        Args:
            tool_calls: LLM 返回的工具调用列表
            messages: 消息历史（会追加工具结果）
            called_tools: 已调用工具的去重集合（会更新）
            on_tool_call: 工具调用回调
            on_tool_result: 工具结果回调

        Returns:
            是否有新的工具调用（非重复）
        """
        any_new_call = False
        for tc in tool_calls:
            tc_id = tc.get("id", "")
            func = tc.get("function", {})
            tool_name = func.get("name", "")
            tool_args_str = func.get("arguments", "{}")

            # 解析参数
            try:
                tool_args = json.loads(tool_args_str) if isinstance(tool_args_str, str) else tool_args_str
            except json.JSONDecodeError:
                tool_args = {}

            # 去重检查：防止 LLM 重复调用同一个工具
            call_key = f"{tool_name}:{json.dumps(tool_args, sort_keys=True, default=str)}"
            if call_key in called_tools:
                # 已经调用过了，注入提示让 LLM 给出最终回答
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": json.dumps({
                        "notice": f"你已经调用过 {tool_name}，结果在上面。请基于已有数据给出最终诊断分析，不要再调用工具。",
                    }, ensure_ascii=False),
                })
                continue

            called_tools.add(call_key)
            any_new_call = True

            # 通知 UI：正在调用工具
            if on_tool_call:
                on_tool_call(tool_name, tool_args)

            # 执行工具
            result_str = self.tools.execute(tool_name, tool_args)

            # 通知 UI：工具返回结果
            if on_tool_result:
                summary = result_str[:200] + "..." if len(result_str) > 200 else result_str
                on_tool_result(tool_name, summary)

            # 把工具结果追加到消息（tool role）
            messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": result_str,
            })

        return any_new_call

    def _run_react_loop(
        self,
        messages: list,
        user_message: str,
        on_tool_call: Optional[Callable],
        on_tool_result: Optional[Callable],
        first_response: dict,
    ) -> str:
        """
        ReAct 循环（Tool Calling 可用时的完整模式）
        """
        response = first_response
        called_tools = set()  # 记录已调用的 (name, args_key)，防止重复调用

        for round_num in range(MAX_TOOL_ROUNDS):

            content = response.get("content")
            tool_calls = response.get("tool_calls")

            # 2. 如果没有工具调用 → LLM 给出最终回答 → 结束
            if not tool_calls:
                final_answer = content or ""
                # 记录到历史
                self._history.append({"role": "user", "content": user_message})
                self._history.append({"role": "assistant", "content": final_answer})
                return final_answer

            # 3. LLM 想调用工具 → 执行工具
            # 注意：Ollama 不支持消息历史中的 tool_calls 字段（会返回 400），
            # 因此 Ollama 剥离 tool_calls，只保留 assistant 文本 + tool 结果；
            # OpenAI 兼容 API 则必须携带 tool_calls 才能承接 role="tool" 消息。
            messages.append(self._build_tool_assistant_msg(content, tool_calls))

            # 4. 使用共享方法执行工具
            any_new_call = self._execute_tool_calls(
                tool_calls, messages, called_tools, on_tool_call, on_tool_result
            )

            # 如果本轮所有工具都是重复的，强制让 LLM 给出最终回答
            if not any_new_call:
                break

            # 5. 下一轮：重新调用 LLM，让它基于工具结果继续推理
            try:
                response = self.llm.chat_with_tools(
                    messages, self.tools.to_openai_format()
                )
            except Exception as e:
                logger.warning(f"Next round chat_with_tools failed: {e}")
                break

        # 如果循环次数用尽，用普通 chat 做总结（不再调用工具）
        summary_prompt = "请基于以上所有工具查询的结果，给出最终的诊断分析和建议。"
        try:
            answer = self.llm.chat(message=summary_prompt, context=messages)
        except Exception as e:
            logger.warning(f"Summary generation failed: {e}")
            answer = "⚠️ 诊断轮次过多，请基于当前信息手动分析。"
        self._history.append({"role": "user", "content": user_message})
        self._history.append({"role": "assistant", "content": answer})
        return answer

    def _run_react_loop_stream(
        self,
        messages: list,
        user_message: str,
        on_tool_call: Optional[Callable],
        on_tool_result: Optional[Callable],
        first_content: str,
        first_tool_calls: list,
    ) -> Iterator[StreamEvent]:
        """
        流式 ReAct 循环

        与 _run_react_loop 相同的逻辑，但：
        - 每一轮 LLM 调用使用流式（逐 token yield）
        - 工具执行结果通过 on_tool_call/on_tool_result 回调通知 UI
        - 最终回答也通过流式 yield
        """
        content = first_content
        tool_calls = first_tool_calls
        called_tools = set()

        for round_num in range(MAX_TOOL_ROUNDS):
            if not tool_calls:
                # 没有工具调用 → 最终回答（content 已经 yield 过了）
                final_answer = content
                self._history.append({"role": "user", "content": user_message})
                self._history.append({"role": "assistant", "content": final_answer})
                yield StreamEvent("done")
                return

            # 有工具调用 → 执行工具
            messages.append(self._build_tool_assistant_msg(content, tool_calls))

            # 使用共享方法执行工具
            any_new_call = self._execute_tool_calls(
                tool_calls, messages, called_tools, on_tool_call, on_tool_result
            )

            if not any_new_call:
                break

            # 下一轮：流式调用 LLM
            content = ""
            tool_calls = None

            for event in self.llm.chat_with_tools_stream(
                messages, self.tools.to_openai_format()
            ):
                if event.type == "content":
                    content += event.content
                    yield event  # 逐 token 转发给 UI
                elif event.type == "tool_calls":
                    tool_calls = event.tool_calls
                elif event.type == "done":
                    break

        # 循环次数用尽
        if tool_calls:
            # 还有未处理的 tool_calls → 用普通 chat 做总结
            summary_prompt = "请基于以上所有工具查询的结果，给出最终的诊断分析和建议。"
            try:
                answer = self.llm.chat(message=summary_prompt, context=messages)
            except Exception as e:
                logger.warning(f"Summary generation failed: {e}")
                answer = "⚠️ 诊断轮次过多，请基于当前信息手动分析。"
            yield StreamEvent("content", content=answer)
            self._history.append({"role": "user", "content": user_message})
            self._history.append({"role": "assistant", "content": answer})
        else:
            # 最后一轮 follow-up streaming 返回了 content 但没有 tool_calls
            # content 已经 yield 给 UI，但需要记录到 history
            final_answer = content or ""
            self._history.append({"role": "user", "content": user_message})
            self._history.append({"role": "assistant", "content": final_answer})

        yield StreamEvent("done")

    def _run_with_prefetch(
        self,
        user_message: str,
        on_tool_call: Optional[Callable] = None,
        on_tool_result: Optional[Callable] = None,
    ) -> str:
        """
        降级模式：预先查询数据，注入上下文，用普通 chat

        当 LLM/Provider 不支持 Tool Calling 时（如旧版 Ollama），
        Agent 自动根据用户消息判断需要哪些工具，预先执行，
        把结果作为上下文注入到 prompt 中，然后用普通 chat 调用。

        这样即使没有原生 Tool Calling，Agent 也能利用知识库数据。
        """
        # 根据用户消息智能预查询
        prefetch_data = self._prefetch_knowledge_for_message(user_message, on_tool_call, on_tool_result)

        # 把预查询结果注入到用户消息中
        if prefetch_data:
            context_text = (
                "\n\n[以下是从知识库自动查询到的相关数据，请基于这些数据分析并回答用户问题]\n"
                "注意：这些是知识库中的真实数据，请直接引用分析，不要说\"未收录\"。\n\n"
                + prefetch_data
            )
            enhanced_message = user_message + context_text
        else:
            enhanced_message = user_message + "\n\n[知识库中未找到直接相关的数据，请基于通用知识给出建议]"

        # 构建消息（用普通 chat 系统提示词）
        messages = []
        system_prompt = self.templates.get_agent_system_prompt()
        messages.append({"role": "system", "content": system_prompt})

        if self.session_code:
            ctx = f"\n[当前诊断上下文]\n故障码: {self.session_code}"
            if self.session_vehicle:
                ctx += f"\n车型: {self.session_vehicle}"
            enhanced_message = ctx + f"\n\n技师提问: {enhanced_message}"

        # 调用普通 chat
        # 如果没有预查询数据，额外提醒 LLM 不要编造
        if not prefetch_data:
            enhanced_message += (
                "\n\n重要提示：知识库中没有找到相关的故障码数据。"
                "请直接告知用户'知识库未收录此信息'，"
                "建议用户使用原厂诊断仪读取或提供更多症状描述。"
                "不要编造故障码含义或诊断建议。"
            )

        response = self.llm.chat(message=enhanced_message, context=messages)

        self._history.append({"role": "user", "content": user_message})
        self._history.append({"role": "assistant", "content": response})
        return response

    def _prefetch_knowledge_for_message(
        self,
        user_message: str,
        on_tool_call: Optional[Callable] = None,
        on_tool_result: Optional[Callable] = None,
    ) -> str:
        """
        根据用户消息，预查询知识库数据作为上下文
        返回所有工具结果的拼接文本
        """
        import re

        results = []
        msg_upper = user_message.upper()

        # 1. 检测故障码（如 P0300、P0A0F、B1420、EV-BMS-001）
        # 注意：不能用宽泛的 [\w-]{3,15}，会把 PLEASE/EVALUATE 等英文单词误判为故障码
        # P/B/C/U 后必须跟 3~4 位十六进制字符；EV 系统码为 EV-XXX-001 形式
        code_pattern = r'\b((?:EV-[A-Z]+-\d{3})|[PBCU][0-9A-Fa-f]{3,4})\b'
        codes = re.findall(code_pattern, msg_upper)

        for code in codes:
            code = code.strip()
            if len(code) >= 4:  # 至少 4 字符才认为是有效故障码
                if on_tool_call:
                    on_tool_call("lookup_code", {"code": code})
                result = self.tools.execute("lookup_code", {"code": code})
                if on_tool_result:
                    on_tool_result("lookup_code", result[:200])
                results.append(f"## 故障码 {code} 信息\n{result}")

                # 同时查关联码
                related = self.tools.execute("get_related_codes", {"code": code})
                results.append(f"## {code} 关联故障码\n{related}")

        # 2. 检测车型关键词
        makes = ["比亚迪", "特斯拉", "蔚来", "小鹏", "理想", "广汽", "吉利",
                 "BYD", "TESLA", "NIO", "XPENG", "LI"]
        for make in makes:
            if make in user_message or make.upper() in msg_upper:
                # 尝试提取车型
                model = self._extract_model(user_message, make)
                if model:
                    if on_tool_call:
                        on_tool_call("get_vehicle_info", {"make": make, "model": model})
                    result = self.tools.execute("get_vehicle_info", {"make": make, "model": model})
                    if on_tool_result:
                        on_tool_result("get_vehicle_info", result[:200])
                    results.append(f"## 车型信息 {make} {model}\n{result}")
                break

        # 3. 检测症状关键词
        symptom_keywords = [
            ("抖动", "缺火"),          # "抖动"→搜"缺火"（技术术语，匹配 P0300）
            ("异响", "异响"),
            ("无法充电", "无法充电"),
            ("充电中断", "充电"),
            ("动力不足", "动力不足"),
            ("无法启动", "无法启动"),
            ("熄火", "熄火"),
            ("漏电", "漏电"),
            ("过热", "过热"),
            ("冒烟", "冒烟"),
            ("异味", "异味"),
            ("故障灯", "故障灯"),
            ("加速无力", "加速无力"),
            ("刹车", "刹车"),
            ("转向", "转向"),
        ]
        for simple_kw, search_kw in symptom_keywords:
            if simple_kw in user_message:
                if on_tool_call:
                    on_tool_call("search_by_symptom", {"keyword": search_kw})
                result = self.tools.execute("search_by_symptom", {"keyword": search_kw})
                if on_tool_result:
                    on_tool_result("search_by_symptom", result[:200])
                results.append(f"## 症状搜索: {search_kw}\n{result}")
                break  # 只搜第一个匹配的症状词

        return "\n\n".join(results)

    @staticmethod
    def _extract_model(text: str, make: str) -> str:
        """从文本中提取车型名"""
        # 简单的车型提取：品牌后面跟着的词
        models_map = {
            "比亚迪": ["秦", "汉", "唐", "宋", "海豚", "海鸥", "元", "护卫舰", "驱逐舰"],
            "特斯拉": ["Model 3", "Model Y", "Model S", "Model X"],
            "蔚来": ["ES6", "ES8", "ET5", "ET7", "EC6"],
            "小鹏": ["P7", "G6", "G9", "P5"],
            "理想": ["L7", "L8", "L9"],
            "BYD": ["Qin", "Han", "Tang", "Song", "Dolphin"],
            "TESLA": ["Model 3", "Model Y", "Model S", "Model X"],
        }
        models = models_map.get(make, [])
        for model in models:
            if model in text:
                return model
        return ""

    def chat(self, message: str) -> str:
        """
        与 Agent 对话（兼容旧接口，内部调用 run）
        """
        return self.run(message)

    def chat_stream(self, message: str):
        """
        流式对话（兼容旧接口）
        内部调用 run_stream，逐 token yield。
        """
        for event in self.run_stream(message):
            if event.type == "content":
                yield event.content

    def reset_session(self):
        """重置当前诊断会话"""
        self.session_code = None
        self.session_vehicle = None
        self._history.clear()

    def get_session_summary(self) -> Dict[str, Any]:
        """获取当前会话摘要"""
        if not self.session_code and not self._history:
            return {"status": "no_active_session"}

        return {
            "code": self.session_code or "无",
            "vehicle_info": self.session_vehicle or "无",
            "turns": len([h for h in self._history if h["role"] == "user"]),
            "knowledge_found": self.kb.lookup(self.session_code) is not None if self.session_code else False,
            "tools_available": len(self.tools),
        }

    def _build_messages(self, user_message: str) -> List[Dict[str, Any]]:
        """
        构建发送给 LLM 的消息列表

        包含：
        1. 系统提示词（告诉 LLM 它有工具可用）+ 专家角色声明
        2. 诊断上下文（当前故障码、车型）
        3. 用户消息
        """
        messages = []

        # 选择专家并获取对应的系统提示词
        expert = self._select_expert(self.session_code, user_message)
        system_prompt = self.templates.get_expert_system_prompt(expert)
        messages.append({"role": "system", "content": system_prompt})

        # 如果有活跃的诊断会话，添加上下文（含专家名称）
        expert_names = {
            key: get_expert_name(key)
            for key in ("battery", "motor", "vcu")
        }
        expert_names["general"] = "通用诊断专家"
        if self.session_code:
            context = f"\n[当前诊断上下文]\n故障码: {self.session_code}"
            if self.session_vehicle:
                context += f"\n车型: {self.session_vehicle}"
            context += f"\n当前专家: {expert_names.get(expert, '通用诊断专家')}"
            user_message = context + f"\n\n技师提问: {user_message}"

        messages.append({"role": "user", "content": user_message})
        return messages

    def _select_expert(self, code: Optional[str], user_message: str) -> str:
        """
        根据故障码和用户消息选择专家

        路由规则（优先级从高到低）：
        1. 查询数据库 system 字段（三电体系：battery/motor/vcu）
        2. P0Axx 码按描述关键词细分（电机/电池）
        3. 按用户消息关键词匹配（仅诊断相关消息）
        4. 默认通用专家

        Returns:
            专家名称: "battery" / "motor" / "vcu" / "general"
        """
        code_upper = (code or "").upper()

        # 1. 查询数据库 system 字段（最可靠）
        if code_upper:
            try:
                kb_data = self.kb.lookup(code_upper)
                if kb_data:
                    system = (kb_data.get("system") or "").upper()
                    desc = (kb_data.get("description") or "").lower()

                    # 按 system 字段路由（三电体系，域映射单一真源）
                    subsystem = get_subsystem_for_system(system)
                    if subsystem:
                        return subsystem

                    # P0Axx 码按描述关键词细分（电机关键词单一真源）
                    if code_upper.startswith("P0A"):
                        if any(kw in desc for kw in get_expert_keywords("motor")):
                            return "motor"
                        # 其他 P0Axx 默认电池（电池冷却、高压系统等）
                        return "battery"

                    # P/B/C/U 码按 system 首字母
                    if system.startswith("P") or system.startswith("B"):
                        return "general"
            except Exception as e:
                logger.debug(f"Expert selection failed: {e}")

        # 2. 按用户消息关键词匹配（仅当没有故障码时，关键词单一真源）
        if not code_upper:
            matched = match_keywords(user_message)
            if matched:
                return matched

        return "general"


# 便捷函数
def create_agent(
    kb: Optional[KnowledgeBase] = None,
    llm: Optional[LLMClient] = None,
) -> DiagnosticAgent:
    """创建诊断 Agent"""
    return DiagnosticAgent(kb=kb, llm=llm)
