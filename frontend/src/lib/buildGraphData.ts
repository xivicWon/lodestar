import type { ClassDto, ObjectPropertyDto } from '../api/types'

export interface GraphNode { id: string; label: string }
export interface GraphEdge { from: string; to: string; label: string; arrows: string }
export interface GraphData { nodes: GraphNode[]; edges: GraphEdge[] }

export function shortName(iri: string): string {
  const hash = iri.split('#').pop() ?? iri
  return hash.split('/').pop() ?? hash
}

export function buildGraphData(
  classes: ClassDto[],
  objectProperties: ObjectPropertyDto[],
): GraphData {
  const nodes: GraphNode[] = classes.map(c => ({ id: c.iri, label: c.label ?? shortName(c.iri) }))
  const edges: GraphEdge[] = []
  for (const p of objectProperties) {
    const from = p.domains[0]
    const to = p.ranges[0]
    if (!from || !to) continue
    edges.push({ from, to, label: p.label ?? shortName(p.iri), arrows: 'to' })
  }
  return { nodes, edges }
}

/**
 * 특정 노드에 직접 연결된 이웃(1-hop)과 그 관계만 남긴 부분 그래프를 만든다.
 * centerIri가 그래프에 없으면 원본을 그대로 반환한다.
 */
export function focusSubgraph(data: GraphData, centerIri: string): GraphData {
  if (!data.nodes.some(n => n.id === centerIri)) return data
  const keep = new Set<string>([centerIri])
  const edges = data.edges.filter(e => e.from === centerIri || e.to === centerIri)
  for (const e of edges) { keep.add(e.from); keep.add(e.to) }
  return { nodes: data.nodes.filter(n => keep.has(n.id)), edges }
}
