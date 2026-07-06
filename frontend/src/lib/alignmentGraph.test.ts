import { describe, it, expect } from 'vitest'
import { alignmentGraph } from './alignmentGraph'
import type { AlignmentDto } from '../api/types'

const aligns: AlignmentDto[] = [
  { sourceIri: 'src#a', targetIri: 'ref#Person', matchType: 'CLOSE', confidence: 0.8, provenance: 'manual' },
]

describe('alignmentGraph', () => {
  it('adds a reference node per aligned target and a dashed edge labelled by match type', () => {
    const g = alignmentGraph(aligns, iri => (iri === 'ref#Person' ? 'Person' : iri))
    expect(g.nodes).toEqual([{ id: 'ref#Person', label: 'Person', group: 'ref' }])
    expect(g.edges).toEqual([{ from: 'src#a', to: 'ref#Person', label: 'closeMatch', arrows: 'to', dashes: true }])
  })

  it('dedupes reference nodes when multiple sources map to the same target', () => {
    const g = alignmentGraph(
      [aligns[0], { sourceIri: 'src#b', targetIri: 'ref#Person', matchType: 'EXACT', confidence: null, provenance: 'manual' }],
      () => 'Person',
    )
    expect(g.nodes).toHaveLength(1)
    expect(g.edges).toHaveLength(2)
  })
})
