
"""Prepare V1/V2/V3 resume comparison for Promptfoo."""

import json
from pathlib import Path

from docx import Document

ROOT = Path(__file__).resolve().parent
FOLDER = ROOT / "resume_comparison"
FOLDER.mkdir(parents=True, exist_ok=True)

V3_FILE = FOLDER / "v3.docx"
EVIDENCE_FILE = FOLDER / "confirmed_evidence.txt"
OUTPUT_FILE = FOLDER / "cases.json"

JD = """
岗位职责：
1. 参与AI产品需求调研与用户访谈。
2. 负责PRD撰写和产品原型设计。
3. 参与RAG知识库与AI Agent产品方案设计。
4. 与算法和研发团队协作推进产品验证。
5. 设计AI产品效果评估指标。

任职要求：
熟悉大模型应用、RAG、产品设计与数据分析。
具备良好的逻辑思维和跨团队沟通能力。
"""

ORIGINAL = """测试候选人
目标岗位：AI产品经理实习生
实习经历
某科技公司｜AI产品实习生｜2025.06-2025.09
负责收集业务用户反馈，开展需求访谈，整理产品需求文档并绘制产品原型，与研发团队沟通功能实现方案。完成PRD和可交互原型，产品尚未正式上线，没有业务增长数据。
项目经历
企业知识库产品设计｜独立项目
围绕企业内部知识查询场景开展需求分析，设计RAG知识检索产品原型，整理知识库检索流程和用户交互方案。项目处于原型验证阶段，尚未进行真实用户规模测试。
技能
Figma、SQL、Python、需求分析、PRD、RAG
测试字段
测试内容"""

V1 = """测试候选人
目标岗位：AI产品经理实习生
实习经历
某科技公司｜AI产品实习生｜2025.06-2025.09
收集业务用户反馈并开展需求访谈，整理产品需求文档、绘制可交互原型，与研发团队沟通功能实现方案。已产出PRD和可交互原型；产品尚未正式上线，暂无业务增长数据。
项目经历
企业知识库产品设计｜独立项目
围绕企业内部知识查询场景开展需求分析，设计RAG知识检索产品原型，梳理知识库检索流程与用户交互方案。项目处于原型验证阶段，尚未进行真实用户规模测试。
技能
Figma、SQL、Python、需求分析、PRD撰写、RAG知识检索
测试字段
测试内容"""

V2 = """测试候选人
目标岗位：AI产品经理实习生
实习经历
某科技公司｜AI产品实习生｜2025.06-2025.09
收集业务用户反馈并开展需求访谈，据此整理产品需求文档、绘制产品原型，与研发团队沟通功能实现方案；完成PRD和可交互原型。产品尚未正式上线，没有业务增长数据。
项目经历
企业知识库产品设计｜独立项目
围绕企业内部知识查询场景开展需求分析，设计RAG知识检索产品原型，整理知识库检索流程与用户交互方案。项目处于原型验证阶段，尚未进行真实用户规模测试。
技能
Figma、SQL、Python、需求分析、PRD、RAG
测试字段
测试内容"""


def extract_docx_text(path: Path) -> str:
    doc = Document(path)
    pieces = [p.text for p in doc.paragraphs]

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                pieces.append(cell.text)

    return "\n".join(
        x for x in pieces if x.strip()
    ).strip()


def main():
    if not V3_FILE.exists():
        print("尚未找到 V3 Word 文件。")
        print("请把 V3 生成的 Word 复制到：")
        print(V3_FILE)
        return

    v3_text = extract_docx_text(V3_FILE)

    if not v3_text:
        raise ValueError("V3 Word 没有可读取的正文")

    # Explicitly reject obvious mismatched test resumes.
    anchors = [
        "测试候选人",
        "某科技公司",
        "2025.06-2025.09",
        "企业知识库产品设计",
    ]
    missing = [
        x for x in anchors if x not in v3_text
    ]

    if missing:
        raise ValueError(
            "V3 文件可能不是同一份测试简历。"
            "缺少：" + "、".join(missing)
        )

    evidence = (
        EVIDENCE_FILE.read_text(encoding="utf-8").strip()
        if EVIDENCE_FILE.exists()
        else ""
    )

    if not evidence:
        print(
            "提醒：没有 confirmed_evidence.txt，"
            "Judge 将只把原 Word 当作事实来源。"
        )

    cases = []

    for version, revised in [
        ("V1", V1),
        ("V2", V2),
        ("V3", v3_text),
    ]:
        cases.append({
            "description": (
                f"{version} | AI产品经理Word简历改写对比"
            ),
            "vars": {
                "version": version,
                "jd_title": "AI产品经理实习生",
                "jd_text": JD,
                "original_text": ORIGINAL,
                "confirmed_evidence": evidence,
                "revised_text": revised,
            },
        })

    OUTPUT_FILE.write_text(
        json.dumps(
            cases, ensure_ascii=False, indent=2
        ),
        encoding="utf-8",
    )

    print("已生成三版本 Promptfoo 测试集")
    print("V1 字符数:", len(V1))
    print("V2 字符数:", len(V2))
    print("V3 字符数:", len(v3_text))
    print("确认经历证据:", "已提供" if evidence else "未提供")
    print("测试集:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
