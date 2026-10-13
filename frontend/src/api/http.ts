import axios, { AxiosError, type AxiosInstance } from 'axios'
import type { ApiErrorPayload } from '@/types'
import { generateRequestId } from '@/utils/idempotency'
import { getCookie } from '@/utils/cookie'

// 统一错误对象，供视图层直接展示 message 与 request_id。
export class ApiError extends Error {
  code: string
  requestId: string
  status?: number
  details?: Record<string, unknown>

  constructor(
    message: string,
    code = 'UNKNOWN',
    requestId = '',
    status?: number,
    details?: Record<string, unknown>,
  ) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.requestId = requestId
    this.status = status
    this.details = details
  }
}

export function getErrorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message
  if (err instanceof Error) return err.message
  return '请求失败，请稍后重试'
}

// 与后端约定的 CSRF 双提交 Cookie / 头名（ADR-016）。
const CSRF_COOKIE_NAME = 'csrf_token'
const CSRF_HEADER_NAME = 'X-CSRF-Token'
const REQUEST_ID_HEADER = 'X-Request-Id'

const MUTATION_METHODS = new Set(['post', 'put', 'patch', 'delete'])

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

const http: AxiosInstance = axios.create({
  baseURL,
  withCredentials: true, // 身份走 HttpOnly Cookie，不放 localStorage
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

http.interceptors.request.use((config) => {
  config.headers.set(REQUEST_ID_HEADER, generateRequestId())

  const method = (config.method ?? 'get').toLowerCase()
  if (MUTATION_METHODS.has(method)) {
    const csrf = getCookie(CSRF_COOKIE_NAME)
    if (csrf) {
      config.headers.set(CSRF_HEADER_NAME, csrf)
    }
  }
  return config
})

// 401 会话过期的统一处理入口，由应用启动时注册（避免 http -> router -> store 循环依赖）。
let unauthorizedHandler: (() => void) | null = null

export function setUnauthorizedHandler(handler: () => void): void {
  unauthorizedHandler = handler
}

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorPayload>) => {
    const status = error.response?.status
    const payload = error.response?.data

    if (status === 401) {
      unauthorizedHandler?.()
    }

    let message: string
    if (payload?.message) {
      message = payload.message
    } else if (status === 401) {
      message = '登录已过期，请重新登录'
    } else if (status === 403) {
      message = '无权限访问该资源'
    } else {
      message = error.message || '网络请求失败'
    }

    const code = payload?.code ?? (error.code === 'ECONNABORTED' ? 'TIMEOUT' : 'NETWORK_ERROR')
    const requestId = payload?.request_id ?? ''

    return Promise.reject(new ApiError(message, code, requestId, status, payload?.details))
  },
)

export default http
