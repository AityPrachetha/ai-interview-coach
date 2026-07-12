import type {
  UserOut,
  Token,
  ResumeOut,
  JobDescriptionOut,
  InterviewSessionOut,
  NextQuestionOut,
  AnswerOut,
  FrameAnalysisOut,
  InterviewReportOut,
  InterviewType,
} from './types';

const API_BASE = import.meta.env.VITE_API_BASE_URL;
const TOKEN_KEY = 'interview_coach_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: {
    method?: string;
    body?: unknown;
    form?: FormData;
    auth?: boolean;
  } = {},
): Promise<T> {
  const { method = 'GET', body, form, auth = true } = options;
  const headers: Record<string, string> = {};

  if (auth) {
    const token = getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
  }

  let fetchBody: BodyInit | undefined;
  if (form) {
    fetchBody = form; // browser sets multipart Content-Type + boundary itself
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    fetchBody = JSON.stringify(body);
  }

  const res = await fetch(`${API_BASE}${path}`, { method, headers, body: fetchBody });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const parsed = await res.json();
      detail = parsed.detail ?? detail;
    } catch {
      // response wasn't JSON - fall back to statusText
    }
    throw new ApiError(res.status, typeof detail === 'string' ? detail : JSON.stringify(detail));
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ---------- Auth ----------

export function signup(email: string, password: string, fullName: string): Promise<UserOut> {
  return request('/auth/signup', {
    method: 'POST',
    body: { email, password, full_name: fullName || null },
    auth: false,
  });
}

export function login(email: string, password: string): Promise<Token> {
  return request('/auth/login', {
    method: 'POST',
    body: { email, password },
    auth: false,
  });
}

// ---------- Resume ----------

export function uploadResume(file: File): Promise<ResumeOut> {
  const form = new FormData();
  form.append('file', file);
  return request('/resumes', { method: 'POST', form });
}

// ---------- Job description ----------

export function createJobDescription(payload: {
  title: string;
  company: string;
  raw_text: string;
}): Promise<JobDescriptionOut> {
  return request('/job-descriptions', { method: 'POST', body: payload });
}

// ---------- Interview session ----------

export function createInterview(payload: {
  resume_id: string;
  job_description_id: string;
  interview_type: InterviewType;
}): Promise<InterviewSessionOut> {
  return request('/interviews', { method: 'POST', body: payload });
}

export function getInterview(sessionId: string): Promise<InterviewSessionOut> {
  return request(`/interviews/${sessionId}`);
}

export function getNextQuestion(sessionId: string): Promise<NextQuestionOut> {
  return request(`/interviews/${sessionId}/next-question`);
}

export function submitAnswerText(
  sessionId: string,
  questionId: string,
  transcript: string,
): Promise<AnswerOut> {
  return request(`/interviews/${sessionId}/answers`, {
    method: 'POST',
    body: { question_id: questionId, transcript },
  });
}

export function submitAnswerAudio(
  sessionId: string,
  questionId: string,
  audioBlob: Blob,
): Promise<AnswerOut> {
  const form = new FormData();
  form.append('question_id', questionId);
  form.append('audio', audioBlob, 'answer.webm');
  return request(`/interviews/${sessionId}/answers/audio`, { method: 'POST', form });
}

export function submitFrame(
  sessionId: string,
  questionId: string,
  frameBlob: Blob,
): Promise<FrameAnalysisOut> {
  const form = new FormData();
  form.append('frame', frameBlob, 'frame.jpg');
  return request(`/interviews/${sessionId}/questions/${questionId}/frames`, {
    method: 'POST',
    form,
  });
}

export function getReport(sessionId: string, recompute = false): Promise<InterviewReportOut> {
  return request(`/interviews/${sessionId}/report${recompute ? '?recompute=true' : ''}`);
}
