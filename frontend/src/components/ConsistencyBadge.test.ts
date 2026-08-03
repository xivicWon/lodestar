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
    // 부분 문자열 하나만 배제하면 구분자가 바뀌거나 'PUBLIC' 이 다른 형태로 남아도 통과한다.
    // 표시 텍스트 전체를 고정해 소속 잔존과 접두 문구 회귀를 함께 잡는다(리뷰 LOD-177).
    expect(mount(ConsistencyBadge).text()).toBe('🔴 모순: TB_CUST_MST')
  })
})
