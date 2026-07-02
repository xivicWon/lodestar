import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ChatPanel from './ChatPanel.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

describe('ChatPanel', () => {
  it('sends the question on button click', async () => {
    const store = useOntologyStore()
    const spy = vi.spyOn(store, 'askChat').mockResolvedValue()
    const w = mount(ChatPanel)
    await w.find('.chat-input').setValue('고객은?')
    await w.find('.chat-send-btn').trigger('click')
    expect(spy).toHaveBeenCalledWith('고객은?')
  })

  it('renders existing messages', () => {
    const store = useOntologyStore()
    store.chatMessages = [
      { role: 'user', text: '무엇이 있나요?' },
      { role: 'assistant', text: '고객과 주문이 있습니다.' },
    ] as any
    const w = mount(ChatPanel)
    expect(w.text()).toContain('무엇이 있나요?')
    expect(w.text()).toContain('고객과 주문이 있습니다.')
  })

  it('does not send blank questions', async () => {
    const store = useOntologyStore()
    const spy = vi.spyOn(store, 'askChat').mockResolvedValue()
    const w = mount(ChatPanel)
    await w.find('.chat-input').setValue('   ')
    await w.find('.chat-send-btn').trigger('click')
    expect(spy).not.toHaveBeenCalled()
  })
})
