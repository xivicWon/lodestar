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
})
