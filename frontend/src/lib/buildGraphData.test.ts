import { describe, it, expect } from 'vitest'
import { buildGraphData, shortName } from './buildGraphData'
import type { ClassDto, ObjectPropertyDto } from '../api/types'

const classes: ClassDto[] = [
  { iri: 'e#customers', label: 'customers', superClasses: [], annotations: [] },
  { iri: 'e#orders', label: 'orders', superClasses: [], annotations: [] },
]
function op(partial: Partial<ObjectPropertyDto>): ObjectPropertyDto {
  return { iri: 'e#r', label: null, domains: [], ranges: [], characteristics: [], inverseOf: null, annotations: [], ...partial }
}

describe('shortName', () => {
  it('takes fragment after # then last path segment', () => {
    expect(shortName('http://x/rdb/shop#orders')).toBe('orders')
    expect(shortName('http://x/orders')).toBe('orders')
  })
})

describe('buildGraphData', () => {
  it('maps each class to a node', () => {
    const g = buildGraphData(classes, [])
    expect(g.nodes).toEqual([
      { id: 'e#customers', label: 'customers' },
      { id: 'e#orders', label: 'orders' },
    ])
  })

  it('maps object property to a directed edge with label', () => {
    const g = buildGraphData(classes, [op({
      iri: 'e#orders_customer_id_ref', label: 'placedBy',
      domains: ['e#orders'], ranges: ['e#customers'],
    })])
    expect(g.edges).toEqual([
      { from: 'e#orders', to: 'e#customers', label: 'placedBy', arrows: 'to' },
    ])
  })

  it('falls back to short iri when label missing', () => {
    const g = buildGraphData(classes, [op({
      iri: 'e#rel_x', label: null, domains: ['e#orders'], ranges: ['e#customers'],
    })])
    expect(g.edges[0].label).toBe('rel_x')
  })

  it('skips edges without domain or range', () => {
    const g = buildGraphData(classes, [
      op({ domains: [], ranges: ['e#customers'] }),
      op({ domains: ['e#orders'], ranges: [] }),
    ])
    expect(g.edges).toEqual([])
  })

  it('keeps self-referencing edge (from == to)', () => {
    const g = buildGraphData(classes, [op({
      iri: 'e#emp_mgr', label: 'manages', domains: ['e#orders'], ranges: ['e#orders'],
    })])
    expect(g.edges[0].from).toBe(g.edges[0].to)
  })
})
