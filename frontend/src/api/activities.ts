import http from './http'
import type { ActivityKind, ActivityResult, LeadActivity } from '@/types'

export interface ActivityCreatePayload {
  kind: ActivityKind
  result?: ActivityResult
  content?: string
  happened_at?: string
  next_follow_up_at?: string
  idempotency_key?: string
}

export async function listActivities(leadId: string): Promise<LeadActivity[]> {
  const { data } = await http.get<LeadActivity[]>(`/leads/${leadId}/activities`)
  return data
}

export async function createActivity(
  leadId: string,
  payload: ActivityCreatePayload,
): Promise<LeadActivity> {
  const { data } = await http.post<LeadActivity>(`/leads/${leadId}/activities`, payload)
  return data
}

export async function revokeActivity(activityId: string, reason: string): Promise<LeadActivity> {
  const { data } = await http.post<LeadActivity>(`/activities/${activityId}/revoke`, { reason })
  return data
}

export interface ActivityRevisePayload {
  reason: string
  happened_at?: string
  result?: ActivityResult
  content?: string
}

export async function reviseActivity(
  activityId: string,
  payload: ActivityRevisePayload,
): Promise<LeadActivity> {
  const { data } = await http.patch<LeadActivity>(`/activities/${activityId}`, payload)
  return data
}
