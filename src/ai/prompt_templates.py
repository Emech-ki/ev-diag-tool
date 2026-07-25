"""
提示词模板
为 LLM 提供结构化的诊断提示词，支持 few-shot、CoT、严重程度自适应
"""

from typing import Optional, Dict, Any


class PromptTemplates:
    """诊断提示词模板"""

    # 严重程度对应的中文标签和图标
    SEVERITY_LABELS = {
        "low": ("低", "ℹ️"),
        "medium": ("中等", "⚠️"),
        "high": ("高", "🔴"),
        "critical": ("严重", "🚨"),
    }

    # ── Few-shot 示例 ──
    FEW_SHOT_EXAMPLE = """## 参考示例

**故障码:** P0300 (随机/多缸缺火)
**知识库信息:** 发动机燃烧不充分，点火系统异常
**技师描述:** 冷车启动时抖动明显，热车后减轻

**分析过程:**
1. P0300 表示多缸缺火，不是单一缸 → 问题大概率出在共用部件（点火线圈供电、燃油压力、进气系统）
2. 冷车抖动 + 热车减轻 → 怀疑与温度相关：积碳、水温传感器、冷启动喷油量
3. 排除单一缸点火故障（那会是 P0301-P0308）

**诊断建议:**
1. 先读取冻结帧数据，确认故障发生时的发动机工况（转速、负荷、水温）
2. 检查火花塞状态（间隙、积碳）→ 如果4个缸都有问题，优先查点火线圈供电线路
3. 测量燃油压力（静态+动态）→ 压力不足会导致多缸混合气偏稀
4. 清洗节气门和进气道积碳 → 冷车抖动常见原因
5. 以上都正常后，检查水温传感器数据是否准确

---

"""

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
        # 判断严重程度，决定 prompt 策略
        severity = "medium"
        if knowledge:
            severity = knowledge.get("severity", "medium")

        sev_label, sev_icon = self.SEVERITY_LABELS.get(severity, ("中等", "⚠️"))
        is_critical = severity in ("high", "critical")

        # 基础信息
        prompt = f"""你是一位经验丰富的新能源汽车维修诊断专家。
请根据以下信息，通过逐步分析给出诊断建议。

## 故障码
{code}

"""

        # 如果有知识库信息，加入作为参考
        if knowledge:
            prompt += f"""## 故障码基础信息（来自维修手册）
描述: {knowledge.get('description', '未知')}
详细说明: {knowledge.get('detail', '无')}
严重程度: {sev_icon} {sev_label}

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
            prompt += f"\n## 技师描述的症状\n{additional_info}\n"

        # 严重程度自适应：高危故障增加安全提醒
        safety_section = ""
        if is_critical:
            safety_section = f"""
## ⚠️ 安全警告（高危故障）
此故障码严重程度为「{sev_label}」，请在诊断建议中特别强调：
- 涉及高压系统时，必须先断开高压维修开关，等待电容放电
- 操作前佩戴绝缘手套（1000V 级别）、护目镜
- 严禁带电操作高压部件
- 如不确定安全操作流程，建议移交高压认证技师

"""
        else:
            safety_section = """## 安全提醒
涉及新能源汽车高压系统（电池包、电机控制器、OBC 等）时，请提醒技师注意高压安全。

"""

        # Few-shot 示例（仅在有知识库信息时添加，避免无数据时误导）
        few_shot = ""
        if knowledge:
            few_shot = self.FEW_SHOT_EXAMPLE

        # 输出要求（含 CoT 推理引导）
        prompt += f"""{safety_section}{few_shot}## 请按以下步骤分析并给出诊断建议

### 1️⃣ 故障分析（Chain of Thought）
请先逐步推理：
- 这个故障码的含义是什么？
- 结合技师描述的症状，哪些原因最吻合？为什么？
- 哪些原因可以先排除？为什么？

### 2️⃣ 可能性排序
将可能原因按可能性从高到低排序，每个原因附上**置信度百分比**和简要理由。

### 3️⃣ 推荐排查路径
建议技师应当**先检查什么、再检查什么**，按照逻辑顺序排列。
注意：不要直接让技师更换零件，而是建议一步步测试和排除。

### 4️⃣ 注意事项
- 维修时的安全注意事项
- 容易忽视的检查点
- 特定车型的已知通病（如果适用）

### 5️⃣ 诊断技巧
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
5. **逐步推理** — 分析问题时展示推理过程，让技师理解你的判断依据

# 工作流程
1. 当技师输入故障码时，先查询知识库获取基础信息
2. 通过提问获取更多上下文（症状、条件、历史）
3. 基于已知信息给出排查建议，展示推理过程
4. 每一步都解释"为什么这样排查"

# 输出格式
- 清晰的分段
- 关键点加粗标记
- 步骤用数字编号
- 安全警告用 ⚠️ 标记
- 推理过程用「分析」标记

# 新能源汽车安全规范
- 高压系统（>60V DC）操作前必须断开维修开关
- 佩戴绝缘手套（1000V 级别）、护目镜
- 等待电容放电（至少 5 分钟）
- 严禁带电操作高压部件
- 电池热失控征兆（冒烟、异味、温度异常升高）时立即撤离

# 知识边界
- 你主要擅长 OBD-II 标准故障码和新能源汽车专用故障码的诊断
- 对于你不太确定的领域，请诚实告知
- 必要时建议技师查阅官方维修手册
"""
