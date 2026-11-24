
"""Create Promptfoo test data from the latest Word evaluation report."""

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent

REPORT_FILE = BASE / "reports" / "resume_eval" / "result.json"
OUTPUT_FILE = BASE / "resume_judge_cases.json"

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

def main():
    if not REPORT_FILE.exists():
        raise FileNotFoundError(
            "找不到 Word 评测报告，请先运行 eval_resume.py"
        )

    report = json.loads(
        REPORT_FILE.read_text(encoding="utf-8")
    )

    original = report.get("original_text", "").strip()
    revised = report.get("revised_text", "").strip()

    if not original or not revised:
        raise ValueError("评测报告缺少原文或修改后的正文")

    cases = [
        {
            "description": "R01 - 最新Word简历改写内容质量评测",
            "vars": {
                "jd_title": report.get(
                    "model_task", "AI产品经理实习生"
                ),
                "jd_text": JD_TEXT,
                "original_text": original,
                "revised_text": revised,
            },
        }
    ]

    OUTPUT_FILE.write_text(
        json.dumps(cases, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("已读取最新的 Word 评测报告")
    print("Word 结构检查:", report.get("passed"),
          "/", report.get("total"))
    print("修改段落数:", report.get("edit_count"))
    print("本次耗时:", report.get("latency_seconds"), "秒")
    print("已生成 Promptfoo 测试集:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
