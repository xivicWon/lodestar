import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import ConsistencyBadge from './ConsistencyBadge.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

describe('ConsistencyBadge', () => {
  it('is empty before reasoning', () => {
    useOntologyStore()
    expect(mount(ConsistencyBadge).text()).toBe('')
  })
  it('shows OK when consistent', () => {
    const s = useOntologyStore()
    s.reasonResult = { consistent: true, unsatisfiableClasses: [], inferredSubClassOf: [] }
    expect(mount(ConsistencyBadge).text()).toContain('일관성 OK')
  })
  it('shows contradiction when inconsistent', () => {
    const s = useOntologyStore()
    s.reasonResult = { consistent: false, unsatisfiableClasses: ['http://ex#A'], inferredSubClassOf: [] }
    const t = mount(ConsistencyBadge).text()
    expect(t).toContain('모순')
    expect(t).toContain('A')
  })
})
