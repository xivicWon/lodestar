import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import RelationsView from './RelationsView.vue'

beforeEach(() => setActivePinia(createPinia()))

describe('RelationsView', () => {
  it('shows list by default and switches to graph on tab click', async () => {
    const w = mount(RelationsView, {
      global: { stubs: {
        RelationsPanel: { template: '<div class="stub-list" />' },
        RelationsGraph: { template: '<div class="stub-graph" />' },
      } },
    })
    expect(w.find('.stub-list').exists()).toBe(true)
    expect(w.find('.stub-graph').exists()).toBe(false)

    await w.find('.tab-graph').trigger('click')
    expect(w.find('.stub-graph').exists()).toBe(true)
    expect(w.find('.stub-list').exists()).toBe(false)

    await w.find('.tab-list').trigger('click')
    expect(w.find('.stub-list').exists()).toBe(true)
  })
})
