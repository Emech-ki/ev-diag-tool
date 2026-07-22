"""
提示词模板
为 LLM 提供结构化的诊断提示词
"""

from typing import Optional, Dict, Any


class PromptTemplates:
    """诊断提示词模板"""

    def build_diagnostic_prompt(
        self,
        code: str,
        knowledge: Optional[Dict[str, Any]] = None,
        vehicle_info: str = "",
        additional_info: str = ""
    ) -> str:
        """
        构建诊断提示词

        Args:
            code: 故障码
            knowledge: 知识库查询结果
            vehicle_info: 车型信息
            additional_info: 附加描述

        Returns:
            格式化的提示词字符串
        """
        # 基础信息
        prompt = f"""你是一位经验丰富的新能源汽车维修诊断专家。
请根据以下信息给出诊断建议。

## 故障码
{code}

"""

        # 如果有知识库信息，加入作为参考
        if knowledge:
            prompt += f"""## 故障码基础信息（来自维修手册）
描述: {knowledge.get('description', '未知')}
详细说明: {knowledge.get('detail', '无')}
严重程度: {knowledge.get('severity', 'medium')}

常见原因:
"""
            causes = knowledge.get('common_causes', [])
            if isinstance(causes, list):
                for cause in causes:
                    prompt += f"- {cause}\n"
            else:
                prompt += "- 信息获取失败\n"

            prompt += f"\n标准诊断步骤:\n"
            steps = knowledge.get('diagnostic_steps', [])
            if isinstance(steps, list):
                for i, step in enumerate(steps, 1):
                    prompt += f"{i}. {step}\n"
            else:
                prompt += "- 信息获取失败\n"

        # 车型和附加信息
        if vehicle_info:
            prompt += f"\n## 车型信息\n{vehicle_info}\n"

        if additional_info:
            prompt += f"\n## 附加描述\n{additional_info}\n"

        # 输出要求
        prompt += f"""
## 请给出以下诊断建议

基于以上信息，请提供：

### 1️⃣ 可能性排序
将常见原因按可能性从高到低排序，并简要说明为什么。

### 2️⃣ 推荐排查路径
建议技师应当**先检查什么、再检查什么**，按照逻辑顺序排列。
注意：不要直接让技师更换零件，而是建议一步步测试和排除。

### 3️⃣ 注意事项
- 维修时的安全注意事项
- 容易忽视的检查点
- 特定车型的已知通病（如果适用）

### 4️⃣ 诊断技巧
- 如何快速区分不同原因
- 推荐的诊断工具和方法

请用中文回复，语言要专业但易懂。强烈建议技师**不要直接更换零件**，而是按照排查步骤一步步确认。
"""

        return prompt

    def get_agent_system_prompt(self) -> str:
        """
        AI Agent 系统提示词
        用于方案C的对话式交互
        """
        return """# 角色
你是一位专业的新能源汽车诊断 AI 助手。你的工作是通过与维修技师对话，帮助他们诊断车辆故障。

# 核心原则
1. **不要武断下结论** — 始终建议"先检查、再确认、后维修"
2. **引导式提问** — 通过提问获取更多信息，缩小故障范围
3. **安全第一** — 任何涉及高压电、安全气囊等安全系统的操作，必须强调安全注意事项
4. **尊重技师** — 你的建议是参考，最终判断权在技师

# 工作流程
1. 当技师输入故障码时，先查询知识库获取基础信息
2. 通过提问获取更多上下文（症状、条件、历史）
3. 基于已知信息给出排查建议
4. 每一步都解释"为什么这样排查"

# 输出格式
- 清晰的分段
- 关键点加粗标记
- 步骤用数字编号
- 安全警告用 ⚠️ 标记

# 知识边界
- 你主要擅长 OBD-II 标准故障码的诊断
- 对于你不太确定的领域，请诚实告知
- 必要时建议技师查阅官方维修手册
"""

    def build_search_prompt(self, keyword: str) -> str:
        """构建搜索相关的提示词"""
        return f"""
请搜索与 "{keyword}" 相关的汽车故障诊断信息。
返回最相关的故障码和诊断建议。
"""
