# Lodestar P6 — 관계 그래프 뷰 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 온톨로지의 클래스=노드, FK 관계=방향 엣지로 vis-network 그래프를 그리고, 기존 관계 목록과 토글로 전환하며, 노드 클릭으로 클래스 선택을 연동한다.

**Architecture:** 순수 매핑 함수 `buildGraphData`(classes/objectProperties → nodes/edges)와 vis 렌더 컴포넌트 `RelationsGraph.vue`를 분리. `RelationsView.vue`가 목록(`RelationsPanel`)과 그래프(`RelationsGraph`)를 토글. **프론트 전용** — 백엔드 무변경, 데이터는 기존 스토어 재사용.

**Tech Stack:** Vue 3 + TS + Pinia, vis-network(+vis-data), Vitest + @vue/test-utils.

## Global Constraints

- **프론트 전용**: 백엔드 코드/API 변경 없음. 데이터는 기존 `store.classes`, `store.objectProperties` 사용.
- vis 렌더(부수효과)와 데이터 매핑(순수)을 분리 — 매핑은 라이브러리 없이 테스트.
- 상호작용: 노드 클릭 → `store.select(iri)`. 그래프에서 편집(rename/추가/삭제)은 하지 않음(목록 담당).
- 작업 디렉터리 `frontend/`. 테스트: `npx vitest run`, 타입체크: `npx vue-tsc -b`.
- 커밋 말미에 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. 브랜치 `main`.

---

## File Structure

- `frontend/src/lib/buildGraphData.ts` — 순수 매핑 함수 + `shortName` (신규)
- `frontend/src/components/RelationsGraph.vue` — vis-network 캔버스 (신규)
- `frontend/src/components/RelationsView.vue` — 목록/그래프 토글 래퍼 (신규)
- `frontend/src/App.vue` — 우측 영역에서 `RelationsPanel` → `RelationsView`로 교체 (수정)
- `frontend/package.json` — vis-network, vis-data 의존성 (수정)
- 테스트: `buildGraphData.test.ts`, `RelationsGraph.test.ts`, `RelationsView.test.ts`

---

## Task 1: vis 의존성 + buildGraphData 순수 매핑

**Files:**
- Modify: `frontend/package.json` (의존성)
- Create: `frontend/src/lib/buildGraphData.ts`
- Test: `frontend/src/lib/buildGraphData.test.ts`

**Interfaces:**
- Produces:
  - `interface GraphNode { id: string; label: string }`
  - `interface GraphEdge { from: string; to: string; label: string; arrows: string }`
  - `interface GraphData { nodes: GraphNode[]; edges: GraphEdge[] }`
  - `function shortName(iri: string): string`
  - `function buildGraphData(classes: ClassDto[], objectProperties: ObjectPropertyDto[]): GraphData`
- Task 2(RelationsGraph)가 이 함수를 소비.

- [ ] **Step 1: 의존성 설치**

Run: `cd frontend && npm install vis-network@^9.1.9 vis-data@^7.1.9`
Expected: `package.json` dependencies에 `vis-network`, `vis-data` 추가, 설치 성공.

- [ ] **Step 2: 실패 테스트 작성**

Create `frontend/src/lib/buildGraphData.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import { buildGraphData, shortName } from './buildGraphData'
import type { ClassDto, ObjectPropertyDto } from '../api/types'

const classes: ClassDto[] = [
  { iri: 'e#customers', label: 'customers', superClasses: [], annotations: [] },
  { iri: 'e#orders', label: 'orders', superClasses: [], annotations: [] },
]
function op(partial: Partial<ObjectPropertyDto>): ObjectPropertyDto {
  return { iri: 'e#r', label: null, domains: [], ranges: [], characteristics: [], inverseOf: null, annotations: [], ...partial }
}

describe('shortName', () => {
  it('takes fragment after # then last path segment', () => {
    expect(shortName('http://x/rdb/shop#orders')).toBe('orders')
    expect(shortName('http://x/orders')).toBe('orders')
  })
})

describe('buildGraphData', () => {
  it('maps each class to a node', () => {
    const g = buildGraphData(classes, [])
    expect(g.nodes).toEqual([
      { id: 'e#customers', label: 'customers' },
      { id: 'e#orders', label: 'orders' },
    ])
  })

  it('maps object property to a directed edge with label', () => {
    const g = buildGraphData(classes, [op({
      iri: 'e#orders_customer_id_ref', label: 'placedBy',
      domains: ['e#orders'], ranges: ['e#customers'],
    })])
    expect(g.edges).toEqual([
      { from: 'e#orders', to: 'e#customers', label: 'placedBy', arrows: 'to' },
    ])
  })

  it('falls back to short iri when label missing', () => {
    const g = buildGraphData(classes, [op({
      iri: 'e#rel_x', label: null, domains: ['e#orders'], ranges: ['e#customers'],
    })])
    expect(g.edges[0].label).toBe('rel_x')
  })

  it('skips edges without domain or range', () => {
    const g = buildGraphData(classes, [
      op({ domains: [], ranges: ['e#customers'] }),
      op({ domains: ['e#orders'], ranges: [] }),
    ])
    expect(g.edges).toEqual([])
  })

  it('keeps self-referencing edge (from == to)', () => {
    const g = buildGraphData(classes, [op({
      iri: 'e#emp_mgr', label: 'manages', domains: ['e#orders'], ranges: ['e#orders'],
    })])
    expect(g.edges[0].from).toBe(g.edges[0].to)
  })
})
```

- [ ] **Step 3: 테스트 실행 (실패 확인)**

Run: `cd frontend && npx vitest run src/lib/buildGraphData.test.ts`
Expected: FAIL — `buildGraphData`/`shortName` 미정의.

- [ ] **Step 4: 구현 작성**

Create `frontend/src/lib/buildGraphData.ts`:

```typescript
import type { ClassDto, ObjectPropertyDto } from '../api/types'

export interface GraphNode { id: string; label: string }
export interface GraphEdge { from: string; to: string; label: string; arrows: string }
export interface GraphData { nodes: GraphNode[]; edges: GraphEdge[] }

export function shortName(iri: string): string {
  const hash = iri.split('#').pop() ?? iri
  return hash.split('/').pop() ?? hash
}

export function buildGraphData(
  classes: ClassDto[],
  objectProperties: ObjectPropertyDto[],
): GraphData {
  const nodes: GraphNode[] = classes.map(c => ({ id: c.iri, label: c.label ?? shortName(c.iri) }))
  const edges: GraphEdge[] = []
  for (const p of objectProperties) {
    const from = p.domains[0]
    const to = p.ranges[0]
    if (!from || !to) continue
    edges.push({ from, to, label: p.label ?? shortName(p.iri), arrows: 'to' })
  }
  return { nodes, edges }
}
```

- [ ] **Step 5: 테스트 실행 (통과 확인)**

Run: `cd frontend && npx vitest run src/lib/buildGraphData.test.ts`
Expected: PASS — 6 tests.

- [ ] **Step 6: 커밋**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/lib/buildGraphData.ts frontend/src/lib/buildGraphData.test.ts
git commit -m "feat(p6): vis 의존성 + buildGraphData 순수 매핑(클래스→노드, FK→엣지)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: RelationsGraph.vue (vis-network 캔버스)

**Files:**
- Create: `frontend/src/components/RelationsGraph.vue`
- Test: `frontend/src/components/RelationsGraph.test.ts`

**Interfaces:**
- Consumes: `buildGraphData`, `store.classes`, `store.objectProperties`, `store.selectedIri`, `store.select`.
- 라이브러리 import는 반드시 `'vis-network/standalone'`에서 `Network`, `DataSet`를 가져온다(테스트 mock이 이 경로를 가로챈다).

- [ ] **Step 1: 실패 테스트 작성 (vis-network mock)**

Create `frontend/src/components/RelationsGraph.test.ts`:

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

const clickHandlers: Array<(p: any) => void> = []
const NetworkMock = vi.fn().mockImplementation(() => ({
  on: (evt: string, cb: (p: any) => void) => { if (evt === 'click') clickHandlers.push(cb) },
  destroy: vi.fn(),
}))
class DataSetMock {
  items: any[]
  constructor(init: any[] = []) { this.items = [...init] }
  add(x: any) { this.items.push(...([] as any[]).concat(x)) }
  clear() { this.items = [] }
  get() { return this.items }
  update(_x: any) { /* no-op */ }
}
vi.mock('vis-network/standalone', () => ({ Network: NetworkMock, DataSet: DataSetMock }))

import RelationsGraph from './RelationsGraph.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => {
  setActivePinia(createPinia())
  clickHandlers.length = 0
  NetworkMock.mockClear()
})

describe('RelationsGraph', () => {
  it('creates a vis Network on mount with a container', () => {
    const w = mount(RelationsGraph, { attachTo: document.body })
    expect(NetworkMock).toHaveBeenCalledTimes(1)
    expect(w.find('.relations-graph').exists()).toBe(true)
  })

  it('node click selects the class in the store', () => {
    const store = useOntologyStore()
    mount(RelationsGraph, { attachTo: document.body })
    expect(clickHandlers.length).toBe(1)
    clickHandlers[0]({ nodes: ['e#orders'], edges: [] })
    expect(store.selectedIri).toBe('e#orders')
  })
})
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

Run: `cd frontend && npx vitest run src/components/RelationsGraph.test.ts`
Expected: FAIL — 컴포넌트 파일 없음.

- [ ] **Step 3: 구현 작성**

Create `frontend/src/components/RelationsGraph.vue`:

```vue
<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { Network, DataSet } from 'vis-network/standalone'
import { useOntologyStore } from '../stores/ontologyStore'
import { buildGraphData } from '../lib/buildGraphData'

const store = useOntologyStore()
const container = ref<HTMLDivElement | null>(null)
let network: Network | null = null
let nodes: DataSet<any> | null = null
let edges: DataSet<any> | null = null

function rebuild() {
  if (!nodes || !edges) return
  const g = buildGraphData(store.classes, store.objectProperties)
  nodes.clear(); nodes.add(g.nodes)
  edges.clear(); edges.add(g.edges)
  highlight()
}

function highlight() {
  if (!nodes) return
  const sel = store.selectedIri
  for (const n of nodes.get() as Array<{ id: string }>) {
    nodes.update({ id: n.id, color: n.id === sel ? '#c7d2fe' : '#e5e7eb' })
  }
}

onMounted(() => {
  nodes = new DataSet<any>([])
  edges = new DataSet<any>([])
  network = new Network(container.value as HTMLElement, { nodes, edges }, {
    nodes: { shape: 'box', color: '#e5e7eb', font: { size: 14 } },
    edges: { arrows: 'to', font: { align: 'top', size: 12 }, color: '#9ca3af' },
    physics: { stabilization: true },
    layout: { improvedLayout: true },
    interaction: { hover: true, dragNodes: true, zoomView: true, dragView: true },
  })
  network.on('click', (params: { nodes: string[] }) => {
    if (params.nodes && params.nodes.length > 0) store.select(params.nodes[0])
  })
  rebuild()
})

onBeforeUnmount(() => { network?.destroy(); network = null })

watch(() => [store.classes, store.objectProperties], rebuild, { deep: true })
watch(() => store.selectedIri, highlight)
</script>

<template>
  <div ref="container" class="relations-graph"></div>
</template>

<style scoped>
.relations-graph { width: 100%; height: 100%; min-height: 420px; }
</style>
```

- [ ] **Step 4: 테스트 실행 (통과 확인)**

Run: `cd frontend && npx vitest run src/components/RelationsGraph.test.ts`
Expected: PASS — 2 tests.

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/components/RelationsGraph.vue frontend/src/components/RelationsGraph.test.ts
git commit -m "feat(p6): RelationsGraph — vis-network 캔버스 + 노드클릭 선택 연동

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: RelationsView.vue 토글 + App.vue 연결

**Files:**
- Create: `frontend/src/components/RelationsView.vue`
- Modify: `frontend/src/App.vue`
- Test: `frontend/src/components/RelationsView.test.ts`

**Interfaces:**
- Consumes: `RelationsPanel.vue`, `RelationsGraph.vue`.
- Produces: 목록/그래프 토글. 기본은 목록. App.vue 우측 영역에서 사용.

- [ ] **Step 1: 실패 테스트 작성**

Create `frontend/src/components/RelationsView.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import RelationsView from './RelationsView.vue'

beforeEach(() => setActivePinia(createPinia()))

describe('RelationsView', () => {
  it('shows list by default and switches to graph on tab click', async () => {
    const w = mount(RelationsView, {
      global: { stubs: {
        RelationsPanel: { template: '<div class="stub-list" />' },
        RelationsGraph: { template: '<div class="stub-graph" />' },
      } },
    })
    expect(w.find('.stub-list').exists()).toBe(true)
    expect(w.find('.stub-graph').exists()).toBe(false)

    await w.find('.tab-graph').trigger('click')
    expect(w.find('.stub-graph').exists()).toBe(true)
    expect(w.find('.stub-list').exists()).toBe(false)

    await w.find('.tab-list').trigger('click')
    expect(w.find('.stub-list').exists()).toBe(true)
  })
})
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

Run: `cd frontend && npx vitest run src/components/RelationsView.test.ts`
Expected: FAIL — 컴포넌트 파일 없음.

- [ ] **Step 3: 구현 작성**

Create `frontend/src/components/RelationsView.vue`:

```vue
<script setup lang="ts">
import { ref } from 'vue'
import RelationsPanel from './RelationsPanel.vue'
import RelationsGraph from './RelationsGraph.vue'

const mode = ref<'list' | 'graph'>('list')
</script>

<template>
  <div class="relations-view">
    <div class="view-tabs">
      <button class="tab-list" :class="{ active: mode === 'list' }" @click="mode = 'list'">목록</button>
      <button class="tab-graph" :class="{ active: mode === 'graph' }" @click="mode = 'graph'">그래프</button>
    </div>
    <div class="view-body">
      <RelationsPanel v-if="mode === 'list'" />
      <RelationsGraph v-else />
    </div>
  </div>
</template>

<style scoped>
.relations-view { display: flex; flex-direction: column; height: 100%; }
.view-tabs { display: flex; gap: 4px; padding: 8px 12px; border-bottom: 1px solid #e5e7eb; }
.view-tabs button { padding: 4px 12px; border: 1px solid #d1d5db; background: white; border-radius: 6px; cursor: pointer; font-size: 13px; }
.view-tabs button.active { background: #4f46e5; color: white; border-color: #4f46e5; }
.view-body { flex: 1; min-height: 0; }
</style>
```

- [ ] **Step 4: 테스트 실행 (통과 확인)**

Run: `cd frontend && npx vitest run src/components/RelationsView.test.ts`
Expected: PASS — 1 test.

- [ ] **Step 5: App.vue에서 RelationsPanel → RelationsView 교체**

`frontend/src/App.vue` 수정:
1. import 교체: `import RelationsPanel from './components/RelationsPanel.vue'` 줄을 `import RelationsView from './components/RelationsView.vue'`로 변경.
2. 템플릿의 `<RelationsPanel />`을 `<RelationsView />`로 변경.

수정 후 우측 섹션은 이렇게 된다:
```html
      <section class="right">
        <ClassDetail />
        <RelationsView />
      </section>
```

- [ ] **Step 6: 전체 프론트 테스트 + 타입체크 (회귀 확인)**

Run: `cd frontend && npx vitest run && npx vue-tsc -b`
Expected: 모든 테스트 통과, 타입 에러 없음.

- [ ] **Step 7: 커밋**

```bash
git add frontend/src/components/RelationsView.vue frontend/src/components/RelationsView.test.ts frontend/src/App.vue
git commit -m "feat(p6): RelationsView 목록⇄그래프 토글 + App 연결

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: 브라우저 E2E 검증 (성공 기준)

**Files:** 없음 (수동/도구 기반 E2E)

> 로컬에서 Docker가 8080/8081 점유 → 백엔드는 8090으로 기동(vite dev proxy 타깃이 8090).

- [ ] **Step 1: 백엔드 기동 (8090)**

Run (백그라운드): `cd backend && ./gradlew bootRun --args='--server.port=8090'`
준비 확인: `curl -s http://localhost:8090/api/ontology/meta | grep baseIri` → 값 반환.

- [ ] **Step 2: 프론트 dev 기동**

Run (백그라운드): `cd frontend && npm run dev`
확인: `http://localhost:5173/` 200.

- [ ] **Step 3: 임포트 → 그래프 확인**

브라우저에서:
1. "RDB 가져오기" → DDL 탭 → 아래 DDL 붙여넣기 → 가져오기
```sql
CREATE TABLE customers (id INTEGER PRIMARY KEY, name VARCHAR(100));
CREATE TABLE orders (id INTEGER PRIMARY KEY, total NUMERIC(10,2), customer_id INTEGER,
  CONSTRAINT fk FOREIGN KEY (customer_id) REFERENCES customers(id));
```
2. 우측에서 **그래프** 탭 클릭 → `customers`/`orders` 노드 + `orders→customers` 방향 엣지(라벨) 표시 확인 (성공기준 1·2)
3. `orders` 노드 클릭 → 좌측 ClassDetail/목록에서 orders 선택됨 확인 (성공기준 3)

- [ ] **Step 4: 갱신 확인**

목록 탭에서 관계 이름을 `placedBy`로 변경 → 그래프 탭으로 전환 시 엣지 라벨이 `placedBy`로 갱신됨 확인 (성공기준 4).

- [ ] **Step 5: 서버 종료 + 아티팩트 정리**

Run:
```bash
for p in 8090 5173; do PID=$(lsof -nP -iTCP:$p -sTCP:LISTEN -t 2>/dev/null); [ -n "$PID" ] && kill -9 $PID; done
rm -rf .playwright-mcp frontend/.playwright-mcp *.png frontend/*.png 2>/dev/null
git status -s
```
Expected: 포트 반환, git 트리 clean.

---

## Self-Review

**Spec coverage (스펙 §별 → 태스크):**
- §2 컴포넌트(RelationsView/RelationsGraph, App 교체) → Task 2·3 ✓
- §3 buildGraphData 순수 매핑(노드/엣지/self-loop/방어) → Task 1 ✓
- §4 상호작용(노드클릭=select) + 반응성(watch classes/objectProperties, selectedIri 하이라이트) → Task 2 ✓
- §5 테스트(buildGraphData/RelationsView/RelationsGraph mock/E2E) → Task 1·2·3·4 ✓
- §6 성공기준 1~5 → Task 4(1~4), 백엔드 무변경(5)은 전 태스크가 프론트 전용 ✓
- §1 D1 vis-network → Task 1 의존성 ✓; D2 토글 → Task 3 ✓; D3 노드클릭·편집제외 → Task 2 ✓; D4 백엔드무변경 → 전체 ✓

**Placeholder scan:** TODO/TBD 없음. 모든 코드 스텝에 완전한 코드 포함.

**Type consistency:** `buildGraphData(classes, objectProperties): GraphData`, `shortName(iri): string` — Task 1 정의와 Task 2 사용 일치. `GraphEdge.arrows: string`(='to'), 노드 `{id,label}` 일관. RelationsGraph는 `'vis-network/standalone'`에서 `Network`,`DataSet`를 import하며 Task 2 테스트 mock 경로와 일치. RelationsView 자식 컴포넌트명(RelationsPanel/RelationsGraph)이 Task 3 테스트 stub 키와 일치 ✓.
