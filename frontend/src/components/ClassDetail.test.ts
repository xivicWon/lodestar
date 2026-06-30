import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import ClassDetail from './ClassDetail.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

describe('ClassDetail', () => {
  it('shows empty state when nothing selected', () => {
    useOntologyStore()
    const wrapper = mount(ClassDetail)
    expect(wrapper.text()).toContain('선택된 클래스가 없습니다')
  })

  it('edits label and calls saveClass on save', async () => {
    const s = useOntologyStore()
    s.classes = [{ iri: 'e#Dog', label: 'Dog', superClasses: ['e#Animal'], annotations: [] }]
    s.select('e#Dog')
    const save = vi.spyOn(s, 'saveClass').mockResolvedValue()
    const wrapper = mount(ClassDetail)

    await wrapper.find('input.label-input').setValue('Doggo')
    await wrapper.find('button.save-btn').trigger('click')
    expect(save).toHaveBeenCalledWith('e#Dog', { label: 'Doggo', superClasses: ['e#Animal'] })
  })
})
