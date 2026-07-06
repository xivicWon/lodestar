import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import RelationLinkModal from './RelationLinkModal.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

function seed() {
  const s = useOntologyStore()
  s.classes = [
    { iri: 'e#tb_ord', label: '주문', superClasses: [], annotations: [] },
    { iri: 'e#tb_usr', label: '사용자', superClasses: [], annotations: [] },
  ]
  return s
}

describe('RelationLinkModal', () => {
  it('lists classes as options with label and original table name', () => {
    seed()
    const w = mount(RelationLinkModal)
    const texts = w.findAll('.from-select option').map(o => o.text())
    expect(texts.some(t => t.includes('주문') && t.includes('tb_ord'))).toBe(true)
  })

  it('defaults the source to the selected class', () => {
    const s = seed()
    s.selectedIri = 'e#tb_ord'
    const w = mount(RelationLinkModal)
    expect((w.find('.from-select').element as HTMLSelectElement).value).toBe('e#tb_ord')
  })

  it('keeps submit disabled until from, to and name are valid', async () => {
    seed()
    const w = mount(RelationLinkModal)
    const btn = () => w.find('.submit-btn')
    expect((btn().element as HTMLButtonElement).disabled).toBe(true)
    await w.find('.from-select').setValue('e#tb_ord')
    await w.find('.to-select').setValue('e#tb_usr')
    await w.find('.name-input').setValue('hasUser')
    expect((btn().element as HTMLButtonElement).disabled).toBe(false)
  })

  it('creates the relation via applyRelation and emits close', async () => {
    const s = seed()
    const spy = vi.spyOn(s, 'applyRelation').mockResolvedValue(undefined as never)
    const w = mount(RelationLinkModal)
    await w.find('.from-select').setValue('e#tb_ord')
    await w.find('.to-select').setValue('e#tb_usr')
    await w.find('.name-input').setValue('hasUser')
    await w.find('.submit-btn').trigger('click')
    expect(spy).toHaveBeenCalledWith('e#tb_ord', 'e#tb_usr', 'hasUser')
    expect(w.emitted('close')).toBeTruthy()
  })

  it('does not submit when source equals target', async () => {
    const s = seed()
    const spy = vi.spyOn(s, 'applyRelation').mockResolvedValue(undefined as never)
    const w = mount(RelationLinkModal)
    await w.find('.from-select').setValue('e#tb_ord')
    await w.find('.to-select').setValue('e#tb_ord')
    await w.find('.name-input').setValue('selfRef')
    expect((w.find('.submit-btn').element as HTMLButtonElement).disabled).toBe(true)
    await w.find('.submit-btn').trigger('click')
    expect(spy).not.toHaveBeenCalled()
  })
})
