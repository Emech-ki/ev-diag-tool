"""
生成故障实训单和答案文件
用法: python scripts/generate_training_docs.py
"""

import json
import sqlite3
from pathlib import Path

from docx import Document
from docx.shared import Pt, Inches, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "obd_codes.db"
OUTPUT_DIR = Path(r"D:\桌面")

# 5个故障场景
SCENARIOS = [
    {
        "id": "LAB-001",
        "code": "P0A00",
        "vehicle": "比亚迪 汉 EV",
        "year": "2022",
        "mileage": "85,000 km",
        "symptoms": "仪表显示电池故障灯，动力输出受限，无法上高压",
        "notes": "客户反映最近充电时间明显变长，更换过冷却液但未做系统排气",
        "expected_expert": "bms",
        "reference_answer": (
            "1. 故障分析：P0A00为电池冷却液温度传感器电路故障，该传感器监测电池包冷却液温度，"
            "为BMS提供温度数据用于控制冷却系统和充放电策略。\n"
            "2. 可能原因（按可能性排序）：\n"
            "   - 冷却液更换后系统内有气泡，导致传感器读数异常（最可能，因客户刚换过冷却液）\n"
            "   - 温度传感器线束接触不良或断裂\n"
            "   - 传感器本身损坏\n"
            "   - BMS采样电路故障\n"
            "3. 推荐排查路径：\n"
            "   第一步：使用诊断仪读取BMS数据流，查看冷却液温度传感器读数是否合理\n"
            "   第二步：检查冷却液液位，执行系统排气程序（排除气泡问题）\n"
            "   第三步：检查传感器线束连接器是否松动或腐蚀\n"
            "   第四步：用万用表测量传感器电阻值，与标准值对比\n"
            "   第五步：如以上正常，检查BMS采样电路\n"
            "4. 安全提醒：操作前断开高压维修开关，等待5分钟放电"
        ),
    },
    {
        "id": "LAB-002",
        "code": "P0A17",
        "vehicle": "特斯拉 Model 3",
        "year": "2021",
        "mileage": "62,000 km",
        "symptoms": "行驶中加速无力，电机异响（高速时明显），偶发动力中断",
        "notes": "异响在80km/h以上最明显，类似金属摩擦声",
        "expected_expert": "motor",
        "reference_answer": (
            "1. 故障分析：P0A17为电机扭矩传感器电路故障，该传感器检测驱动电机的实际输出扭矩，"
            "为电机控制器MCU提供反馈信号。故障会导致MCU无法准确控制电机输出。\n"
            "2. 可能原因（按可能性排序）：\n"
            "   - 旋变传感器（位置/扭矩传感器）线束断裂或接触不良\n"
            "   - 旋变传感器本身损坏\n"
            "   - 电机控制器MCU内部采样电路故障\n"
            "   - 电机轴承磨损导致传感器信号干扰（结合异响判断）\n"
            "3. 推荐排查路径：\n"
            "   第一步：使用诊断仪读取电机控制器数据流，查看扭矩传感器信号是否正常\n"
            "   第二步：检查旋变传感器线束（重点检查弯曲处是否有断裂）\n"
            "   第三步：用示波器检测旋变传感器正弦/余弦信号波形\n"
            "   第四步：检查电机轴承是否有磨损（结合异响症状）\n"
            "   第五步：如传感器正常，检查MCU控制板\n"
            "4. 安全提醒：电机三相线缆电压400V+，严禁带电操作"
        ),
    },
    {
        "id": "LAB-003",
        "code": "P0A01",
        "vehicle": "蔚来 ES6",
        "year": "2023",
        "mileage": "35,000 km",
        "symptoms": "充电速度变慢，电池温度警告灯亮，空调制冷异常",
        "notes": "快充从30%到80%需要1.5小时（正常45分钟），夏天高温时更明显",
        "expected_expert": "thermal",
        "reference_answer": (
            "1. 故障分析：P0A01为电池冷却液温度传感器范围/性能异常，该传感器监测电池包冷却系统温度。"
            "温度异常会导致BMS限制充电功率以保护电池。\n"
            "2. 可能原因（按可能性排序）：\n"
            "   - 冷却液不足或冷却系统故障（水泵、散热器）\n"
            "   - 电池散热风扇失效\n"
            "   - 温度传感器故障（虚报高温）\n"
            "   - 冷却液管路堵塞\n"
            "   - 热泵空调系统故障（影响整体热管理）\n"
            "3. 推荐排查路径：\n"
            "   第一步：读取BMS温度数据流，确认各区域温度\n"
            "   第二步：检查冷却液液位和冷却循环泵工作状态\n"
            "   第三步：检查电池散热风扇工作状态和PWM信号\n"
            "   第四步：验证温度传感器读数是否准确（用红外测温枪对比）\n"
            "   第五步：如有局部过热，检查对应模组绝缘\n"
            "4. 安全提醒：冷却系统高温时勿打开水箱盖"
        ),
    },
    {
        "id": "LAB-004",
        "code": "P0300",
        "vehicle": "比亚迪 秦PLUS DM-i",
        "year": "2022",
        "mileage": "45,000 km",
        "symptoms": "冷车启动时发动机抖动明显，热车后减轻，油耗增加约15%",
        "notes": "火花塞已行驶4万公里未更换，使用92号汽油",
        "expected_expert": "general",
        "reference_answer": (
            "1. 故障分析：P0300为随机/多缸缺火，表示发动机多个气缸出现燃烧不充分。"
            "不是单一缸问题，说明是共用部件异常。\n"
            "2. 可能原因（按可能性排序）：\n"
            "   - 火花塞磨损或积碳（4万公里未更换，高度怀疑）\n"
            "   - 点火线圈老化（冷车时绝缘下降）\n"
            "   - 进气道积碳（冷车抖动+热车减轻的经典表现）\n"
            "   - 燃油品质问题（92号汽油可能不适合该发动机）\n"
            "   - 水温传感器数据不准导致冷车喷油量异常\n"
            "3. 推荐排查路径：\n"
            "   第一步：读取冻结帧数据，确认故障发生时的发动机工况\n"
            "   第二步：检查火花塞状态（间隙、积碳、电极磨损）\n"
            "   第三步：测量各缸点火线圈电阻值\n"
            "   第四步：清洗节气门和进气道积碳\n"
            "   第五步：检查燃油压力和水温传感器数据\n"
            "4. 注意：DM-i车型在纯电模式下不报此码，需在HEV模式下测试"
        ),
    },
    {
        "id": "LAB-005",
        "code": "B1420",
        "vehicle": "小鹏 P7",
        "year": "2021",
        "mileage": "52,000 km",
        "symptoms": "安全气囊故障灯常亮，此前发生过轻微碰撞但气囊未弹出",
        "notes": "碰撞维修后故障灯亮起，维修过前保险杠和水箱框架",
        "expected_expert": "general",
        "reference_answer": (
            "1. 故障分析：B1420为安全气囊系统点火电路故障，可能是碰撞传感器、"
            "气囊模块或线路在维修后未正确恢复。\n"
            "2. 可能原因（按可能性排序）：\n"
            "   - 碰撞维修时线束未正确连接（最可能，维修后出现）\n"
            "   - 碰撞传感器损坏或移位\n"
            "   - 安全气囊控制模块ACU故障\n"
            "   - 气囊点火器电阻异常\n"
            "   - 安全带预紧器线路故障\n"
            "3. 推荐排查路径：\n"
            "   第一步：使用诊断仪读取安全气囊系统详细故障码\n"
            "   第二步：检查前碰撞传感器线束连接器（重点检查维修区域）\n"
            "   第三步：检查气囊控制模块ACU的供电和接地\n"
            "   第四步：测量气囊点火器电路电阻（标准值2-3Ω）\n"
            "   第五步：清除故障码后路试验证\n"
            "4. 安全提醒：气囊系统维修必须断电等待3分钟以上，严禁用万用表直接测气囊"
        ),
    },
]


def get_kb_data(code):
    """从数据库获取知识库数据"""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute(
        "SELECT code, description, detail, severity, common_causes, diagnostic_steps, related_codes, symptoms, system "
        "FROM obd_codes WHERE code = ?",
        (code,),
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "code": row[0],
        "description": row[1],
        "detail": row[2],
        "severity": row[3],
        "common_causes": row[4],
        "diagnostic_steps": row[5],
        "related_codes": row[6],
        "symptoms": row[7],
        "system": row[8],
    }


def parse_json_field(value):
    """解析JSON字段"""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return []


def set_cell_text(cell, text, bold=False, font_size=10, color=None):
    """设置单元格文本"""
    cell.text = ""
    p = cell.paragraphs[0]
    run = p.add_run(text)
    run.font.size = Pt(font_size)
    run.font.name = "微软雅黑"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
    if bold:
        run.font.bold = True
    if color:
        run.font.color.rgb = color


def add_heading(doc, text, level=1):
    """添加标题"""
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.name = "微软雅黑"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
    return h


def add_paragraph(doc, text, bold=False, font_size=11):
    """添加段落"""
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(font_size)
    run.font.name = "微软雅黑"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
    if bold:
        run.font.bold = True
    return p


def generate_training_sheet():
    """生成故障实训单"""
    doc = Document()

    # 设置默认字体
    style = doc.styles["Normal"]
    style.font.name = "微软雅黑"
    style.font.size = Pt(10.5)
    style._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")

    # 标题
    title = doc.add_heading("EV-Diag-Tool 故障实训单", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in title.runs:
        run.font.name = "微软雅黑"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")

    add_paragraph(doc, "新能源汽车智能诊断工具 — 实训考核", font_size=12).alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_paragraph(doc, "")

    # 说明
    add_paragraph(doc, "实训说明：", bold=True)
    add_paragraph(doc, "1. 打开 EV-Diag-Tool 程序")
    add_paragraph(doc, "2. 根据下方故障信息，在程序中输入故障码进行诊断")
    add_paragraph(doc, "3. 与 AI 诊断助手对话，获取诊断建议")
    add_paragraph(doc, "4. 记录你的诊断步骤和最终结论")
    add_paragraph(doc, "5. 导出诊断报告，与答案对照")
    add_paragraph(doc, "")

    for i, scenario in enumerate(SCENARIOS):
        # 分页（除第一个场景外）
        if i > 0:
            doc.add_page_break()

        # 场景标题
        add_heading(doc, f"实训 {scenario['id']}：{scenario['vehicle']}", level=1)

        # 信息表格
        table = doc.add_table(rows=8, cols=2, style="Table Grid")
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        fields = [
            ("实训编号", scenario["id"]),
            ("故障码", scenario["code"]),
            ("车型", scenario["vehicle"]),
            ("年款", scenario["year"]),
            ("行驶里程", scenario["mileage"]),
            ("症状描述", scenario["symptoms"]),
            ("技师备注", scenario["notes"]),
            ("实训任务", "1. 查询故障码信息\n2. 与AI对话获取诊断建议\n3. 记录诊断步骤\n4. 导出诊断报告"),
        ]

        for row_idx, (label, value) in enumerate(fields):
            set_cell_text(table.rows[row_idx].cells[0], label, bold=True, font_size=10)
            set_cell_text(table.rows[row_idx].cells[1], value, font_size=10)
            # 设置第一列宽度
            table.rows[row_idx].cells[0].width = Cm(3)

        add_paragraph(doc, "")

        # 诊断记录区
        add_heading(doc, "诊断记录", level=2)
        add_paragraph(doc, "我的诊断分析：", bold=True)
        add_paragraph(doc, "（请在此记录你的分析过程）")
        add_paragraph(doc, "")
        add_paragraph(doc, "最终结论：", bold=True)
        add_paragraph(doc, "（请在此写出你的诊断结论和维修建议）")
        add_paragraph(doc, "")
        add_paragraph(doc, "使用的专家：", bold=True)
        add_paragraph(doc, "（记录 AI 使用了哪个专家：BMS/电机/热管理/通用）")

    # 保存
    output_path = OUTPUT_DIR / "EV-Diag-Tool_故障实训单.docx"
    doc.save(str(output_path))
    print(f"实训单已保存: {output_path}")
    return output_path


def generate_answer_sheet():
    """生成答案文件"""
    doc = Document()

    # 设置默认字体
    style = doc.styles["Normal"]
    style.font.name = "微软雅黑"
    style.font.size = Pt(10.5)
    style._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")

    # 标题
    title = doc.add_heading("EV-Diag-Tool 故障实训单 — 参考答案", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in title.runs:
        run.font.name = "微软雅黑"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")

    add_paragraph(doc, "仅供教学参考，实际维修请结合车辆具体状况判断", font_size=11).alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_paragraph(doc, "")

    for i, scenario in enumerate(SCENARIOS):
        if i > 0:
            doc.add_page_break()

        code = scenario["code"]
        kb = get_kb_data(code)

        add_heading(doc, f"答案 {scenario['id']}：{code} — {scenario['vehicle']}", level=1)

        # 知识库数据
        if kb:
            add_heading(doc, "一、知识库标准数据", level=2)

            table = doc.add_table(rows=5, cols=2, style="Table Grid")
            kb_fields = [
                ("故障码描述", kb["description"] or "无"),
                ("严重程度", {"low": "低", "medium": "中", "high": "高", "critical": "严重"}.get(kb["severity"], kb["severity"])),
                ("系统", kb["system"] or "无"),
                ("详细说明", (kb["detail"] or "无")[:200] + ("..." if kb["detail"] and len(kb["detail"]) > 200 else "")),
                ("相关故障码", kb["related_codes"] or "无"),
            ]
            for row_idx, (label, value) in enumerate(kb_fields):
                set_cell_text(table.rows[row_idx].cells[0], label, bold=True, font_size=10)
                set_cell_text(table.rows[row_idx].cells[1], str(value), font_size=10)
                table.rows[row_idx].cells[0].width = Cm(3)

            add_paragraph(doc, "")

            # 常见原因
            causes = parse_json_field(kb["common_causes"])
            if causes:
                add_heading(doc, "二、常见原因", level=2)
                for j, cause in enumerate(causes, 1):
                    add_paragraph(doc, f"{j}. {cause}")

            # 诊断步骤
            steps = parse_json_field(kb["diagnostic_steps"])
            if steps:
                add_heading(doc, "三、标准诊断步骤", level=2)
                for j, step in enumerate(steps, 1):
                    add_paragraph(doc, f"{j}. {step}")

        # 专家路由
        add_heading(doc, "四、预期专家路由", level=2)
        expert_names = {"bms": "BMS 电池管理专家", "motor": "电机驱动专家", "thermal": "热管理专家", "general": "通用诊断专家"}
        add_paragraph(doc, f"应路由到：{expert_names.get(scenario['expected_expert'], scenario['expected_expert'])}")
        add_paragraph(doc, f"路由依据：故障码 {code} 属于 {scenario['expected_expert']} 领域")

        # 参考答案
        add_heading(doc, "五、参考诊断结论", level=2)
        for line in scenario["reference_answer"].split("\n"):
            add_paragraph(doc, line)

    # 保存
    output_path = OUTPUT_DIR / "EV-Diag-Tool_实训答案.docx"
    doc.save(str(output_path))
    print(f"答案文件已保存: {output_path}")
    return output_path


def main():
    print("=" * 50)
    print("EV-Diag-Tool 故障实训单生成器")
    print("=" * 50)

    if not DB_PATH.exists():
        print(f"[ERROR] 数据库不存在: {DB_PATH}")
        return

    print("\n生成实训单...")
    sheet_path = generate_training_sheet()

    print("\n生成答案文件...")
    answer_path = generate_answer_sheet()

    print("\n" + "=" * 50)
    print("生成完成！")
    print(f"  实训单: {sheet_path}")
    print(f"  答案: {answer_path}")
    print("=" * 50)


if __name__ == "__main__":
    main()
