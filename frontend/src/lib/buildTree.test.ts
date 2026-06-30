import { describe, it, expect } from 'vitest'
import { buildTree, OWL_THING } from './buildTree'
import type { ClassDto } from '../api/types'

const cls = (iri: string, superClasses: string[] = []): ClassDto =>
  ({ iri, label: iri.split('#')[1] ?? iri, superClasses, annotations: [] })

describe('buildTree', () => {
  it('puts classes with no superclass at root', () => {
    const tree = buildTree([cls('e#Animal'), cls('e#Plant')])
    expect(tree.map(n => n.iri).sort()).toEqual(['e#Animal', 'e#Plant'])
  })

  it('nests a subclass under its parent', () => {
    const tree = buildTree([cls('e#Animal'), cls('e#Dog', ['e#Animal'])])
    const animal = tree.find(n => n.iri === 'e#Animal')!
    expect(animal.children.map(c => c.iri)).toEqual(['e#Dog'])
  })

  it('treats owl:Thing-only parent as root', () => {
    const tree = buildTree([cls('e#Animal', [OWL_THING])])
    expect(tree.map(n => n.iri)).toEqual(['e#Animal'])
  })

  it('shows a multi-parent class under each parent', () => {
    const tree = buildTree([cls('e#A'), cls('e#B'), cls('e#C', ['e#A', 'e#B'])])
    const a = tree.find(n => n.iri === 'e#A')!
    const b = tree.find(n => n.iri === 'e#B')!
    expect(a.children.map(c => c.iri)).toEqual(['e#C'])
    expect(b.children.map(c => c.iri)).toEqual(['e#C'])
  })

  it('does not infinite-loop on a cycle', () => {
    const tree = buildTree([cls('e#A', ['e#B']), cls('e#B', ['e#A'])])
    expect(Array.isArray(tree)).toBe(true) // returns without stack overflow
  })
})
