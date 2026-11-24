from __future__ import annotations

import pytest

from backend.ai_service import _demo_introduction, count_spoken_chars
from backend.schemas import IntroductionInput, IntroductionResult


def test_count_spoken_chars_ignores_punctuation_and_spaces():
    assert count_spoken_chars('你好， Career Story！') == len('你好CareerStory')


def test_introduction_duration_is_bounded():
    assert IntroductionInput(duration_minutes=1).duration_minutes == 1
    assert IntroductionInput(duration_minutes=3.5).duration_minutes == 3.5
    with pytest.raises(Exception):
        IntroductionInput(duration_minutes=0)
    with pytest.raises(Exception):
        IntroductionInput(duration_minutes=10.5)


def test_demo_introduction_uses_confirmed_experience_and_discloses_limit():
    confirmed = [{
        'id': 11,
        'title': '供应商风险智能感知系统',
        'background': '供应商风险信息分散。',
        'task': '参与风险感知产品方案梳理。',
        'actions': '梳理风险全景和靶向提示模块。',
        'methods': 'RAG 检索增强。',
        'results': '完成产品方案草稿。',
        'skills': ['需求分析', 'RAG'],
    }]
    result = _demo_introduction(
        {'title': 'AI 产品经理实习生'},
        confirmed,
        {'highlights': [{'experience_id': 11}]},
        3,
    )
    assert isinstance(result, IntroductionResult)
    assert '供应商风险智能感知系统' in result.introduction
    assert 'RAG' in result.introduction
    assert result.notes
