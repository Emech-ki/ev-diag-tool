"""
阶段三功能验证脚本
覆盖：知识库、工具框架、Agent、Provider、UI 集成
运行：python scripts/verify_features.py
"""

import sys
import os
import json
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️ WARN"
SKIP = "⏭️ SKIP"

results = []


def test(name, func):
    """运行一个测试，记录结果"""
    try:
        result = func()
        if result is True:
            results.append((PASS, name, ""))
        elif result is False:
            results.append((FAIL, name, "返回 False"))
        elif isinstance(result, str):
            results.append((WARN, name, result))
        else:
            results.append((PASS, name, ""))
    except Exception as e:
        results.append((FAIL, name, f"{type(e).__name__}: {e}"))


# ═══════════════════════════════════════════════════════════
# 第一组：知识库基础功能
# ═══════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("第一组：知识库基础功能")
print("=" * 60)

from src.engine.knowledge_base import KnowledgeBase
kb = KnowledgeBase()


def test_kb_lookup_p0300():
    r = kb.lookup("P0300")
    assert r is not None, "P0300 未找到"
    assert "缺火" in r["description"] or "失火" in r["description"], f"描述不匹配: {r['description']}"
    return True

def test_kb_lookup_not_found():
    r = kb.lookup("Z9999")
    assert r is None, "Z9999 不应该存在"
    return True

def test_kb_search():
    results = kb.search("抖动")
    assert len(results) > 0, "搜索'抖动'无结果"
    return True

def test_kb_symptoms():
    r = kb.lookup("P0300")
    symptoms = r.get("symptoms", [])
    assert len(symptoms) > 0, f"P0300 无症状数据: {symptoms}"
    return True

def test_kb_related_codes():
    r = kb.lookup("P0300")
    related = r.get("related_codes", [])
    assert len(related) > 0, f"P0300 无关联码: {related}"
    return True

def test_kb_severity():
    r = kb.lookup("P0300")
    assert r["severity"] in ("low", "medium", "high", "critical"), f"严重程度异常: {r['severity']}"
    return True

def test_kb_vehicle_empty():
    makes = kb.get_vehicle_makes()
    if len(makes) == 0:
        return "车型表为空，需运行 python scripts/seed_db.py"
    return True


test("P0300 故障码查询", test_kb_lookup_p0300)
test("不存在的故障码返回 None", test_kb_lookup_not_found)
test("关键词搜索", test_kb_search)
test("症状字段存在", test_kb_symptoms)
test("关联故障码存在", test_kb_related_codes)
test("严重程度字段有效", test_kb_severity)
test("车型数据库", test_kb_vehicle_empty)


# ═══════════════════════════════════════════════════════════
# 第二组：工具框架 (Tool Registry)
# ═══════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("第二组：工具框架 (Tool Registry)")
print("=" * 60)

from src.ai.tools import Tool, ToolParam, ToolRegistry


def test_tool_register():
    reg = ToolRegistry()
    reg.register(Tool(name="t1", description="test", parameters=[], function=lambda: "{}"))
    assert "t1" in reg
    assert len(reg) == 1
    return True

def test_tool_schema():
    t = Tool(
        name="lookup_code",
        description="查询故障码",
        parameters=[ToolParam(name="code", type="string", description="故障码", required=True)],
        function=lambda code: "{}",
    )
    s = t.to_openai_schema()
    assert s["type"] == "function"
    assert s["function"]["name"] == "lookup_code"
    assert "code" in s["function"]["parameters"]["properties"]
    assert "code" in s["function"]["parameters"]["required"]
    return True

def test_tool_execute():
    reg = ToolRegistry()
    reg.register(Tool(
        name="echo", description="回显",
        parameters=[ToolParam(name="text", type="string", description="输入")],
        function=lambda text: json.dumps({"echo": text}),
    ))
    r = json.loads(reg.execute("echo", {"text": "hello"}))
    assert r["echo"] == "hello"
    return True

def test_tool_unknown():
    reg = ToolRegistry()
    r = json.loads(reg.execute("nonexistent", {}))
    assert "error" in r
    return True

def test_tool_openai_format():
    reg = ToolRegistry()
    for i in range(3):
        reg.register(Tool(name=f"t{i}", description=f"工具{i}", parameters=[], function=lambda: "{}"))
    fmt = reg.to_openai_format()
    assert len(fmt) == 3
    for f in fmt:
        assert f["type"] == "function"
    return True


test("工具注册和查找", test_tool_register)
test("OpenAI Schema 格式", test_tool_schema)
test("工具执行", test_tool_execute)
test("未知工具错误处理", test_tool_unknown)
test("批量导出格式", test_tool_openai_format)


# ═══════════════════════════════════════════════════════════
# 第三组：诊断工具集 (9 个工具)
# ═══════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("第三组：诊断工具集 (9 个工具)")
print("=" * 60)

from src.ai.diagnostic_tools import register_diagnostic_tools

reg = ToolRegistry()
register_diagnostic_tools(reg, kb)


def test_tool_lookup_code():
    r = json.loads(reg.execute("lookup_code", {"code": "P0300"}))
    assert r["found"] is True
    assert "缺火" in r["description"] or "失火" in r["description"]
    assert len(r["common_causes"]) > 0
    return True

def test_tool_lookup_not_found():
    r = json.loads(reg.execute("lookup_code", {"code": "Z9999"}))
    assert r["found"] is False
    return True

def test_tool_search_symptom():
    r = json.loads(reg.execute("search_by_symptom", {"keyword": "抖动"}))
    assert r["found"] is True
    assert r["count"] > 0
    return True

def test_tool_search_empty():
    r = json.loads(reg.execute("search_by_symptom", {"keyword": ""}))
    assert "error" in r
    return True

def test_tool_vehicle_info():
    r = json.loads(reg.execute("get_vehicle_info", {"make": "比亚迪", "model": "秦PLUS EV"}))
    # 车型表有数据，应该返回找到
    assert r["found"] is True, f"Expected found=True, got {r.get('found')}"
    assert "common_codes" in r, "Missing common_codes field"
    return True

def test_tool_related_codes():
    r = json.loads(reg.execute("get_related_codes", {"code": "P0300"}))
    assert r["related_count"] > 0
    return True

def test_tool_diagnostic_steps():
    r = json.loads(reg.execute("get_diagnostic_steps", {"code": "P0300"}))
    assert len(r["diagnostic_steps"]) > 0
    return True

def test_tool_wiring_info():
    r = json.loads(reg.execute("get_wiring_info", {"code": "P0300"}))
    assert "wiring_hint" in r
    return True

def test_tool_record_symptom():
    r = json.loads(reg.execute("record_symptom", {"code": "P0300", "symptom": "测试症状-验证脚本"}))
    assert r["success"] is True
    return True

def test_tool_common_fixes():
    r = json.loads(reg.execute("get_common_fixes", {"code": "P0300"}))
    assert len(r["common_causes"]) > 0
    return True

def test_tool_search_by_system():
    r = json.loads(reg.execute("search_codes_by_system", {"system": "P"}))
    assert r["found"] is True
    assert r["count"] > 0
    return True

def test_tool_schema_all_valid():
    schemas = reg.to_openai_format()
    assert len(schemas) == 9, f"期望 9 个工具，实际 {len(schemas)}"
    for s in schemas:
        assert s["type"] == "function"
        assert "name" in s["function"]
        assert "description" in s["function"]
    return True


test("lookup_code: 查 P0300", test_tool_lookup_code)
test("lookup_code: 不存在的码", test_tool_lookup_not_found)
test("search_by_symptom: 搜'抖动'", test_tool_search_symptom)
test("search_by_symptom: 空关键词", test_tool_search_empty)
test("get_vehicle_info: 车型表为空", test_tool_vehicle_info)
test("get_related_codes: P0300 关联码", test_tool_related_codes)
test("get_diagnostic_steps: P0300 诊断步骤", test_tool_diagnostic_steps)
test("get_wiring_info: P0300 电路信息", test_tool_wiring_info)
test("record_symptom: 记录症状", test_tool_record_symptom)
test("get_common_fixes: P0300 修复方案", test_tool_common_fixes)
test("search_codes_by_system: 动力总成", test_tool_search_by_system)
test("全部 9 个工具 Schema 有效", test_tool_schema_all_valid)


# ═══════════════════════════════════════════════════════════
# 第四组：LLM Provider
# ═══════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("第四组：LLM Provider")
print("=" * 60)

from src.ai.llm_client import LLMClient
from src.ai.providers.ollama import OllamaProvider
from src.ai.providers.openai_compat import OpenAICompatProvider


def test_provider_ollama_init():
    p = OllamaProvider(model_name="test:latest", base_url="http://localhost:11434")
    assert p.provider_name == "ollama"
    assert p.model_name == "test:latest"
    return True

def test_provider_openai_init():
    p = OpenAICompatProvider(api_key="test-key", base_url="https://api.example.com", model_name="gpt-4")
    assert p.provider_name == "openai"
    assert p.model_name == "gpt-4"
    return True

def test_provider_url_normalize():
    p = OpenAICompatProvider(api_key="k", base_url="https://api.deepseek.com", model_name="m")
    assert p._base_url.endswith("/v1"), f"URL 未自动补全 /v1: {p._base_url}"
    return True

def test_llm_client_singleton():
    LLMClient._instance = None
    c1 = LLMClient()
    c2 = LLMClient()
    assert c1 is c2, "LLMClient 不是单例"
    return True

def test_llm_client_switch():
    LLMClient._instance = None
    c = LLMClient()
    c.switch_provider("openai")
    assert c.provider.provider_name == "openai"
    c.switch_provider("ollama")
    assert c.provider.provider_name == "ollama"
    return True

def test_provider_has_chat_with_tools():
    """测试 Provider 是否实现了 chat_with_tools 方法"""
    p = OllamaProvider()
    assert hasattr(p, 'chat_with_tools'), "OllamaProvider 缺少 chat_with_tools"
    p2 = OpenAICompatProvider(api_key="test", base_url="https://example.com", model_name="m")
    assert hasattr(p2, 'chat_with_tools'), "OpenAICompatProvider 缺少 chat_with_tools"
    return True

def test_ollama_available():
    p = OllamaProvider()
    try:
        available = p.is_available()
        if not available:
            return "Ollama 服务不可用（可能未启动）"
        return True
    except Exception:
        return "Ollama 连接失败"


test("Ollama Provider 初始化", test_provider_ollama_init)
test("OpenAI Provider 初始化", test_provider_openai_init)
test("URL 自动补全 /v1", test_provider_url_normalize)
test("LLMClient 单例", test_llm_client_singleton)
test("Provider 切换", test_llm_client_switch)
test("chat_with_tools 方法存在", test_provider_has_chat_with_tools)
test("Ollama 服务可用性", test_ollama_available)


# ═══════════════════════════════════════════════════════════
# 第五组：Agent 核心
# ═══════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("第五组：Agent 核心")
print("=" * 60)

from src.ai.agent import DiagnosticAgent


def test_agent_init():
    agent = DiagnosticAgent(kb=kb)
    assert agent.session_code is None
    assert len(agent.tools) == 9
    return True

def test_agent_start_diagnosis():
    agent = DiagnosticAgent(kb=kb)
    result = agent.start_diagnosis("P0300", "比亚迪 秦")
    assert result["code"] == "P0300"
    assert agent.session_code == "P0300"
    assert agent.session_vehicle == "比亚迪 秦"
    return True

def test_agent_reset():
    agent = DiagnosticAgent(kb=kb)
    agent.start_diagnosis("P0300")
    agent.reset_session()
    assert agent.session_code is None
    return True

def test_agent_session_summary():
    agent = DiagnosticAgent(kb=kb)
    s = agent.get_session_summary()
    assert s["status"] == "no_active_session"
    agent.start_diagnosis("P0300")
    s = agent.get_session_summary()
    assert s["code"] == "P0300"
    assert s["tools_available"] == 9
    return True

def test_agent_build_messages():
    agent = DiagnosticAgent(kb=kb)
    agent.start_diagnosis("P0300")
    msgs = agent._build_messages("这个故障怎么修")
    assert msgs[0]["role"] == "system"
    assert "P0300" in msgs[1]["content"]
    return True

def test_agent_prefetch():
    """测试降级模式的预查询"""
    agent = DiagnosticAgent(kb=kb)
    data = agent._prefetch_tools("P0300 故障码怎么修")
    assert "P0300" in data, f"预查询未包含 P0300: {data[:200]}"
    return True

def test_agent_prefetch_symptom():
    """测试症状关键词预查询"""
    agent = DiagnosticAgent(kb=kb)
    data = agent._prefetch_tools("冷车启动抖动怎么办")
    assert "缺火" in data or "search_by_symptom" in data, f"预查询未搜症状: {data[:200]}"
    return True

def test_agent_run():
    """测试 Agent.run() 完整调用（需要 LLM 可用）"""
    agent = DiagnosticAgent(kb=kb)
    LLMClient._instance = None
    llm = LLMClient()
    if not llm.is_available():
        return "LLM 不可用，跳过 run() 测试"
    result = agent.run("P0300 是什么故障")
    assert len(result) > 10, f"回复太短: {result}"
    return True


test("Agent 初始化", test_agent_init)
test("Agent 开始诊断", test_agent_start_diagnosis)
test("Agent 重置会话", test_agent_reset)
test("Agent 会话摘要", test_agent_session_summary)
test("Agent 消息构建", test_agent_build_messages)
test("Agent 预查询（故障码）", test_agent_prefetch)
test("Agent 预查询（症状）", test_agent_prefetch_symptom)
test("Agent.run() 完整调用", test_agent_run)


# ═══════════════════════════════════════════════════════════
# 第六组：Prompt 模板
# ═══════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("第六组：Prompt 模板")
print("=" * 60)

from src.ai.prompt_templates import PromptTemplates

templates = PromptTemplates()


def test_prompt_diagnostic():
    p = templates.build_diagnostic_prompt(
        code="P0300",
        knowledge={"description": "测试", "detail": "", "severity": "high",
                   "common_causes": ["原因1"], "diagnostic_steps": ["步骤1"]}
    )
    assert "P0300" in p
    assert "原因1" in p
    assert "Chain of Thought" in p
    return True

def test_prompt_safety():
    p = templates.build_diagnostic_prompt(
        code="P0A0E",
        knowledge={"description": "绝缘故障", "detail": "", "severity": "critical",
                   "common_causes": [], "diagnostic_steps": []}
    )
    assert "安全警告" in p
    assert "绝缘手套" in p
    return True

def test_prompt_tool_agent():
    p = templates.get_tool_agent_system_prompt()
    assert "工具" in p
    assert "lookup_code" in p
    assert "search_by_symptom" in p
    return True


test("诊断 Prompt 构建", test_prompt_diagnostic)
test("高危安全提醒", test_prompt_safety)
test("工具感知系统提示词", test_prompt_tool_agent)


# ═══════════════════════════════════════════════════════════
# 汇总
# ═══════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("验证结果汇总")
print("=" * 60)

passed = sum(1 for s, _, _ in results if s == PASS)
failed = sum(1 for s, _, _ in results if s == FAIL)
warned = sum(1 for s, _, _ in results if s == WARN)

for status, name, detail in results:
    line = f"  {status} {name}"
    if detail:
        line += f" — {detail}"
    print(line)

print(f"\n总计: {passed} 通过 / {failed} 失败 / {warned} 警告")

if failed > 0:
    print("\n⚠️ 有失败项需要修复！")
    sys.exit(1)
elif warned > 0:
    print("\n⚠️ 有警告项需要关注。")
    sys.exit(0)
else:
    print("\n🎉 全部通过！")
    sys.exit(0)
