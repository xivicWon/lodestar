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

  it('importDdl posts sql and refreshes', async () => {
    const post = vi.spyOn(client, 'apiPost').mockResolvedValue({} as any)
    vi.spyOn(client, 'apiGet').mockResolvedValue([] as any)
    const s = useOntologyStore()
    await s.importDdl('CREATE TABLE t (id INT);', 'shop')
    expect(post).toHaveBeenCalledWith('/rdb/import/ddl', { sql: 'CREATE TABLE t (id INT);', schemaName: 'shop' })
  })
})
