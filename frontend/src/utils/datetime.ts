// 时间约定：API 统一 ISO 8601 UTC，UI 按用户本地时区显示（docs/api-contract.md §1）。

const EMPTY = '—'

function toDate(iso: string | null | undefined): Date | null {
  if (!iso) return null
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? null : d
}

export function formatDateTime(iso: string | null | undefined): string {
  const d = toDate(iso)
  return d ? d.toLocaleString() : EMPTY
}

export function formatDate(iso: string | null | undefined): string {
  const d = toDate(iso)
  return d ? d.toLocaleDateString() : EMPTY
}

// 将 ISO 转为 `<input type="datetime-local">` 需要的本地时间字符串。
export function toLocalInputValue(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number): string => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// 当前本地时间转为 ISO UTC，用于 occurred_at 等提交字段。
export function nowToISO(): string {
  return new Date().toISOString()
}
