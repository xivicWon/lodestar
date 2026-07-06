import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useOntologyStore } from './ontologyStore'
import * as client from '../api/client'

beforeEach(() => setActivePinia(createPinia()))

describe('ontologyStore reference', () => {
  it('fetchReference loads reference classes and meta separately from source classes', async () => {
    const s = useOntologyStore()
    s.classes = [{ iri: 'src#a', label: 'A', superClasses: [], annotations: [] }]
    vi.spyOn(client, 'apiGet').mockImplementation(async (path: string) => {
      if (path === '/reference/classes') return [{ iri: 'ref#Person', label: 'Person', superClasses: [], annotations: [] }] as any
      if (path === '/reference/meta') return { ontologyIri: 'ref', source: 'r.ttl', classCount: 1 } as any
      return [] as any
    })
    await s.fetchReference()
    expect(s.referenceClasses.map(c => c.iri)).toEqual(['ref#Person'])
    expect(s.referenceMeta?.classCount).toBe(1)
    expect(s.classes.map(c => c.iri)).toEqual(['src#a']) // 소스 불변
  })

  it('clearReference empties reference state', async () => {
    const s = useOntologyStore()
    s.referenceClasses = [{ iri: 'ref#Person', label: 'Person', superClasses: [], annotations: [] }]
    vi.spyOn(client, 'apiDelete').mockResolvedValue(undefined)
    await s.clearReference()
    expect(s.referenceClasses).toEqual([])
    expect(s.referenceMeta).toBeNull()
  })
})
