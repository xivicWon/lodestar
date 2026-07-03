import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import TrashPanel from './TrashPanel.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

describe('TrashPanel', () => {
  it('fetches trash on mount', () => {
    const store = useOntologyStore()
    const spy = vi.spyOn(store, 'fetchTrash').mockResolvedValue()
    mount(TrashPanel)
    expect(spy).toHaveBeenCalled()
  })

  it('shows empty hint when no entries', () => {
    const store = useOntologyStore()
    vi.spyOn(store, 'fetchTrash').mockResolvedValue()
    const w = mount(TrashPanel)
    expect(w.find('.trash-empty').exists()).toBe(true)
  })

  it('renders entries and buttons call restore/purge', async () => {
    const store = useOntologyStore()
    vi.spyOn(store, 'fetchTrash').mockResolvedValue()
    store.trash = [{ iri: 'e#A', label: 'TB_A', trashedAt: Date.now() }]
    const restore = vi.spyOn(store, 'restoreTrash').mockResolvedValue()
    const purge = vi.spyOn(store, 'purgeTrash').mockResolvedValue()
    const w = mount(TrashPanel)
    expect(w.find('.trash-list').text()).toContain('TB_A')
    await w.find('.trash-restore-btn').trigger('click')
    expect(restore).toHaveBeenCalledWith('e#A')
    await w.find('.trash-purge-btn').trigger('click')
    expect(purge).toHaveBeenCalledWith('e#A')
  })
})
