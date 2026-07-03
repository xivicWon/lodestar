# Lodestar E12 — 실 DB 대상 AI 의미추정 (현재 온톨로지 일반화) 설계

> 작성일: 2026-07-03
> 상태: **설계 승인됨 (구현 전)**
> 제품명: Lodestar · 리포 코드네임: onto-studio
> 선행: E3(AI 의미추정, 샘플 전용), E7(신뢰도), E8(그라운딩), E10(이름+컬럼 판정 품질 실증)

## 0. 배경 & 목적

E3의 AI 의미추정은 번들 **샘플 DB에만** 붙어 있어(`SemanticEnricher`가 `SampleLegacyDb` 하드 결합), 실제 임포트한 DB(예: withcollector 118테이블)엔 간판 기능을 못 돌린다. 이를 **현재 로드된 온톨로지**(라이브 JDBC·DDL·샘플 무엇으로 임포트했든) 대상으로 일반화한다.

## 1. 핵심 결정

| # | 결정 | 근거 |
|---|------|------|
| D1 | 근거 입력 = **온톨로지의 테이블명 + 컬럼명만** (샘플 행 없음) | DB 재접속 불필요 → read-only 원칙 가장 보수적 준수, 자격증명 보관 안 함. E10이 이름+컬럼만으로 정밀 판정 실증 |
| D2 | 대상 = **현재 `OntologyHolder`의 온톨로지** | 실 DB·DDL·샘플 임포트 결과 모두 지원 |
| D3 | 대규모(수백 클래스)는 **청크 분할**(기본 40개/콜) | 타임아웃·출력 잘림 방지 |
| D4 | **E8 그라운딩 유지** — 확정 클래스 제외 + 확정 앵커 주입 | 기조 일관 |
| D5 | targetIri = **온톨로지의 실제 클래스 IRI** (slug 재구성 없음) | 정확·깔끔 |

## 2. 구조 & 흐름

```
POST /api/ai/enrich            (현재 온톨로지 대상)
   collectContext(): 온톨로지에서 클래스별 {classIri, shortName, columns[]} 수집
        columns = 해당 클래스가 domain 인 DataProperty 의 짧은 이름
   confirmed 제외 + 확정 앵커 준비 (E8)
   미확정 대상 없으면 → 빈 결과(AI 미호출)
   대상 클래스를 40개씩 청크 → 청크별 프롬프트(앵커 + 그 청크 대상) → advisor.ask 1콜 → 파싱
   병합 → EnrichmentCandidate[] (targetIri = 실제 클래스 IRI)

POST /api/ai/enrich/scored?runs=N   (현재 온톨로지, E7 신뢰도)
   enrichCurrent() 를 N회 → ConsensusScorer 집계 (기존 ScoredEnricher 로직 재사용)
```

## 3. 컴포넌트 (경계 명확)

- **`SemanticEnricher` 리팩터** (`com.ontostudio.ai`):
  - 신규 `enrichCurrent(): List<EnrichmentCandidate>` — `OntologyHolder`+`OntologyMapper`로 컨텍스트 수집, 청크 분할, 청크별 `advisor.ask`, 파싱·병합.
  - 신규 internal `collectContext(): List<ClassCtx>` where `ClassCtx(iri, name, columns: List<String>)`.
    - 클래스 = `holder.ontology.classesInSignature()` 중 `!isOWLThing`.
    - name = `OntologyMapper.labelOf(iri)` 있으면 그것, 없으면 IRI fragment(`#` 뒤).
    - columns = `dataPropertiesInSignature` 중 domain 에 이 클래스가 있는 것들의 short name(라벨 또는 fragment의 `.` 뒤).
  - 신규 internal `buildPromptFor(targets: List<ClassCtx>, anchors: List<Pair<name,label>>): String` — E3 프롬프트 구조 재사용(확정 사실 섹션 + 추정 대상 섹션, 샘플 행 라인 없음).
  - 신규 internal `parseCandidates(response, nameToIri: Map<String,String>): List<EnrichmentCandidate>` — 응답 table 명을 nameToIri 로 실제 IRI 매핑(모르는 table 은 무시).
  - 청크 크기 `@Value("\${lodestar.enrich.chunk-size:40}")`.
  - **기존 `enrichSample()`·`buildPrompt(conn)`·`parse()` 는 그대로 유지**(샘플 경로 회귀 보호). 공통 프롬프트 문구는 헬퍼로 뽑아 재사용해도 되나 기존 시그니처 불변.
- **`ScoredEnricher` 확장** — 신규 `scoredEnrichCurrent(runs): List<ScoredCandidate>` (enrichCurrent 를 N회 반복해 기존 집계 로직 재사용). 기존 `scoredEnrich`(샘플)은 유지.
- **`AiController` 확장** — `POST /api/ai/enrich` → `enricher.enrichCurrent()`; `POST /api/ai/enrich/scored?runs=5` → `scoredEnricher.scoredEnrichCurrent(runs)`. 기존 `/enrich/sample`·`/enrich/sample/scored` 유지.
- **프론트** — EnrichPanel "AI 의미 추정" 버튼을 **현재 온톨로지** 대상으로: store 액션 `enrichCurrent()` → `apiPost('/ai/enrich',{})`, `scoredEnrichCurrent(runs)` → `apiPost('/ai/enrich/scored?runs='+runs,{})`. (샘플 임포트는 ImportPanel 버튼으로 이미 존재하므로, enrich 는 로드된 온톨로지를 대상으로 하는 게 자연스럽다.) 승인은 기존 confirm(E8) 재사용.

## 4. 테스트 (결정론적, 실 AI 없이)

- **`SemanticEnricher` enrichCurrent 단위테스트**: 손으로 온톨로지 구성(SchemaToOwlMapper on SchemaModel: 예 TB_CUST_MST(CUST_NO,CUST_NM)+TB_ORD_HD) → holder.replace. 페이크 AiAdvisor(프롬프트 캡처, 고정 JSON) → 후보의 targetIri 가 실제 클래스 IRI 와 일치, 프롬프트에 클래스·컬럼 포함.
- **청크 분할**: chunk-size=2, 클래스 5개 → advisor 3회 호출(카운트), 결과 병합 개수 검증. 각 호출 프롬프트에 확정 앵커 포함.
- **그라운딩**: 한 클래스 사전 확정 → 추정 대상에서 제외되고 앵커 섹션에 등장. 전부 확정 → AI 미호출·빈 결과.
- **컨트롤러**: `@SpringBootTest @AutoConfigureMockMvc @MockitoBean AiAdvisor` → 샘플/DDL 임포트로 온톨로지 존재 상태에서 `POST /api/ai/enrich` 200 + 후보 필드.
- **회귀**: 기존 `/enrich/sample`·scored·E8·E10 테스트 유지.
- **프론트**: store enrichCurrent/scoredEnrichCurrent(mock) + EnrichPanel 버튼이 새 경로 호출.

## 5. 성공 기준

1. withcollector(118T) 임포트 후 "AI 의미 추정" → **118개 실 테이블에 비즈니스 라벨 후보** 생성(샘플 아님).
2. 대규모도 청크 분할로 타임아웃 없이 완료.
3. 확정 클래스는 제외·앵커로 반영(E8), 승인 시 확정까지.
4. DB 재접속·자격증명 보관 없음(온톨로지만 근거).

## 6. 범위 밖 (다음)

- 샘플 행 기반 보강(명시 동의 + 세션 한정 옵션).
- 관계까지 함께 추정(현재 라벨=클래스만).
- E13 recall 벤치(별도).
