import request from './request'

export interface DataCenterSection {
  total: number
  by_status: Record<string, number>
}

export interface DataCenterOverview {
  workspace_id: string
  assets: DataCenterSection
  knowledge: DataCenterSection
  research: DataCenterSection
  agents: DataCenterSection
  content_drafts: DataCenterSection
  content_performance: {
    publish_count: number
    impressions: number
    clicks: number
    likes: number
    comments: number
    shares: number
    click_through_rate: number
  }
  health: Record<string, number>
}

export const dataCenterApi = {
  overview: (workspaceId: string) => request.get<any, DataCenterOverview>('/api/v1/data-center/overview', { params: { workspace_id: workspaceId } })
}
