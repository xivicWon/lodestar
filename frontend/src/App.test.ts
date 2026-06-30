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

  it('shows error banner when store.error is set, and dismiss clears it', async () => {
    const store = useOntologyStore()
    vi.spyOn(store, 'refresh').mockResolvedValue()
    const wrapper = mount(App)
    store.error = '온톨로지 파일을 읽을 수 없습니다'
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.error-banner').exists()).toBe(true)
    expect(wrapper.find('.error-banner').text()).toContain('온톨로지 파일을 읽을 수 없습니다')
    await wrapper.find('.dismiss-error').trigger('click')
    expect(store.error).toBeNull()
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.error-banner').exists()).toBe(false)
  })
})
