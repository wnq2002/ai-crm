import http from './http'
import type { User } from '@/types'

export interface LoginPayload {
  username: string
  password: string
}

export interface ChangePasswordPayload {
  old_password: string
  new_password: string
}

export async function login(payload: LoginPayload): Promise<User> {
  const { data } = await http.post<User>('/auth/login', payload)
  return data
}

export async function logout(): Promise<void> {
  await http.post('/auth/logout')
}

export async function getMe(): Promise<User> {
  const { data } = await http.get<User>('/auth/me')
  return data
}

export async function changePassword(payload: ChangePasswordPayload): Promise<User> {
  const { data } = await http.post<User>('/auth/change-password', payload)
  return data
}
