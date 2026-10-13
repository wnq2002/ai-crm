// 与 docs/api-contract.md §1「通用约定」对齐的请求/响应外壳类型。

export interface ApiErrorPayload {
  code?: string
  message?: string
  request_id?: string
  details?: Record<string, unknown>
}

export interface Page<T> {
  items: T[]
  page: number
  page_size: number
  total: number
}

export interface PageQuery {
  page?: number
  page_size?: number
  sort?: string
}
