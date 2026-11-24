
"""Career Story Agent - Word Resume Evaluation.

Uses synthetic resume data, not the user's real resume.
Run from the evaluation directory.
"""

from pathlib import Path
from io import BytesIO
import json
import time
import httpx
from docx import Document
from docx.shared import Pt, Cm

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "reports" / "resume_eval"
OUTPUT.mkdir(parents=True, exist_ok=True)

API = "http://127.0.0.1:8000/api/resumes/tailor"

JD_TITLE = "AI产品经理实习生"
JD_COMPANY = "示例科技公司"
JD_TEXT = """
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

def make_test_resume(path):
    doc = Document()

    section = doc.sections[0]
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)

    doc.add_heading("测试候选人", level=0)
    doc.add_paragraph("目标岗位：AI产品经理实习生")

    doc.add_heading("实习经历", level=1)
    doc.add_paragraph(
        "某科技公司｜AI产品实习生｜2025.06-2025.09"
    )

    doc.add_paragraph(
        "负责收集业务用户反馈，开展需求访谈，"
        "整理产品需求文档并绘制产品原型，"
        "与研发团队沟通功能实现方案。"
        "完成PRD和可交互原型，"
        "产品尚未正式上线，没有业务增长数据。",
        style="List Bullet"
    )

    doc.add_heading("项目经历", level=1)
    doc.add_paragraph("企业知识库产品设计｜独立项目")

    doc.add_paragraph(
        "围绕企业内部知识查询场景开展需求分析，"
        "设计RAG知识检索产品原型，"
        "整理知识库检索流程和用户交互方案。"
        "项目处于原型验证阶段，"
        "尚未进行真实用户规模测试。",
        style="List Bullet"
    )

    doc.add_heading("技能", level=1)
    doc.add_paragraph(
        "Figma、SQL、Python、需求分析、PRD、RAG"
    )

    # Include a table to check structural preservation.
    table = doc.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    table.cell(0, 0).text = "测试字段"
    table.cell(0, 1).text = "测试内容"

    doc.save(path)


def get_structure(doc):
    return {
        "sections": len(doc.sections),
        "tables": len(doc.tables),
        "table_shapes": [
            (len(t.rows), len(t.columns))
            for t in doc.tables
        ],
        "paragraphs": len(doc.paragraphs),
        "styles": [
            p.style.name for p in doc.paragraphs
        ],
        "headings": [
            p.text for p in doc.paragraphs
            if p.style.name.startswith("Heading")
        ],
        "margins": [
            (
                s.top_margin,
                s.bottom_margin,
                s.left_margin,
                s.right_margin,
            )
            for s in doc.sections
        ],
    }


def all_text(doc):
    pieces = [p.text for p in doc.paragraphs]

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                pieces.append(cell.text)

    return "\n".join(pieces)


def run():
    original = OUTPUT / "synthetic_resume.docx"
    revised = OUTPUT / "tailored_resume.docx"

    make_test_resume(original)

    before = Document(original)
    before_structure = get_structure(before)
    before_text = all_text(before)

    start = time.perf_counter()

    with httpx.Client(timeout=180.0) as client:
        with original.open("rb") as f:
            response = client.post(
                API,
                files={
                    "file": (
                        original.name,
                        f,
                        "application/vnd.openxmlformats-"
                        "officedocument.wordprocessingml.document",
                    )
                },
                data={
                    "jd_title": JD_TITLE,
                    "jd_company": JD_COMPANY,
                    "jd_text": JD_TEXT,
                },
            )

    latency = round(time.perf_counter() - start, 2)

    if response.status_code != 200:
        print("API failed:", response.status_code)
        print(response.text[:500])
        return

    revised.write_bytes(response.content)

    after = Document(BytesIO(response.content))
    after_structure = get_structure(after)
    after_text = all_text(after)

    protected = [
        "某科技公司",
        "2025.06-2025.09",
        "企业知识库产品设计",
        "测试候选人",
    ]

    checks = {
        "docx_can_open": True,
        "sections_preserved": (
            before_structure["sections"]
            == after_structure["sections"]
        ),
        "tables_preserved": (
            before_structure["table_shapes"]
            == after_structure["table_shapes"]
        ),
        "paragraph_count_preserved": (
            before_structure["paragraphs"]
            == after_structure["paragraphs"]
        ),
        "paragraph_styles_preserved": (
            before_structure["styles"]
            == after_structure["styles"]
        ),
        "margins_preserved": (
            before_structure["margins"]
            == after_structure["margins"]
        ),
        "protected_facts_preserved": all(
            x in after_text for x in protected
        ),
        "content_actually_changed": (
            before_text != after_text
        ),
    }

    report = {
        "module": "Word Resume Tailoring",
        "model_task": JD_TITLE,
        "latency_seconds": latency,
        "edit_count": response.headers.get(
            "X-Resume-Edit-Count"
        ),
        "skipped_count": response.headers.get(
            "X-Resume-Skipped-Count"
        ),
        "checks": checks,
        "passed": sum(checks.values()),
        "total": len(checks),
        "original_text": before_text,
        "revised_text": after_text,
    }

    report_path = OUTPUT / "result.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n=== Word Resume Evaluation ===")

    for key, passed in checks.items():
        label = "PASS" if passed else "FAIL"
        print(f"{label}: {key}")

    print(f"\nScore: {report['passed']}/{report['total']}")
    print(f"Latency: {latency}s")
    print(f"Edits: {report['edit_count']}")
    print(f"Report: {report_path}")
    print(f"Revised DOCX: {revised}")


if __name__ == "__main__":
    run()
