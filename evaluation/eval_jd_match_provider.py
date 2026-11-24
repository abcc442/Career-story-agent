
"""Promptfoo provider for JD parsing and experience matching.

Directly calls existing Career Story Agent functions.
Does not read or modify the application's SQLite database.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from backend import ai_service as ai


def _as_data(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


def call_api(prompt, options, context):
    """Entry point used by Promptfoo Python Provider."""

    vars_ = (context or {}).get("vars", {})
    task = vars_.get("task")

    if not ai.ai_enabled():
        return {
            "error": "未检测到项目 .env 中的有效 AI 配置"
        }

    try:
        if task == "jd":

            jd_text = vars_.get("jd_text", "")

            if not jd_text.strip():
                return {
                    "error": "jd_text 不能为空"
                }

            result = asyncio.run(
                ai.parse_jd(jd_text)
            )

        elif task == "match":

            jd = _as_data(vars_.get("jd"))
            experiences = _as_data(
                vars_.get("confirmed")
            )

            if (
                not isinstance(jd, dict)
                or not isinstance(experiences, list)
            ):
                return {
                    "error": "jd 必须为对象，confirmed 必须为数组"
                }

            result = asyncio.run(
                ai.match_jd(jd, experiences)
            )

        else:
            return {
                "error": "未知评测任务，仅支持 jd 或 match"
            }

        return {
            "output": json.dumps(
                result.model_dump(),
                ensure_ascii=False
            )
        }

    except Exception as exc:

        # Do not print API keys or private resume data.
        return {
            "error": (
                f"{task} 执行失败："
                f"{type(exc).__name__}"
            )
        }
