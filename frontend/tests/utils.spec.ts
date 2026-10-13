import { describe, expect, it } from 'vitest'
import { generateIdempotencyKey, generateUuid } from '@/utils/idempotency'
import { formatDateTime, nowToISO, toLocalInputValue } from '@/utils/datetime'

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

describe('idempotency utils', () => {
  it('generates a UUID-shaped idempotency key', () => {
    expect(generateIdempotencyKey()).toMatch(UUID_RE)
  })

  it('generates distinct UUIDs', () => {
    expect(generateUuid()).not.toBe(generateUuid())
  })
})

describe('datetime utils', () => {
  it('renders empty values as a dash', () => {
    expect(formatDateTime(null)).toBe('—')
    expect(formatDateTime(undefined)).toBe('—')
  })

  it('converts an ISO timestamp to a datetime-local input value', () => {
    const value = toLocalInputValue('2026-10-10T08:00:00Z')
    expect(value).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/)
  })

  it('produces an ISO string for now', () => {
    expect(nowToISO()).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/)
  })
})
