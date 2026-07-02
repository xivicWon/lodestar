import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useOntologyStore } from './ontologyStore'
import * as client from '../api/client'

beforeEach(() => setActivePinia(createPinia()))
afterEach(() => vi.restoreAllMocks())

const result = {
  iri: 'e#B',
  upstream: ['e#A'],
  downstream: ['e#C'],
}

describe('ontologyStore impact analysis', () => {
  it('fetchImpact loads result from /impact with encoded iri', async () => {
    const spy = vi.spyOn(client, 'apiGet').mockResolvedValue(result as any)
    const s = useOntologyStore()
    await s.fetchImpact('e#B')
    expect(spy).toHaveBeenCalledWith('/impact?iri=' + encodeURIComponent('e#B'))
    expect(s.impact).toEqual(result)
  })
})
