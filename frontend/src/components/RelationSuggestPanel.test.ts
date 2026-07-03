import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import RelationSuggestPanel from './RelationSuggestPanel.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

const evidence = {
  matchType: 'token', matchStem: 'GROUP', matchedOn: 'group',
  viaType: 'string', viaFunctional: false,
  targetHasSameColumn: false, targetSimilarKeys: ['GROUP_SEQ'],
  cardinality: 'N:1 추정', cardinalityReason: '대상이 코드/마스터 성격',
  alternatives: [{ toIri: 'e#TB_GROUP', toLabel: '그룹', confidence: 0.9, matchType: 'exact' }],
  fromLabel: '주문', toLabel: '고객',
  fromColumns: ['ORD_NO', 'CUST_NO', 'GROUP_CD'], toColumns: ['GROUP_SEQ', 'GROUP_NM'],
}

const cand = {
  fromIri: 'e#TB_ORD_HD', toIri: 'e#TB_CUST_MST',
  viaColumn: 'CUST_NO', confidence: 0.6, suggestedName: 'hasCust', evidence,
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

  it('expands evidence detail on 상세 근거 toggle', async () => {
    const store = useOntologyStore()
    store.relCandidates = [cand] as any
    const w = mount(RelationSuggestPanel)
    // 기본 접힘: 상세 근거 텍스트 없음.
    expect(w.text()).not.toContain('토큰 부분일치')
    await w.find('.detail-toggle').trigger('click')
    // 펼치면 매칭 방식·유사키·모호성·컬럼 근거가 보인다.
    expect(w.text()).toContain('토큰 부분일치')
    expect(w.text()).toContain('GROUP_SEQ')
    expect(w.text()).toContain('N:1 추정')
    expect(w.text()).toContain('더 유력')
    expect(w.text()).toContain('GROUP_CD')
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
