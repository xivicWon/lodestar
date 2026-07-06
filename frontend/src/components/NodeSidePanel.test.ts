import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import NodeSidePanel from './NodeSidePanel.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

function seed() {
  const s = useOntologyStore()
  s.classes = [
    { iri: 'e#tb_ast_chk_lst', label: '자산 점검 체크리스트', superClasses: [], annotations: [] },
    { iri: 'e#tb_usr', label: '사용자', superClasses: [], annotations: [] },
    { iri: 'e#tb_doc', label: '문서', superClasses: [], annotations: [] },
  ]
  s.objectProperties = [
    { iri: 'e#r1', label: 'hasUser', domains: ['e#tb_ast_chk_lst'], ranges: ['e#tb_usr'], characteristics: [], inverseOf: null, annotations: [] },
    { iri: 'e#r2', label: 'refersTo', domains: ['e#tb_doc'], ranges: ['e#tb_ast_chk_lst'], characteristics: [], inverseOf: null, annotations: [] },
  ]
  s.selectedIri = 'e#tb_ast_chk_lst'
  return s
}

describe('NodeSidePanel', () => {
  it('renders nothing when no class is selected', () => {
    useOntologyStore()
    const w = mount(NodeSidePanel)
    expect(w.find('.side-panel').exists()).toBe(false)
  })

  it('shows the label and original table name of the selected class', () => {
    seed()
    const w = mount(NodeSidePanel)
    expect(w.find('.sp-label').text()).toBe('자산 점검 체크리스트')
    expect(w.find('.sp-orig').text()).toContain('tb_ast_chk_lst')
  })

  it('lists outgoing and incoming relation mappings', () => {
    seed()
    const w = mount(NodeSidePanel)
    const maps = w.findAll('.map').map(m => m.text())
    // 나가는: hasUser → 사용자
    expect(maps.some(t => t.includes('나감') && t.includes('hasUser') && t.includes('사용자'))).toBe(true)
    // 들어오는: 문서 → refersTo
    expect(maps.some(t => t.includes('들어옴') && t.includes('refersTo') && t.includes('문서'))).toBe(true)
  })

  it('marks the class as confirmed when a confirmation exists', () => {
    const s = seed()
    s.confirmations = [{ iri: 'e#tb_ast_chk_lst', label: '자산 점검 체크리스트', kind: 'class' }]
    const w = mount(NodeSidePanel)
    expect(w.find('.chip').text()).toContain('확정')
  })

  it('saves label edits via saveClass', async () => {
    const s = seed()
    const spy = vi.spyOn(s, 'saveClass').mockResolvedValue(undefined as never)
    const w = mount(NodeSidePanel)
    await w.find('.label-input').setValue('자산 체크리스트')
    await w.find('.save-btn').trigger('click')
    expect(spy).toHaveBeenCalledWith('e#tb_ast_chk_lst', expect.objectContaining({ label: '자산 체크리스트' }))
  })

  it('emits close and add-relation from the header and action button', async () => {
    seed()
    const w = mount(NodeSidePanel)
    await w.find('.sp-close').trigger('click')
    expect(w.emitted('close')).toBeTruthy()
    await w.find('.add-rel-btn').trigger('click')
    expect(w.emitted('add-relation')).toBeTruthy()
  })
})
