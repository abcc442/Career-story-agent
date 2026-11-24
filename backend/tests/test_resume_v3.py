"""Offline smoke tests; no paid API and no access to the user's database."""
import io
import json
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient

from backend import db, main, ai_service as ai
from backend.schemas import MatchResult, MatchItem, ResumeTailorResult, ResumeParagraphEdit


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'test.sqlite')
    db.init_db()
    with TestClient(main.app) as c:
        yield c


def synthetic_docx():
    doc = Document()
    doc.add_heading('测试候选人', 0)
    doc.add_paragraph('负责用户访谈、需求整理和原型设计，项目尚未正式上线，没有业务增长数据。')
    doc.add_paragraph('企业知识库检索方案原型验证与体验设计。')
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = '表格单元格'
    table.cell(0, 1).text = '测试项目'
    data = io.BytesIO()
    doc.save(data)
    return data.getvalue()


def seed(client):
    jd = client.post('/api/jds', json={'title': 'AI产品经理', 'raw_text': '参与用户需求分析、原型设计与跨团队沟通，要求RAG产品经验。', 'company': '测试企业'})
    # Avoid AI by using demo mode in tests; if key configured, patch parse_jd during seed instead.
    assert jd.status_code == 201, jd.text
    exp = client.post('/api/experiences', json={
        'title':'用户研究项目', 'actions':'开展5场用户访谈并形成需求清单', 'results':'完成交互原型',
        'status':'confirmed', 'experience_type':'project', 'skills':['需求分析'],
    })
    assert exp.status_code == 201, exp.text
    return jd.json()['id'], exp.json()['id']


def test_preview_and_apply_preserve_docx(client, monkeypatch):
    monkeypatch.setattr(ai, 'ai_enabled', lambda: False)
    jd_id, exp_id = seed(client)

    async def fake_match(jd, confirmed):
        return MatchResult(items=[MatchItem(requirement='需求分析', level='strong', experience_ids=[exp_id], evidence='用户访谈')], priority_ids=[exp_id], gaps=[])

    async def fake_tailor(paragraphs, title, company, text, confirmed, match_data):
        paragraph = next(x for x in paragraphs if '负责用户访谈' in x['text'])
        return ResumeTailorResult(target_title=title, edits=[ResumeParagraphEdit(
            paragraph_id=paragraph['paragraph_id'], original_text=paragraph['text'],
            revised_text='开展5场用户访谈，整理需求清单并完成交互原型；项目尚未正式上线，没有业务增长数据。',
            reason='加入确认记录中的用户访谈与交付物', source_experience_ids=[exp_id], matched_requirements=['需求分析']
        )], review_notes=['未发现真实线上效果指标，请补充验证情况。'])

    monkeypatch.setattr(ai, 'match_jd', fake_match)
    monkeypatch.setattr(ai, 'tailor_resume', fake_tailor)
    original = synthetic_docx()
    response = client.post('/api/resumes/tailor/preview', data={'jd_id':jd_id,'use_confirmed':'true'}, files={'file':('resume.docx',original,'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview['confirmed_count'] == 1
    assert preview['edits'][0]['source_experience_ids'] == [exp_id]
    assert preview['review_notes']
    applied = client.post('/api/resumes/tailor/apply', data={'jd_id':jd_id, 'edits_json':json.dumps(preview['edits'],ensure_ascii=False)}, files={'file':('resume.docx',original,'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
    assert applied.status_code == 200, applied.text
    old, new = Document(io.BytesIO(original)), Document(io.BytesIO(applied.content))
    assert len(old.paragraphs) == len(new.paragraphs)
    assert len(old.tables) == len(new.tables)
    assert len(new.tables) == 1
    assert '5场用户访谈' in new.paragraphs[1].text
    assert '尚未正式上线' in new.paragraphs[1].text
    assert applied.headers['X-Resume-Edit-Count'] == '1'


def test_apply_rejects_unconfirmed_fact_and_changed_source(client, monkeypatch):
    monkeypatch.setattr(ai, 'ai_enabled', lambda: False)
    jd_id, exp_id = seed(client)
    original = synthetic_docx()
    paragraph = '负责用户访谈、需求整理和原型设计，项目尚未正式上线，没有业务增长数据。'
    base = {'paragraph_id':1,'original_text':paragraph,'revised_text':'组织999场访谈，项目尚未正式上线，没有业务增长数据。','reason':'test','source_experience_ids':[exp_id]}
    res = client.post('/api/resumes/tailor/apply', data={'jd_id':jd_id,'edits_json':json.dumps([base],ensure_ascii=False)}, files={'file':('resume.docx',original)})
    assert res.status_code == 422, res.text
    base['revised_text'] = '进行了需求访谈，项目尚未正式上线，没有业务增长数据。'
    base['original_text'] = '不一致原文'
    res = client.post('/api/resumes/tailor/apply', data={'jd_id':jd_id,'edits_json':json.dumps([base],ensure_ascii=False)}, files={'file':('resume.docx',original)})
    assert res.status_code == 422, res.text


def test_numeric_grounding():
    edit = ResumeParagraphEdit(paragraph_id=1, original_text='进行了用户访谈', revised_text='进行了5场用户访谈', source_experience_ids=[1])
    assert ai._tailor_safe_edit(edit, '进行了用户访谈')[0] is False
    assert ai._tailor_safe_edit(edit, '进行了用户访谈', '共计5场用户访谈')[0] is True
