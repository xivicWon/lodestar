import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import RelationSuggestPanel from './RelationSuggestPanel.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

const cand = {
  fromIri: 'e#TB_ORD_HD', toIri: 'e#TB_CUST_MST',
  viaColumn: 'CUST_NO', confidence: 0.6, suggestedName: 'hasCust',
}

describe('RelationSuggestPanel', () => {
  it('runs suggestion on button click', async () => {
    const store = useOntologyStore()
    const spy = vi.spyOn(store, 'suggestRelations').mockResolvedValue()
    const w = mount(RelationSuggestPanel)
    await w.find('.rel-run-btn').trigger('click')
    expect(spy).toHaveBeenCalled()
  })

  it('renders candidates and approving calls applyRelation', async () => {
    const store = useOntologyStore()
    store.relCandidates = [cand] as any
    const spy = vi.spyOn(store, 'applyRelation').mockResolvedValue()
    const w = mount(RelationSuggestPanel)
    expect(w.text()).toContain('CUST_NO')
    expect(w.text()).toContain('hasCust')
    await w.find('.approve-btn').trigger('click')
    expect(spy).toHaveBeenCalledWith('e#TB_ORD_HD', 'e#TB_CUST_MST', 'hasCust')
  })

  it('AI 판정 button calls judgeRelations', async () => {
    const store = useOntologyStore()
    const spy = vi.spyOn(store, 'judgeRelations').mockResolvedValue()
    const w = mount(RelationSuggestPanel)
    await w.find('.rel-judge-btn').trigger('click')
    expect(spy).toHaveBeenCalled()
  })

  it('renders judged candidates with keep badge and approve calls applyRelation', async () => {
    const store = useOntologyStore()
    store.judgedRelations = [
      { ...cand, keep: true, reason: '말이 됨' },
      { ...cand, toIri: 'e#TB_X', suggestedName: 'hasX', keep: false, reason: '노이즈' },
    ] as any
    const spy = vi.spyOn(store, 'applyRelation').mockResolvedValue()
    const w = mount(RelationSuggestPanel)
    expect(w.text()).toContain('관계')
    expect(w.text()).toContain('제외')
    expect(w.text()).toContain('말이 됨')
    expect(w.text()).toContain('노이즈')
    // 이제 keep·drop 모두 승인+거부 버튼 → 최종 결정은 사람.
    const approve = w.findAll('.judged-list .approve-btn')
    const dismiss = w.findAll('.judged-list .dismiss-btn')
    expect(approve.length).toBe(2)
    expect(dismiss.length).toBe(2)
    await approve[0].trigger('click')
    expect(spy).toHaveBeenCalledWith('e#TB_ORD_HD', 'e#TB_CUST_MST', 'hasCust')
  })

  it('rejecting a judged (AI-kept) candidate calls dismissJudged (사람이 뒤집음)', async () => {
    const store = useOntologyStore()
    store.judgedRelations = [{ ...cand, keep: true, reason: '말이 됨' }] as any
    const spy = vi.spyOn(store, 'dismissJudged')
    const w = mount(RelationSuggestPanel)
    await w.find('.judged-list .dismiss-btn').trigger('click')
    expect(spy).toHaveBeenCalledWith('e#TB_ORD_HD', 'e#TB_CUST_MST', 'CUST_NO')
  })

  it('approving an AI-dropped candidate still calls applyRelation (사람이 되살림)', async () => {
    const store = useOntologyStore()
    store.judgedRelations = [{ ...cand, keep: false, reason: '노이즈' }] as any
    const spy = vi.spyOn(store, 'applyRelation').mockResolvedValue()
    const w = mount(RelationSuggestPanel)
    await w.find('.judged-list .approve-btn').trigger('click')
    expect(spy).toHaveBeenCalledWith('e#TB_ORD_HD', 'e#TB_CUST_MST', 'hasCust')
  })

  it('rejecting a suggest candidate calls dismissRelation', async () => {
    const store = useOntologyStore()
    store.relCandidates = [cand] as any
    const spy = vi.spyOn(store, 'dismissRelation')
    const w = mount(RelationSuggestPanel)
    await w.find('.dismiss-btn').trigger('click')
    expect(spy).toHaveBeenCalledWith(0)
  })
})
