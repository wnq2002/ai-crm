import http from './http'
import type {
  Company,
  CompanyDetail,
  CompanyListItem,
  CompanyMergePayload,
  CompanyMergePreview,
  Lead,
  Page,
} from '@/types'

export interface CompanyListQuery {
  q?: string
  page?: number
  page_size?: number
  sort?: string
}

export interface CompanyCreatePayload {
  canonical_name: string
  aliases?: string[]
  industry?: string
  phone?: string
  website?: string
}

export async function listCompanies(params: CompanyListQuery): Promise<Page<CompanyListItem>> {
  const { data } = await http.get<Page<CompanyListItem>>('/companies', { params })
  return data
}

export async function getCompany(id: string): Promise<CompanyDetail> {
  const { data } = await http.get<CompanyDetail>(`/companies/${id}`)
  return data
}

export async function createCompany(payload: CompanyCreatePayload): Promise<Company> {
  const { data } = await http.post<Company>('/companies', payload)
  return data
}

export async function getCompanyLeads(id: string): Promise<Lead[]> {
  const { data } = await http.get<Lead[]>(`/companies/${id}/leads`)
  return data
}

export async function mergeCompanies(payload: CompanyMergePayload): Promise<CompanyDetail> {
  const { data } = await http.post<CompanyDetail>('/companies/merge', payload)
  return data
}

export async function mergePreview(payload: {
  source_company_id: string
  target_company_id: string
}): Promise<CompanyMergePreview> {
  const { data } = await http.post<CompanyMergePreview>('/companies/merge-preview', payload)
  return data
}
