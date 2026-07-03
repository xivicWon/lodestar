# Lodestar E10 — AI 관계 판정 (후보 노이즈 필터) 설계

> 작성일: 2026-07-03
> 상태: **설계 승인됨 (구현 전)**
> 제품명: Lodestar · 리포 코드네임: onto-studio
> 선행: E2(암시적 관계 발굴), E3-1(AiAdvisor). 실 DB(withcollector: 118테이블·FK 0)에서 E2 후보 97개가 저신뢰(0.6)·오탐 다수임을 확인.

## 0. 배경 & 목적

FK 없는 레거시(예: 사내 `withcollector`)는 E2 이름-휴리스틱이 관계 후보를 많이 뽑지만 노이즈가 섞인다(예: `GROUP_CD` 하나가 6개 그룹 테이블에 매칭). 사람이 일일이 골라내기 벅차다. **`claude -p`가 후보를 배치로 판정해 말이 되는 관계만 남기면** 승인 부담이 크게 준다. 대상은 **현재 로드된 온톨로지**(샘플뿐 아니라 실 DB 임포트 결과 포함).

## 1. 핵심 결정

| # | 결정 | 근거 |
|---|------|------|
| D1 | 판정 = **배치 1회 호출** (후보 전체 → claude 1콜) | 점진적 시작. 콜 수가 후보 수와 무관해 저렴·빠름 |
| D2 | 입력 = **이름 + 양쪽 컬럼 목록** (데이터 행 미열람) | 메타데이터만 → 안전. 판정엔 충분한 맥락 |
| D3 | 대상 = **현재 온톨로지** (RelationService.suggest 결과) | 실 DB 임포트 결과에도 적용 |
| D4 | 승인은 **항상 사람** (AI는 필터/랭킹만) | 기조: 추론은 제안, 확정은 사람 |

## 2. 구조 & 흐름

```
POST /api/rel/suggest/judged
   ① candidates = RelationService.suggest()          ← 기존 E2 (현재 온톨로지)
   ② JudgedRelations = RelationJudge.judge(candidates):   ← 신규
        각 후보에 인덱스 부여, from/to 테이블 + 각 컬럼목록 + viaColumn 으로 배치 프롬프트 1개
        → AiAdvisor.ask (claude -p 1회)
        → 응답 JSON [{i, keep, reason}] 을 인덱스로 후보에 매핑 (누락 인덱스는 keep=false 취급)
   ③ 반환 List<JudgedCandidate> — keep=true 우선 정렬, aiReason 포함
프론트: RelationSuggestPanel "AI 판정" 버튼 → keep/drop 배지 + 이유 → keep 만 노출/우선 → 승인(기존 applyRelation → ObjectProperty)
```

## 3. 컴포넌트 (경계 명확)

- **`JudgedCandidate`** (신규 DTO) — `fromIri, toIri, viaColumn, confidence, suggestedName`(E2 RelationCandidate 필드) + `keep: Boolean, reason: String`.
- **`RelationJudge`** (신규, `com.ontostudio.rel`, @Service) — `judge(candidates: List<RelationCandidate>): List<JudgedCandidate>`.
  - 후보 없으면 빈 리스트(AI 미호출).
  - 각 후보에 0-based 인덱스. from/to 클래스의 컬럼 목록은 `OntologyMapper.dataPropertyDto`/holder로 조회(짧은 이름).
  - 배치 프롬프트: "각 후보 관계가 말이 되는지 keep(true/false)와 한 줄 이유. JSON 배열 [{\"i\":n,\"keep\":bool,\"reason\":\"...\"}] 만 출력." + 후보 목록.
  - `AiAdvisor.ask` 1회. 관대 JSON 추출(E3 parse 방식). 인덱스로 매핑, 응답에 없는 인덱스는 `keep=false, reason="판정 없음"`.
  - keep=true 우선(그다음 confidence desc) 정렬.
- **`RelationController` 확장** — `POST /api/rel/suggest/judged` → `judge(service.suggest())`.
- 재사용: `RelationService`(E2), `AiAdvisor`(E3-1), 프론트 `applyRelation`(E2).
- **프론트** — store `judgedRelations` 상태 + `judgeRelations()` → `apiPost('/rel/suggest/judged',{})`; `RelationSuggestPanel`에 "🧠 AI 판정" 버튼, keep 배지(초록)/drop(회색)+이유, keep 우선 표시, 승인은 기존 `applyRelation`.

## 4. 테스트 (결정론적, 실 AI 없이)

- **`RelationJudgeTest`**: 온톨로지를 손으로 구성(SchemaToOwlMapper on SchemaModel: 예 tbl_a(A_ID)·tbl_b) → RelationService로 후보 생성 또는 후보 직접 구성. 페이크 AiAdvisor가 `[{"i":0,"keep":true,...},{"i":1,"keep":false,...}]` 반환 → judge 결과가 인덱스대로 keep 매핑·정렬되는지, 프롬프트에 테이블/컬럼명이 포함되는지(프롬프트 캡처) 검증. 후보 0개면 AI 미호출·빈 결과(throwing 페이크로 확인).
- **컨트롤러**(@SpringBootTest @AutoConfigureMockMvc, @MockitoBean AiAdvisor): 샘플/DDL 임포트로 후보가 생기는 온톨로지 상태에서 `POST /rel/suggest/judged` → 200 + `keep`/`reason` 필드 존재.
- **프론트**: 스토어 `judgeRelations`(mock apiPost) + `RelationSuggestPanel` AI판정 버튼·배지·승인 컴포넌트 테스트.

## 5. 성공 기준

1. FK 없는 온톨로지에서 E2 후보를 AI가 배치 판정해 keep/drop + 이유를 붙인다.
2. keep 후보가 우선 표시되고, 승인 시 기존 경로로 실제 관계가 생성된다.
3. 판정/매핑/정렬 로직은 결정론적 테스트로 검증(실 AI 불필요).

## 6. 범위 밖 (다음 슬라이스)

- N회 합의 신뢰도(E7 기조를 관계 판정에 적용).
- 샘플 행 기반 판정(값 매칭 확인) — 실 DB 데이터 열람 필요.
- 관계 자동 승인(항상 사람 승인 유지).
- 판정 결과의 세이브포인트(확정) 확장.
