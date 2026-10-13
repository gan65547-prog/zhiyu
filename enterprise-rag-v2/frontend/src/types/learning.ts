export interface LearningDiagnosisRequest {
  question_text: string
  kp_code?: string | null
  subject_info?: string | null
  subject_id?: string | null
  textbook_version_id?: string | null
  grade_level?: string | null
  error_tags?: string[] | null
  original_images?: string[] | null
  original_answer?: string | null
}

export interface StageInfo {
  stage: number
  name: string
  status: 'pending' | 'running' | 'done' | 'error'
  data?: any
  elapsed_ms?: number | null
}

export interface LearningDiagnosisReport {
  id: string
  user_id: string
  subject_id: string
  question_text: string
  error_tags: string[]
  weak_knowledge_points: Array<{
    kp_id: string
    name: string
    difficulty: number
    confidence: number
  }>
  error_analysis: any[]
  stage_results: Record<string, StageInfo>
  report_content: any
  overall_mastery_score: number | null
  rating: string | null
  feedback: string | null
  created_at: string
  updated_at: string
}

export interface LearningDiagnosisReportListItem {
  id: string
  subject_id: string
  grade_level: string | null
  question_text: string
  overall_mastery_score: number | null
  weak_knowledge_points: any[]
  rating: string | null
  created_at: string
}

export interface LearningDiagnosisFeedback {
  report_id: string
  rating: 'useful' | 'useless'
  feedback?: string | null
}

// SSE event types (复用现有 SSE 协议)
export interface SSEStageEvent {
  stage: number
  name: string
  status: string
}

export interface SSEProgressEvent {
  percent: number
}

export interface SSEContentEvent {
  section: string
  text: string
}

export interface SSESourcesEvent {
  documents: Array<{ content: string; score?: number; title?: string }>
}

export interface PracticeSession {
  id: string
  diagnosis_report_id: string
  knowledge_point_ids: string[]
  exercises: PracticeExercise[]
  answers_submitted: Array<{ idx: number; answer: string; correct: boolean; submitted_at: string }>
  exercises_completed: number
  exercises_correct: number
  mastery_before: number | null
  mastery_after: number | null
  status: 'generated' | 'in_progress' | 'completed' | 'verified' | 'regenerated'
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface PracticeExercise {
  idx: number
  question: string
  answer: string
  hints: string[]
  kp_name: string
  difficulty: 'easy' | 'medium' | 'hard'
}

export interface PracticeAnswerResult {
  correct: boolean
  correct_answer: string
  encouragement: string
  exercises_completed: number
  exercises_correct: number
  status: string
}
