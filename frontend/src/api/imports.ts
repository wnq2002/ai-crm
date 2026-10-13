import http from './http'

export interface ImportRowError {
  row_number: number
  message: string
}

export interface ImportPreviewResult {
  preview_token: string
  total_rows: number
  valid_rows: number
  duplicates: unknown[]
  errors: ImportRowError[]
}

export interface ImportCommitResult {
  job_id: string
  success_rows: number
  failed_rows: number
  skipped_rows: number
}

export async function downloadImportTemplate(): Promise<Blob> {
  const { data } = await http.get<Blob>('/imports/template', { responseType: 'blob' })
  return data
}

export async function previewImport(file: File): Promise<ImportPreviewResult> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await http.post<ImportPreviewResult>('/imports/preview', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function commitImport(
  previewToken: string,
  idempotencyKey: string,
): Promise<ImportCommitResult> {
  const { data } = await http.post<ImportCommitResult>('/imports/commit', {
    preview_token: previewToken,
    idempotency_key: idempotencyKey,
  })
  return data
}

export async function getImportResult(jobId: string): Promise<unknown> {
  const { data } = await http.get<unknown>(`/imports/${jobId}`)
  return data
}

export async function exportLeads(params: Record<string, unknown>): Promise<Blob> {
  const { data } = await http.get<Blob>('/leads/export', { params, responseType: 'blob' })
  return data
}
