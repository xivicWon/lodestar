# Lodestar E8 — 세이브포인트 + 그라운딩 설계

> 작성일: 2026-07-02
> 상태: **설계 승인됨 (구현 전)**
> 제품명: Lodestar · 리포 코드네임: onto-studio
> 선행: E3(AI 의미추정), E7(확률적 신뢰도). 운영 모델 ②③ 구현.

## 0. 배경 & 기조

운영 모델(사용자 정의):
1. **추론은 제안** (E3/E7이 담당 — 신뢰도까지)
2. **운영자가 승인하면 고정된다 (세이브포인트)** ← 이 스펙
3. **다음 추론은 확정된 것을 기조로 확장 (그라운딩)** ← 이 스펙

**슬라이스 범위:** 승인 시 확정 사실을 **온톨로지와 분리된 별도 저장소**에 영속하고(재임포트에도 살아남는 토대), 다음 추정은 확정 항목을 **제외**하고 확정 라벨을 **앵커로 주입**해 그 위에서 추론한다. 재임포트 병합(C)과 관계 확정 그라운딩은 다음 슬라이스.

## 1. 핵심 결정

| # | 결정 | 근거 |
|---|------|------|
| D1 | 확정 상태 = **별도 저장소**(ConfirmationStore, 파일 영속) | 온톨로지와 분리 → 재임포트/재로드에도 확정 유지(다음 슬라이스에서 IRI 매칭 병합에 활용) |
| D2 | 승인 = **라벨 반영 + 확정 기록 원자적** (`POST /api/enrich/confirm`) | 사용자 한 동작에 표시(온톨로지)와 잠금(저장소)이 함께 |
| D3 | 다음 추정 = **확정 제외 + 앵커 주입(그라운딩)** | ③의 정의 "저장된 추론을 기조로 확장"에 정확히 부합 |
| D4 | 그라운딩은 `SemanticEnricher` 한 곳 확장 | ScoredEnricher(E7)가 이를 재사용 → 자동 반영 |

## 2. 구조 & 흐름

```
운영자 승인 ──► POST /api/enrich/confirm {targetIri, label}
   │  ① ClassService.setLabel(targetIri, label)  (기존 재사용, 온톨로지 표시)
   │  ② ConfirmationStore.confirm(iri, label)     (별도 저장소, 파일 영속)
   ▼
[ConfirmationStore]  IRI → ConfirmedFact{iri,label,kind}   ·  data/confirmations.json
   │
   ▼ 다음 추정 (SemanticEnricher.buildPrompt)
   ├─ 확정 테이블은 "추정 대상"에서 제외
   ├─ 확정 라벨을 "이미 확정된 사실(변경 금지)" 앵커 섹션으로 주입
   └─ 미확정 0개면 AI 호출 없이 빈 결과
```

## 3. 컴포넌트 (경계 명확)

- **`ConfirmationStore`** (신규, `com.ontostudio.savepoint`) — `ConfirmedFact(iri, label, kind)` 맵.
  파일 영속(`@Value lodestar.confirmations.file`, 기본 `./data/confirmations.json`, 없으면 생성). 연산: `confirm(fact)`, `all(): List<ConfirmedFact>`, `isConfirmed(iri): Boolean`, `remove(iri)`. JSON 직렬화(Jackson). 스레드 안전(동기화).
- **`ConfirmController`** (신규) — `POST /api/enrich/confirm {targetIri,label}`(라벨 반영+확정), `GET /api/confirmations`, `DELETE /api/confirmations?iri=`.
- **`SemanticEnricher` 확장** — `ConfirmationStore` 주입. `buildPrompt`가 확정 제외 + 앵커 주입. 미확정 0개면 빈 결과. `enrichSample`은 시그니처 유지(내부만 변경) → `ScoredEnricher`/기존 컨트롤러 무변경.
- **프론트** — store `confirmations`, `fetchConfirmations()`, `confirm(targetIri,label)`(→ `/api/enrich/confirm` 후 refresh + 후보에서 제거). `EnrichPanel` 승인 버튼이 `confirm` 호출, "확정 N건" 표시, 확정 항목은 재추정 결과에서 제외됨을 확인.

## 4. 테스트 (결정론적, 실 AI 없이)

- **`ConfirmationStoreTest`**: confirm→isConfirmed true; 파일에 쓴 뒤 **새 인스턴스로 재로드 시 유지**; remove 후 false; 임시 디렉터리(`Files.createTempFile`) 사용.
- **`SemanticEnricher` 그라운딩 테스트**: 페이크 AiAdvisor로 **프롬프트 캡처** → 확정 테이블이 "추정 대상"에 **없고** "확정된 사실"에 **있는지**, 후보에 미확정만 나오는지. 확정 0개면 기존 동작 유지. 미확정 0개면 AI 미호출·빈 결과.
- **`ConfirmController` 통합**(@SpringBootTest): sample 임포트 → `POST /confirm` → `/api/classes` 라벨 반영 확인 + `/api/confirmations` 등장 확인.
- **프론트**: store `confirm`(mock apiPost/apiGet) + `EnrichPanel` 승인→confirm 호출·확정 카운트 컴포넌트 테스트.

## 5. 성공 기준

1. 제안 승인 시 라벨 반영 + 세이브포인트 파일 영속.
2. 재추정 시 확정 테이블 제외 + 확정 라벨 앵커 주입으로 미확정 추론이 확정 맥락에 일관.
3. 확정 목록 조회·삭제 가능.
4. 그라운딩/저장 로직 결정론적 테스트로 검증(실 AI 불필요).

## 6. 범위 밖 (다음 슬라이스)

- 재임포트 시 확정 저장소를 IRI로 매칭해 라벨 자동 복원(병합) — 결정론적 IRI 활용.
- 관계(E2) 확정의 그라운딩 확장(같은 store 재사용).
- 확정 이력/타임스탬프/운영자 정보, 프로젝트별 확정 분리.
