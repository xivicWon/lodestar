import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useOntologyStore } from './ontologyStore'
import * as client from '../api/client'

beforeEach(() => setActivePinia(createPinia()))
afterEach(() => vi.restoreAllMocks())

describe('ontologyStore reasoning', () => {
  it('runReasoner stores the result', async () => {
    vi.spyOn(client, 'apiPost').mockResolvedValue({
      consistent: true, unsatisfiableClasses: [],
      inferredSubClassOf: [{ sub: 'e#Dog', sup: 'e#Carnivore' }],
    } as any)
    const s = useOntologyStore()
    await s.runReasoner()
    expect(s.reasonResult?.consistent).toBe(true)
    expect(s.reasonResult?.inferredSubClassOf).toEqual([{ sub: 'e#Dog', sup: 'e#Carnivore' }])
  })

  it('inferredChildrenOf maps edges to labelled children', async () => {
    const s = useOntologyStore()
    s.classes = [
      { iri: 'e#Carnivore', label: '육식동물', superClasses: [], annotations: [] },
      { iri: 'e#Dog', label: '개', superClasses: ['e#Animal'], annotations: [] },
    ]
    vi.spyOn(client, 'apiPost').mockResolvedValue({
      consistent: true, unsatisfiableClasses: [],
      inferredSubClassOf: [{ sub: 'e#Dog', sup: 'e#Carnivore' }],
    } as any)
    await s.runReasoner()
    expect(s.inferredChildrenOf('e#Carnivore')).toEqual([{ iri: 'e#Dog', label: '개' }])
    expect(s.inferredChildrenOf('e#Dog')).toEqual([])
  })
})
