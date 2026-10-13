// 生成 UUIDv4，用于幂等键与请求 ID。
export function generateUuid(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

// 创建/跟进请求的幂等键（PRD §8/§9，防双击与网络重试重复计数）。
export function generateIdempotencyKey(): string {
  return generateUuid()
}

// 每次请求的 X-Request-Id（ADR-014）。
export function generateRequestId(): string {
  return generateUuid()
}
