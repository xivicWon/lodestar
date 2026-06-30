import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import App from './App.vue'
import { useOntologyStore } from './stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

describe('App', () => {
  it('renders toolbar + tree + detail and refreshes on mount', async () => {
    const s = useOntologyStore()
    const refresh = vi.spyOn(s, 'refresh').mockResolvedValue()
    const wrapper = mount(App)
    expect(wrapper.find('.toolbar').exists()).toBe(true)
    expect(wrapper.find('.class-tree').exists()).toBe(true)
    expect(wrapper.find('.class-detail').exists()).toBe(true)
    expect(refresh).toHaveBeenCalled()
  })
})
