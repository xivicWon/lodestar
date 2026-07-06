import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ClassTree from './ClassTree.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

describe('ClassTree reference section', () => {
  it('shows a load button when no reference ontology is loaded', () => {
    useOntologyStore()
    const w = mount(ClassTree)
    expect(w.find('.reference-load-btn').exists()).toBe(true)
  })

  it('lists reference classes under a reference section when loaded', () => {
    const s = useOntologyStore()
    s.referenceMeta = { ontologyIri: 'ref', source: 'r.ttl', classCount: 1 }
    s.referenceClasses = [{ iri: 'ref#Person', label: 'Person', superClasses: [], annotations: [] }]
    const w = mount(ClassTree)
    expect(w.find('.reference-section').exists()).toBe(true)
    expect(w.text()).toContain('Person')
  })
})
