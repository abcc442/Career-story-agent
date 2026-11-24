export type Page = 'home' | 'experiences' | 'jd' | 'interview';
export type Mode = 'ai' | 'demo';

export interface Experience {
  id: number;
  title: string;
  organization: string;
  experience_type: 'internship' | 'work' | 'project' | 'research' | 'competition' | 'campus' | 'other';
  parent_experience_id: number | null;
  period: string;
  background: string;
  task: string;
  actions: string;
  methods: string;
  results: string;
  evidence: string;
  skills: string[];
  status: 'draft' | 'confirmed';
  source: string;
  created_at: string;
  updated_at: string;
}
export type ExperiencePayload = Omit<Experience, 'id' | 'source' | 'created_at' | 'updated_at'>;
export interface Requirement { label: string; priority: '核心' | '重要' | '加分'; meaning: string }
export interface JD { id: number; title: string; company: string; raw_text: string; requirements: Requirement[]; mode: Mode; created_at: string }
export interface Match { requirement: string; level: 'strong' | 'partial' | 'gap'; experience_ids: number[]; evidence: string; reason: string }
export interface StoryHighlight { experience_id: number; role: string; reason: string; resume_bullets: string[]; interview_angle: string }
export interface StoryData {
  headline: string; positioning: string; narrative: string;
  highlights: StoryHighlight[]; introduction: string; interview_questions: string[]; cautions: string[];
  introduction_minutes?: number; introduction_target_chars?: number; introduction_actual_chars?: number;
  introduction_mode?: Mode; introduction_notes?: string[];
}
export interface Story { id: number; jd_id: number; mode: Mode; created_at: string; data: StoryData; match_data: { items: Match[]; priority_ids: number[]; gaps: string[] } }
export interface InterviewMessage { role: 'assistant' | 'user'; content: string; feedback?: {summary: string; strengths: string[]; improvements: string[]} | null }
export interface Interview { id: number; story_id: number; messages: InterviewMessage[]; created_at: string }
export const emptyExperience = (): ExperiencePayload => ({
  title: '', organization: '', experience_type: 'other', parent_experience_id: null, period: '', background: '', task: '', actions: '', methods: '', results: '', evidence: '', skills: [], status: 'draft',
});

export interface ResumeV3Edit {
  paragraph_id: number;
  original_text: string;
  revised_text: string;
  reason: string;
  source_experience_ids: number[];
  source_experiences: {id: number; title: string}[];
  matched_requirements: string[];
}
export interface ResumeV3Preview {
  jd_id: number;
  filename: string;
  confirmed_count: number;
  use_confirmed: boolean;
  match: {items: Match[]; priority_ids: number[]; gaps: string[]} | null;
  edits: ResumeV3Edit[];
  review_notes: string[];
  notice: string;
}
