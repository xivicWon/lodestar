import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import App from './App.vue'
import { useOntologyStore } from './stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

// 그래프(vis-network)는 App 테스트 관심사가 아니므로 스텁으로 대체한다.
const appStubs = { RelationsView: { template: '<div class="stub-relations" />' } }
const mountApp = () => mount(App, { global: { stubs: appStubs } })

describe('App', () => {
  it('renders toolbar + tree + graph main and refreshes on mount', async () => {
    const s = useOntologyStore()
    const refresh = vi.spyOn(s, 'refresh').mockResolvedValue()
    vi.spyOn(s, 'fetchConfirmations').mockResolvedValue()
    vi.spyOn(s, 'fetchReference').mockResolvedValue()
    const wrapper = mountApp()
    expect(wrapper.find('.toolbar').exists()).toBe(true)
    expect(wrapper.find('.class-tree').exists()).toBe(true)
    // 상세는 side panel 로 이동 → 초기(미선택)엔 안 뜨고, 그래프 메인이 자리한다.
    expect(wrapper.find('.stub-relations').exists()).toBe(true)
    expect(wrapper.find('.link-cta').exists()).toBe(true)
    expect(refresh).toHaveBeenCalled()
  })

  it('shows error banner when store.error is set, and dismiss clears it', async () => {
    const store = useOntologyStore()
    vi.spyOn(store, 'refresh').mockResolvedValue()
    vi.spyOn(store, 'fetchConfirmations').mockResolvedValue()
    vi.spyOn(store, 'fetchReference').mockResolvedValue()
    const wrapper = mountApp()
    store.error = '온톨로지 파일을 읽을 수 없습니다'
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.error-banner').exists()).toBe(true)
    expect(wrapper.find('.error-banner').text()).toContain('온톨로지 파일을 읽을 수 없습니다')
    await wrapper.find('.dismiss-error').trigger('click')
    expect(store.error).toBeNull()
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.error-banner').exists()).toBe(false)
  })

  it('shows pipeline step status: import done with count, reason consistent', async () => {
    const store = useOntologyStore()
    vi.spyOn(store, 'refresh').mockResolvedValue()
    vi.spyOn(store, 'fetchConfirmations').mockResolvedValue()
    vi.spyOn(store, 'fetchReference').mockResolvedValue()
    store.classes = [
      { iri: 'e#A', label: 'A', superClasses: [], annotations: [] },
      { iri: 'e#B', label: 'B', superClasses: [], annotations: [] },
    ]
    store.reasonResult = { consistent: true, inferredSubClassOf: [] } as any
    const wrapper = mountApp()
    await wrapper.vm.$nextTick()
    const chips = wrapper.findAll('.step-chip')
    // ① 가져오기: 완료(done) + 클래스 수 표시
    expect(chips[0].classes()).toContain('st-done')
    expect(chips[0].text()).toContain('2개')
    // ④ 검증·추론: reasonResult 일관성 OK → 완료
    const reasonChip = chips.find(c => c.text().includes('검증·추론'))!
    expect(reasonChip.classes()).toContain('st-done')
    expect(reasonChip.text()).toContain('일관성 OK')
    // ⑤ 질문: 활용 단계 → 상태 배지 없음(idle)
    const chatChip = chips.find(c => c.text().includes('질문'))!
    expect(chatChip.classes()).toContain('st-idle')
  })
})
