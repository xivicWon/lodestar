import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import AlignmentModal from './AlignmentModal.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

function seed() {
  const s = useOntologyStore()
  s.classes = [{ iri: 'src#a', label: '자산', superClasses: [], annotations: [] }]
  s.referenceClasses = [{ iri: 'ref#Person', label: 'Person', superClasses: [], annotations: [] }]
  s.selectedIri = 'src#a'
  return s
}

describe('AlignmentModal', () => {
  it('defaults the source to the selected class and lists reference classes as targets', () => {
    seed()
    const w = mount(AlignmentModal)
    expect((w.find('.from-select').element as HTMLSelectElement).value).toBe('src#a')
    expect(w.findAll('.to-select option').some(o => o.text().includes('Person'))).toBe(true)
  })

  it('creates the alignment with the chosen match type and emits close', async () => {
    const s = seed()
    const spy = vi.spyOn(s, 'createAlignment').mockResolvedValue(undefined as never)
    const w = mount(AlignmentModal)
    await w.find('.to-select').setValue('ref#Person')
    await w.find('.match-select').setValue('CLOSE')
    await w.find('.conf-input').setValue('0.8')
    await w.find('.submit-btn').trigger('click')
    expect(spy).toHaveBeenCalledWith('src#a', 'ref#Person', 'CLOSE', 0.8)
    expect(w.emitted('close')).toBeTruthy()
  })

  it('keeps submit disabled until a target is chosen', () => {
    seed()
    const w = mount(AlignmentModal)
    expect((w.find('.submit-btn').element as HTMLButtonElement).disabled).toBe(true)
  })
})
