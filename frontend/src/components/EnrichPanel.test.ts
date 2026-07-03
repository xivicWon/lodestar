import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import EnrichPanel from './EnrichPanel.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

const cand = { targetIri: 'e#TB_CUST_MST', currentName: 'TB_CUST_MST', suggestedLabel: '고객 마스터', description: '거래처 기본정보' }

describe('EnrichPanel', () => {
  it('runs current-ontology enrichment on button click', async () => {
    const store = useOntologyStore()
    const spy = vi.spyOn(store, 'enrichCurrent').mockResolvedValue()
    const w = mount(EnrichPanel)
    await w.find('.enrich-run-btn').trigger('click')
    expect(spy).toHaveBeenCalled()
  })

  it('renders candidates and confirms one on approve', async () => {
    const store = useOntologyStore()
    store.enrichCandidates = [cand] as any
    const spy = vi.spyOn(store, 'confirm').mockResolvedValue()
    const w = mount(EnrichPanel)
    expect(w.text()).toContain('TB_CUST_MST')
    expect(w.text()).toContain('고객 마스터')
    await w.find('.approve-btn').trigger('click')
    expect(spy).toHaveBeenCalledWith('e#TB_CUST_MST', '고객 마스터')
  })

  it('renders confirmed count', () => {
    const store = useOntologyStore()
    store.confirmations = [
      { iri: 'e#A', label: '고객', kind: 'class' },
      { iri: 'e#B', label: '주문', kind: 'class' },
    ] as any
    const w = mount(EnrichPanel)
    expect(w.find('.confirm-count').text()).toContain('확정 2건')
  })

  it('runs current-ontology scored evaluation on button click', async () => {
    const store = useOntologyStore()
    const spy = vi.spyOn(store, 'scoredEnrichCurrent').mockResolvedValue()
    const w = mount(EnrichPanel)
    await w.find('.scored-run-btn').trigger('click')
    expect(spy).toHaveBeenCalledWith(5)
  })

  it('renders scored candidate with confidence badge and approves consensus label', async () => {
    const store = useOntologyStore()
    store.scoredCandidates = [{
      targetIri: 'e#TB_ORD_HD', currentName: 'TB_ORD_HD', consensusLabel: '주문 헤더',
      description: '주문 전표', agreement: 0.6, n: 5,
      variants: [{ label: '주문 헤더', count: 3 }, { label: '오더 정보', count: 2 }],
    }] as any
    const spy = vi.spyOn(store, 'confirm').mockResolvedValue()
    const w = mount(EnrichPanel)
    // agreement 0.6 → amber '보통' badge
    const badge = w.find('.agree-badge')
    expect(badge.classes()).toContain('badge-mid')
    expect(badge.text()).toContain('보통')
    expect(badge.text()).toContain('60%')
    expect(w.text()).toContain('주문 헤더')
    expect(w.text()).toContain('오더 정보 ×2')
    await w.find('.scored-list .approve-btn').trigger('click')
    expect(spy).toHaveBeenCalledWith('e#TB_ORD_HD', '주문 헤더')
  })

  it('shows green 확신 badge for high agreement', () => {
    const store = useOntologyStore()
    store.scoredCandidates = [{
      targetIri: 'e#X', currentName: 'X', consensusLabel: 'L', description: '',
      agreement: 0.9, n: 5, variants: [{ label: 'L', count: 5 }],
    }] as any
    const w = mount(EnrichPanel)
    const badge = w.find('.agree-badge')
    expect(badge.classes()).toContain('badge-high')
    expect(badge.text()).toContain('확신')
  })
})
