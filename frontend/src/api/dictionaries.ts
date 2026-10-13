import http from './http'
import type {
  Department,
  DepartmentContact,
  NeedType,
  SourceCategory,
  SourceDetail,
} from '@/types'

// 业务字典统一挂载在 /settings/*（api-contract §10）；market 可读，写操作仅 admin + CSRF。
export interface DepartmentPayload {
  name: string
}
export interface DepartmentUpdatePayload {
  name?: string
  active?: boolean
}
export interface DepartmentContactPayload {
  department_id: string
  name: string
  is_default?: boolean
  active?: boolean
}
export interface DepartmentContactUpdatePayload {
  name?: string
  is_default?: boolean
  active?: boolean
}
export interface SourceCategoryPayload {
  code: string
  name: string
}
export interface SourceCategoryUpdatePayload {
  name?: string
  active?: boolean
}
export interface SourceDetailPayload {
  category_id: string
  name: string
}
export interface SourceDetailUpdatePayload {
  name?: string
  active?: boolean
}
export interface NeedTypePayload {
  name: string
}
export interface NeedTypeUpdatePayload {
  name?: string
  active?: boolean
}

// ── 部门 ─────────────────────────────────────────────
export async function listDepartments(): Promise<Department[]> {
  const { data } = await http.get<Department[]>('/settings/departments')
  return data
}

export async function createDepartment(payload: DepartmentPayload): Promise<Department> {
  const { data } = await http.post<Department>('/settings/departments', payload)
  return data
}

export async function updateDepartment(
  id: string,
  payload: DepartmentUpdatePayload,
): Promise<Department> {
  const { data } = await http.patch<Department>(`/settings/departments/${id}`, payload)
  return data
}

// ── 部门对接人 ────────────────────────────────────────
export async function listDepartmentContacts(): Promise<DepartmentContact[]> {
  const { data } = await http.get<DepartmentContact[]>('/settings/department-contacts')
  return data
}

export async function createDepartmentContact(
  payload: DepartmentContactPayload,
): Promise<DepartmentContact> {
  const { data } = await http.post<DepartmentContact>('/settings/department-contacts', payload)
  return data
}

export async function updateDepartmentContact(
  id: string,
  payload: DepartmentContactUpdatePayload,
): Promise<DepartmentContact> {
  const { data } = await http.patch<DepartmentContact>(
    `/settings/department-contacts/${id}`,
    payload,
  )
  return data
}

// ── 来源分类 ─────────────────────────────────────────
export async function listSourceCategories(): Promise<SourceCategory[]> {
  const { data } = await http.get<SourceCategory[]>('/settings/source-categories')
  return data
}

export async function createSourceCategory(
  payload: SourceCategoryPayload,
): Promise<SourceCategory> {
  const { data } = await http.post<SourceCategory>('/settings/source-categories', payload)
  return data
}

export async function updateSourceCategory(
  id: string,
  payload: SourceCategoryUpdatePayload,
): Promise<SourceCategory> {
  const { data } = await http.patch<SourceCategory>(
    `/settings/source-categories/${id}`,
    payload,
  )
  return data
}

// ── 来源详情 ─────────────────────────────────────────
export async function listSourceDetails(): Promise<SourceDetail[]> {
  const { data } = await http.get<SourceDetail[]>('/settings/source-details')
  return data
}

export async function createSourceDetail(
  payload: SourceDetailPayload,
): Promise<SourceDetail> {
  const { data } = await http.post<SourceDetail>('/settings/source-details', payload)
  return data
}

export async function updateSourceDetail(
  id: string,
  payload: SourceDetailUpdatePayload,
): Promise<SourceDetail> {
  const { data } = await http.patch<SourceDetail>(`/settings/source-details/${id}`, payload)
  return data
}

// ── 需求类型 ─────────────────────────────────────────
export async function listNeedTypes(): Promise<NeedType[]> {
  const { data } = await http.get<NeedType[]>('/settings/need-types')
  return data
}

export async function createNeedType(payload: NeedTypePayload): Promise<NeedType> {
  const { data } = await http.post<NeedType>('/settings/need-types', payload)
  return data
}

export async function updateNeedType(
  id: string,
  payload: NeedTypeUpdatePayload,
): Promise<NeedType> {
  const { data } = await http.patch<NeedType>(`/settings/need-types/${id}`, payload)
  return data
}

// ── 删除（仅未被引用时允许；被引用则后端 409 拦截）────
export async function deleteDepartment(id: string): Promise<void> {
  await http.delete(`/settings/departments/${id}`)
}

export async function deleteDepartmentContact(id: string): Promise<void> {
  await http.delete(`/settings/department-contacts/${id}`)
}

export async function deleteSourceCategory(id: string): Promise<void> {
  await http.delete(`/settings/source-categories/${id}`)
}

export async function deleteSourceDetail(id: string): Promise<void> {
  await http.delete(`/settings/source-details/${id}`)
}

export async function deleteNeedType(id: string): Promise<void> {
  await http.delete(`/settings/need-types/${id}`)
}

// 批量改派：把某对接人名下的存量线索转给同部门另一对接人（保留历史）
export async function reassignContactLeads(
  id: string,
  toContactId: string,
): Promise<{ moved_leads: number }> {
  const { data } = await http.post<{ moved_leads: number }>(
    `/settings/department-contacts/${id}/reassign`,
    { to_contact_id: toContactId },
  )
  return data
}
