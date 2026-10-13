import http from './http'
import type { Page, Role, User } from '@/types'

// 用户账号管理（api-contract §10）：写操作仅 admin + CSRF。
export interface UserCreatePayload {
  username: string
  display_name: string
  role: Role
  password: string
}

export interface UserUpdatePayload {
  display_name?: string
  role?: Role
  is_active?: boolean
  new_password?: string
}

export async function listUsers(page = 1, pageSize = 100): Promise<Page<User>> {
  const { data } = await http.get<Page<User>>('/admin/users', {
    params: { page, page_size: pageSize },
  })
  return data
}

export async function createUser(payload: UserCreatePayload): Promise<User> {
  const { data } = await http.post<User>('/admin/users', payload)
  return data
}

export async function updateUser(id: string, payload: UserUpdatePayload): Promise<User> {
  const { data } = await http.patch<User>(`/admin/users/${id}`, payload)
  return data
}
