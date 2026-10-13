// PII 脱敏展示（列表页「联系方式脱敏摘要」，api-contract §1）。仅用于前端展示层。

export function maskPhone(phone: string | null | undefined): string {
  if (!phone) return '—'
  if (phone.length < 7) return phone
  return `${phone.slice(0, 3)}****${phone.slice(-4)}`
}

export function maskEmail(email: string | null | undefined): string {
  if (!email) return '—'
  const at = email.indexOf('@')
  if (at <= 0) return email
  const local = email.slice(0, at)
  const domain = email.slice(at)
  return `${local.slice(0, 1)}***${domain}`
}

export function maskWechat(wechat: string | null | undefined): string {
  if (!wechat) return '—'
  if (wechat.length <= 4) return wechat
  return `${wechat.slice(0, 2)}***${wechat.slice(-2)}`
}

// 列表单元格的脱敏摘要：优先手机号，其次邮箱，再次微信。
export function maskContactSummary(
  phone: string | null | undefined,
  email: string | null | undefined,
  wechat: string | null | undefined,
): string {
  if (phone) return maskPhone(phone)
  if (email) return maskEmail(email)
  if (wechat) return maskWechat(wechat)
  return '—'
}
