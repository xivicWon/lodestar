import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useOntologyStore } from './ontologyStore'
import * as client from '../api/client'

beforeEach(() => setActivePinia(createPinia()))
afterEach(() => vi.restoreAllMocks())

const cand = {
  fromIri: 'e#TB_ORD_HD', toIri: 'e#TB_CUST_MST',
  viaColumn: 'CUST_NO', confidence: 0.6, suggestedName: 'hasCust',
}

describe('ontologyStore relation suggestion', () => {
  it('suggestRelations loads candidates from /rel/suggest', async () => {
    const spy = vi.spyOn(client, 'apiPost').mockResolvedValue([cand] as any)
    const s = useOntologyStore()
    await s.suggestRelations()
    expect(spy).toHaveBeenCalledWith('/rel/suggest', {})
    expect(s.relCandidates).toEqual([cand])
  })

  it('applyRelation posts an object property and removes the candidate', async () => {
    const s = useOntologyStore()
    s.relCandidates = [cand] as any
    const post = vi.spyOn(client, 'apiPost').mockResolvedValue({} as any)
    vi.spyOn(client, 'apiGet').mockImplementation((path: string) => {
      if (path === '/classes') return Promise.resolve([]) as any
      return Promise.resolve({}) as any
    })
    await s.applyRelation('e#TB_ORD_HD', 'e#TB_CUST_MST', 'hasCust')
    expect(post).toHaveBeenCalledWith('/properties/object', {
      label: 'hasCust', domains: ['e#TB_ORD_HD'], ranges: ['e#TB_CUST_MST'],
    })
    expect(s.relCandidates).toEqual([])
  })

  it('judgeRelations loads judged candidates from /rel/suggest/judged', async () => {
    const judged = { ...cand, keep: true, reason: '말이 됨' }
    const spy = vi.spyOn(client, 'apiPost').mockResolvedValue([judged] as any)
    const s = useOntologyStore()
    await s.judgeRelations()
    expect(spy).toHaveBeenCalledWith('/rel/suggest/judged', {})
    expect(s.judgedRelations).toEqual([judged])
  })

  it('applyRelation also removes a matching judged candidate', async () => {
    const s = useOntologyStore()
    s.judgedRelations = [{ ...cand, keep: true, reason: 'ok' }] as any
    vi.spyOn(client, 'apiPost').mockResolvedValue({} as any)
    vi.spyOn(client, 'apiGet').mockResolvedValue([] as any)
    await s.applyRelation('e#TB_ORD_HD', 'e#TB_CUST_MST', 'hasCust')
    expect(s.judgedRelations).toEqual([])
  })

  it('dismissRelation removes the candidate at index', () => {
    const s = useOntologyStore()
    s.relCandidates = [cand, { ...cand, viaColumn: 'X_NO' }] as any
    s.dismissRelation(0)
    expect(s.relCandidates.length).toBe(1)
    expect(s.relCandidates[0].viaColumn).toBe('X_NO')
  })
})
