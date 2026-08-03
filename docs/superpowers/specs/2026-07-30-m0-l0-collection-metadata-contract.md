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
| `projectId` | 수집 대상 프로젝트의 안정 식별자 | 비어있지 않은 문자열. **기본값 `lodestar` 는 이 저장소 전용**이다 — 다른 프로젝트를 수집할 때는 반드시 주입한다(CODE 는 `--project-id`, DB 는 수집 호출의 `projectId`). 여러 프로젝트가 기본값을 공유하면 "프로젝트를 지목한다" 는 뜻이 사라진다 |
| `sourceId` | **소스 하나**를 지목하는 식별자 | 실행 단위는 `<스킴>:<경로 또는 이름>`. **한 실행이 여러 소스를 읽는 트랙의 소스 단위 값은 그 실행의 범위 기준 상대경로**이며 스킴을 붙이지 않는다 — 스킴은 실행 단위(`meta.source_id`)가 이미 정한다(§3) |
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
| DB | 라이브 JDBC | `db:jdbc:<vendor>://<host>:<port>/<database>` — host·port 를 빼면 서로 다른 서버의 같은 이름 DB(운영/스테이징)가 같은 소스가 된다. **자격증명은 넣지 않는다** |
| CODE | 소스 파일 | 수집 범위 루트 기준 **상대경로** (`nodes[].source_id`) |
| CODE | 실행 전체(범위) | `code:<범위 이름>` (`meta.source_id` — 절대경로가 아니다, §5.2) |

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

- **테이블의 소속(schema)이 스냅샷 신원에 들어간다(#126).** `TableInfo.schema` ·
  `ForeignKeyInfo.refSchema` 가 소속을 담고, `SchemaCanonical.bytes` 가 그것을 직렬화한다.
  그래서 `sales.orders` 와 `archive.orders` 는 다른 신원이고, 테이블이 스키마 사이를 옮기면
  `contentHash` 가 바뀐다 — "수집기가 실제로 본 것을 가리킨다" 가 이 축에서도 성립한다.
  (#113 시점에는 `TableInfo` 가 이름만 담아 둘이 한 신원으로 접혔고, 이 문단은 그 **알려진 한계**를
  적던 자리였다.)
  - **catalog 는 모델에 담지 않는다.** `MetadataService` 의 수집은 `conn.catalog` 하나로 한정되므로
    카탈로그는 한 스냅샷 안에서 상수이고, 그 신원은 이미 `sourceId`(vendor·host·port·database)가
    담는다. 담으면 번들 샘플의 H2 카탈로그(`LEGACY_<nanoTime>`)가 해시에 섞여 같은 스냅샷이 매 실행
    다른 신원을 갖는다 — 소속을 담으려다 결정성을 잃는 교환이다. 수집 범위가 여러 카탈로그로
    넓어지면 이 전제가 깨지므로, 그때 이 항을 다시 연다.
  - `schema = null` 은 **소속을 모른다**는 뜻이다(비한정 DDL). 그 경우 정규화 바이트는 이 변경 전과
    같아 기존 DDL 입력의 `revision` 은 흔들리지 않는다. 반면 **소속을 보고하는 벤더**(PostgreSQL ·
    H2 등, `TABLE_SCHEM` 이 채워지는 드라이버)의 라이브·번들 경로는 `contentHash`·`revision` 이
    #126 에서 한 번 바뀌었다(`bench/l0/metadata/completeness-db.json` 의 `volatile` 블록이 그 값을
    싣는다). MySQL 처럼 `TABLE_SCHEM` 이 비고 DB 가 `TABLE_CAT` 으로 오는 드라이버에서는 소속이
    `null` 로 남아 신원이 그대로다 — 그쪽은 한 스냅샷이 카탈로그 하나로 닫히므로 애초에 소속이
    다른 동명 테이블이 생기지 않는다(위의 catalog 항과 같은 이유).
  - **하류 파급 — 클래스 IRI 에 소속이 붙는다.** `SchemaToOwlMapper` 는 소속이 있으면
    `<base><schema>/<table>` 로 IRI 를 만든다(없으면 예전 그대로). 동명 테이블의 IRI 충돌을 없애기
    위한 것이며, 그 대가로 **#126 이전에 저장된 확정(세이브포인트)의 IRI 는 라이브·번들 경로에서
    더 이상 매칭되지 않는다**. E9 `ConfirmationMerger` 는 그것을 자동 삭제하지 않고 `stale` 로
    보고하며 저장소에 그대로 둔다(D2) — 사용자는 목록에서 보고 다시 확정한다.
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
  바이트의 sha256. 내용만 잇지 않고 경로를 함께 잇는다 — 내용만 이으면 파일 추가·이동이 묻힌다.
  분모는 **수집기가 실제로 읽은 파일**(확장자 필터를 통과한 것)이다. 범위 안에 있으나 필터로
  제외된 파일은 이 해시에 들어가지 않는다 — 그 제외를 사유와 함께 드러내는 것은 이 계약이 아니라
  L0-fix-3(오류·제외 채널)의 몫이다.
- `meta.source_id` — **실행 위치가 아니라 범위 이름**이다. 절대경로를 그대로 실으면 같은 스냅샷을
  다른 기계에서 수집했을 때 산출물이 달라진다(`meta.source_root` 를 정규화에서 빼는 것과 같은 이유).
  git 저장소 안이면 저장소 루트 기준 상대경로, 아니면 범위 디렉토리 이름을 쓴다.
- `nodes[].content_hash` — 그 노드가 나온 **파일**의 해시. 노드 단위로 5필드가 닫힌다
  (`project_id`·`revision`·`collector_version` 은 실행 단위로 하나다 — 한 실행은 한 스냅샷이다).
- `meta.revision` — 수집 범위 루트에서 `git rev-parse HEAD`. 커밋 sha 를 쓰려면 **수집한 것이 그
  커밋에서 그대로 나와야** 하므로 두 가지를 본다: 범위 안에 수정된 파일이 없는가, 그리고 수집한
  파일이 전부 HEAD 에 추적되는가. 후자를 빼면 gitignore 된 소스를 수집해도 워킹트리는 clean 이라
  "HEAD 로 재현된다" 는 거짓 주장이 된다. **수집한 파일에 심볼릭 링크가 있으면 무조건 `dirty:`** 다 —
  수집기는 링크 대상의 바이트를 읽는데 git 은 링크(대상 경로 문자열)만 추적하므로, 대상이 범위 밖에
  있으면 그 내용이 바뀌어도 워킹트리는 clean 이다. 재현되지 않으면 `dirty:`, git 이 아니면 `nogit:` +
  범위 해시 앞 12자. CLI `--revision` 으로 덮어쓸 수 있다(형식에 맞지 않으면 거절한다).
- `collector_version` — `lodestar-codegraph@<pyproject version>[+<sha>]`. 기존
  `meta.generated_by`("lodestar-codegraph v1")는 세대만 있고 커밋·semver 가 없어 #88 에서
  별칭으로만 인정됐다 — 그 자리를 이 필드가 대신한다(`generated_by` 는 하위호환으로 유지).

## 6. 재측정

두 트랙을 **#88 프로브와 같은 방식으로** 다시 잰다 — DB 는 산출물 타입 그래프(중첩 포함)의 멤버
이름과 실제 수집 경로 3종의 값, CODE 는 실제 수집 실행이 낸 `meta`·`nodes` 키와 값. 수집기가
언어별로 나뉘어 있으므로 측정도 나뉜다(#88 이 프로브를 나눈 것과 같은 이유).

| 트랙 | 측정 | 결과 |
|---|---|---|
| DB | `backend/.../rdb/L0DbMetadataCompletenessTest.kt` | `bench/l0/metadata/completeness-db.json` |
| CODE | `bench/l0/metadata_completeness.py` | `bench/l0/metadata/completeness-code.json` |

`metadata_completeness.py` 가 코드 트랙을 재고 **두 트랙의 판정을 함께** 낸다. 각 측정은 자기 결과의
표류 검사를 하며, 입력 내용에 따라 달라지는 `volatile` 블록(revision·contentHash·노드 수)만 검사에서
제외한다. `projectId`·`collectorVersion` 은 입력이 바뀐다고 달라지지 않는 **계약이 고정하는 신원**이므로
`identity` 블록에 두어 표류 검사를 받는다 — 바뀌었다면 의도된 변경이고, 그러면 diff 에 남아야 한다.

DB 측정의 `live-jdbc` 경로는 **운영 진입점(`LiveJdbcSource.extract`)을 그대로 돌린다.** 측정이
`MetadataService` 에 sourceId 를 직접 주입하면, 운영 경로의 신원 생성·전달이 깨져도 게이트가
통과한다 — 재지 않은 경로를 잰 것으로 세게 된다. 커넥션 공급만 갈아끼운다.

검증에 실패한 측정은 `--bootstrap` 으로도 기준이 되지 못한다. 고장난 결과가 baseline 으로 남으면
이후의 정상 실행이 그 기준과 달라 표류로 잡힌다 — 고장난 쪽이 기준이 되는 것이다.

**키의 존재로 세지 않는다.** 자리가 있어도 빈 값이나 플레이스홀더가 담겨 있으면 신원이 아니므로,
두 측정 모두 값의 사용 가능성(§2.1)과 형식(§2)까지 확인한 뒤에만 완전성에 센다. 형식만 보면
형식상 유효한 아무 해시나 실려도 통과하므로, CODE 측정은 노드가 지목한 **파일을 직접 읽어**
그 바이트의 해시와 같은지까지 본다.

**노드 수는 합격 기준이 아니다.** 수집 범위의 내용이 바뀌면 노드 수도 바뀌므로 `nodeCount` 는
`volatile` 블록에 있고 표류 검사 대상이 아니다. 합격 기준은 "**모든** 노드가 자기 소스를 지목하고
그 해시가 실제 파일 바이트와 같은가" 이며, 노드가 0건이면 그 자체로 실패다(빈 순회는 통과가 아니다).

### 6.1 코드 트랙 프로브 표류 — 열린 항목

이 이슈는 `backend/src/main/kotlin` 안의 파일을 고치는데, 그 디렉토리가 **코드 트랙 프로브의 입력
범위 그 자체**다. 그래서 이 브랜치에서 `probe_code.py --check` 는 실패한다(표류 블록:
`input`·`inventory`·`readOnly`·`provenance`·`determinismControl`). 프로브가 입력 신원을 검사하고
있다는 증거이지 고장이 아니다.

새 runId 로 정리하려면 입력 revision 을 다시 고정해야 하는데, gold manifest 는 `3c27259` 를
**`APPROVED`** 로 고정하고 있고 확인기 V3·V4 가 그 값을 강제한다. 따라서 코드 트랙의 새 실측은
**I2 Gold Set 개정(승인 사항, I1 §7)** 이 선행이며 이 이슈 범위 밖이다. 자세한 재현 조건은
[`bench/l0/README.md`](bench/l0/README.md) 에 적었다.

**#88 의 baseline 산출물(`run-l0-*-3c27259-001`)은 손대지 않는다.** 그것은 revision `3c27259`
시점의 증거이고, 고친 코드로 덮어쓰면 그 시점의 사실이 사라진다(I3 §5.5 — 새 실측은 새 runId).
따라서 이 이슈는 `gate-l0-metadata-completeness` 하나만 닫는다. L0 전체 판정을 `BLOCKED` 에서
움직이려면 나머지 게이트(결정성 H1, PII 마스킹 H2, 오류 가시성)까지 고친 뒤 **새 runId 로 전 트랙을
다시 재는** 별도 실행이 필요하다.
