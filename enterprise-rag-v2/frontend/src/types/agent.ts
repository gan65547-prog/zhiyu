export interface AgentRunStep {
  id: string
  step_key: string
  step_order: number
  status: string
  output_json: Record<string, unknown>
  error_message?: string | null
}

export interface AgentRun {
  id: string
  research_run_id?: string | null
  definition_id: string
  status: string
  current_step?: string | null
  progress: number
  error_message?: string | null
  retry_count: number
  steps: AgentRunStep[]
  created_at: string
  updated_at: string
}

export interface AgentRunListResponse {
  items: AgentRun[]
  total: number
  page: number
  page_size: number
}

export interface AgentDefinition {
  id: string
  workspace_id: string
  name: string
  agent_type: string
  description?: string | null
  version: number
  workflow: Array<{ key: string; label?: string; tool?: string; input?: Record<string, unknown> }>
  status: string
  created_at: string
  updated_at: string
}

export interface AgentSchedule {
  id: string
  workspace_id: string
  definition_id: string
  project_id: string
  name: string
  schedule_expression: string
  timezone: string
  config_json: Record<string, unknown>
  enabled: boolean
  next_run_at: string
  last_run_at?: string | null
  last_run_id?: string | null
  last_error?: string | null
  created_at: string
  updated_at: string
}

export interface AgentApproval {
  id: string
  agent_run_id: string
  research_run_id?: string | null
  step_id?: string | null
  step_key?: string | null
  status: string
  reviewer_id?: string | null
  comment?: string | null
  created_at: string
  reviewed_at?: string | null
}
export interface AgentEvent { id: string; event_type: string; step_key?: string | null; status: string; title?: string | null; content: Record<string, unknown>; created_at: string }
export interface AgentTool { key: string; label: string; description: string; input_schema: Record<string, string>; requires_approval: boolean; read_only: boolean }
export interface AgentToolExecution { run_id: string; step_key: string; tool: string; status: string; approval_id?: string | null; output: Record<string, unknown> }
