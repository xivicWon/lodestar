# Lodestar P6 — 관계 그래프 뷰 설계 문서

> 작성일: 2026-07-01
> 상태: **설계 승인됨 (구현 전)**
> 제품명: **Lodestar** · 리포 코드네임: `onto-studio`
> 선행: P5 (RDB→OWL v1) 완료 — classes/objectProperties가 이미 프론트 스토어에 존재.

## 0. 배경 & 목적

P5 설계에서 "안 B: 노드-엣지 그래프"로 v2에 미뤄둔 관계 시각화를 구현한다.
데이터(classes + objectProperties)는 이미 스토어에 있으므로, **프론트 전용 기능**으로 그래프 뷰만 추가한다.

**한 줄 정의:** "테이블=노드, FK 관계=방향 엣지로 온톨로지를 vis-network 그래프로 조망하고,
노드 클릭으로 기존 선택 상태와 연동한다."

## 1. 핵심 결정 (Q&A로 확정)

| # | 결정 | 근거 |
|---|------|------|
| D1 | 렌더링 = **vis-network** 라이브러리 | 드래그·줌·방향화살표·엣지라벨 기본 제공. "검증된 라이브러리에 위임" 기조 |
| D2 | 기존 목록과 **토글 전환**(목록 ⇄ 그래프) | 목록=정밀 편집, 그래프=조망. 상호보완, 화면 안 좁아짐 |
| D3 | 상호작용 = **노드 클릭 = 클래스 선택 연동**(read-only + 드래그/줌) | 그래프-트리-상세 한 몸. 엣지 편집은 목록이 담당(YAGNI) |
| D4 | **백엔드 변경 없음** | classes/objectProperties API 그대로 사용 |

## 2. 구조 & 컴포넌트

```
App.vue (right section)
  └─ RelationsView.vue      ← 신규 래퍼. "목록 ⇄ 그래프" 토글 상태 보유
       ├─ RelationsPanel.vue   (기존, 그대로)
       └─ RelationsGraph.vue   ← 신규. vis-network 캔버스
```

- **의존성**: `vis-network` (+ `vis-data`) 프론트에 추가.
- **`RelationsView.vue`**: 상단 토글 버튼 2개(목록/그래프), `v-if`로 하위 컴포넌트 하나만 렌더.
  App.vue의 기존 `<RelationsPanel />` 자리를 `<RelationsView />`로 교체.
- **`RelationsGraph.vue`**: `<div>` 컨테이너에 vis-network `Network` 인스턴스 생성.
  `onMounted` 생성, `onBeforeUnmount`에서 `network.destroy()`.
  store의 classes/objectProperties를 `watch`해 DataSet 갱신.

**경계:** 그래프 데이터 매핑(순수 로직)과 vis 렌더(부수효과)를 분리 →
매핑은 라이브러리 없이 테스트, 렌더 컴포넌트는 얇게 유지.

## 3. 데이터 매핑 (순수 함수)

`frontend/src/lib/buildGraphData.ts`:

```
buildGraphData(classes: ClassDto[], objectProperties: ObjectPropertyDto[])
  → { nodes: {id, label}[], edges: {from, to, label, arrows}[] }
```

- **노드**: 각 클래스 → `{ id: iri, label: label ?? short(iri) }`
- **엣지**: 각 ObjectProperty → `{ from: domains[0], to: ranges[0], label: label ?? short(iri), arrows: 'to' }`
  - `domains[0]` 또는 `ranges[0]`가 없으면 그 엣지는 **건너뜀**(방어)
  - 자기참조(from == to)는 그대로 두고 vis-network가 self-loop로 렌더
- `short(iri)`: `#` 뒤 또는 마지막 `/` 뒤 조각 (RelationsPanel과 동일 규칙 → `lib`로 공용화 검토)

## 4. 상호작용 & 반응성

**상호작용 (D3):**
- vis-network 기본: 드래그·줌·팬 활성
- `network.on('click', params)` → `params.nodes[0]` 있으면 `store.select(iri)`
- 선택 동기화: `watch(() => store.selectedIri)` → 해당 노드 하이라이트(`nodes.update({id, color})`)

**반응성:**
- `watch(() => [store.classes, store.objectProperties], rebuild)` — 임포트·rename·삭제 시 갱신.
  rebuild는 `buildGraphData` 결과로 DataSet 갱신.
- 토글로 그래프를 처음 열 때 마운트되도록 `v-if` 기반(마운트 시 생성, 언마운트 시 destroy).

**vis-network 옵션:**
- 노드 shape = box(테이블 느낌), 방향 화살표, 엣지 라벨 표시
- `physics.stabilization: true` 후 정지(위치 흔들림 최소화), `layout.improvedLayout: true`

## 5. 테스트

- **`buildGraphData.test.ts` (순수, 핵심):** 클래스 N개→노드 N개; ObjectProperty→엣지(from/to/arrows='to'/label);
  domain 또는 range 없으면 엣지 제외; 자기참조 from==to 유지. vis 불필요.
- **`RelationsView.test.ts`:** 토글 클릭 시 목록↔그래프 전환(그래프 컴포넌트는 stub). DOM만 검증.
- **`RelationsGraph.vue`:** `vis-network`를 `vi.mock`으로 대체 → 마운트 시 `Network` 생성자 호출 + 컨테이너 존재 +
  click 콜백이 `store.select` 호출을 검증. (canvas는 jsdom에서 안 돌아 실제 렌더는 제외)
- **브라우저 E2E(Playwright):** 임포트 → 그래프 토글 → 노드/엣지 표시 → 노드 클릭 시 선택 확인.

## 6. 성공 기준

1. 임포트한 스키마가 그래프로 표시 (테이블=노드, FK=방향 엣지+라벨)
2. 목록 ⇄ 그래프 토글 동작
3. 노드 클릭 → 해당 클래스가 ClassDetail/목록에서 선택됨
4. rename/임포트 후 그래프가 갱신됨
5. 백엔드 변경 없음 (프론트 전용)

## 7. 범위 밖 (추후)

- 그래프에서 관계 이름변경·추가·삭제 (목록이 담당)
- 노드 위치 저장/레이아웃 커스터마이즈
- 대규모 그래프(수백 노드) 성능 튜닝·클러스터링
- DataProperty(속성)까지 그래프에 표시 (현재는 클래스+관계만)
