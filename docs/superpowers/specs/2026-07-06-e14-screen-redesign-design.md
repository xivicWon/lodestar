# Lodestar E14 — 화면 재설계 (그래프 중심 + Floating Side Panel) 설계

> 작성일: 2026-07-06
> 상태: **와이어프레임 승인됨 (그래프 기본화면 + floating side panel)**
> 제품명: Lodestar · 리포 코드네임: onto-studio
> 선행: P2(클래스 에디터), P6(관계 그래프), E12(현재 온톨로지 의미추정), E13(근거 카드)

## 0. 배경 & 문제

현재 작업 화면은 좌(클래스 목록) + 우(상세폼 상단 40% / 관계뷰 하단)로 상하 분할돼
있다. 운영자가 실제로 하는 일 — "이 테이블이 무슨 의미이고 무엇과 연결됐는지 보고,
관계를 이어붙이는 것" — 에 비해 그래프가 좁고, 상세폼이 항상 자리를 차지한다.

또한 의미복원(enrich)으로 라벨이 업무명으로 바뀌면 **원본 테이블명이 화면에서 사라져**
운영자가 "이 '자산 점검 체크리스트'가 원래 어느 테이블이었지?"를 알 수 없다.

## 1. 목표

1. **원본 테이블명 상시 노출** — 목록·그래프·상세 어디서나 복원 라벨과 원본 테이블명을 병기.
2. **그래프를 기본 화면**으로 — 진입 시 그래프가 우측 전체를 채운다.
3. **Floating side panel** — 목록/노드 클릭 시 그래프를 **밀지 않고 그 위에 떠서** 슬라이드 인.
   노드 정보 + 연결된 데이터 맵핑을 보여준다.
4. **관계 연동 = 레이어 팝업(모달)** — 소스/타깃 클래스를 선택해 관계를 만든다.

## 2. 핵심 결정

| # | 결정 | 근거 |
|---|------|------|
| D1 | 원본 테이블명 = `shortName(iri)` (IRI 프래그먼트) | 별도 필드 없음. enrich가 label만 덮고 IRI는 원본 테이블명 보존 |
| D2 | `shortName`을 `lib/shortName.ts` 공용 유틸로 분리 | buildGraphData·ClassTreeNode·SidePanel 공유 |
| D3 | 목록: 원본명이 라벨과 다를 때만 서브라인 노출 | 미복원(label==원본명) 시 중복 방지 |
| D4 | side panel = floating 카드(그래프 위 오버레이, 슬라이드) | 사용자 확정. 그래프를 shrink하지 않음 |
| D5 | side panel 노출 조건 = `selectedIri != null && !dismissed` | 목록/그래프 클릭으로 열고 ×/Esc로 닫되 선택은 유지 |
| D6 | 노드 정보는 **실제 보유 필드만** — 라벨·원본테이블·IRI·상위클래스·설명(comment)·확정상태 | PK/컬럼수는 프론트 데이터 모델에 없음 → 가짜 UI 금지 |
| D7 | 연결 맵핑 = `objectProperties` 중 domain/range가 선택 클래스인 것(나가는/들어오는 구분) | 이미 로드된 데이터 재사용, 추가 호출 없음 |
| D8 | 연동 모달 필드 = 소스 클래스·타깃 클래스·관계 이름 | `POST /properties/object`가 label+domains+ranges만 받음. 컬럼 맵핑은 미저장 → 스코프 밖 |
| D9 | 기존 상세폼(ClassDetail) 편집 기능은 side panel 안으로 흡수 | 라벨/상위클래스 편집 접근성 유지 |

## 3. 컴포넌트 구조

```
App.vue
├─ (상단) 파이프라인 바 / 관리 바  ......... 유지
└─ .panes
   ├─ aside.left → ClassTree → ClassTreeNode  ... [변경] 원본 테이블명 병기
   └─ section.right (그래프 단일 메인)          ... [변경]
      ├─ RelationsGraph (기본, 전체)
      ├─ 그래프 툴바: [관계 연동] 버튼          ... [신규 트리거]
      ├─ NodeSidePanel (floating, 슬라이드)     ... [신규]
      │   ├─ 노드 정보 (라벨·원본테이블·IRI·상위·설명·확정)
      │   ├─ 라벨/상위 편집 (ClassDetail 흡수)
      │   └─ 연결된 데이터 맵핑 (나가는/들어오는 관계)
      └─ RelationLinkModal (레이어 팝업)        ... [신규]
          └─ 소스 클래스·타깃 클래스·관계 이름 → applyRelation
```

기존 `RelationsView`(목록/그래프 탭)·`ClassDetail`·`ImpactPanel`의 배치는
그래프 중심 레이아웃에 맞춰 재배치한다. 목록·표 보기는 side panel 또는 보조 탭으로 유지.

## 4. 데이터 흐름

- **원본 테이블명**: `shortName(class.iri)`. 라벨과 다르면 노출.
- **연결 맵핑**(선택 클래스 iri 기준):
  - 나가는: `objectProperties.filter(p => p.domains[0] === iri)` → `p.label` → range 클래스
  - 들어오는: `objectProperties.filter(p => p.ranges[0] === iri)` → domain 클래스 → `p.label`
  - 대상 클래스 표기: 대상 label + `shortName(대상 iri)`
- **관계 생성**: 모달 → `store.applyRelation(fromIri, toIri, name)` (기존 액션 재사용).

## 5. 이슈 분해 (마일스톤 E14)

- **#A 목록에 원본 테이블명 병기** — `shortName` 유틸 분리 + ClassTreeNode 서브라인 + 테스트.
- **#B 그래프 기본화면 + floating side panel + 연동 모달** — App 재구성 + NodeSidePanel + RelationLinkModal + 테스트.

두 이슈는 App.vue를 공유하므로 하나의 브랜치 `feat/e14-screen-redesign`에서
구현하고 PR로 함께 닫는다.

## 6. 품질 게이트

- 프론트: `cd frontend && npx vitest run && npx vue-tsc -b` 그린.
- TDD: shortName 유틸·ClassTreeNode·NodeSidePanel·RelationLinkModal 각 테스트 선작성.
- read-only 원칙 유지: 실 DB 변경 없음. 모든 변경은 온톨로지/로컬.

## 7. 스코프 밖 (후속)

- 컬럼 수준 맵핑 저장/표시 (ObjectProperty에 via-column 메타 추가 필요).
- 관계 특성(FUNCTIONAL/TRANSITIVE/SYMMETRIC) 선택 UI.
- 목록·표 전용 뷰 고도화.
