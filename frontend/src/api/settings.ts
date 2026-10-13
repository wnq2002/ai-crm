import http from './http'

// AI Provider 配置（api-contract §10 / ADR-029）：密钥仅写不读回。
export interface AIConfig {
  provider: string | null
  endpoint: string | null
  model: string | null
  timeout_seconds: number
  api_key_configured: boolean
  api_key: string | null
  updated_at: string | null
}

export interface AIConfigPayload {
  provider: string
  endpoint: string
  model: string
  api_key?: string
  timeout_seconds: number
}

export async function getAIConfig(): Promise<AIConfig> {
  const { data } = await http.get<AIConfig>('/settings/ai')
  return data
}

export async function saveAIConfig(payload: AIConfigPayload): Promise<AIConfig> {
  const { data } = await http.put<AIConfig>('/settings/ai', payload)
  return data
}
