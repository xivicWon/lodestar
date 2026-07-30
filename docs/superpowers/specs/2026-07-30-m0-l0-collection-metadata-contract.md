# M0 · L0-fix — 수집 식별 메타데이터 계약 v0 (DB·CODE 공통)

- 이슈: #113 (선행 #88) · 게이트: `gate-l0-metadata-completeness`
- 상위 계약: [I1 Baseline Contract](2026-07-29-m0-i1-baseline-contract.md) §2.3 (L0 출력 필수값)
- 실측 근거: [L0 Source 검증](2026-07-30-m0-l0-source-validation.md) · `bench/l0/runs/run-l0-{db,code}-3c27259-001`

## 1. 왜

#88 실측에서 DB·CODE 두 트랙 모두 `gate-l0-metadata-completeness` **FAIL(0/5)** 이었다. 산출물에
수집 신원을 담을 **자리 자체가 없어서** 실패한 것이지, 값을 채우지 않아서가 아니다. 자리가 없으면
"이 산출물이 무엇을, 어느 시점의, 어떤 수집기로 만든 것인가" 를 산출물만 보고 답할 수 없고,
L1 이후의 모든 수치가 추적 불가능한 입력 위에 서게 된다(I1 P5).

이 문서는 두 트랙이 **같은 5필드를 같은 의미로** 기록하도록 계약을 고정한다.

## 2. 필수 5필드

| 필드 | 의미 | 형식 |
|---|---|---|
| `projectId` | 수집 대상 프로젝트의 안정 식별자 | 비어있지 않은 문자열. 기본값 `lodestar` |
| `sourceId` | **소스 하나**를 지목하는 식별자 | `<스킴>:<경로 또는 이름>` (§3) |
| `revision` | 그 소스의 **스냅샷 식별자** | git sha(7~40 hex) 또는 `<스킴>:<contentHash 앞 12자>` (§4) |
| `contentHash` | 수집기가 **실제로 읽은 바이트**의 해시 | `sha256:<64 hex>` |
| `collectorVersion` | 산출물을 만든 수집기의 신원 | `<이름>@<semver>[+<commit 7~40 hex>]` |

**완전성(completeness) = 산출물에서 소스 단위로 조회 가능한 필드 수 / 5.** 값이 있으면 되는 게
아니라 **소스를 지목한 채로** 조회돼야 한다 — CODE 트랙처럼 한 실행이 여러 소스를 읽으면
`sourceId`·`contentHash` 는 소스 단위(노드/파일)에 붙어야 한다(#88 측정 규칙 M-CODE-3).

### 2.1 금지

- **빈 값·플레이스홀더 금지.** 다섯 필드 모두 비어있을 수 없다. 모르는 값을 `"unknown"` 으로 채워
  게이트를 통과시키는 것은 은폐다(I1 §4.1 "실패·제외 은폐" 금지).
- **없는 신원을 지어내지 않는다.** VCS 가 정본이 아닌 소스(라이브 DB, 인라인 DDL)는 git sha 를
  꾸며내지 않고 §4 의 **스킴 접두어**로 "이건 커밋이 아니다" 를 드러낸다.

## 3. `sourceId` 스킴

| 트랙 | 소스 | `sourceId` |
|---|---|---|
| DB | 인라인 DDL 텍스트 | `db:ddl:<논리 스키마 이름>` |
| DB | 번들 샘플 레거시 | `db:legacy-sample` (gold 고정 id 와 같다) |
| DB | 라이브 JDBC | `db:jdbc:<vendor>/<database>` |
| CODE | 소스 파일 | 수집 범위 루트 기준 **상대경로** (`nodes[].source_id`) |
| CODE | 실행 전체(범위) | `code:<수집 범위 루트>` (`meta.source_id`) |

## 4. `revision` 스킴

git 커밋이 정본인 소스는 커밋 sha 를 그대로 쓴다. 아니면 접두어를 붙인 **내용 파생 식별자**를 쓴다.
시각(timestamp)은 쓰지 않는다 — 같은 입력의 두 실행이 달라져 결정성 측정(H1)을 오염시킨다.

| 접두어 | 쓰는 곳 | 뜻 |
|---|---|---|
| (없음, hex) | 워킹트리가 git 이고 clean | 그 커밋의 스냅샷 |
| `inline:` | 요청 본문으로 들어온 DDL 텍스트 | 커밋된 적 없는 텍스트. 내용이 곧 신원 |
| `bundle:` | 리포에 번들된 리소스 | 커밋되어 있으나 런타임이 커밋을 모른다 |
| `live:` | 라이브 DB 카탈로그 | VCS 가 없다. 정규화 스냅샷의 내용이 신원 |
| `dirty:` | git 이지만 워킹트리가 clean 이 아님 | HEAD 로 재현되지 않는다 |
| `nogit:` | git 저장소가 아님 | 재현 좌표가 리포 밖에 있다 |

## 5. 트랙별 반영

### 5.1 DB (Kotlin)

`SchemaModel` 이 `metadata: CollectionMetadata` 를 **필수 생성자 인자**로 갖는다. 기본값을 두지
않는 것이 요점이다 — 기본값이 있으면 신원 없는 산출물이 계속 만들어진다.

```
SchemaModel(tables: List<TableInfo>, metadata: CollectionMetadata)
```

- `contentHash` — DDL 경로는 **입력 SQL 바이트**, JDBC 경로는 **정규화 스냅샷 바이트**
  (`SchemaCanonical.bytes`, 테이블/컬럼/키를 결정적으로 직렬화한 것). JDBC 에는 읽은 원본 바이트라는
  것이 없으므로 "수집기가 실제로 본 것" 의 정규화 표현을 해싱하고, `revision` 의 `live:` 접두어가
  그 사실을 드러낸다.
- `collectorVersion` — `lodestar-rdb-collector@<backend version>`. 빌드가 커밋을 알면
  (`-Dlodestar.build.revision=<sha>` 또는 `LODESTAR_BUILD_REVISION`) `+<sha>` 가 붙는다.

### 5.2 CODE (Python)

`codegraph.json` 이 두 층위에 기록한다.

```
meta.project_id · meta.source_id · meta.revision · meta.content_hash · meta.collector_version
nodes[].source_id · nodes[].content_hash
```

- `meta.content_hash` — 수집 범위의 **범위 해시**: `"<상대경로> <파일해시>\n"` 을 경로 정렬해 이은
  바이트의 sha256. 파일 하나가 바뀌면 반드시 바뀐다.
- `nodes[].content_hash` — 그 노드가 나온 **파일**의 해시. 노드 단위로 5필드가 닫힌다
  (`project_id`·`revision`·`collector_version` 은 실행 단위로 하나다 — 한 실행은 한 스냅샷이다).
- `meta.revision` — 수집 범위 루트에서 `git rev-parse HEAD`. 워킹트리가 dirty 면 `dirty:`,
  git 이 아니면 `nogit:` + 범위 해시 앞 12자. CLI `--revision` 으로 덮어쓸 수 있다.
- `collector_version` — `lodestar-codegraph@<pyproject version>[+<sha>]`. 기존
  `meta.generated_by`("lodestar-codegraph v1")는 세대만 있고 커밋·semver 가 없어 #88 에서
  별칭으로만 인정됐다 — 그 자리를 이 필드가 대신한다(`generated_by` 는 하위호환으로 유지).

## 6. 재측정

`bench/l0/metadata_completeness.py` 가 두 트랙을 **#88 프로브와 같은 방식으로** 다시 잰다 —
DB 는 산출물 타입 그래프(중첩 포함)의 멤버 이름, CODE 는 실제 수집 실행이 낸 `meta`·`nodes` 키.
결과는 `bench/l0/metadata/completeness.json` 에 남고, 스크립트가 두 트랙 5/5 를 단언한다.

**#88 의 baseline 산출물(`run-l0-*-3c27259-001`)은 손대지 않는다.** 그것은 revision `3c27259`
시점의 증거이고, 고친 코드로 덮어쓰면 그 시점의 사실이 사라진다(I3 §5.5 — 새 실측은 새 runId).
따라서 이 이슈는 `gate-l0-metadata-completeness` 하나만 닫는다. L0 전체 판정을 `BLOCKED` 에서
움직이려면 나머지 게이트(결정성 H1, PII 마스킹 H2, 오류 가시성)까지 고친 뒤 **새 runId 로 전 트랙을
다시 재는** 별도 실행이 필요하다.
