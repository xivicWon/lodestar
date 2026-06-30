# P2 — 클래스 편집기 프론트엔드 설계 문서

> 작성일: 2026-07-01
> 상태: **설계 완료 (구현 전)**
> 상위 문서: [2026-07-01-onto-studio-design.md](./2026-07-01-onto-studio-design.md)
> 선행: P1 백엔드 코어 (완료, `backend/`)

## 0. 목표

상위 설계의 **Phase 2**. P1 백엔드 REST API 위에 얹는 **웹 UI**. 점진적 구현 원칙에 따라
**초안은 "클래스 편집기" 한 화면**으로 한정한다. 속성·개체 화면은 그 다음.

**P2 초안 완료 정의(DoD):**
- 브라우저에서 OWL 파일을 불러오면 클래스 계층이 **트리로** 보인다.
- 트리에서 클래스를 고르면 우측에 상세(label/상위/설명)가 뜨고 **편집·저장**된다.
- 클래스 **추가·삭제**가 되고, **Turtle로 내보내기(다운로드)** 된다.
- (속성·개체 편집, 추론, AI는 P2 범위 밖.)

## 1. 범위 (Scope)

### 포함
- 2패인 레이아웃: 좌측 **클래스 트리**, 우측 **상세/편집 폼**, 상단 **툴바**.
- 클래스: 목록 조회, 트리 구성, 생성, label·상위클래스·설명(rdfs:comment) 편집, 삭제.
- 온톨로지: 파일 업로드 로드, Turtle 내보내기, 새 온톨로지.

### 제외 (다음 단계)
- 속성(Object/Data) 편집 화면, 개체(Individual) 편집 화면.
- 추론 결과 표시(P3), AI 린트(P4).
- 그래프 시각화, 검색 UI(백엔드엔 있으나 화면은 후순위), 다중 온톨로지 탭.

## 2. 기술 스택 & 구조

- **Vite + Vue 3 + TypeScript**
- **Pinia** — 상태 관리
- 경량 **fetch 기반 API 클라이언트** (별도 HTTP 라이브러리 없음)
- **Vitest + @vue/test-utils** — 단위 테스트

```
frontend/
├─ package.json
├─ vite.config.ts            # /api 프록시 → http://localhost:8090
├─ tsconfig.json
├─ index.html
└─ src/
   ├─ main.ts
   ├─ App.vue                # 레이아웃: Toolbar + 2패인
   ├─ api/
   │  ├─ client.ts           # fetch 래퍼 (baseUrl=/api, 에러→ApiError 파싱)
   │  └─ types.ts            # ClassDto, OntologyMetaDto 등 (백엔드 DTO 미러)
   ├─ stores/
   │  └─ ontologyStore.ts    # classes[], selectedIri, meta, 액션
   ├─ lib/
   │  └─ buildTree.ts        # 평면 ClassDto[] → 중첩 트리 (순수 함수, 테스트 대상)
   └─ components/
      ├─ Toolbar.vue         # 불러오기/저장(export)/새로/+클래스
      ├─ ClassTree.vue       # 좌측 트리 (선택 이벤트)
      ├─ ClassTreeNode.vue   # 재귀 노드
      └─ ClassDetail.vue     # 우측 편집 폼
```

설계 원칙: 각 단위 단일 책임. **트리 구성 로직은 컴포넌트에서 분리한 순수 함수**(`buildTree.ts`)로
두어 독립 테스트 가능하게 한다.

## 3. 백엔드 연결 (CORS 회피)

- **Vite 개발 프록시**: `vite.config.ts`의 `server.proxy`로 `/api` → `http://localhost:8090`.
- 브라우저는 프론트와 동일 출처(`localhost:5173`)로 `/api`를 호출 → **CORS 설정 불필요**, 백엔드 무수정.
- 백엔드 포트는 8090 가정(8080·8081 타 서비스 점유). 프록시 타깃만 바꾸면 됨.

## 4. 트리 구성 — 핵심 설계 결정

> 백엔드 `GET /api/classes/tree`는 **명시적 상위가 없는 최상위 클래스를 누락**하는 알려진 버그가 있다
> (런타임 확인됨: 클래스 2개인데 `[]` 반환). 원인은 owl:Thing의 자식을 "`subClassOf owl:Thing`
> 공리를 가진 클래스"로만 찾기 때문.

**결정:** 프론트는 `/api/classes/tree`를 쓰지 않고, **평면 목록 `GET /api/classes`를 받아
`superClasses`로 클라이언트에서 트리를 구성**한다(`lib/buildTree.ts`).
- 장점: 백엔드 버그 우회, orphan(상위 없음)·다중부모 모두 정확히 표현, 프론트가 표시 로직을 제어.
- 규칙: superClasses가 비었거나 owl:Thing뿐인 클래스는 **루트**. 나머지는 각 상위 아래에 배치
  (다중부모는 각 부모 아래 중복 노드). 사이클은 방문 경로(ancestors) 셋으로 가드.
- (백엔드 tree 버그 자체는 P3 진입 전 별도 수정 권장 — 본 문서 범위 밖.)

## 5. 데이터 흐름

| 동작 | 흐름 |
|------|------|
| 로드 | 파일 선택 → `POST /api/ontology/load`(multipart) → store가 `GET /api/classes`+`meta` 재조회 → 트리 갱신 |
| 선택 | 트리 노드 클릭 → `selectedIri` 설정 → `ClassDetail`이 해당 ClassDto 표시 |
| 편집·저장 | 폼 수정 → `PATCH /api/classes/{iri}`(label/superClasses) → store 목록 갱신 |
| 추가 | 툴바 `+클래스` → 이름 입력 → `POST /api/classes` → 갱신 후 새 노드 선택 |
| 삭제 | `DELETE /api/classes/{iri}` → 409(사용 중)면 안내 후 `?cascade=true` 재시도 확인 |
| 내보내기 | `GET /api/ontology/export?format=turtle` → Blob 다운로드 |

- IRI는 경로 변수로 보낼 때 `encodeURIComponent` 적용.
- **설명(rdfs:comment) 편집은 백엔드 PATCH가 아직 미지원**(현재 `PatchClassRequest`는 label/superClasses만). P2 초안에서 설명은 **읽기 전용 표시**로 두고, 편집 지원이 필요하면 별도의 작은 백엔드 태스크(PATCH에 annotations/comment 추가)로 분리한다. (F3 참고)

## 6. 에러 처리
- API 클라이언트가 비2xx 응답의 `{error,message,targetIri}`를 파싱해 throw → store가 잡아
  사용자 알림(토스트/인라인 메시지)으로 표시.
- 로드 실패(422 load_failed), 삭제 충돌(409 in_use), 없음(404)을 사람이 읽는 메시지로.

## 7. 점진적 구현 순서 (P2 내부 단계)

| 단계 | 내용 | 검증 |
|------|------|------|
| **F1 셋업** | Vite/Vue/TS 스캐폴드 + 프록시 + `api/client` + `ontologyStore`(classes 로드/표시) | 앱이 뜨고 `/api/classes` 결과를 화면에 나열 |
| **F2 트리** | `lib/buildTree`(순수 함수) + `ClassTree`/`ClassTreeNode`, 선택 | buildTree 단위 테스트; 트리 렌더·선택 동작 |
| **F3 상세/편집** | `ClassDetail` 폼(label/상위 편집 + 설명 읽기전용) + 저장(PATCH label/superClasses) | 편집→저장→트리/상세 갱신 |
| **F4 툴바** | +클래스/삭제 + 파일 로드 + Turtle 내보내기 | 추가·삭제·로드·다운로드 end-to-end |
| *— 초안 완료 —* | (클래스 편집기 동작) | |

## 8. 테스트 전략
- **순수 로직**: `buildTree`(평면→중첩, orphan/다중부모/사이클) 단위 테스트 — 가장 중요.
- **store**: 액션(load/refresh/select/save) 모킹된 client로 테스트.
- **컴포넌트**: ClassTree 렌더·선택 이벤트, ClassDetail 폼 바인딩 — @vue/test-utils.
- E2E(브라우저 자동화)는 P2 범위 밖(수동 확인 + 단위/컴포넌트로 충분).

## 9. 미해결 질문 (P2)
- 디자인 톤(색/타이포)은 구현 시 frontend-design 가이드로 — MVP는 깔끔한 라이트 테마.
- 설명(rdfs:comment) **편집** 지원 시점: 초안은 읽기전용. 편집이 필요하면 백엔드 PATCH에
  annotations/comment 수용을 추가하는 별도 백엔드 태스크를 먼저 처리.
- 빌드/배포(정적 호스팅 vs 백엔드가 정적 파일 서빙)는 초안 이후 결정.
