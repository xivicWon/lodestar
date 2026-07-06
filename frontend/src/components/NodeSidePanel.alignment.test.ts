import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import NodeSidePanel from './NodeSidePanel.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

function seed() {
  const s = useOntologyStore()
  s.classes = [{ iri: 'src#a', label: '자산', superClasses: [], annotations: [] }]
  s.referenceClasses = [{ iri: 'ref#Person', label: 'Person', superClasses: [], annotations: [] }]
  s.alignments = [{ sourceIri: 'src#a', targetIri: 'ref#Person', matchType: 'CLOSE', confidence: 0.8, provenance: 'manual' }]
  s.selectedIri = 'src#a'
  return s
}

describe('NodeSidePanel alignments', () => {
  it('shows alignment badges for the selected class with target label and match type', () => {
    seed()
    const w = mount(NodeSidePanel)
    const t = w.find('.alignments').text()
    expect(t).toContain('Person')
    expect(t.toLowerCase()).toContain('closematch')
  })

  it('emits add-alignment from the action button', async () => {
    seed()
    const w = mount(NodeSidePanel)
    await w.find('.align-add-btn').trigger('click')
    expect(w.emitted('add-alignment')).toBeTruthy()
  })
})
