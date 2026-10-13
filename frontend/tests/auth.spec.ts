import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import type { User } from '@/types'
import * as authApi from '@/api/auth'

vi.mock('@/api/auth', () => ({
  login: vi.fn(),
  logout: vi.fn(),
  getMe: vi.fn(),
  changePassword: vi.fn(),
}))

const baseUser: User = {
  id: 'u1',
  username: 'alice',
  display_name: 'Alice',
  role: 'market',
  is_active: true,
  must_change_password: false,
}

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('login sets the user and reflects must_change_password', async () => {
    vi.mocked(authApi.login).mockResolvedValue({ ...baseUser, must_change_password: true })
    const auth = useAuthStore()

    await auth.login({ username: 'alice', password: 'secret' })

    expect(auth.user?.username).toBe('alice')
    expect(auth.isAuthenticated).toBe(true)
    expect(auth.mustChangePassword).toBe(true)
  })

  it('fetchMe handles failure by staying unauthenticated but initialized', async () => {
    vi.mocked(authApi.getMe).mockRejectedValue(new Error('unauthorized'))
    const auth = useAuthStore()

    await auth.fetchMe()

    expect(auth.isAuthenticated).toBe(false)
    expect(auth.initialized).toBe(true)
  })

  it('hasRole checks against the current role', async () => {
    vi.mocked(authApi.getMe).mockResolvedValue({ ...baseUser, role: 'admin' })
    const auth = useAuthStore()

    await auth.fetchMe()

    expect(auth.hasRole('admin')).toBe(true)
    expect(auth.hasRole('market')).toBe(false)
    expect(auth.hasRole('admin', 'market')).toBe(true)
  })

  it('logout clears the user even if the API call fails', async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(baseUser)
    vi.mocked(authApi.logout).mockRejectedValue(new Error('network'))
    const auth = useAuthStore()
    await auth.fetchMe()
    expect(auth.isAuthenticated).toBe(true)

    await auth.logout()

    expect(auth.isAuthenticated).toBe(false)
    expect(auth.user).toBeNull()
  })
})
