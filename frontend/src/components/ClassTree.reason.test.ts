import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import ClassTree from './ClassTree.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

describe('ClassTree inferred overlay', () => {
  it('renders inferred child under its inferred parent with a badge', () => {
    const s = useOntologyStore()
    s.classes = [
      { iri: 'e#Carnivore', label: '육식동물', superClasses: [], annotations: [] },
      { iri: 'e#Dog', label: '개', superClasses: ['e#Animal'], annotations: [] },
      { iri: 'e#Animal', label: '동물', superClasses: [], annotations: [] },
    ]
    s.reasonResult = { consistent: true, unsatisfiableClasses: [],
      inferredSubClassOf: [{ sub: 'e#Dog', sup: 'e#Carnivore' }] }
    const wrapper = mount(ClassTree)
    // Carnivore node shows an inferred child "개" tagged 추론됨
    const inferred = wrapper.find('.inferred-child')
    expect(inferred.exists()).toBe(true)
    expect(inferred.text()).toContain('개')
    expect(inferred.text()).toContain('추론됨')
  })
})
