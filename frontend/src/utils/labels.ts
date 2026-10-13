import type {
  ActivityKind,
  ActivityResult,
  HandoffStatus,
  IntakeMethod,
  OutcomeStatus,
  QualificationStatus,
  WechatRelationship,
} from '@/types'

export const QUALIFICATION_LABELS: Record<QualificationStatus, string> = {
  pending: '待确认',
  valid: '有效',
  invalid: '无效',
}

export const HANDOFF_LABELS: Record<HandoffStatus, string> = {
  not_handed_off: '未交接',
  handed_off: '已交接',
}

export const OUTCOME_LABELS: Record<OutcomeStatus, string> = {
  unknown: '暂无反馈',
  in_progress: '推进中',
  won: '已成交',
  lost: '未成交',
  deferred: '暂缓',
}

export const INTAKE_LABELS: Record<IntakeMethod, string> = {
  manual: '手动',
  import: '导入',
  api: 'API',
}

export const ACTIVITY_KIND_LABELS: Record<ActivityKind, string> = {
  phone: '电话',
  wechat_request: '微信申请',
  wechat_approved: '微信通过',
  wechat_chat: '微信沟通',
  note: '备注',
}

export const ACTIVITY_RESULT_LABELS: Record<ActivityResult, string> = {
  connected: '已接通',
  unconnected: '未接通',
  rejected: '拒接',
}

export const WECHAT_RELATIONSHIP_LABELS: Record<WechatRelationship, string> = {
  none: '未添加',
  pending: '待通过',
  approved: '已通过',
}
