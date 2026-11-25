
"""Career Story Agent local-first API. Run: uvicorn backend.main:app --reload"""
from __future__ import annotations

import io
import json
import logging
import re
import os
import unicodedata
from difflib import SequenceMatcher
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / '.env')
os.environ.setdefault('OPENAI_AGENTS_DISABLE_TRACING', '1')

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Literal
from .schemas import ResumeParagraphEdit

from . import ai_service as ai
from .db import add_run, all_rows, connection, decode, init_db, one, utc_now
from .schemas import AnswerInput, ExperienceInput, GenerateInput, IntroductionInput, JDInput, TextInput

log = logging.getLogger('career')


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title='Career Story Agent API', version='0.1.0', lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'http://localhost:5173',
        'http://127.0.0.1:5173',
        'https://abcc442.github.io',
    ],
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*'],
    expose_headers=['X-Resume-Edit-Count', 'X-Resume-Skipped-Count', 'X-Resume-Template-Preserved'],
)


def required(table: str, record_id: int) -> dict:
    result = one(table, record_id)
    if result is None:
        raise HTTPException(404, detail='未找到对应数据')
    return decode(result)


async def agent_call(operation: str, func, *args):
    try:
        result = await func(*args)
    except Exception as exc:
        log.exception(
            'Agent operation %s failed (mode=%s, model=%s, exception_type=%s)',
            operation, ai.mode(), os.getenv('OPENAI_MODEL', 'gpt-4.1-mini'), type(exc).__name__,
        )
        add_run(operation, ai.mode(), False)
        # Never return provider internals or sensitive prompts to users.
        raise HTTPException(502, detail='AI 请求失败。请检查 API Key、模型权限及网络连接，查看后端日志。') from exc
    add_run(operation, ai.mode(), True)
    return result


@app.get('/api/health')
def health():
    return {'status': 'ok'}


@app.get('/api/meta')
def meta():
    return {'mode': ai.mode(), 'model': os.getenv('OPENAI_MODEL', 'gpt-4.1-mini') if ai.ai_enabled() else None, 'app': 'Career Story Agent'}


@app.get('/api/experiences')
def get_experiences():
    return [decode(row) for row in all_rows('experiences')]


def validate_parent_link(exp: ExperienceInput, current_id: int | None = None):
    if exp.parent_experience_id is None:
        return
    if current_id is not None and exp.parent_experience_id == current_id:
        raise HTTPException(400, detail='经历不能关联自身。')
    parent = required('experiences', exp.parent_experience_id)
    if parent.get('experience_type') not in ('internship', 'work'):
        raise HTTPException(400, detail='项目只能关联到实习或正式工作经历。')


@app.post('/api/experiences', status_code=201)
def add_experience(exp: ExperienceInput):
    validate_parent_link(exp)
    now = utc_now()
    with connection() as db:
        cur = db.execute('''INSERT INTO experiences
        (title,organization,experience_type,parent_experience_id,period,background,task,actions,methods,results,evidence,skills,status,source,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
            exp.title, exp.organization, exp.experience_type, exp.parent_experience_id, exp.period, exp.background, exp.task,
            exp.actions, exp.methods, exp.results, exp.evidence,
            json.dumps(exp.skills[:15], ensure_ascii=False), exp.status, 'manual', now, now,
        ))
        record_id = cur.lastrowid
    return required('experiences', record_id)


@app.put('/api/experiences/{experience_id}')
def update_experience(experience_id: int, exp: ExperienceInput):
    required('experiences', experience_id)
    validate_parent_link(exp, experience_id)
    with connection() as db:
        db.execute('''UPDATE experiences SET title=?,organization=?,experience_type=?,parent_experience_id=?,period=?,background=?,task=?,actions=?,methods=?,results=?,evidence=?,skills=?,status=?,updated_at=? WHERE id=?''', (
            exp.title, exp.organization, exp.experience_type, exp.parent_experience_id, exp.period, exp.background, exp.task,
            exp.actions, exp.methods, exp.results, exp.evidence, json.dumps(exp.skills[:15], ensure_ascii=False),
            exp.status, utc_now(), experience_id,
        ))
    return required('experiences', experience_id)


@app.delete('/api/experiences/{experience_id}', status_code=204)
def delete_experience(experience_id: int):
    required('experiences', experience_id)
    with connection() as db:
        db.execute('UPDATE experiences SET parent_experience_id=NULL WHERE parent_experience_id=?', (experience_id,))
        db.execute('DELETE FROM experiences WHERE id=?', (experience_id,))


@app.post('/api/experiences/extract')
async def extract_experiences(body: TextInput):
    result = await agent_call('extract', ai.extract, body.text)
    return {'experiences': [r.model_dump() for r in result.experiences[:8]], 'note': result.note, 'mode': ai.mode()}


@app.post('/api/experiences/{experience_id}/question')
async def ask_experience(experience_id: int):
    exp = required('experiences', experience_id)
    result = await agent_call('question', ai.followup, exp)
    return result.model_dump()


@app.post('/api/experiences/{experience_id}/answer')
async def answer_experience(experience_id: int, body: AnswerInput):
    exp = required('experiences', experience_id)
    result = await agent_call('answer_proposal', ai.propose_answer, exp, body.answer)
    return result.model_dump()  # Intentionally not persisted until user accepts.


ALLOWED_SUFFIXES = {'.pdf', '.docx', '.txt', '.md'}
MAX_UPLOAD_SIZE = 5 * 1024 * 1024


@app.post('/api/resumes/read')
async def read_resume(file: UploadFile = File(...)):
    suffix = Path(file.filename or '').suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(400, detail='仅支持 PDF、DOCX、TXT、MD 文件')
    content = await file.read(MAX_UPLOAD_SIZE + 1)
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, detail='文件不能超过5MB')
    try:
        if suffix == '.pdf':
            from pypdf import PdfReader
            pdf = PdfReader(io.BytesIO(content))
            if len(pdf.pages) > 35:
                raise HTTPException(400, detail='PDF页数超过35页')
            text = '\n'.join(page.extract_text() or '' for page in pdf.pages)
        elif suffix == '.docx':
            from docx import Document
            document = Document(io.BytesIO(content))
            paragraphs = [p.text for p in document.paragraphs]
            for table in document.tables:
                for row in table.rows:
                    paragraphs.append(' | '.join(cell.text for cell in row.cells))
            text = '\n'.join(paragraphs)
        else:
            try:
                text = content.decode('utf-8-sig')
            except UnicodeDecodeError:
                text = content.decode('gb18030')
    except HTTPException:
        raise
    except Exception as exc:
        log.warning('Resume parsing failed: %s', type(exc).__name__)
        raise HTTPException(422, detail='无法读取文件内容，请尝试复制文字或转换文件格式。') from exc
    if not text.strip():
        raise HTTPException(422, detail='没有提取到文字，扫描版PDF请先转换成可复制文本。')
    return {'text': text[:25000], 'truncated': len(text) > 25000, 'filename': file.filename}


def _iter_docx_paragraphs(container):
    """Yield body paragraphs and table-cell paragraphs in document order."""
    from docx.text.paragraph import Paragraph
    from docx.table import Table
    from docx.oxml.text.paragraph import CT_P
    from docx.oxml.table import CT_Tbl

    parent = container.element.body if hasattr(container, 'element') else container._tc
    for child in parent.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, container)
        elif isinstance(child, CT_Tbl):
            table = Table(child, container)
            for row in table.rows:
                for cell in row.cells:
                    yield from _iter_docx_paragraphs(cell)


def _normalize_paragraph_text(text: str) -> str:
    """Normalize harmless Word/model differences without changing the source text."""
    normalized = unicodedata.normalize('NFKC', text or '')
    return ''.join(
        char for char in normalized
        if not char.isspace()
        and not char in ('\\u200b', '\\u200c', '\\u200d', '\\ufeff')
        and not unicodedata.category(char).startswith('P')
    ).casefold()


def _paragraph_source_matches(source: str, model_source: str) -> bool:
    """Accept exact/formatting-only copies and very small transcription differences."""
    left = _normalize_paragraph_text(source)
    right = _normalize_paragraph_text(model_source)
    if not left or not right:
        return False
    if left == right:
        return True
    # Short labels/headings are too ambiguous for fuzzy matching.
    if min(len(left), len(right)) < 24:
        return False
    return SequenceMatcher(None, left, right, autojunk=False).ratio() >= 0.90


def _replace_paragraph_text_preserving_style(paragraph, text: str) -> bool:
    """
    Replace paragraph text while retaining paragraph-level layout and a representative
    character style. Complex embedded Word objects remain deliberately untouched.
    """
    runs = [run for run in paragraph.runs if run.text]
    # Do not destroy hyperlinks, fields, drawings, objects, or manual line/tab layout.
    if paragraph._p.xpath(
        './/w:hyperlink | .//w:fldSimple | .//w:fldChar | .//w:drawing | '
        './/w:object | .//w:tab | .//w:br | .//w:cr'
    ):
        return False
    if not runs:
        paragraph.add_run(text)
        return True

    def signature(run):
        font = run.font
        color = font.color.rgb if font.color and font.color.type else None
        size = font.size.pt if font.size else None
        return (font.name, size, font.bold, font.italic, font.underline, color, run.style.name if run.style else None)

    signatures = {signature(run) for run in runs}
    if len(signatures) == 1:
        target = runs[0]
    else:
        # Mixed inline formatting is common in Word templates. Instead of skipping
        # the whole paragraph, retain the dominant text run's character formatting.
        # Paragraph style, bullets, indentation, spacing, tables and page layout remain.
        target = max(runs, key=lambda run: len(run.text))

    target_element = target._r
    target.text = text
    for run in paragraph.runs:
        if run._r is not target_element:
            run.text = ''
    return True


@app.post('/api/resumes/tailor')
async def tailor_resume_docx(
    file: UploadFile = File(...),
    jd_title: str = Form(...),
    jd_company: str = Form(''),
    jd_text: str = Form(...),
):
    """Apply AI edits to the uploaded DOCX in place, retaining its existing layout and styles."""
    if Path(file.filename or '').suffix.lower() != '.docx':
        raise HTTPException(400, detail='岗位定制简历目前仅支持 .docx Word 文件。请先将简历另存为 .docx。')
    content = await file.read(MAX_UPLOAD_SIZE + 1)
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, detail='文件不能超过5MB')
    if len(jd_text.strip()) < 10:
        raise HTTPException(422, detail='请提供完整的岗位 JD。')
    try:
        from docx import Document
        original = Document(io.BytesIO(content))
        all_paragraphs = list(_iter_docx_paragraphs(original))
        # De-duplicate merged table cells while retaining the first occurrence.
        unique_paragraphs = []
        seen = set()
        for paragraph in all_paragraphs:
            marker = id(paragraph._p)
            if marker not in seen:
                seen.add(marker)
                unique_paragraphs.append(paragraph)
        editable_paragraphs = [
            {'paragraph_id': idx, 'text': paragraph.text.strip()}
            for idx, paragraph in enumerate(unique_paragraphs)
            if paragraph.text.strip()
        ]
        paragraph_lookup = {
            item['paragraph_id']: unique_paragraphs[item['paragraph_id']]
            for item in editable_paragraphs
        }
        resume_text = '\n'.join(item['text'] for item in editable_paragraphs)
    except Exception as exc:
        raise HTTPException(422, detail='无法解析该 Word 文件，请确认文件未损坏。') from exc
    if len(resume_text.strip()) < 30:
        raise HTTPException(422, detail='没有读取到足够的简历文字；请检查是否为图片扫描版 Word。')
    result = await agent_call(
        'tailor_resume', ai.tailor_resume, editable_paragraphs,
        jd_title[:180], jd_company[:180], jd_text[:10000]
    )
    applied = 0
    skipped = 0
    skip_reasons = {'invalid_id': 0, 'source_mismatch': 0, 'invalid_revision': 0, 'complex_format': 0, 'duplicate': 0}
    seen_paragraph_ids = set()
    requested_edits = result.edits[:12]
    for edit in requested_edits:
        paragraph = paragraph_lookup.get(edit.paragraph_id)
        if paragraph is None:
            skipped += 1
            skip_reasons['invalid_id'] += 1
            continue
        if edit.paragraph_id in seen_paragraph_ids:
            skipped += 1
            skip_reasons['duplicate'] += 1
            continue
        seen_paragraph_ids.add(edit.paragraph_id)

        # paragraph_id is the primary locator; source text is a second safety check.
        # Normalize whitespace/Unicode/punctuation and tolerate tiny model transcription
        # differences, while refusing ambiguous or substantially different paragraphs.
        if not _paragraph_source_matches(paragraph.text, edit.original_text):
            skipped += 1
            skip_reasons['source_mismatch'] += 1
            continue

        revised = edit.revised_text.strip()
        if (
            not revised
            or _normalize_paragraph_text(revised) == _normalize_paragraph_text(paragraph.text)
            or len(revised) > 2500
        ):
            skipped += 1
            skip_reasons['invalid_revision'] += 1
            continue
        if _replace_paragraph_text_preserving_style(paragraph, revised):
            applied += 1
        else:
            skipped += 1
            skip_reasons['complex_format'] += 1

    log.info(
        'Resume tailoring completed: requested=%d applied=%d skipped=%d reasons=%s',
        len(requested_edits), applied, skipped, skip_reasons
    )
    if applied == 0:
        if not requested_edits:
            detail = 'AI 没有生成任何段落修改建议（edits 为空）。原始简历未被改变；请检查后端是否处于真实 AI 模式，或更换支持结构化输出的模型后重试。'
        else:
            detail = (
                'AI 已返回修改建议，但没有段落通过安全校验。原始简历未被改变。'
                f'共收到 {len(requested_edits)} 条建议，跳过 {skipped} 条；'
                f'原因统计：段落编号无效 {skip_reasons["invalid_id"]}、'
                f'原文匹配失败 {skip_reasons["source_mismatch"]}、'
                f'修改内容无效 {skip_reasons["invalid_revision"]}、'
                f'复杂 Word 对象无法安全编辑 {skip_reasons["complex_format"]}、'
                f'重复段落 {skip_reasons["duplicate"]}。'
            )
        raise HTTPException(422, detail=detail)
    try:
        buffer = io.BytesIO()
        original.save(buffer)
        buffer.seek(0)
    except Exception as exc:
        log.exception('DOCX in-place editing failed')
        raise HTTPException(500, detail='原 Word 模板修改失败，原文件未被覆盖。请查看后端日志。') from exc
    safe_title = re.sub(r'[^0-9A-Za-z一-龥_-]+', '_', jd_title).strip('_')[:40] or '目标岗位'
    original_stem = Path(file.filename or 'resume.docx').stem
    filename = f'{original_stem}_{safe_title}_定制版.docx'
    headers = {
        'Content-Disposition': f"attachment; filename*=UTF-8''{quote(filename)}",
        'X-Resume-Edit-Count': str(applied),
        'X-Resume-Skipped-Count': str(skipped),
        'X-Resume-Template-Preserved': 'true',
    }
    return StreamingResponse(
        buffer,
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        headers=headers
    )


class ResumeApplyInput(BaseModel):
    # All proposed edits must still be confirmed by the user before applying.
    edits: list[ResumeParagraphEdit] = Field(default_factory=list, max_length=6)


def _resume_document_from_content(content: bytes):
    from docx import Document
    try:
        document = Document(io.BytesIO(content))
        seen = set()
        paragraphs = []
        for p in _iter_docx_paragraphs(document):
            if id(p._p) not in seen:
                seen.add(id(p._p))
                paragraphs.append(p)
        source = [
            {'paragraph_id': idx, 'text': p.text}
            for idx, p in enumerate(paragraphs) if p.text.strip()
        ]
        if sum(len(p['text'].strip()) for p in source) < 30:
            raise HTTPException(422, detail='Word 中可读取的正文不足。')
        return document, paragraphs, source
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, detail='无法解析 Word 文件。') from exc


async def _read_word_upload(file: UploadFile) -> bytes:
    if Path(file.filename or '').suffix.lower() != '.docx':
        raise HTTPException(400, detail='请选择 .docx 文件。')
    content = await file.read(MAX_UPLOAD_SIZE + 1)
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, detail='Word 文件不能超过 5MB。')
    return content


@app.post('/api/resumes/tailor/preview')
async def preview_resume_v3(
    file: UploadFile = File(...),
    jd_id: int = Form(...),
    use_confirmed: bool = Form(True),
):
    """Generate suggestions, but never mutate or persist the Word file."""
    jd = required('jds', jd_id)
    content = await _read_word_upload(file)
    _doc, _paragraphs, source = _resume_document_from_content(content)
    confirmed = []
    if use_confirmed:
        confirmed = [
            decode(row) for row in all_rows('experiences')
            if row['status'] == 'confirmed' and row['source'] != 'demo'
        ][:25]
    match = None
    if confirmed:
        match = await agent_call('tailor_v3_match', ai.match_jd, jd, confirmed)
    result = await agent_call(
        'tailor_v3_preview', ai.tailor_resume, source,
        jd['title'], jd['company'], jd['raw_text'], confirmed,
        match.model_dump() if match else None,
    )
    allowed = {x['id']: x for x in confirmed}
    return {
        'jd_id': jd_id,
        'filename': file.filename,
        'use_confirmed': use_confirmed,
        'confirmed_count': len(confirmed),
        'match': match.model_dump() if match else None,
        'edits': [
            {
                **e.model_dump(),
                'source_experiences': [
                    {'id': i, 'title': allowed[i]['title']}
                    for i in e.source_experience_ids if i in allowed
                ],
            }
            for e in result.edits
        ],
        'review_notes': result.review_notes,
        'notice': '所有修改均需用户逐条审核；自动校验不能代替事实核实。',
    }


@app.post('/api/resumes/tailor/apply')
async def apply_resume_v3(
    file: UploadFile = File(...),
    jd_id: int = Form(...),
    edits_json: str = Form(...),
):
    """Apply only the edits explicitly selected by the user to the uploaded original."""
    jd = required('jds', jd_id)
    content = await _read_word_upload(file)
    document, paragraphs, source = _resume_document_from_content(content)
    try:
        edits = ResumeApplyInput(edits=json.loads(edits_json)).edits
    except Exception as exc:
        raise HTTPException(422, detail='修改清单格式不正确。') from exc
    if not edits:
        raise HTTPException(422, detail='请至少勾选一条修改。')
    original_by_id = {item['paragraph_id']: item['text'] for item in source}
    allowed = {
        r['id']: decode(r) for r in all_rows('experiences')
        if r['status'] == 'confirmed' and r['source'] != 'demo'
    }
    applied = 0
    seen = set()
    for edit in edits:
        pid = edit.paragraph_id
        if pid in seen or pid not in original_by_id or edit.original_text != original_by_id[pid]:
            raise HTTPException(422, detail=f'段落 {pid} 的原文与当前 Word 不一致。请重新生成预览。')
        seen.add(pid)
        if any(i not in allowed for i in edit.source_experience_ids):
            raise HTTPException(422, detail=f'段落 {pid} 使用的经历未确认或已经删除，请重新预览。')
        evidence = json.dumps([allowed[i] for i in edit.source_experience_ids], ensure_ascii=False)
        safe, reason = ai._tailor_safe_edit(edit, original_by_id[pid], evidence)
        if not safe:
            raise HTTPException(422, detail=f'段落 {pid} 安全校验未通过：{reason}')
        if not _replace_paragraph_text_preserving_style(paragraphs[pid], edit.revised_text):
            raise HTTPException(422, detail=f'段落 {pid} 含复杂格式对象，不能安全修改。')
        applied += 1
    buffer = io.BytesIO()
    document.save(buffer)
    buffer.seek(0)
    safe_title = re.sub(r'[^0-9A-Za-z一-龥_-]+', '_', jd['title']).strip('_')[:40] or '目标岗位'
    filename = f'{Path(file.filename or "resume.docx").stem}_{safe_title}_V3定制版.docx'
    return StreamingResponse(
        buffer,
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        headers={
            'Content-Disposition': f"attachment; filename*=UTF-8''{quote(filename)}",
            'X-Resume-Edit-Count': str(applied),
            'X-Resume-Template-Preserved': 'true',
            'Access-Control-Expose-Headers': 'X-Resume-Edit-Count',
        },
    )


@app.get('/api/jds')
def get_jds():
    return [decode(row) for row in all_rows('jds')]


@app.post('/api/jds', status_code=201)
async def add_jd(jd: JDInput):
    parsed = await agent_call('parse_jd', ai.parse_jd, jd.raw_text)
    with connection() as db:
        cur = db.execute('INSERT INTO jds(title,company,raw_text,requirements,mode,created_at) VALUES (?,?,?,?,?,?)', (
            jd.title, jd.company, jd.raw_text,
            json.dumps([r.model_dump() for r in parsed.requirements], ensure_ascii=False), ai.mode(), utc_now(),
        ))
        record_id = cur.lastrowid
    return required('jds', record_id)


@app.post('/api/stories/generate', status_code=201)
async def generate_story(body: GenerateInput):
    jd = required('jds', body.jd_id)
    confirmed = [decode(row) for row in all_rows('experiences') if row['status'] == 'confirmed']
    log.info(
        'Starting story generation: jd_id=%s confirmed_experiences=%s mode=%s model=%s',
        body.jd_id, len(confirmed), ai.mode(), os.getenv('OPENAI_MODEL', 'gpt-4.1-mini'),
    )
    if not confirmed:
        raise HTTPException(400, detail='请先确认至少一条个人经历，再生成职业故事。')
    matched = await agent_call('match', ai.match_jd, jd, confirmed)
    narrative = await agent_call('story', ai.create_story, jd, confirmed, matched)
    if any(exp['source'] == 'demo' for exp in confirmed):
        narrative.cautions.append('该故事使用了虚构的示例经历，仅用于产品演示，严禁作为个人简历使用。')
    story_data = narrative.model_dump()
    intro_target = 230
    intro_actual = ai.count_spoken_chars(narrative.introduction)
    story_data.update({
        'introduction_minutes': 1,
        'introduction_target_chars': intro_target,
        'introduction_actual_chars': intro_actual,
        'introduction_mode': ai.mode(),
        'introduction_notes': [],
    })
    if ai.mode() == 'demo':
        story_data['introduction_notes'].append('当前为规则演示提纲，尚未按时长进行 AI 扩写。')
    elif intro_actual < round(intro_target * 0.85):
        story_data['introduction_notes'].append('当前自我介绍短于1分钟建议长度，可以使用下方时长工具重新生成。')
    with connection() as db:
        cur = db.execute('INSERT INTO stories(jd_id,data,match_data,mode,created_at) VALUES (?,?,?,?,?)', (
            jd['id'], json.dumps(story_data, ensure_ascii=False),
            json.dumps(matched.model_dump(), ensure_ascii=False), ai.mode(), utc_now(),
        ))
        record_id = cur.lastrowid
    return required('stories', record_id)


@app.get('/api/stories')
def list_stories():
    return [decode(r) for r in all_rows('stories')]


@app.get('/api/stories/{story_id}')
def get_story(story_id: int):
    return required('stories', story_id)


@app.post('/api/stories/{story_id}/introduction')
async def regenerate_introduction(story_id: int, body: IntroductionInput):
    story = required('stories', story_id)
    jd = required('jds', story['jd_id'])
    confirmed = [decode(row) for row in all_rows('experiences') if row['status'] == 'confirmed']
    if not confirmed:
        raise HTTPException(400, detail='请先确认至少一条真实经历，再生成自我介绍。')

    result = await agent_call(
        'self_introduction', ai.generate_introduction,
        jd, confirmed, story['data'], story.get('match_data') or {}, body.duration_minutes,
    )
    target_chars = round(float(body.duration_minutes) * 230)
    actual_chars = ai.count_spoken_chars(result.introduction)
    story_data = dict(story['data'])
    notes = list(result.notes)
    if any(exp.get('source') == 'demo' for exp in confirmed):
        notes.append('经历库中包含示例数据，请勿将示例内容直接用于真实面试。')
    story_data.update({
        'introduction': result.introduction,
        'introduction_minutes': float(body.duration_minutes),
        'introduction_target_chars': target_chars,
        'introduction_actual_chars': actual_chars,
        'introduction_mode': ai.mode(),
        'introduction_notes': list(dict.fromkeys(notes)),
    })
    with connection() as db:
        db.execute('UPDATE stories SET data=? WHERE id=?', (json.dumps(story_data, ensure_ascii=False), story_id))
    return required('stories', story_id)


class InterviewStart(BaseModel):
    story_id: int


class InterviewQuickStart(BaseModel):
    jd_id: int


@app.post('/api/interviews/quick-start', status_code=201)
def quick_start_interview(body: InterviewQuickStart):
    """Start interview from confirmed facts, without waiting for story/model generation.

    The outline is explicitly a rule-based draft; AI follow-up still uses the
    configured model when the user submits an interview answer.
    """
    jd = required('jds', body.jd_id)
    confirmed = [decode(row) for row in all_rows('experiences') if row['status'] == 'confirmed']
    if not confirmed:
        raise HTTPException(400, detail='请先在「认识你」中确认至少一条真实经历。')
    matched = ai.demo_match(jd, confirmed)
    outline = ai.demo_story(jd, confirmed, matched)
    outline.cautions.append('这是从已确认经历快速整理的规则草稿，尚未经过深度 AI 职业叙事分析。')
    questions = outline.interview_questions or ['请结合一个真实项目介绍你的个人贡献。']
    now = utc_now()
    with connection() as db:
        outline_data = outline.model_dump()
        outline_data.update({
            'introduction_minutes': 1,
            'introduction_target_chars': 230,
            'introduction_actual_chars': ai.count_spoken_chars(outline.introduction),
            'introduction_mode': 'demo',
            'introduction_notes': ['快速开始生成的是规则提纲；可使用下方时长工具调用 AI 生成完整口语稿。'],
        })
        cursor = db.execute(
            'INSERT INTO stories(jd_id,data,match_data,mode,created_at) VALUES (?,?,?,?,?)',
            (jd['id'], json.dumps(outline_data, ensure_ascii=False),
             json.dumps(matched.model_dump(), ensure_ascii=False), 'demo', now),
        )
        story_id = cursor.lastrowid
        cursor = db.execute(
            'INSERT INTO interviews(story_id,messages,created_at) VALUES (?,?,?)',
            (story_id, json.dumps([{'role': 'assistant', 'content': questions[0], 'feedback': None}], ensure_ascii=False), now),
        )
        interview_id = cursor.lastrowid
    return {'story_id': story_id, 'interview_id': interview_id, 'preparation_mode': 'rule_based'}


@app.post('/api/interviews', status_code=201)
def start_interview(body: InterviewStart):
    story = required('stories', body.story_id)
    questions = story['data'].get('interview_questions') or ['请介绍一个最能代表你能力的项目，以及你自己的贡献。']
    messages = [{'role': 'assistant', 'content': questions[0], 'feedback': None}]
    with connection() as db:
        cur = db.execute('INSERT INTO interviews(story_id,messages,created_at) VALUES (?,?,?)', (
            body.story_id, json.dumps(messages, ensure_ascii=False), utc_now(),
        ))
        record_id = cur.lastrowid
    return required('interviews', record_id)


@app.get('/api/interviews')
def list_interviews():
    return [decode(row) for row in all_rows('interviews')]


@app.get('/api/interviews/{interview_id}')
def get_interview(interview_id: int):
    return required('interviews', interview_id)


@app.post('/api/interviews/{interview_id}/reply')
async def reply_interview(interview_id: int, body: AnswerInput):
    interview = required('interviews', interview_id)
    story = required('stories', interview['story_id'])
    messages = interview['messages']
    result = await agent_call('interview', ai.interview_reply, story, messages, body.answer)
    messages = [*messages, {'role': 'user', 'content': body.answer}, {
        'role': 'assistant', 'content': result.next_question,
        'feedback': {'summary': result.feedback, 'strengths': result.strengths, 'improvements': result.improvements},
    }]
    with connection() as db:
        db.execute('UPDATE interviews SET messages=? WHERE id=?', (json.dumps(messages, ensure_ascii=False), interview_id))
    return required('interviews', interview_id)


@app.post('/api/demo/seed')
def seed_demo():
    if all_rows('experiences') or all_rows('jds'):
        raise HTTPException(409, detail='已有数据。示例数据只能载入空白工作区，避免污染真实经历。')
    samples = [
        dict(title='供应商风险智能感知系统', organization='示例｜企业实习', period='示例经历', background='供应商风险信息分散，需要辅助业务人员查找参考依据。', task='参与风险感知产品方案梳理。', actions='访谈业务使用场景，梳理风险识别流程，参与RAG检索增强方案和页面原型设计。', methods='需求分析、业务流程图、RAG方案讨论、产品原型', results='完成产品需求与方案草稿；未提供上线效果数据。', evidence='仅为示例内容，非真实用户经历。', skills=['需求分析', 'RAG', '产品规划']),
        dict(title='AI 数字宠物与3D家园产品', organization='示例｜个人项目', period='示例经历', background='宠物成长记录缺乏情感化的数字呈现。', task='规划用户价值与交互流程。', actions='设计宠物创建、成长档案和家园交互的用户流程，绘制产品原型。', methods='用户旅程、竞品分析、原型设计', results='形成PRD和可交互原型，暂未验证实际增长指标。', evidence='仅为示例内容，非真实用户经历。', skills=['用户研究', '原型', 'AI产品']),
        dict(title='数据分析与库存优化', organization='示例｜研究项目', period='示例经历', background='需要在业务约束下寻找更合理的库存方案。', task='搭建可验证的数据分析与优化流程。', actions='整理输入数据，建立约束模型并编写测试验证。', methods='Python、数据分析、优化建模', results='完成数据处理与模型测试；无业务上线结果。', evidence='仅为示例内容，非真实用户经历。', skills=['数据分析', 'Python', '建模']),
    ]
    now = utc_now()
    with connection() as db:
        for e in samples:
            db.execute('''INSERT INTO experiences (title,organization,period,background,task,actions,methods,results,evidence,skills,status,source,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (e['title'], e['organization'], e['period'], e['background'], e['task'], e['actions'], e['methods'], e['results'], e['evidence'], json.dumps(e['skills'], ensure_ascii=False), 'confirmed', 'demo', now, now))
        jd_text = 'AI产品经理实习生：负责用户需求分析、PRD和产品原型；理解大模型AI应用与RAG技术；具备数据分析能力，能够跨团队协作推进方案。'
        parsed = ai.demo_jd(jd_text)
        cur = db.execute('INSERT INTO jds(title,company,raw_text,requirements,mode,created_at) VALUES (?,?,?,?,?,?)', (
            'AI 产品经理实习生', '示例公司', jd_text, json.dumps([x.model_dump() for x in parsed.requirements], ensure_ascii=False), 'demo', now,
        ))
        jd_id = cur.lastrowid
    return {'ok': True, 'jd_id': jd_id, 'experience_count': len(samples)}


@app.get('/api/export')
def export_all():
    if os.getenv('RENDER') or os.getenv('DISABLE_ADMIN_ENDPOINTS') == '1':
        raise HTTPException(403, detail='公开部署环境不允许批量导出数据。')
    return {name: [decode(row) for row in all_rows(name)] for name in ('experiences', 'jds', 'stories', 'interviews')}


@app.delete('/api/data')
def delete_all():
    if os.getenv('RENDER') or os.getenv('DISABLE_ADMIN_ENDPOINTS') == '1':
        raise HTTPException(403, detail='公开部署环境不允许清空全部数据。')
    with connection() as db:
        for name in ('interviews', 'stories', 'jds', 'experiences', 'agent_runs'):
            db.execute(f'DELETE FROM {name}')
    return {'ok': True}
