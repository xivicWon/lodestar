import type { ClassDto } from '../api/types'

export const OWL_THING = 'http://www.w3.org/2002/07/owl#Thing'

export interface TreeNode { iri: string; label: string | null; children: TreeNode[] }

/** Build a nested tree from a flat class list using superClasses.
 *  Roots = classes with no named superclass (or only owl:Thing). Cyclic edges are skipped. */
export function buildTree(classes: ClassDto[]): TreeNode[] {
  const byIri = new Map<string, ClassDto>()
  for (const c of classes) byIri.set(c.iri, c)

  const parentsOf = (c: ClassDto): string[] =>
    c.superClasses.filter(s => s !== OWL_THING && byIri.has(s))

  const isRoot = (c: ClassDto): boolean => parentsOf(c).length === 0

  const childrenOf = (parentIri: string, ancestors: Set<string>): TreeNode[] => {
    if (ancestors.has(parentIri)) return []
    const path = new Set(ancestors).add(parentIri)
    return classes
      .filter(c => parentsOf(c).includes(parentIri))
      .map(c => ({ iri: c.iri, label: c.label, children: childrenOf(c.iri, path) }))
  }

  return classes
    .filter(isRoot)
    .map(c => ({ iri: c.iri, label: c.label, children: childrenOf(c.iri, new Set<string>()) }))
}
