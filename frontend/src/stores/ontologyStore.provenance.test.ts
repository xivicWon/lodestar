import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useOntologyStore } from './ontologyStore'
import * as client from '../api/client'

beforeEach(() => setActivePinia(createPinia()))

describe('applyRelation provenance', () => {
  it('sends provenance fields to POST /properties/object', async () => {
    const s = useOntologyStore()
    const post = vi.spyOn(client, 'apiPost').mockResolvedValue({} as any)
    vi.spyOn(s, 'refresh').mockResolvedValue()
    await s.applyRelation('a', 'b', 'placedBy', { kind: 'NAMEPATTERN', provenance: 'INFERRED', confidence: 0.6 })
    expect(post).toHaveBeenCalledWith('/properties/object', {
      label: 'placedBy', domains: ['a'], ranges: ['b'],
      kind: 'NAMEPATTERN', provenance: 'INFERRED', confidence: 0.6,
    })
  })

  it('omits provenance fields when none passed (manual default on backend)', async () => {
    const s = useOntologyStore()
    const post = vi.spyOn(client, 'apiPost').mockResolvedValue({} as any)
    vi.spyOn(s, 'refresh').mockResolvedValue()
    await s.applyRelation('a', 'b', 'rel')
    expect(post).toHaveBeenCalledWith('/properties/object', { label: 'rel', domains: ['a'], ranges: ['b'] })
  })
})
