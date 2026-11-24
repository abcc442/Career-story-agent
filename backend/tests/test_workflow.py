from backend.schemas import ExperienceInput


def test_health_and_mode(client):
    assert client.get('/api/health').json() == {'status': 'ok'}
    assert client.get('/api/meta').json()['mode'] == 'demo'


def test_confirmed_only_story_and_interview(client):
    exp = client.post('/api/experiences', json={
        'title': '智能问答产品', 'actions': '负责需求访谈、PRD与原型，设计了RAG检索流程。',
        'methods': '用户访谈、原型设计', 'results': '完成原型设计与评审。', 'skills': ['RAG'],
        'status': 'draft',
    })
    assert exp.status_code == 201
    jd = client.post('/api/jds', json={
        'title': 'AI产品经理', 'raw_text': '要求能够完成用户需求调研和产品原型设计，理解RAG与AI应用。',
    })
    assert jd.status_code == 201
    jd_id = jd.json()['id']
    blocked = client.post('/api/stories/generate', json={'jd_id': jd_id})
    assert blocked.status_code == 400
    body = {k: exp.json()[k] for k in ExperienceInput.model_fields}
    body['status'] = 'confirmed'
    assert client.put(f"/api/experiences/{exp.json()['id']}", json=body).status_code == 200
    story = client.post('/api/stories/generate', json={'jd_id': jd_id})
    assert story.status_code == 201, story.text
    assert story.json()['mode'] == 'demo'
    assert story.json()['data']['highlights'][0]['experience_id'] == exp.json()['id']
    session = client.post('/api/interviews', json={'story_id': story.json()['id']})
    assert session.status_code == 201
    reply = client.post(f"/api/interviews/{session.json()['id']}/reply", json={'answer': '我负责需求访谈和原型设计。'})
    assert reply.status_code == 200
    assert len(reply.json()['messages']) == 3
    assert client.get('/api/export').json()['experiences']


def test_followup_is_proposal_until_confirmed(client):
    exp = client.post('/api/experiences', json={'title': '活动推荐系统'}).json()
    q = client.post(f"/api/experiences/{exp['id']}/question")
    assert q.status_code == 200
    proposed = client.post(f"/api/experiences/{exp['id']}/answer", json={'answer': '我负责PRD编写。'})
    assert proposed.status_code == 200
    assert 'PRD' in proposed.json()['proposed_value']
    unchanged = client.get('/api/experiences').json()[0]
    assert unchanged['actions'] == ''  # No silent updates.


def test_upload_safety_and_reset(client):
    bad = client.post('/api/resumes/read', files={'file': ('bad.exe', b'hello', 'application/octet-stream')})
    assert bad.status_code == 400
    ok = client.post('/api/resumes/read', files={'file': ('resume.txt', '负责用户研究和原型设计'.encode(), 'text/plain')})
    assert ok.status_code == 200
    assert '用户研究' in ok.json()['text']
    seed = client.post('/api/demo/seed')
    assert seed.status_code == 200
    assert client.post('/api/demo/seed').status_code == 409
    assert client.delete('/api/data').json() == {'ok': True}
    assert client.get('/api/experiences').json() == []


def test_demo_extract_does_not_claim_ai(client):
    res = client.post('/api/experiences/extract', json={'text': 'ABC项目\n负责原型设计和需求调研。\n\nDEF项目\n做了数据整理。'})
    assert res.status_code == 200
    assert res.json()['mode'] == 'demo'
    assert len(res.json()['experiences']) == 2
    assert res.json()['experiences'][0]['actions'] == ''



def test_experience_type_and_parent_link(client):
    internship = client.post('/api/experiences', json={
        'title': '产品经理实习', 'experience_type': 'internship', 'organization': '测试企业'
    })
    assert internship.status_code == 201
    project = client.post('/api/experiences', json={
        'title': '供应商风险项目', 'experience_type': 'project',
        'parent_experience_id': internship.json()['id']
    })
    assert project.status_code == 201
    assert project.json()['experience_type'] == 'project'
    assert project.json()['parent_experience_id'] == internship.json()['id']
    invalid = client.post('/api/experiences', json={
        'title': '错误关联', 'experience_type': 'project',
        'parent_experience_id': project.json()['id']
    })
    assert invalid.status_code == 400


def test_tailor_resume_docx_preserves_original_template(client, monkeypatch):
    from io import BytesIO
    from docx import Document
    from docx.shared import Inches
    from backend import ai_service
    from backend.schemas import ResumeTailorResult, ResumeParagraphEdit

    original_text = '原始项目经历：参与RAG方案设计，负责梳理业务需求、检索流程与产品方案，形成项目需求文档'

    async def fake_tailor(paragraphs, jd_title, jd_company, jd_text):
        assert any(item['text'] == original_text for item in paragraphs)
        assert jd_title == 'AI产品经理'
        target = next(item for item in paragraphs if item['text'] == original_text)
        return ResumeTailorResult(
            target_title=jd_title,
            edits=[ResumeParagraphEdit(
                paragraph_id=target['paragraph_id'],
                original_text=original_text,
                revised_text='参与RAG方案设计，梳理业务需求与检索流程，形成产品需求文档。',
                reason='突出与岗位相关的AI产品方案设计能力'
            )],
            review_notes=['请核对个人贡献范围。']
        )
    monkeypatch.setattr(ai_service, 'tailor_resume', fake_tailor)

    source = Document()
    source.sections[0].top_margin = Inches(0.8)
    title = source.add_paragraph('测试候选人')
    title.style = 'Title'
    source.add_heading('项目经历', level=1)
    target = source.add_paragraph(original_text, style='List Bullet')
    table = source.add_table(rows=1, cols=2)
    table.cell(0, 0).text = '技能'
    table.cell(0, 1).text = 'Python、RAG'
    buf = BytesIO()
    source.save(buf)
    buf.seek(0)

    response = client.post(
        '/api/resumes/tailor',
        data={'jd_title': 'AI产品经理', 'jd_company': '测试公司', 'jd_text': '负责AI产品需求分析、RAG应用设计和PRD编写。'},
        files={'file': ('resume.docx', buf.getvalue(), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')}
    )
    assert response.status_code == 200, response.text
    assert response.headers['X-Resume-Edit-Count'] == '1'
    assert response.headers['X-Resume-Template-Preserved'] == 'true'
    output = Document(BytesIO(response.content))
    assert len(output.paragraphs) == len(source.paragraphs)
    assert output.paragraphs[0].text == '测试候选人'
    assert output.paragraphs[0].style.name == 'Title'
    assert output.paragraphs[1].text == '项目经历'
    assert output.paragraphs[2].text == '参与RAG方案设计，梳理业务需求与检索流程，形成产品需求文档。'
    assert output.paragraphs[2].style.name == 'List Bullet'
    assert output.sections[0].top_margin == source.sections[0].top_margin
    assert len(output.tables) == 1
    assert output.tables[0].cell(0, 1).text == 'Python、RAG'


def test_tailor_resume_rejects_mismatched_ai_target(client, monkeypatch):
    from io import BytesIO
    from docx import Document
    from backend import ai_service
    from backend.schemas import ResumeTailorResult, ResumeParagraphEdit

    async def fake_tailor(paragraphs, jd_title, jd_company, jd_text):
        return ResumeTailorResult(
            target_title=jd_title,
            edits=[ResumeParagraphEdit(
                paragraph_id=0, original_text='AI编造的原文',
                revised_text='不应被写入文档'
            )]
        )
    monkeypatch.setattr(ai_service, 'tailor_resume', fake_tailor)

    source = Document()
    source.add_paragraph('真实候选人')
    source.add_paragraph('真实项目经历：负责用户访谈和原型设计。')
    buf = BytesIO()
    source.save(buf)
    buf.seek(0)
    response = client.post(
        '/api/resumes/tailor',
        data={'jd_title': 'AI产品经理', 'jd_text': '负责AI产品需求分析和原型设计。'},
        files={'file': ('resume.docx', buf.getvalue(), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')}
    )
    assert response.status_code == 422


def test_interview_quick_start_needs_confirmed_experience_and_jd(client):
    jd = client.post('/api/jds', json={
        'title': 'AI产品经理', 'raw_text': '负责用户需求分析、PRD设计，理解大模型应用。'
    }).json()
    response = client.post('/api/interviews/quick-start', json={'jd_id': jd['id']})
    assert response.status_code == 400
    exp = client.post('/api/experiences', json={'title': '供应商风险项目', 'status': 'confirmed',
        'actions': '参与RAG知识检索方案梳理及业务需求访谈。', 'results': '形成初版产品方案。'}).json()
    response = client.post('/api/interviews/quick-start', json={'jd_id': jd['id']})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body['preparation_mode'] == 'rule_based'
    story = client.get(f"/api/stories/{body['story_id']}").json()
    assert story['jd_id'] == jd['id']
    assert story['mode'] == 'demo'  # Must not pretend a rule outline was generated by AI.
    assert exp['id'] in [h['experience_id'] for h in story['data']['highlights']]
    interview = client.get(f"/api/interviews/{body['interview_id']}").json()
    assert interview['story_id'] == body['story_id']
    assert interview['messages'][0]['role'] == 'assistant'
    reply = client.post(f"/api/interviews/{body['interview_id']}/reply", json={'answer': '我负责需求访谈和RAG检索方案。'})
    assert reply.status_code == 200
    assert len(reply.json()['messages']) == 3
