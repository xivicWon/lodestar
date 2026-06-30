import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import Toolbar from './Toolbar.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

describe('Toolbar', () => {
  it('creates a class from prompt input', async () => {
    const s = useOntologyStore()
    const create = vi.spyOn(s, 'createClass').mockResolvedValue()
    vi.stubGlobal('prompt', vi.fn(() => 'Animal'))
    const wrapper = mount(Toolbar)
    await wrapper.find('button.add-class-btn').trigger('click')
    expect(create).toHaveBeenCalledWith('Animal')
    vi.unstubAllGlobals()
  })

  it('deletes the selected class', async () => {
    const s = useOntologyStore()
    s.classes = [{ iri: 'e#Dog', label: 'Dog', superClasses: [], annotations: [] }]
    s.select('e#Dog')
    const del = vi.spyOn(s, 'deleteClass').mockResolvedValue()
    const wrapper = mount(Toolbar)
    await wrapper.find('button.delete-btn').trigger('click')
    expect(del).toHaveBeenCalledWith('e#Dog')
  })
})
