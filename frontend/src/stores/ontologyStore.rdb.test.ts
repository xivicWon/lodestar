import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useOntologyStore } from './ontologyStore'
import * as client from '../api/client'
import type { ObjectPropertyDto } from '../api/types'

const rel: ObjectPropertyDto = {
  iri: 'e#orders_customer_id_ref', label: 'orders → customers (customer_id)',
  domains: ['e#orders'], ranges: ['e#customers'], characteristics: [], inverseOf: null, annotations: [],
}

beforeEach(() => setActivePinia(createPinia()))
afterEach(() => vi.restoreAllMocks())

describe('ontologyStore rdb', () => {
  it('refresh loads object properties', async () => {
    vi.spyOn(client, 'apiGet').mockImplementation(async (p: string) =>
      p === '/properties/object' ? [rel] : (p === '/classes' ? [] : {} as any))
    const s = useOntologyStore()
    await s.refresh()
    expect(s.objectProperties).toEqual([rel])
  })

  it('enrichSample posts and stores candidates', async () => {
    const cand = { targetIri: 'e#TB_CUST_MST', currentName: 'TB_CUST_MST', suggestedLabel: '고객 마스터', description: 'x' }
    vi.spyOn(client, 'apiPost').mockResolvedValue([cand] as any)
    const s = useOntologyStore()
    await s.enrichSample()
    expect(s.enrichCandidates).toEqual([cand])
  })

  it('applyEnrichment patches class label and removes candidate', async () => {
    const cand = { targetIri: 'e#TB_CUST_MST', currentName: 'TB_CUST_MST', suggestedLabel: '고객 마스터', description: 'x' }
    const patch = vi.spyOn(client, 'apiPatch').mockResolvedValue({} as any)
    vi.spyOn(client, 'apiGet').mockResolvedValue([] as any)
    const s = useOntologyStore()
    s.enrichCandidates = [cand] as any
    await s.applyEnrichment('e#TB_CUST_MST', '고객 마스터')
    expect(patch).toHaveBeenCalledWith('/classes/by-iri?iri=' + encodeURIComponent('e#TB_CUST_MST'), { label: '고객 마스터' })
    expect(s.enrichCandidates.length).toBe(0)
  })

  it('renameRelation patches label and refreshes', async () => {
    const patch = vi.spyOn(client, 'apiPatch').mockResolvedValue({} as any)
    vi.spyOn(client, 'apiGet').mockResolvedValue([] as any)
    const s = useOntologyStore()
    await s.renameRelation('e#orders_customer_id_ref', 'placedBy')
    expect(patch).toHaveBeenCalledWith(
      '/properties/object/label?iri=' + encodeURIComponent('e#orders_customer_id_ref'),
      { label: 'placedBy' })
  })

  it('importSample posts to sample endpoint and refreshes', async () => {
    const post = vi.spyOn(client, 'apiPost').mockResolvedValue({} as any)
    vi.spyOn(client, 'apiGet').mockResolvedValue([] as any)
    const s = useOntologyStore()
    await s.importSample()
    expect(post).toHaveBeenCalledWith('/rdb/import/sample', {})
  })

  it('importDdl posts sql and refreshes', async () => {
    const post = vi.spyOn(client, 'apiPost').mockResolvedValue({} as any)
    vi.spyOn(client, 'apiGet').mockResolvedValue([] as any)
    const s = useOntologyStore()
    await s.importDdl('CREATE TABLE t (id INT);', 'shop')
    expect(post).toHaveBeenCalledWith('/rdb/import/ddl', { sql: 'CREATE TABLE t (id INT);', schemaName: 'shop' })
  })

  it('importSample captures merge summary into lastMerge', async () => {
    const result = { meta: {}, merge: { reapplied: 2, stale: 1, staleIris: ['e#X'] } }
    vi.spyOn(client, 'apiPost').mockResolvedValue(result as any)
    vi.spyOn(client, 'apiGet').mockResolvedValue([] as any)
    const s = useOntologyStore()
    await s.importSample()
    expect(s.lastMerge).toEqual({ reapplied: 2, stale: 1, staleIris: ['e#X'] })
  })

  it('importDdl captures merge summary into lastMerge', async () => {
    const result = { meta: {}, merge: { reapplied: 1, stale: 0, staleIris: [] } }
    vi.spyOn(client, 'apiPost').mockResolvedValue(result as any)
    vi.spyOn(client, 'apiGet').mockResolvedValue([] as any)
    const s = useOntologyStore()
    await s.importDdl('CREATE TABLE t (id INT);', 'shop')
    expect(s.lastMerge).toEqual({ reapplied: 1, stale: 0, staleIris: [] })
  })
})
