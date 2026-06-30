import { ApiError } from './types'
export { ApiError } from './types'

const BASE = '/api'

async function parseError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json()
    return new ApiError(body.error ?? 'error', body.message ?? res.statusText, body.targetIri ?? null)
  } catch {
    return new ApiError('error', res.statusText || `HTTP ${res.status}`, null)
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path)
  if (!res.ok) throw await parseError(res)
  return res.json() as Promise<T>
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  if (!res.ok) throw await parseError(res)
  return res.json() as Promise<T>
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  if (!res.ok) throw await parseError(res)
  return res.json() as Promise<T>
}

export async function apiDelete(path: string): Promise<void> {
  const res = await fetch(BASE + path, { method: 'DELETE' })
  if (!res.ok) throw await parseError(res)
}

export async function apiUpload<T>(path: string, file: File, fields: Record<string, string> = {}): Promise<T> {
  const form = new FormData()
  form.append('file', file)
  for (const [k, v] of Object.entries(fields)) form.append(k, v)
  const res = await fetch(BASE + path, { method: 'POST', body: form })
  if (!res.ok) throw await parseError(res)
  return res.json() as Promise<T>
}

export async function apiDownload(path: string): Promise<Blob> {
  const res = await fetch(BASE + path)
  if (!res.ok) throw await parseError(res)
  return res.blob()
}
