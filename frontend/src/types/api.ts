// 与 docs/api-contract.md §3「通用资源模型与枚举」及 backend/app/schemas 对齐的类型定义。

export type Role = 'admin' | 'market'

export type QualificationStatus = 'pending' | 'valid' | 'invalid'
export type HandoffStatus = 'not_handed_off' | 'handed_off'
export type OutcomeStatus = 'unknown' | 'in_progress' | 'won' | 'lost' | 'deferred'
export type IntakeMethod = 'manual' | 'import' | 'api'
export type WechatRelationship = 'none' | 'pending' | 'approved'
export type ActivityKind =
  | 'phone'
  | 'wechat_request'
  | 'wechat_approved'
  | 'wechat_chat'
  | 'note'
export type ActivityResult = 'connected' | 'unconnected' | 'rejected'

export interface User {
  id: string
  username: string
  display_name: string
  role: Role
  is_active: boolean
  must_change_password: boolean
}

export interface Company {
  id: string
  canonical_name: string
  normalized_name: string
  aliases: string[]
  industry?: string | null
  phone?: string | null
  website?: string | null
  merged_into_id?: string | null
  created_at: string
  updated_at: string
}

export interface Contact {
  id: string
  company_id?: string | null
  name?: string | null
  phone?: string | null
  email?: string | null
  wechat_id?: string | null
  created_at: string
}

export interface SourceCategory {
  id: string
  code: string
  name: string
  active: boolean
}

export interface SourceDetail {
  id: string
  category_id: string
  name: string
  active: boolean
}

export interface NeedType {
  id: string
  name: string
  active: boolean
}

export interface Department {
  id: string
  name: string
  active: boolean
}

export interface DepartmentContact {
  id: string
  department_id: string
  name: string
  active: boolean
  is_default: boolean
}

export interface Lead {
  id: string
  company_id?: string | null
  contact_id?: string | null
  company_name_raw?: string | null
  contact_name_raw?: string | null
  phone_raw?: string | null
  email_raw?: string | null
  wechat_raw?: string | null
  need_type_id?: string | null
  inquiry_text?: string | null
  occurred_at: string
  source_category_id?: string | null
  source_detail_id?: string | null
  source_detail_text?: string | null
  notes?: string | null
  intake_method: IntakeMethod
  external_source_event_id?: string | null
  qualification_status: QualificationStatus
  handoff_status: HandoffStatus
  outcome_status: OutcomeStatus
  phone_total_count: number
  wechat_count: number
  recent_followup_at?: string | null
  wechat_relationship: WechatRelationship
  department_id?: string | null
  department_contact_id?: string | null
  created_by: string
  created_at: string
  updated_at: string
  archived_at?: string | null
  version: number
}

// 线索列表项：不含明文联系方式，由后端提供脱敏 contact_summary（api-contract §4）。
export interface LeadListItem {
  id: string
  occurred_at: string
  company_name_raw?: string | null
  contact_name_raw?: string | null
  contact_summary?: string | null
  need_type_id?: string | null
  inquiry_text?: string | null
  qualification_status: QualificationStatus
  handoff_status: HandoffStatus
  outcome_status: OutcomeStatus
  department_id?: string | null
  department_contact_id?: string | null
  source_category_id?: string | null
  source_detail_id?: string | null
  source_detail_text?: string | null
  recent_followup_at?: string | null
  next_follow_up_at?: string | null
  follow_up_count: number
  follow_up_status: string
  created_at: string
  updated_at: string
}

// 线索详情类型：保留明文联系方式（market/admin 授权访问用于跟进）。
export type LeadDetail = Lead

export interface LeadActivity {
  id: string
  lead_id: string
  kind: ActivityKind
  result?: ActivityResult | null
  content?: string | null
  happened_at: string
  created_at: string
  created_by: string
  revoked_at?: string | null
  revoked_by?: string | null
  revoke_reason?: string | null
}

export interface Handoff {
  id: string
  lead_id: string
  from_department_id?: string | null
  to_department_id: string
  to_contact_id?: string | null
  note?: string | null
  happened_at: string
  created_by: string
  reason?: string | null
}

export interface OutcomeEvent {
  id: string
  lead_id: string
  from_outcome: OutcomeStatus
  to_outcome: OutcomeStatus
  note?: string | null
  feedback_at: string
  created_by: string
  created_at: string
}

// 企业列表项（api-contract §5 定稿）：扁平结构，含聚合的关联线索数与最近咨询时间。
export interface CompanyListItem {
  id: string
  canonical_name: string
  industry?: string | null
  phone?: string | null
  website?: string | null
  lead_count: number
  recent_inquiry_at?: string | null
}

// 企业详情（api-contract §5 定稿）：含联系人与全部关联线索。
export interface CompanyDetail {
  id: string
  canonical_name: string
  normalized_name: string
  aliases: string[]
  industry?: string | null
  phone?: string | null
  website?: string | null
  merged_into_id?: string | null
  contacts: Contact[]
  leads: Lead[]
}

export interface CompanyMergePayload {
  source_company_id: string
  target_company_id: string
  reason?: string
}

// 合并预览影响（api-contract §5 merge-preview）。
export interface CompanyMergePreview {
  lead_relink_count: number
  contact_merge_count: number
  alias_destination: string
}
