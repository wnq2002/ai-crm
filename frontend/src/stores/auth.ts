import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import * as authApi from '@/api/auth'
import type { ChangePasswordPayload, LoginPayload } from '@/api/auth'
import type { Role, User } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const initialized = ref(false)

  const isAuthenticated = computed(() => user.value !== null)
  const role = computed<Role | null>(() => user.value?.role ?? null)
  const mustChangePassword = computed(() => user.value?.must_change_password ?? false)

  async function fetchMe(): Promise<void> {
    try {
      user.value = await authApi.getMe()
    } catch {
      user.value = null
    } finally {
      initialized.value = true
    }
  }

  async function login(payload: LoginPayload): Promise<void> {
    user.value = await authApi.login(payload)
    initialized.value = true
  }

  async function changePassword(payload: ChangePasswordPayload): Promise<void> {
    user.value = await authApi.changePassword(payload)
  }

  async function logout(): Promise<void> {
    try {
      await authApi.logout()
    } catch {
      // 即便服务端登出失败，也清除本地状态，避免残留会话视图。
    }
    user.value = null
  }

  function clear(): void {
    user.value = null
  }

  function hasRole(...roles: Role[]): boolean {
    return role.value !== null && roles.includes(role.value)
  }

  return {
    user,
    initialized,
    isAuthenticated,
    role,
    mustChangePassword,
    fetchMe,
    login,
    changePassword,
    logout,
    clear,
    hasRole,
  }
})
