import { describe, it, expect, beforeEach, vi } from 'vitest'
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

  it('shows a sequential number badge per class', () => {
    const s = useOntologyStore()
    s.classes = [
      { iri: 'e#Animal', label: 'Animal', superClasses: [], annotations: [] },
      { iri: 'e#Dog', label: 'Dog', superClasses: ['e#Animal'], annotations: [] },
    ]
    const wrapper = mount(ClassTree)
    const nums = wrapper.findAll('.node-num').map(n => n.text())
    expect(nums).toEqual(['1', '2'])
  })

  it('trashes a class when its × button is clicked', async () => {
    const s = useOntologyStore()
    s.classes = [
      { iri: 'e#Animal', label: 'Animal', superClasses: [], annotations: [] },
    ]
    const spy = vi.spyOn(s, 'trashClass').mockResolvedValue(undefined as never)
    const wrapper = mount(ClassTree)
    await wrapper.find('.node-del').trigger('click')
    expect(spy).toHaveBeenCalledWith('e#Animal')
  })

  it('shows the original table name (iri fragment) when the label differs', () => {
    const s = useOntologyStore()
    s.classes = [
      { iri: 'e#tb_ast_chk_lst', label: '자산 점검 체크리스트', superClasses: [], annotations: [] },
    ]
    const wrapper = mount(ClassTree)
    const orig = wrapper.find('.node-orig')
    expect(orig.exists()).toBe(true)
    expect(orig.text()).toContain('tb_ast_chk_lst')
  })

  it('hides the original table name when the label equals the iri fragment', () => {
    const s = useOntologyStore()
    s.classes = [
      { iri: 'e#tb_usr', label: 'tb_usr', superClasses: [], annotations: [] },
    ]
    const wrapper = mount(ClassTree)
    expect(wrapper.find('.node-orig').exists()).toBe(false)
  })

  it('matches search by original table name even after enrich renamed the label', async () => {
    const s = useOntologyStore()
    s.classes = [
      { iri: 'e#tb_ord_hd', label: '주문 헤더', superClasses: [], annotations: [] },
      { iri: 'e#tb_cust_mst', label: '고객 마스터', superClasses: [], annotations: [] },
    ]
    const wrapper = mount(ClassTree)
    await wrapper.find('.tree-search').setValue('tb_ord')
    expect(wrapper.text()).toContain('주문 헤더')
    expect(wrapper.text()).not.toContain('고객 마스터')
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
