import request from './request'
import type { AgentApproval, AgentDefinition, AgentEvent, AgentRun, AgentRunListResponse, AgentSchedule, AgentTool, AgentToolExecution } from '@/types/agent'

export const agentApi = {
  listDefinitions: (workspaceId: string) => request.get<any, AgentDefinition[]>('/api/v1/agents', { params: { workspace_id: workspaceId } }),
  listTools: () => request.get<any, AgentTool[]>('/api/v1/agents/tools'),
  createDefinition: (payload: { workspace_id: string; name: string; agent_type: string; description?: string; workflow?: Array<{ key: string; label?: string; tool?: string; input?: Record<string, unknown> }> }) => request.post<any, AgentDefinition>('/api/v1/agents', payload),
  createRun: (payload: { workspace_id: string; definition_id: string; input?: Record<string, unknown>; config?: Record<string, unknown> }) => request.post<any, AgentRun>('/api/v1/agents/runs', payload),
  executeToolStep: (runId: string, stepKey: string, input: Record<string, unknown>) => request.post<any, AgentToolExecution>(`/api/v1/agents/runs/${runId}/steps/${stepKey}/execute`, { input }),
  listRuns: (workspaceId: string) => request.get<any, AgentRunListResponse>('/api/v1/agents/runs', { params: { workspace_id: workspaceId, page: 1, page_size: 100 } }),
  getRun: (runId: string) => request.get<any, AgentRun>(`/api/v1/agents/runs/${runId}`),
  listEvents: (runId: string) => request.get<any, AgentEvent[]>(`/api/v1/agents/runs/${runId}/events`),
  cancelRun: (runId: string) => request.post<any, AgentRun>(`/api/v1/agents/runs/${runId}/cancel`),
  retryRun: (runId: string) => request.post<any, AgentRun>(`/api/v1/agents/runs/${runId}/retry`),
  listSchedules: (workspaceId: string) => request.get<any, AgentSchedule[]>('/api/v1/agents/schedules', { params: { workspace_id: workspaceId } }),
  createSchedule: (payload: { workspace_id: string; definition_id: string; project_id: string; name: string; schedule_expression: string; timezone: string; next_run_at: string }) => request.post<any, AgentSchedule>('/api/v1/agents/schedules', payload),
  enableSchedule: (scheduleId: string) => request.post<any, AgentSchedule>(`/api/v1/agents/schedules/${scheduleId}/enable`),
  disableSchedule: (scheduleId: string) => request.post<any, AgentSchedule>(`/api/v1/agents/schedules/${scheduleId}/disable`),
  listApprovals: (workspaceId: string) => request.get<any, AgentApproval[]>('/api/v1/agents/approvals', { params: { workspace_id: workspaceId, pending_only: true } }),
  reviewApproval: (approvalId: string, status: 'approved' | 'rejected', comment?: string) => request.post<any, AgentApproval>(`/api/v1/agents/approvals/${approvalId}/review`, { status, comment })
}
