// frontend/src/stores/ontologyStore.alignment.test.ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useOntologyStore } from './ontologyStore'
import * as client from '../api/client'

beforeEach(() => setActivePinia(createPinia()))

describe('ontologyStore alignments', () => {
  it('createAlignment posts and refreshes the alignment list', async () => {
    const s = useOntologyStore()
    const post = vi.spyOn(client, 'apiPost').mockResolvedValue({
      sourceIri: 'src#a', targetIri: 'ref#Person', matchType: 'CLOSE', confidence: 0.8, provenance: 'manual',
    } as any)
    vi.spyOn(client, 'apiGet').mockResolvedValue([
      { sourceIri: 'src#a', targetIri: 'ref#Person', matchType: 'CLOSE', confidence: 0.8, provenance: 'manual' },
    ] as any)
    await s.createAlignment('src#a', 'ref#Person', 'CLOSE', 0.8)
    expect(post).toHaveBeenCalledWith('/alignments', { sourceIri: 'src#a', targetIri: 'ref#Person', matchType: 'CLOSE', confidence: 0.8 })
    expect(s.alignments).toHaveLength(1)
  })

  it('alignmentsOf filters by source class', () => {
    const s = useOntologyStore()
    s.alignments = [
      { sourceIri: 'src#a', targetIri: 'ref#P', matchType: 'CLOSE', confidence: null, provenance: 'manual' },
      { sourceIri: 'src#b', targetIri: 'ref#Q', matchType: 'EXACT', confidence: null, provenance: 'manual' },
    ]
    expect(s.alignmentsOf('src#a').map(a => a.targetIri)).toEqual(['ref#P'])
  })
})
