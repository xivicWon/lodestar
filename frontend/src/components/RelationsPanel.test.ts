import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import RelationsPanel from './RelationsPanel.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

describe('RelationsPanel', () => {
  it('renders each object property as domain → range', () => {
    const store = useOntologyStore()
    store.objectProperties = [{
      iri: 'e#orders_customer_id_ref', label: 'orders → customers',
      domains: ['e#orders'], ranges: ['e#customers'], characteristics: [], inverseOf: null, annotations: [],
    }] as any
    const w = mount(RelationsPanel)
    expect(w.text()).toContain('orders')
    expect(w.text()).toContain('customers')
    expect(w.findAll('.relation-row').length).toBe(1)
  })

  it('renames relation via prompt on rename button click', async () => {
    const store = useOntologyStore()
    store.objectProperties = [{
      iri: 'e#orders_customer_id_ref', label: 'orders → customers',
      domains: ['e#orders'], ranges: ['e#customers'], characteristics: [], inverseOf: null, annotations: [],
    }] as any
    const spy = vi.spyOn(store, 'renameRelation').mockResolvedValue()
    vi.spyOn(window, 'prompt').mockReturnValue('placedBy')
    const w = mount(RelationsPanel)
    await w.find('.rename-btn').trigger('click')
    expect(spy).toHaveBeenCalledWith('e#orders_customer_id_ref', 'placedBy')
  })

  it('shows empty hint when no relations', () => {
    useOntologyStore()
    const w = mount(RelationsPanel)
    expect(w.text()).toContain('관계가 없습니다')
  })
})
