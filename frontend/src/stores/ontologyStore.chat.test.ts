import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useOntologyStore } from './ontologyStore'
import * as client from '../api/client'
import { ApiError } from '../api/client'

beforeEach(() => setActivePinia(createPinia()))
afterEach(() => vi.restoreAllMocks())

describe('ontologyStore AI chat', () => {
  it('askChat appends user and assistant messages', async () => {
    const spy = vi.spyOn(client, 'apiPost').mockResolvedValue({ answer: '고객과 주문이 있습니다.' } as any)
    const s = useOntologyStore()
    await s.askChat('무엇이 있나요?')
    expect(spy).toHaveBeenCalledWith('/ai/chat', { question: '무엇이 있나요?' })
    expect(s.chatMessages).toEqual([
      { role: 'user', text: '무엇이 있나요?' },
      { role: 'assistant', text: '고객과 주문이 있습니다.' },
    ])
    expect(s.asking).toBe(false)
  })

  it('askChat ignores empty questions', async () => {
    const spy = vi.spyOn(client, 'apiPost').mockResolvedValue({ answer: 'x' } as any)
    const s = useOntologyStore()
    await s.askChat('   ')
    expect(spy).not.toHaveBeenCalled()
    expect(s.chatMessages).toEqual([])
  })

  it('askChat records error and keeps the user message', async () => {
    vi.spyOn(client, 'apiPost').mockRejectedValue(new ApiError('ai_failed', 'AI 실패', null))
    const s = useOntologyStore()
    await s.askChat('질문?')
    expect(s.error).toBe('AI 실패')
    expect(s.chatMessages).toEqual([{ role: 'user', text: '질문?' }])
    expect(s.asking).toBe(false)
  })
})
