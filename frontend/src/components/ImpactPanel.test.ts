import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ImpactPanel from './ImpactPanel.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

describe('ImpactPanel', () => {
  it('runs fetchImpact for the selected class on button click', async () => {
    const store = useOntologyStore()
    store.select('e#B')
    const spy = vi.spyOn(store, 'fetchImpact').mockResolvedValue()
    const w = mount(ImpactPanel)
    await w.find('.impact-run-btn').trigger('click')
    expect(spy).toHaveBeenCalledWith('e#B')
  })

  it('renders upstream and downstream by short name', () => {
    const store = useOntologyStore()
    store.impact = { iri: 'e#B', upstream: ['e#A'], downstream: ['e#C'] } as any
    const w = mount(ImpactPanel)
    expect(w.find('.upstream-list').text()).toContain('A')
    expect(w.find('.downstream-list').text()).toContain('C')
  })

  it('clicking an impacted item selects it', async () => {
    const store = useOntologyStore()
    store.impact = { iri: 'e#B', upstream: ['e#A'], downstream: ['e#C'] } as any
    const spy = vi.spyOn(store, 'select')
    const w = mount(ImpactPanel)
    await w.find('.downstream-list .impact-item').trigger('click')
    expect(spy).toHaveBeenCalledWith('e#C')
  })
})
