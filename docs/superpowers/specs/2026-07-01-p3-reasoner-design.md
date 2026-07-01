# P3 — 추론기(Reasoner) 설계 문서

> 작성일: 2026-07-01
> 상태: **설계 완료 (구현 전)**
> 상위 문서: [2026-07-01-onto-studio-design.md](./2026-07-01-onto-studio-design.md)
> 선행: P1 백엔드(완료), P2 클래스 편집기(완료)

## 0. 목표

상위 설계의 **Phase 3**. 온톨로지에 **HermiT 추론기**를 붙여 논리 공리로부터 **새 지식을 계산**하고,
프론트에서 **눈으로** 확인한다. 점진 원칙에 따라 초안은 **일관성 검사 + 추론된 계층** 두 가지.

**핵심 동기:** 지금까지는 "명시된(asserted) 분류 트리"만 보였다. 추론기는 명시하지 않은 사실을
공리로부터 도출한다 — 예: `개 ⊑ (먹는다 some 동물)` + `육식동물 ≡ 동물 ⊓ (먹는다 some 동물)` →
추론기가 **`개 ⊑ 육식동물`을 자동 발견**.

**P3 초안 완료 정의(DoD):**
- `POST /api/reason` → 일관성 여부 + 추론된 subclass 엣지(명시 안 된 것)를 반환.
- 프론트 "추론 실행" 버튼 → 🟢/🔴 일관성 배지 + 트리에 추론된 엣지를 **"(추론됨)"** 로 구분 표시.
- 데모 공리로 `개 → 육식동물` 자동 분류가 화면에 나타난다.
- (설명/Explanation, 개체 실체화 추론 표시는 P3 범위 밖 — 추후.)

## 1. 범위 (Scope)

### 포함
- HermiT 추론기 연동(백엔드).
- **일관성 검사**: `isConsistent()`; 모순 시 unsatisfiable 클래스 목록.
- **추론된 계층**: 각 클래스의 추론된 직접 상위 중 **명시되지 않은** 엣지만 추출.
- 프론트: 추론 실행 버튼 + 일관성 배지 + 트리 inferred 엣지 오버레이.
- 데모용 공리가 포함된 샘플(개→육식동물).

### 제외 (다음 단계)
- Explanation("왜 모순인지/왜 추론됐는지" 근거).
- 개체(Individual) 실체화 추론 표시(휘스커스→육식동물)는 백엔드가 계산은 하되 P3 UI엔 미표시.
- 추론기 선택 UI, 증분 추론, 성능 튜닝.

## 2. 아키텍처

```
Frontend (Vue)                         Backend (Kotlin/Spring)
 Toolbar "추론 실행" ──POST /api/reason──▶ ReasonerService
 일관성 배지 🟢/🔴  ◀───ReasonResultDto──   ├─ HermiT OWLReasoner(holder.ontology)
 트리 inferred 엣지                        ├─ checkConsistency()
                                          └─ inferredSubClassOf()  (asserted 제외)
```

- **의존성**: HermiT (`net.sourceforge.owlapi:org.semanticweb.hermit`, OWL API 5.x 호환).
- 추론기는 `holder.ontology`에 대해 **요청 시 생성·실행**(인메모리 단일 온톨로지, MVP는 매 요청 새 reasoner). `synchronized(holder.lock)`로 보호.
- 추론 결과는 백엔드가 **계산만** 하고 온톨로지에 쓰지 않음(비침습적).

## 3. 데이터 모델 (DTO)

```kotlin
data class InferredEdgeDto(val sub: String, val sup: String)   // IRI 쌍 (inferred subclass)
data class ReasonResultDto(
    val consistent: Boolean,
    val unsatisfiableClasses: List<String>,   // 모순 시 nothing-equivalent 클래스 IRI
    val inferredSubClassOf: List<InferredEdgeDto>  // asserted 아닌, 추론된 직접 상위 엣지
)
```

프론트 store는 이 결과를 보관하고, 트리 렌더 시 `inferredSubClassOf`를 오버레이한다.

## 4. 추론 로직 (백엔드)

- **일관성**: `reasoner.isConsistent()`. false면 `unsatisfiableClasses` = `reasoner.getUnsatisfiableClasses()`
  (owl:Nothing 등가류) 중 owl:Nothing 제외한 IRI 목록.
- **추론된 계층**: 각 명명 클래스 `c`에 대해 `reasoner.getSuperClasses(c, true)`(직접 상위)를 구하고,
  그중 **명시된 SubClassOf 공리에 없는** (sub=c, sup=s) 쌍만 `inferredSubClassOf`에 담는다.
  owl:Thing 대상 엣지는 제외.
  - 온톨로지가 비일관이면 계층 계산은 생략하고 `inferredSubClassOf=[]`.

## 5. 프론트 표시

- 툴바 **"추론 실행"** 버튼 → `ontologyStore.runReasoner()` → `POST /api/reason` → 결과 저장.
- **일관성 배지**: 결과 있으면 🟢 "일관성 OK" / 🔴 "모순: <클래스 목록>". 결과 없으면 미표시.
- **트리 오버레이**: `ClassTree`가 store의 inferred 엣지를 참조해, 각 부모 노드 아래에
  **추론된 자식**을 "(추론됨)" 배지와 함께 별도 표기(명시 자식과 시각 구분). buildTree는 그대로 두고,
  inferred 엣지는 **별도 계산(`mergeInferred`)** 으로 오버레이 — asserted 트리를 훼손하지 않음.

## 6. 점진적 구현 순서

| 단계 | 내용 | 검증 |
|------|------|------|
| **P3.1** | 백엔드: HermiT 의존성 + `ReasonerService.checkConsistency()` + `POST /api/reason`(일관성만) | 일관 온톨로지→consistent=true; 서로소+양쪽소속 개체→false |
| **P3.2** | 백엔드: `inferredSubClassOf()` 추가 (asserted 제외) | 데모 공리 → `개 ⊑ 육식동물` 엣지 검출 |
| **P3.3** | 프론트: store `runReasoner` + 툴바 버튼 + 일관성 배지 | 버튼→배지 표시 |
| **P3.4** | 프론트: 트리 inferred 엣지 오버레이("(추론됨)") + 데모 검증 | `개` 아래 육식동물 "(추론됨)" 표시 |

## 7. 테스트 전략
- **ReasonerService 단위**: 일관 온톨로지 true; 일부러 만든 모순(disjoint + 양쪽 개체) false;
  데모 공리에서 `개 ⊑ 육식동물` inferred 엣지 검출(asserted 아님 확인).
- **프론트**: store `runReasoner`(모킹된 client), 배지 렌더, 트리 inferred 오버레이 단위.
- **브라우저 검증**: 데모 샘플 로드 → 추론 실행 → 배지 + `개→육식동물(추론됨)` 확인.

## 8. 미해결 질문 (P3)
- HermiT 정확 버전/좌표는 구현 시 Maven Central 최신 호환으로 확정(OWL API 5.5.0 호환 필수).
- 대형 온톨로지 추론 시간(동기 요청)의 타임아웃 정책 — MVP는 소형 가정, 추후 비동기화.
- 개체 실체화 추론(individual→클래스) 표시 여부 — 초안은 계층만, 추후 확장.
