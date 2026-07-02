import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useOntologyStore } from './ontologyStore'
import * as client from '../api/client'

beforeEach(() => setActivePinia(createPinia()))
afterEach(() => vi.restoreAllMocks())

describe('ontologyStore savepoint (E8)', () => {
  it('confirm posts to /enrich/confirm, refreshes, drops candidate, reloads confirmations', async () => {
    const post = vi.spyOn(client, 'apiPost').mockResolvedValue({} as any)
    const get = vi.spyOn(client, 'apiGet').mockImplementation(async (path: string) => {
      if (path === '/confirmations') return [{ iri: 'e#TB_CUST_MST', label: '고객 마스터', kind: 'class' }] as any
      return [] as any
    })
    const s = useOntologyStore()
    s.enrichCandidates = [{ targetIri: 'e#TB_CUST_MST', currentName: 'TB_CUST_MST', suggestedLabel: '고객 마스터', description: '' }] as any
    s.scoredCandidates = [{ targetIri: 'e#TB_CUST_MST' }] as any

    await s.confirm('e#TB_CUST_MST', '고객 마스터')

    expect(post).toHaveBeenCalledWith('/enrich/confirm', { targetIri: 'e#TB_CUST_MST', label: '고객 마스터' })
    expect(get).toHaveBeenCalledWith('/confirmations')
    expect(s.enrichCandidates).toHaveLength(0)
    expect(s.scoredCandidates).toHaveLength(0)
    expect(s.confirmations).toEqual([{ iri: 'e#TB_CUST_MST', label: '고객 마스터', kind: 'class' }])
  })

  it('fetchConfirmations stores the list', async () => {
    vi.spyOn(client, 'apiGet').mockResolvedValue([{ iri: 'e#A', label: 'L', kind: 'class' }] as any)
    const s = useOntologyStore()
    await s.fetchConfirmations()
    expect(s.confirmations).toEqual([{ iri: 'e#A', label: 'L', kind: 'class' }])
  })

  it('deleteConfirmation calls DELETE with iri and refetches', async () => {
    const del = vi.spyOn(client, 'apiDelete').mockResolvedValue()
    vi.spyOn(client, 'apiGet').mockResolvedValue([] as any)
    const s = useOntologyStore()
    await s.deleteConfirmation('e#A')
    expect(del).toHaveBeenCalledWith('/confirmations?iri=e%23A')
    expect(s.confirmations).toEqual([])
  })
})
