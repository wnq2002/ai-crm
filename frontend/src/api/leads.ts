import http from './http'
import type { Company, Lead, LeadListItem, Page } from '@/types'

export interface LeadListQuery {
  q?: string
  qualification_status?: string
  handoff_status?: string
  outcome_status?: string
  source_category_id?: string
  source_detail_id?: string
  need_type_id?: string
  department_id?: string
  occurred_from?: string
  occurred_to?: string
  archived?: boolean
  todo?: string
  page?: number
  page_size?: number
  sort?: string
}

export interface LeadCreatePayload {
  occurred_at?: string
  contact_name_raw?: string
  phone_raw?: string
  email_raw?: string
  wechat_raw?: string
  company_name_raw?: string
  need_type_id?: string
  inquiry_text?: string
  source_category_id?: string
  source_detail_id?: string
  source_detail_text?: string
  notes?: string
  intake_method?: string
  external_source_event_id?: string
  idempotency_key?: string
  parse_record?: { raw_text: string; parsed_json?: Record<string, unknown> }
}

export interface ExtractedField {
  value: string | null
  confidence: string | null
}

export interface LeadParseResult {
  company_name: ExtractedField
  contact_name: ExtractedField
  phone: ExtractedField
  email: ExtractedField
  inquiry_text: ExtractedField
  need_type: ExtractedField
  source_channel: ExtractedField
  hints: string[]
}

export async function parseLead(rawText: string): Promise<LeadParseResult> {
  const { data } = await http.post<LeadParseResult>('/leads/parse', { raw_text: rawText })
  return data
}

export interface LeadCreateResult {
  lead: Lead
  company_candidates: Company[]
}

export interface LeadUpdatePayload {
  version: number
  occurred_at?: string
  contact_name_raw?: string
  phone_raw?: string
  email_raw?: string
  wechat_raw?: string
  company_name_raw?: string
  need_type_id?: string
  inquiry_text?: string
  source_category_id?: string
  source_detail_id?: string
  source_detail_text?: string
  notes?: string
}

export interface TimelineEvent {
  id: string
  type: string
  result?: string | null
  content?: string | null
  happened_at?: string
  recorded_at?: string
  created_by: string
  created_by_name?: string | null
}

export async function listLeads(params: LeadListQuery): Promise<Page<LeadListItem>> {
  const { data } = await http.get<Page<LeadListItem>>('/leads', { params })
  return data
}

export async function createLead(payload: LeadCreatePayload): Promise<LeadCreateResult> {
  const { data } = await http.post<LeadCreateResult>('/leads', payload)
  return data
}

export async function getLead(id: string): Promise<Lead> {
  const { data } = await http.get<Lead>(`/leads/${id}`)
  return data
}

export async function updateLead(id: string, payload: LeadUpdatePayload): Promise<Lead> {
  const { data } = await http.patch<Lead>(`/leads/${id}`, payload)
  return data
}

export async function archiveLead(id: string): Promise<void> {
  await http.post(`/leads/${id}/archive`)
}

export async function unarchiveLead(id: string): Promise<Lead> {
  const { data } = await http.post<Lead>(`/leads/${id}/unarchive`)
  return data
}

export async function getLeadTimeline(id: string): Promise<TimelineEvent[]> {
  const { data } = await http.get<TimelineEvent[]>(`/leads/${id}/timeline`)
  return data
}

export async function getCompanyCandidates(id: string): Promise<Company[]> {
  const { data } = await http.get<Company[]>(`/leads/${id}/company-candidates`)
  return data
}

export async function linkCompany(leadId: string, companyId: string): Promise<Lead> {
  const { data } = await http.post<Lead>(`/leads/${leadId}/link-company`, { company_id: companyId })
  return data
}

export async function unlinkCompany(leadId: string): Promise<Lead> {
  const { data } = await http.delete<Lead>(`/leads/${leadId}/company-link`)
  return data
}

export interface QualificationPayload {
  qualification_status: 'valid' | 'invalid'
  reason?: string
}

export interface HandoffPayload {
  department_id: string
  department_contact_id?: string
  note?: string
}

export interface OutcomePayload {
  outcome_status: 'in_progress' | 'won' | 'lost' | 'deferred'
  note?: string
  feedback_at?: string
}

export async function setQualification(
  leadId: string,
  payload: QualificationPayload,
): Promise<Lead> {
  const { data } = await http.post<Lead>(`/leads/${leadId}/qualification`, payload)
  return data
}

export async function setHandoff(leadId: string, payload: HandoffPayload): Promise<Lead> {
  const { data } = await http.post<Lead>(`/leads/${leadId}/handoff`, payload)
  return data
}

export async function setOutcome(leadId: string, payload: OutcomePayload): Promise<Lead> {
  const { data } = await http.post<Lead>(`/leads/${leadId}/outcome`, payload)
  return data
}
