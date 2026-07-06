import type { AlignmentDto } from '../api/types'
import type { GraphNode, GraphEdge } from './buildGraphData'

const SKOS_LABEL: Record<string, string> = {
  EXACT: 'exactMatch', CLOSE: 'closeMatch', BROAD: 'broadMatch', NARROW: 'narrowMatch', RELATED: 'relatedMatch',
}

/** 정렬 링크를 그래프 조각(참조 노드 + 점선 엣지)으로 만든다. 참조 노드는 group 'ref'. */
export function alignmentGraph(
  alignments: AlignmentDto[],
  refLabelOf: (iri: string) => string,
): { nodes: (GraphNode & { group: string })[]; edges: (GraphEdge & { dashes: boolean })[] } {
  const nodes = new Map<string, GraphNode & { group: string }>()
  const edges: (GraphEdge & { dashes: boolean })[] = []
  for (const a of alignments) {
    if (!nodes.has(a.targetIri)) nodes.set(a.targetIri, { id: a.targetIri, label: refLabelOf(a.targetIri), group: 'ref' })
    edges.push({ from: a.sourceIri, to: a.targetIri, label: SKOS_LABEL[a.matchType], arrows: 'to', dashes: true })
  }
  return { nodes: [...nodes.values()], edges }
}
