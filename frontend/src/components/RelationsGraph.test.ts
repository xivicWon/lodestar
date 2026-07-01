import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

const h = vi.hoisted(() => {
  const clickHandlers: Array<(p: any) => void> = []
  const NetworkMock = vi.fn().mockImplementation(() => ({
    on: (evt: string, cb: (p: any) => void) => { if (evt === 'click') clickHandlers.push(cb) },
    destroy: vi.fn(),
  }))
  class DataSetMock {
    items: any[]
    constructor(init: any[] = []) { this.items = [...init] }
    add(x: any) { this.items.push(...([] as any[]).concat(x)) }
    clear() { this.items = [] }
    get() { return this.items }
    update(_x: any) { /* no-op */ }
  }
  return { clickHandlers, NetworkMock, DataSetMock }
})
const { clickHandlers, NetworkMock } = h
vi.mock('vis-network/standalone', () => ({ Network: h.NetworkMock, DataSet: h.DataSetMock }))

import RelationsGraph from './RelationsGraph.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => {
  setActivePinia(createPinia())
  clickHandlers.length = 0
  NetworkMock.mockClear()
})

describe('RelationsGraph', () => {
  it('creates a vis Network on mount with a container', () => {
    const w = mount(RelationsGraph, { attachTo: document.body })
    expect(NetworkMock).toHaveBeenCalledTimes(1)
    expect(w.find('.relations-graph').exists()).toBe(true)
  })

  it('node click selects the class in the store', () => {
    const store = useOntologyStore()
    mount(RelationsGraph, { attachTo: document.body })
    expect(clickHandlers.length).toBe(1)
    clickHandlers[0]({ nodes: ['e#orders'], edges: [] })
    expect(store.selectedIri).toBe('e#orders')
  })
})
