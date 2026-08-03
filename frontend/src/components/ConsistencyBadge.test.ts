import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import ConsistencyBadge from './ConsistencyBadge.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

describe('ConsistencyBadge', () => {
  it('is empty before reasoning', () => {
    useOntologyStore()
    expect(mount(ConsistencyBadge).text()).toBe('')
  })
  it('shows OK when consistent', () => {
    const s = useOntologyStore()
    s.reasonResult = { consistent: true, unsatisfiableClasses: [], inferredSubClassOf: [] }
    expect(mount(ConsistencyBadge).text()).toContain('일관성 OK')
  })
  it('shows contradiction when inconsistent', () => {
    const s = useOntologyStore()
    s.reasonResult = { consistent: false, unsatisfiableClasses: ['http://ex#A'], inferredSubClassOf: [] }
    const t = mount(ConsistencyBadge).text()
    expect(t).toContain('모순')
    expect(t).toContain('A')
  })
  it('소속이 붙은 IRI 도 다른 화면과 같은 이름 규칙으로 보여준다', () => {
    // #126 이후 라이브·번들 임포트의 IRI 조각은 `<스키마>/<테이블>` 이다. 다른 화면은 전부
    // shortName() 으로 원본 테이블명만 보여주므로, 여기만 스키마가 붙으면 같은 클래스가
    // 화면마다 다른 이름으로 읽힌다.
    const s = useOntologyStore()
    s.reasonResult = {
      consistent: false,
      unsatisfiableClasses: ['http://lodestar/rdb/legacy#PUBLIC/TB_CUST_MST'],
      inferredSubClassOf: [],
    }
    const t = mount(ConsistencyBadge).text()
    expect(t).toContain('TB_CUST_MST')
    expect(t).not.toContain('PUBLIC/TB_CUST_MST')
  })
})
