import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useOntologyStore } from './ontologyStore'
import * as client from '../api/client'

beforeEach(() => setActivePinia(createPinia()))
afterEach(() => vi.restoreAllMocks())

describe('ontologyStore trash (E11)', () => {
  it('fetchTrash stores the list', async () => {
    vi.spyOn(client, 'apiGet').mockResolvedValue(
      [{ iri: 'e#A', label: 'TB_A', trashedAt: 1 }] as any)
    const s = useOntologyStore()
    await s.fetchTrash()
    expect(s.trash).toEqual([{ iri: 'e#A', label: 'TB_A', trashedAt: 1 }])
  })

  it('trashClass posts to /trash, clears selection, refreshes and refetches trash', async () => {
    const post = vi.spyOn(client, 'apiPost').mockResolvedValue({} as any)
    vi.spyOn(client, 'apiGet').mockImplementation(async (path: string) => {
      if (path === '/trash') return [{ iri: 'e#A', label: 'TB_A', trashedAt: 1 }] as any
      return [] as any
    })
    const s = useOntologyStore()
    s.select('e#A')
    await s.trashClass('e#A')
    expect(post).toHaveBeenCalledWith('/trash', { iri: 'e#A' })
    expect(s.selectedIri).toBeNull()
    expect(s.trash).toEqual([{ iri: 'e#A', label: 'TB_A', trashedAt: 1 }])
  })

  it('restoreTrash posts to /trash/restore then refreshes and refetches', async () => {
    const post = vi.spyOn(client, 'apiPost').mockResolvedValue({} as any)
    vi.spyOn(client, 'apiGet').mockResolvedValue([] as any)
    const s = useOntologyStore()
    await s.restoreTrash('e#A')
    expect(post).toHaveBeenCalledWith('/trash/restore?iri=e%23A', {})
    expect(s.trash).toEqual([])
  })

  it('purgeTrash calls DELETE with iri then refetches', async () => {
    const del = vi.spyOn(client, 'apiDelete').mockResolvedValue()
    vi.spyOn(client, 'apiGet').mockResolvedValue([] as any)
    const s = useOntologyStore()
    await s.purgeTrash('e#A')
    expect(del).toHaveBeenCalledWith('/trash?iri=e%23A')
    expect(s.trash).toEqual([])
  })
})
