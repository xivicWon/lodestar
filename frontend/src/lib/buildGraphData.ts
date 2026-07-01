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
