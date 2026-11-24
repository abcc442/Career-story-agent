"""Typed outputs act as constraints on agent reasoning and API responses."""
from typing import Literal
from pydantic import BaseModel, Field


class ExperienceInput(BaseModel):
    experience_type: Literal['internship', 'work', 'project', 'research', 'competition', 'campus', 'other'] = 'other'
    parent_experience_id: int | None = None
    title: str = Field(min_length=1, max_length=180)
    organization: str = Field(default='', max_length=180)
    period: str = Field(default='', max_length=100)
    background: str = Field(default='', max_length=4000)
    task: str = Field(default='', max_length=4000)
    actions: str = Field(default='', max_length=6000)
    methods: str = Field(default='', max_length=4000)
    results: str = Field(default='', max_length=4000)
    evidence: str = Field(default='', max_length=3000)
    skills: list[str] = Field(default_factory=list, max_length=15)
    status: Literal['draft', 'confirmed'] = 'draft'


class ExperienceExtract(BaseModel):
    experience_type: Literal['internship', 'work', 'project', 'research', 'competition', 'campus', 'other'] = 'other'
    parent_experience_id: int | None = None
    title: str
    organization: str = ''
    period: str = ''
    background: str = ''
    task: str = ''
    actions: str = ''
    methods: str = ''
    results: str = ''
    evidence: str = ''
    skills: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    experiences: list[ExperienceExtract] = Field(default_factory=list)
    note: str = ''


class FollowupResult(BaseModel):
    question: str
    reason: str


class AnswerProposal(BaseModel):
    field: Literal['background', 'task', 'actions', 'methods', 'results', 'evidence']
    proposed_value: str
    reason: str


class JDRequirement(BaseModel):
    label: str
    priority: Literal['核心', '重要', '加分'] = '重要'
    meaning: str = ''


class JDAnalysis(BaseModel):
    requirements: list[JDRequirement]


class MatchItem(BaseModel):
    requirement: str
    level: Literal['strong', 'partial', 'gap']
    experience_ids: list[int] = Field(default_factory=list)
    evidence: str = ''
    reason: str = ''


class MatchResult(BaseModel):
    items: list[MatchItem]
    priority_ids: list[int]
    gaps: list[str] = Field(default_factory=list)


class StoryHighlight(BaseModel):
    experience_id: int
    role: str
    reason: str
    resume_bullets: list[str]
    interview_angle: str


class StoryResult(BaseModel):
    headline: str
    positioning: str
    narrative: str
    highlights: list[StoryHighlight]
    introduction: str
    interview_questions: list[str]
    cautions: list[str] = Field(default_factory=list)


class IntroductionInput(BaseModel):
    duration_minutes: float = Field(default=1, ge=1, le=10)


class IntroductionResult(BaseModel):
    introduction: str = Field(min_length=20, max_length=6000)
    notes: list[str] = Field(default_factory=list, max_length=8)


class InterviewFeedback(BaseModel):
    feedback: str
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    next_question: str


class JDInput(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    company: str = Field(default='', max_length=180)
    raw_text: str = Field(min_length=10, max_length=12000)


class TextInput(BaseModel):
    text: str = Field(min_length=10, max_length=25000)


class AnswerInput(BaseModel):
    answer: str = Field(min_length=2, max_length=4000)


class GenerateInput(BaseModel):
    jd_id: int



class ResumeParagraphEdit(BaseModel):
    paragraph_id: int = Field(ge=0)
    original_text: str
    revised_text: str
    reason: str = ''
    source_experience_ids: list[int] = Field(default_factory=list)
    matched_requirements: list[str] = Field(default_factory=list)


class ResumeTailorResult(BaseModel):
    target_title: str
    edits: list[ResumeParagraphEdit] = Field(default_factory=list)
    review_notes: list[str] = Field(default_factory=list)
