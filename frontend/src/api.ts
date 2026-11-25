
import type {
  Experience,
  ExperiencePayload,
  JD,
  Interview,
  Story,
  ResumeV3Preview,
  ResumeV3Edit
} from './types';

// GitHub Pages connects to Render.
// Local development continues using the existing Vite /api proxy.
const API_BASE =
  window.location.hostname === 'abcc442.github.io'
    ? 'https://career-story-agent.onrender.com'
    : '';

const apiUrl = (path: string): string =>
  `${API_BASE}/api${path}`;

async function request<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(apiUrl(path), {
      ...init,
      headers:
        init?.body instanceof FormData
          ? undefined
          : {
              'Content-Type': 'application/json',
              ...init?.headers
            }
    });
  } catch (err) {
    if (
      err instanceof Error &&
      (err.name === 'TimeoutError' ||
        err.name === 'AbortError')
    ) {
      throw new Error(
        '职业主线生成等待超时。可以在「面试准备」直接开始练习，不必等待 AI 故事。'
      );
    }

    throw new Error(
      '无法连接后端。线上请检查 Render 服务状态及跨域配置；本地请启动 FastAPI（127.0.0.1:8000）。'
    );
  }

  if (!response.ok) {
    let message = `请求失败 (${response.status})`;

    try {
      const body = await response.json();
      message =
        typeof body.detail === 'string'
          ? body.detail
          : message;
    } catch {
      // Keep the fallback message.
    }

    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

const json = (value: unknown) => JSON.stringify(value);

export const api = {
  meta: () =>
    request<{
      mode: 'ai' | 'demo';
      model: string | null;
    }>('/meta'),

  experiences: () =>
    request<Experience[]>('/experiences'),

  createExperience: (body: ExperiencePayload) =>
    request<Experience>('/experiences', {
      method: 'POST',
      body: json(body)
    }),

  saveExperience: (
    id: number,
    body: ExperiencePayload
  ) =>
    request<Experience>(`/experiences/${id}`, {
      method: 'PUT',
      body: json(body)
    }),

  deleteExperience: (id: number) =>
    request<void>(`/experiences/${id}`, {
      method: 'DELETE'
    }),

  tailorResume: (
    file: File,
    jd: {
      title: string;
      company: string;
      raw_text: string;
    }
  ) => {
    const body = new FormData();

    body.append('file', file);
    body.append('jd_title', jd.title);
    body.append('jd_company', jd.company);
    body.append('jd_text', jd.raw_text);

    return fetch(apiUrl('/resumes/tailor'), {
      method: 'POST',
      body
    }).then(async response => {
      if (!response.ok) {
        let message = `请求失败 (${response.status})`;

        try {
          const data = await response.json();
          if (typeof data.detail === 'string') {
            message = data.detail;
          }
        } catch {
          // Keep fallback message.
        }

        throw new Error(message);
      }

      return {
        blob: await response.blob(),
        editCount: Number(
          response.headers.get('X-Resume-Edit-Count') || 0
        )
      };
    });
  },

  previewTailoredResume: (
    file: File,
    jd: JD,
    useConfirmed: boolean
  ) => {
    const body = new FormData();

    body.append('file', file);
    body.append('jd_id', String(jd.id));
    body.append('use_confirmed', String(useConfirmed));

    return request<ResumeV3Preview>(
      '/resumes/tailor/preview',
      {
        method: 'POST',
        body
      }
    );
  },

  applyTailoredResume: async (
    file: File,
    jd: JD,
    edits: ResumeV3Edit[]
  ) => {
    const body = new FormData();

    body.append('file', file);
    body.append('jd_id', String(jd.id));

    body.append(
      'edits_json',
      JSON.stringify(
        edits.map(
          ({
            paragraph_id,
            original_text,
            revised_text,
            reason,
            source_experience_ids,
            matched_requirements
          }) => ({
            paragraph_id,
            original_text,
            revised_text,
            reason,
            source_experience_ids,
            matched_requirements
          })
        )
      )
    );

    let response: Response;

    try {
      response = await fetch(
        apiUrl('/resumes/tailor/apply'),
        {
          method: 'POST',
          body
        }
      );
    } catch {
      throw new Error(
        '无法连接后端。线上请检查 Render 服务状态；本地请确认 FastAPI 已启动。'
      );
    }

    if (!response.ok) {
      let message = `请求失败 (${response.status})`;

      try {
        const result = await response.json();

        if (typeof result.detail === 'string') {
          message = result.detail;
        }
      } catch {
        // Keep fallback message.
      }

      throw new Error(message);
    }

    return {
      blob: await response.blob(),
      editCount: Number(
        response.headers.get('X-Resume-Edit-Count') ||
          edits.length
      )
    };
  },

  readResume: (file: File) => {
    const body = new FormData();
    body.append('file', file);

    return request<{
      text: string;
      filename: string;
      truncated: boolean;
    }>('/resumes/read', {
      method: 'POST',
      body
    });
  },

  extract: (text: string) =>
    request<{
      experiences: ExperiencePayload[];
      note: string;
      mode: string;
    }>('/experiences/extract', {
      method: 'POST',
      body: json({ text })
    }),

  question: (id: number) =>
    request<{
      question: string;
      reason: string;
    }>(`/experiences/${id}/question`, {
      method: 'POST'
    }),

  propose: (id: number, answer: string) =>
    request<{
      field: keyof ExperiencePayload;
      proposed_value: string;
      reason: string;
    }>(`/experiences/${id}/answer`, {
      method: 'POST',
      body: json({ answer })
    }),

  jds: () =>
    request<JD[]>('/jds'),

  createJD: (body: {
    title: string;
    company: string;
    raw_text: string;
  }) =>
    request<JD>('/jds', {
      method: 'POST',
      body: json(body)
    }),

  stories: () =>
    request<Story[]>('/stories'),

  generate: (jd_id: number) =>
    request<Story>('/stories/generate', {
      method: 'POST',
      body: json({ jd_id }),
      signal: AbortSignal.timeout(45000)
    }),

  generateIntroduction: (
    story_id: number,
    duration_minutes: number
  ) =>
    request<Story>(
      `/stories/${story_id}/introduction`,
      {
        method: 'POST',
        body: json({ duration_minutes }),
        signal: AbortSignal.timeout(90000)
      }
    ),

  interviews: () =>
    request<Interview[]>('/interviews'),

  startInterview: (story_id: number) =>
    request<Interview>('/interviews', {
      method: 'POST',
      body: json({ story_id })
    }),

  quickStartInterview: (jd_id: number) =>
    request<{
      story_id: number;
      interview_id: number;
      preparation_mode: string;
    }>('/interviews/quick-start', {
      method: 'POST',
      body: json({ jd_id })
    }),

  replyInterview: (
    id: number,
    answer: string
  ) =>
    request<Interview>(`/interviews/${id}/reply`, {
      method: 'POST',
      body: json({ answer })
    }),

  seed: () =>
    request<{
      ok: boolean;
      jd_id: number;
    }>('/demo/seed', {
      method: 'POST'
    }),

  export: () =>
    request<unknown>('/export'),

  clear: () =>
    request('/data', {
      method: 'DELETE'
    })
};
