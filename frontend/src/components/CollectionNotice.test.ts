import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import CollectionNotice from './CollectionNotice.vue'
import { useOntologyStore } from '../stores/ontologyStore'
import type { CollectionReport } from '../api/types'

beforeEach(() => setActivePinia(createPinia()))

const base: CollectionReport = {
  sourceKind: 'ddl', locatorScheme: 'line',
  collected: 27, skipped: 0, failed: 0, partial: 0, complete: true,
  issues: [], partials: [],
}

describe('CollectionNotice', () => {
  it('is hidden before any import', () => {
    useOntologyStore()
    expect(mount(CollectionNotice).text()).toBe('')
  })

  it('is hidden when the collector reported nothing missing', () => {
    const s = useOntologyStore()
    s.lastCollection = { ...base }
    expect(mount(CollectionNotice).text()).toBe('')
  })

  it('lists legitimate exclusions with reason, locator and target', () => {
    const s = useOntologyStore()
    s.lastCollection = {
      ...base, skipped: 1,
      issues: [{ kind: 'SKIPPED', reasonCode: 'OUT_OF_SCOPE_BY_DESIGN', reason: '행 데이터는 L0 범위 밖이다', locator: '#L2', target: 'INSERT INTO customers' }],
    }
    const t = mount(CollectionNotice).text()
    expect(t).toContain('제외 1건')
    expect(t).toContain('OUT_OF_SCOPE_BY_DESIGN')
    expect(t).toContain('행 데이터는 L0 범위 밖이다')
    expect(t).toContain('#L2')
    expect(t).toContain('INSERT INTO customers')
  })

  /** 건수만 보이는 화면은 gold R-F-2 기준으로 미보고다 — 사유·좌표가 함께 나와야 한다. */
  it('does not show counts without the per-item reasons', () => {
    const s = useOntologyStore()
    s.lastCollection = {
      ...base, failed: 1,
      issues: [{ kind: 'FAILED', reasonCode: 'PARSE_ERROR', reason: '쉼표 누락으로 컬럼이 흡수됐다', locator: '#L3', target: 'CREATE TABLE broken' }],
    }
    const items = mount(CollectionNotice).findAll('[data-test="issue"]')
    expect(items.length).toBe(1)
    expect(items[0].text()).toContain('PARSE_ERROR')
    expect(items[0].text()).toContain('#L3')
  })

  it('marks a partial collection as partial, not as full success', () => {
    const s = useOntologyStore()
    s.lastCollection = {
      ...base, failed: 1, partial: 1, complete: false,
      issues: [{ kind: 'FAILED', reasonCode: 'PARSE_ERROR', reason: '깨진 문장', locator: '#L3', target: 'CREATE TABLE broken' }],
      partials: [{ kind: 'PARTIAL', reasonCode: 'PARTIAL_COLLECTION', reason: '테이블 27건 산출 · 실패 1건', locator: '#L1', target: '(ddl-text)' }],
    }
    const w = mount(CollectionNotice)
    expect(w.text()).toContain('부분 수집')
    expect(w.text()).not.toContain('완전 수집')
    expect(w.find('[role="alert"]').exists()).toBe(true)
    expect(w.find('[data-test="partial"]').text()).toContain('테이블 27건 산출 · 실패 1건')
  })

  /** 정당한 제외만 있으면 완전 수집이다 — 없는 경고를 만들면 경고가 신호이기를 그친다. */
  it('keeps a skipped-only import labelled complete while still listing it', () => {
    const s = useOntologyStore()
    s.lastCollection = {
      ...base, skipped: 1,
      issues: [{ kind: 'SKIPPED', reasonCode: 'OUT_OF_SCOPE_BY_DESIGN', reason: '행 데이터', locator: '#L2', target: 'INSERT INTO t' }],
    }
    const w = mount(CollectionNotice)
    expect(w.text()).toContain('완전 수집')
    expect(w.find('[role="alert"]').exists()).toBe(false)
    expect(w.findAll('[data-test="issue"]').length).toBe(1)
  })

  /** 어느 임포트의 보고인지 적지 않으면 남아 있는 보고와 방금의 보고가 구별되지 않는다. */
  it('names the input path the report came from', () => {
    const s = useOntologyStore()
    s.lastCollection = {
      ...base, sourceKind: 'sample', locatorScheme: 'jdbc', skipped: 1,
      issues: [{ kind: 'SKIPPED', reasonCode: 'UNSUPPORTED_OBJECT_TYPE', reason: 'VIEW', locator: 'jdbc://L/P/V', target: 'V' }],
    }
    expect(mount(CollectionNotice).find('[data-test="source"]').text()).toBe('샘플 레거시')
  })

  it('shows the jdbc locator scheme untouched for the live path', () => {
    const s = useOntologyStore()
    s.lastCollection = {
      ...base, sourceKind: 'jdbc', locatorScheme: 'jdbc', skipped: 1,
      issues: [{ kind: 'SKIPPED', reasonCode: 'UNSUPPORTED_OBJECT_TYPE', reason: 'VIEW 는 수집 대상이 아니다', locator: 'jdbc://LEGACY/PUBLIC/VW_ORD_SUMMARY', target: 'VW_ORD_SUMMARY' }],
    }
    expect(mount(CollectionNotice).text()).toContain('jdbc://LEGACY/PUBLIC/VW_ORD_SUMMARY')
  })
})
