import http from './http'

export interface ReportQuery {
  from?: string
  to?: string
}

export interface DashboardSummary {
  total_leads: number
  distinct_companies: number
  pending: number
  valid: number
  handed_off: number
  no_feedback: number
  won: number
  phone_total: number
  wechat_count: number
  pending_to_confirm: number
  valid_not_handed_off: number
  handed_off_no_feedback: number
  todos: TodoCounts
  todo_list: TodoItem[]
  recent_leads: RecentLead[]
  recent_events?: RecentEvent[]
}

export interface TodoCounts {
  overdue: number
  first_follow: number
  today: number
  no_progress: number
  stale: number
  handed_off_pending: number
}

export interface TodoItem {
  lead_id: string
  company_name_raw: string | null
  contact_name_raw: string | null
  qualification_status: string
  outcome_status: string
  follow_up_count: number
  last_followup_at: string | null
  next_follow_up_at: string | null
  todo: string
}

export interface RecentLead {
  id: string
  company_name_raw: string | null
  contact_name_raw: string | null
  occurred_at: string
  qualification_status: string
}

export interface RecentEvent {
  event_type: string
  occurred_at: string
  actor_name: string
}

export interface TrendBucket {
  date: string
  leads: number
  valid: number
  handed_off: number
}

export interface DashboardTrend {
  buckets: TrendBucket[]
}

export interface ReportOverview {
  total_leads: number
  distinct_companies: number
  valid: number
  invalid: number
  pending: number
  effective_rate: number | null
  handed_off: number
  outcome_won: number
  outcome_lost: number
  outcome_in_progress: number
  no_feedback: number
}

export interface SourceStat {
  category_id: string
  category_name: string
  lead_count: number
  valid_count: number
  handed_off_count: number
}

export interface ActivityStat {
  user_id: string
  display_name: string
  total: number
  phone_total: number
}

export interface HandoffStat {
  department: string
  count: number
}

export async function getDashboardSummary(params: ReportQuery): Promise<DashboardSummary> {
  const { data } = await http.get<DashboardSummary>('/dashboard/summary', { params })
  return data
}

export async function getDashboardTrend(params: ReportQuery): Promise<DashboardTrend> {
  const { data } = await http.get<DashboardTrend>('/dashboard/trend', { params })
  return data
}

export async function getReportsOverview(params: ReportQuery): Promise<ReportOverview> {
  const { data } = await http.get<ReportOverview>('/reports/overview', { params })
  return data
}

export async function getReportsSources(params: ReportQuery): Promise<SourceStat[]> {
  const { data } = await http.get<SourceStat[]>('/reports/sources', { params })
  return data
}

export async function getReportsActivities(params: ReportQuery): Promise<ActivityStat[]> {
  const { data } = await http.get<ActivityStat[]>('/reports/activities', { params })
  return data
}

export async function getReportsHandoffs(params: ReportQuery): Promise<HandoffStat[]> {
  const { data } = await http.get<HandoffStat[]>('/reports/handoffs', { params })
  return data
}

export async function exportReports(params: ReportQuery): Promise<Blob> {
  const { data } = await http.get<Blob>('/reports/export', { params, responseType: 'blob' })
  return data
}
