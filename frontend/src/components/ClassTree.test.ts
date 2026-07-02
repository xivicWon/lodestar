import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import ClassTree from './ClassTree.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

describe('ClassTree', () => {
  it('renders nested class labels and selects on click', async () => {
    const s = useOntologyStore()
    s.classes = [
      { iri: 'e#Animal', label: 'Animal', superClasses: [], annotations: [] },
      { iri: 'e#Dog', label: 'Dog', superClasses: ['e#Animal'], annotations: [] },
    ]
    const wrapper = mount(ClassTree)
    expect(wrapper.text()).toContain('Animal')
    expect(wrapper.text()).toContain('Dog')

    await wrapper.findAll('.node-label')[0].trigger('click')
    expect(s.selectedIri).toBe('e#Animal')
  })

  it('filters nodes by search query', async () => {
    const s = useOntologyStore()
    s.classes = [
      { iri: 'e#TB_CUST_MST', label: 'TB_CUST_MST', superClasses: [], annotations: [] },
      { iri: 'e#TB_ORD_HD', label: 'TB_ORD_HD', superClasses: [], annotations: [] },
      { iri: 'e#TB_ORD_DTL', label: 'TB_ORD_DTL', superClasses: [], annotations: [] },
    ]
    const wrapper = mount(ClassTree)
    await wrapper.find('.tree-search').setValue('ORD')
    expect(wrapper.text()).toContain('TB_ORD_HD')
    expect(wrapper.text()).toContain('TB_ORD_DTL')
    expect(wrapper.text()).not.toContain('TB_CUST_MST')
  })
})
