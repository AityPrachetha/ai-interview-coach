// Mirrors app/schemas.py on the backend. Keep field names identical -
// these are not renamed/camelCased so a diff against the backend schema
// stays easy.

export type InterviewType = 'HR' | 'TECHNICAL' | 'BEHAVIORAL';

export type InterviewStatus = 'CREATED' | 'QUESTIONS_READY' | 'IN_PROGRESS' | 'COMPLETED';

export interface UserOut {
  id: string;
  email: string;
  full_name: string | null;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface ResumeOut {
  id: string;
  original_filename: string | null;
  extracted_skills: Record<string, unknown> | null;
  created_at: string;
}

export interface JobDescriptionOut {
  id: string;
  title: string | null;
  company: string | null;
  extracted_requirements: Record<string, unknown> | null;
  created_at: string;
}

export interface QuestionOut {
  id: string;
  text: string;
  order_index: number;
  topic: string | null;
  is_followup: number;
}

export interface InterviewSessionOut {
  id: string;
  interview_type: InterviewType;
  status: InterviewStatus;
  resume_match_score: number | null;
  skill_match_details: Record<string, unknown> | null;
  questions: QuestionOut[];
  created_at: string;
}

export interface NextQuestionOut {
  completed: boolean;
  question: QuestionOut | null;
  session_status: InterviewStatus;
}

export interface StarScore {
  situation?: number;
  task?: number;
  action?: number;
  result?: number;
}

export interface AnswerOut {
  id: string;
  question_id: string;
  transcript: string | null;
  relevance_score: number | null;
  star_score: StarScore | null;
  created_at: string;
  strengths: string[];
  weaknesses: string[];
  session_status: InterviewStatus;
  followup_generated: boolean;
  next_question: QuestionOut | null;
  speaking_pace_wpm: number | null;
  filler_word_count: number | null;
  voice_confidence_score: number | null;
  eye_contact_score: number | null;
  facial_expression_score: number | null;
  posture_score: number | null;
}

export interface FrameAnalysisOut {
  face_detected: boolean;
  eye_contact_score: number | null;
  facial_expression_score: number | null;
  posture_score: number | null;
}

export interface QuestionAnswerSummary {
  question_id: string;
  question_text: string;
  topic: string | null;
  is_followup: boolean;
  transcript: string | null;
  relevance_score: number | null;
  star_score: StarScore | null;
  speaking_pace_wpm: number | null;
  filler_word_count: number | null;
  voice_confidence_score: number | null;
  eye_contact_score: number | null;
  facial_expression_score: number | null;
  posture_score: number | null;
}

export interface ImprovementSuggestion {
  area: string;
  suggestion: string;
}

export interface InterviewReportOut {
  session_id: string;
  session_status: InterviewStatus;
  is_preliminary: boolean;
  questions_answered: number;
  total_questions: number;
  weight_coverage: number;
  communication_score: number | null;
  confidence_score: number | null;
  technical_score: number | null;
  behavioral_score: number | null;
  resume_match_score: number | null;
  hiring_readiness_score: number | null;
  improvement_suggestions: ImprovementSuggestion[];
  questions: QuestionAnswerSummary[];
}
