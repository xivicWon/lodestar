import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

const h = vi.hoisted(() => {
  const clickHandlers: Array<(p: any) => void> = []
  const NetworkMock = vi.fn().mockImplementation(() => ({
    on: (evt: string, cb: (p: any) => void) => { if (evt === 'click') clickHandlers.push(cb) },
    setOptions: vi.fn(),
    fit: vi.fn(),
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

  it('in link mode, clicking two nodes creates a relation via applyRelation', async () => {
    const store = useOntologyStore()
    const spy = vi.spyOn(store, 'applyRelation').mockResolvedValue(undefined as never)
    vi.spyOn(window, 'prompt').mockReturnValue('placedBy')
    const w = mount(RelationsGraph, { attachTo: document.body })
    await w.find('.link-toggle').trigger('click') // 관계 추가 모드 진입
    clickHandlers[0]({ nodes: ['e#orders'], edges: [] })   // 출발
    clickHandlers[0]({ nodes: ['e#customers'], edges: [] }) // 도착
    expect(spy).toHaveBeenCalledWith('e#orders', 'e#customers', 'placedBy')
    expect(store.selectedIri).toBeNull() // 링크 모드에선 선택되지 않음
  })

  it('link mode does not create a relation when prompt is cancelled', async () => {
    const store = useOntologyStore()
    const spy = vi.spyOn(store, 'applyRelation').mockResolvedValue(undefined as never)
    vi.spyOn(window, 'prompt').mockReturnValue(null)
    const w = mount(RelationsGraph, { attachTo: document.body })
    await w.find('.link-toggle').trigger('click')
    clickHandlers[0]({ nodes: ['e#orders'], edges: [] })
    clickHandlers[0]({ nodes: ['e#customers'], edges: [] })
    expect(spy).not.toHaveBeenCalled()
  })
})
