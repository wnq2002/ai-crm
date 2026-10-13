import { describe, expect, it } from 'vitest'
import { maskContactSummary, maskEmail, maskPhone, maskWechat } from '@/utils/pii'

describe('pii masking', () => {
  it('masks phone numbers', () => {
    expect(maskPhone('13812345678')).toBe('138****5678')
    expect(maskPhone(null)).toBe('—')
    expect(maskPhone('123')).toBe('123')
  })

  it('masks emails', () => {
    expect(maskEmail('abc@example.com')).toBe('a***@example.com')
    expect(maskEmail(undefined)).toBe('—')
  })

  it('masks wechat ids', () => {
    expect(maskWechat('wxid_abc123')).toBe('wx***23')
    expect(maskWechat('ab')).toBe('ab')
  })

  it('picks phone over email over wechat for summary', () => {
    expect(maskContactSummary('13812345678', 'a@b.com', 'wx')).toBe('138****5678')
    expect(maskContactSummary(null, 'a@b.com', 'wx')).toBe('a***@b.com')
    expect(maskContactSummary(null, null, 'wxid_xyz')).toBe('wx***yz')
    expect(maskContactSummary(null, null, null)).toBe('—')
  })
})
