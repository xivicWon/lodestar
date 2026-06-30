import { describe, it, expect, vi, afterEach } from 'vitest'
import { apiGet, ApiError } from './client'

afterEach(() => vi.restoreAllMocks())

describe('apiGet', () => {
  it('returns parsed json on 200', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      new Response(JSON.stringify({ status: 'ok' }), { status: 200, headers: { 'Content-Type': 'application/json' } })))
    expect(await apiGet<{ status: string }>('/health')).toEqual({ status: 'ok' })
  })

  it('throws ApiError carrying error/message on non-2xx', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      new Response(JSON.stringify({ error: 'not_found', message: '없음', targetIri: 'x' }), { status: 404, headers: { 'Content-Type': 'application/json' } })))
    await expect(apiGet('/classes/x')).rejects.toMatchObject({ error: 'not_found', message: '없음', targetIri: 'x' })
  })
})
