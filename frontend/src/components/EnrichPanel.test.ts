import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import EnrichPanel from './EnrichPanel.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

const cand = { targetIri: 'e#TB_CUST_MST', currentName: 'TB_CUST_MST', suggestedLabel: '고객 마스터', description: '거래처 기본정보' }

describe('EnrichPanel', () => {
  it('runs enrichment on button click', async () => {
    const store = useOntologyStore()
    const spy = vi.spyOn(store, 'enrichSample').mockResolvedValue()
    const w = mount(EnrichPanel)
    await w.find('.enrich-run-btn').trigger('click')
    expect(spy).toHaveBeenCalled()
  })

  it('renders candidates and approves one', async () => {
    const store = useOntologyStore()
    store.enrichCandidates = [cand] as any
    const spy = vi.spyOn(store, 'applyEnrichment').mockResolvedValue()
    const w = mount(EnrichPanel)
    expect(w.text()).toContain('TB_CUST_MST')
    expect(w.text()).toContain('고객 마스터')
    await w.find('.approve-btn').trigger('click')
    expect(spy).toHaveBeenCalledWith('e#TB_CUST_MST', '고객 마스터')
  })
})
