"""
工具调用框架 (Tool Calling Framework)
定义工具的数据结构、注册机制和执行引擎

类比单片机概念：
- ToolParam ≈ 寄存器位域定义（名称、类型、描述）
- Tool ≈ 外设驱动（功能描述 + 参数 + 执行函数）
- ToolRegistry ≈ 中断向量表（注册/查找/分发执行）
- tool_calls ≈ 中断请求（LLM 发出的函数调用信号）
"""

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolParam:
    """
    工具参数定义
    类比：寄存器中的一个位域 — 名称、类型、是否必填
    """
    name: str               # 参数名，如 "code"
    type: str               # JSON Schema 类型: "string", "integer", "array"
    description: str        # 参数说明，LLM 据此理解参数含义
    required: bool = True   # 是否必填
    enum: Optional[List[str]] = None  # 可选值列表（如 ["P", "B", "C", "U"]）


@dataclass
class Tool:
    """
    一个可被 LLM 调用的工具
    类比：一个外设驱动 — 有名称、功能描述、参数规格、执行函数
    """
    name: str                       # 工具名，如 "lookup_code"
    description: str                # 功能描述，LLM 据此决定何时调用
    parameters: List[ToolParam]     # 参数列表
    function: Callable[..., str]    # 实际执行的 Python 函数，返回 JSON 字符串

    def to_openai_schema(self) -> dict:
        """
        转为 OpenAI function calling 的 JSON Schema 格式

        OpenAI 要求的格式：
        {
            "type": "function",
            "function": {
                "name": "lookup_code",
                "description": "查询故障码详情",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "故障码"}
                    },
                    "required": ["code"]
                }
            }
        }
        """
        properties = {}
        required = []

        for param in self.parameters:
            prop = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            properties[param.name] = prop
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def execute(self, arguments: Dict[str, Any]) -> str:
        """
        执行工具，返回 JSON 字符串结果

        Args:
            arguments: 参数字典，来自 LLM 的 tool_calls

        Returns:
            JSON 字符串，将作为 tool role 消息返回给 LLM
        """
        try:
            result = self.function(**arguments)
            # 确保返回值是字符串
            if isinstance(result, str):
                return result
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": f"工具 {self.name} 执行失败: {str(e)}"},
                ensure_ascii=False,
            )


class ToolRegistry:
    """
    工具注册表
    类比：中断向量表 — 注册每个工具的入口地址，收到中断请求时分发执行

    使用方式：
        registry = ToolRegistry()
        registry.register(Tool(name="lookup_code", ...))
        registry.register(Tool(name="search_symptom", ...))

        # LLM 请求调用时
        result = registry.execute("lookup_code", {"code": "P0300"})

        # 导出给 LLM
        tools_schema = registry.to_openai_format()
    """

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """注册一个工具（类比：注册中断处理函数）"""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        """根据名称查找工具（类比：查中断向量表）"""
        return self._tools.get(name)

    def execute(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        执行指定工具（类比：响应中断，调用处理函数）

        Args:
            name: 工具名
            arguments: 参数字典

        Returns:
            工具执行结果的 JSON 字符串
        """
        tool = self._tools.get(name)
        if tool is None:
            return json.dumps(
                {"error": f"未知工具: {name}，可用工具: {list(self._tools.keys())}"},
                ensure_ascii=False,
            )
        return tool.execute(arguments)

    def to_openai_format(self) -> List[dict]:
        """
        导出所有工具为 OpenAI tools 格式
        直接传给 LLM API 的 tools 参数
        """
        return [tool.to_openai_schema() for tool in self._tools.values()]

    def list_tools(self) -> List[str]:
        """列出所有已注册的工具名"""
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
