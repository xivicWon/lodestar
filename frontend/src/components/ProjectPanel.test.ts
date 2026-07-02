import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ProjectPanel from './ProjectPanel.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

describe('ProjectPanel', () => {
  it('lists projects on mount', () => {
    const store = useOntologyStore()
    const spy = vi.spyOn(store, 'listProjects').mockResolvedValue()
    mount(ProjectPanel)
    expect(spy).toHaveBeenCalled()
  })

  it('saveProject called with entered name on save click', async () => {
    const store = useOntologyStore()
    vi.spyOn(store, 'listProjects').mockResolvedValue()
    const spy = vi.spyOn(store, 'saveProject').mockResolvedValue()
    const w = mount(ProjectPanel)
    await w.find('.project-name-input').setValue('myproj')
    await w.find('.project-save-btn').trigger('click')
    expect(spy).toHaveBeenCalledWith('myproj')
  })

  it('renders project list with load buttons that call loadProject', async () => {
    const store = useOntologyStore()
    vi.spyOn(store, 'listProjects').mockResolvedValue()
    store.projects = ['t']
    const spy = vi.spyOn(store, 'loadProject').mockResolvedValue()
    const w = mount(ProjectPanel)
    expect(w.find('.project-list').text()).toContain('t')
    await w.find('.project-load-btn').trigger('click')
    expect(spy).toHaveBeenCalledWith('t')
  })
})
