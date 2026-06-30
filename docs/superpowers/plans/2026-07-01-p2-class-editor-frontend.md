# P2 Class Editor Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** P1 백엔드 위에 얹는 Vue 3 클래스 편집기 화면 — 2패인(좌 트리 / 우 상세·편집) + 툴바(로드/저장/추가/삭제).

**Architecture:** Vite+Vue3+TS SPA. 순수 트리 구성 로직(`buildTree`)을 컴포넌트와 분리, Pinia 스토어가 API 호출·상태를 담당, 컴포넌트는 스토어를 구독해 렌더. 백엔드는 Vite 개발 프록시(`/api`→localhost:8090)로 동일 출처처럼 호출(CORS 불필요). 클래스 트리는 백엔드 `/tree`(orphan 누락 버그)를 쓰지 않고 평면 `/api/classes`를 받아 프론트에서 구성.

**Tech Stack:** Vite, Vue 3 (`<script setup lang="ts">`), TypeScript, Pinia, Vitest + @vue/test-utils + jsdom.

## Global Constraints

- 프론트는 `frontend/` 디렉터리(백엔드 `backend/`와 형제). 백엔드 코드는 수정하지 않는다.
- 백엔드 API 베이스 `/api`, 개발 프록시 타깃 `http://localhost:8090`.
- 엔티티 식별자는 IRI(string). 경로 변수로 보낼 때 `encodeURIComponent`.
- owl:Thing IRI 상수 = `http://www.w3.org/2002/07/owl#Thing`.
- 트리는 평면 `GET /api/classes` + `superClasses`로 클라이언트에서 구성(`lib/buildTree.ts`). 사이클은 ancestors 경로 셋으로 가드.
- rdfs:comment(설명)는 **읽기 전용**(백엔드 PATCH 미지원). 편집은 label/superClasses만.
- TDD: 실패 테스트 → 실패 확인 → 최소 구현 → 통과 확인 → 커밋. 자주 커밋.
- 모든 명령은 `cd frontend`에서 실행.

---

## File Structure

```
frontend/
├─ package.json
├─ vite.config.ts            # 프록시 + vitest(jsdom)
├─ tsconfig.json / tsconfig.node.json
├─ index.html
└─ src/
   ├─ main.ts                # createApp + Pinia
   ├─ App.vue                # Toolbar + 2패인 레이아웃
   ├─ api/
   │  ├─ types.ts            # ClassDto, OntologyMetaDto, ApiError
   │  └─ client.ts           # fetch 래퍼 (get/post/patch/del/upload/download)
   ├─ lib/
   │  └─ buildTree.ts        # 평면→중첩 트리 (순수 함수)
   ├─ stores/
   │  └─ ontologyStore.ts    # 상태 + 액션
   └─ components/
      ├─ ClassTree.vue
      ├─ ClassTreeNode.vue   # 재귀
      ├─ ClassDetail.vue
      └─ Toolbar.vue
```

---

## Task 1: 스캐폴드 + Vite 프록시 + API 클라이언트

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/index.html`, `frontend/src/main.ts`, `frontend/src/App.vue`
- Create: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`
- Test: `frontend/src/api/client.test.ts`

**Interfaces:**
- Produces:
  - `types.ts`: `interface AnnotationDto { property: string; value: string; lang: string | null }`, `interface ClassDto { iri: string; label: string | null; superClasses: string[]; annotations: AnnotationDto[] }`, `interface OntologyMetaDto { ontologyIri: string | null; baseIri: string; prefixes: Record<string,string>; counts: Record<string,number> }`, `class ApiError extends Error { error: string; targetIri: string | null }`
  - `client.ts`: `apiGet<T>(path: string): Promise<T>`, `apiPost<T>(path: string, body: unknown): Promise<T>`, `apiPatch<T>(path: string, body: unknown): Promise<T>`, `apiDelete(path: string): Promise<void>`, `apiUpload<T>(path: string, file: File, fields?: Record<string,string>): Promise<T>`, `apiDownload(path: string): Promise<Blob>`

- [ ] **Step 1: package.json + configs**

`frontend/package.json`:
```json
{
  "name": "onto-studio-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "dependencies": { "vue": "^3.5.13", "pinia": "^2.2.6" },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.2.1",
    "@vue/test-utils": "^2.4.6",
    "jsdom": "^25.0.1",
    "typescript": "^5.6.3",
    "vite": "^6.0.5",
    "vitest": "^2.1.8",
    "vue-tsc": "^2.1.10"
  }
}
```

`frontend/vite.config.ts`:
```typescript
/// <reference types="vitest" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: { '/api': { target: 'http://localhost:8090', changeOrigin: true } },
  },
  test: { environment: 'jsdom', globals: true },
})
```

`frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022", "module": "ESNext", "moduleResolution": "bundler",
    "strict": true, "jsx": "preserve", "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "types": ["vitest/globals"], "skipLibCheck": true, "noEmit": true
  },
  "include": ["src/**/*.ts", "src/**/*.vue"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

`frontend/tsconfig.node.json`:
```json
{
  "compilerOptions": { "module": "ESNext", "moduleResolution": "bundler", "composite": true, "skipLibCheck": true },
  "include": ["vite.config.ts"]
}
```

`frontend/index.html`:
```html
<!doctype html>
<html lang="ko">
  <head><meta charset="UTF-8" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><title>onto-studio</title></head>
  <body><div id="app"></div><script type="module" src="/src/main.ts"></script></body>
</html>
```

- [ ] **Step 2: install deps**

Run: `cd frontend && npm install`
Expected: `node_modules` created, no error.

- [ ] **Step 3: Write the failing test** — `frontend/src/api/client.test.ts`:
```typescript
import { describe, it, expect, vi, afterEach } from 'vitest'
import { apiGet, ApiError } from './client'

afterEach(() => vi.restoreAllMocks())

describe('apiGet', () => {
  it('returns parsed json on 200', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      new Response(JSON.stringify({ status: 'ok' }), { status: 200, headers: { 'Content-Type': 'application/json' } })))
    expect(await apiGet<{ status: string }>('/health')).toEqual({ status: 'ok' })
  })

  it('throws ApiError carrying error/message on non-2xx', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      new Response(JSON.stringify({ error: 'not_found', message: '없음', targetIri: 'x' }), { status: 404, headers: { 'Content-Type': 'application/json' } })))
    await expect(apiGet('/classes/x')).rejects.toMatchObject({ error: 'not_found', message: '없음', targetIri: 'x' })
  })
})
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/api/client.test.ts`
Expected: FAIL — `./client` not found / `apiGet` undefined.

- [ ] **Step 5: Implement types + client**

`frontend/src/api/types.ts`:
```typescript
export interface AnnotationDto { property: string; value: string; lang: string | null }
export interface ClassDto { iri: string; label: string | null; superClasses: string[]; annotations: AnnotationDto[] }
export interface OntologyMetaDto { ontologyIri: string | null; baseIri: string; prefixes: Record<string, string>; counts: Record<string, number> }

export class ApiError extends Error {
  error: string
  targetIri: string | null
  constructor(error: string, message: string, targetIri: string | null) {
    super(message); this.name = 'ApiError'; this.error = error; this.targetIri = targetIri
  }
}
```

`frontend/src/api/client.ts`:
```typescript
import { ApiError } from './types'
export { ApiError } from './types'

const BASE = '/api'

async function parseError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json()
    return new ApiError(body.error ?? 'error', body.message ?? res.statusText, body.targetIri ?? null)
  } catch {
    return new ApiError('error', res.statusText || `HTTP ${res.status}`, null)
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path)
  if (!res.ok) throw await parseError(res)
  return res.json() as Promise<T>
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  if (!res.ok) throw await parseError(res)
  return res.json() as Promise<T>
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  if (!res.ok) throw await parseError(res)
  return res.json() as Promise<T>
}

export async function apiDelete(path: string): Promise<void> {
  const res = await fetch(BASE + path, { method: 'DELETE' })
  if (!res.ok) throw await parseError(res)
}

export async function apiUpload<T>(path: string, file: File, fields: Record<string, string> = {}): Promise<T> {
  const form = new FormData()
  form.append('file', file)
  for (const [k, v] of Object.entries(fields)) form.append(k, v)
  const res = await fetch(BASE + path, { method: 'POST', body: form })
  if (!res.ok) throw await parseError(res)
  return res.json() as Promise<T>
}

export async function apiDownload(path: string): Promise<Blob> {
  const res = await fetch(BASE + path)
  if (!res.ok) throw await parseError(res)
  return res.blob()
}
```

`frontend/src/main.ts`:
```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'

createApp(App).use(createPinia()).mount('#app')
```

`frontend/src/App.vue` (placeholder; assembled in Task 7):
```vue
<script setup lang="ts"></script>
<template>
  <div class="app">onto-studio</div>
</template>
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/api/client.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 7: Commit**

```bash
cd frontend && git add -A
git commit -m "feat(p2): Vue/Vite 스캐폴드 + 프록시 + API 클라이언트"
```

---

## Task 2: buildTree 순수 함수

**Files:**
- Create: `frontend/src/lib/buildTree.ts`
- Test: `frontend/src/lib/buildTree.test.ts`

**Interfaces:**
- Consumes: `ClassDto` from `../api/types`
- Produces: `interface TreeNode { iri: string; label: string | null; children: TreeNode[] }`, `function buildTree(classes: ClassDto[]): TreeNode[]`, `const OWL_THING = 'http://www.w3.org/2002/07/owl#Thing'`

- [ ] **Step 1: Write the failing test** — `frontend/src/lib/buildTree.test.ts`:
```typescript
import { describe, it, expect } from 'vitest'
import { buildTree, OWL_THING } from './buildTree'
import type { ClassDto } from '../api/types'

const cls = (iri: string, superClasses: string[] = []): ClassDto =>
  ({ iri, label: iri.split('#')[1] ?? iri, superClasses, annotations: [] })

describe('buildTree', () => {
  it('puts classes with no superclass at root', () => {
    const tree = buildTree([cls('e#Animal'), cls('e#Plant')])
    expect(tree.map(n => n.iri).sort()).toEqual(['e#Animal', 'e#Plant'])
  })

  it('nests a subclass under its parent', () => {
    const tree = buildTree([cls('e#Animal'), cls('e#Dog', ['e#Animal'])])
    const animal = tree.find(n => n.iri === 'e#Animal')!
    expect(animal.children.map(c => c.iri)).toEqual(['e#Dog'])
  })

  it('treats owl:Thing-only parent as root', () => {
    const tree = buildTree([cls('e#Animal', [OWL_THING])])
    expect(tree.map(n => n.iri)).toEqual(['e#Animal'])
  })

  it('shows a multi-parent class under each parent', () => {
    const tree = buildTree([cls('e#A'), cls('e#B'), cls('e#C', ['e#A', 'e#B'])])
    const a = tree.find(n => n.iri === 'e#A')!
    const b = tree.find(n => n.iri === 'e#B')!
    expect(a.children.map(c => c.iri)).toEqual(['e#C'])
    expect(b.children.map(c => c.iri)).toEqual(['e#C'])
  })

  it('does not infinite-loop on a cycle', () => {
    const tree = buildTree([cls('e#A', ['e#B']), cls('e#B', ['e#A'])])
    expect(Array.isArray(tree)).toBe(true) // returns without stack overflow
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/buildTree.test.ts`
Expected: FAIL — `./buildTree` not found.

- [ ] **Step 3: Implement** — `frontend/src/lib/buildTree.ts`:
```typescript
import type { ClassDto } from '../api/types'

export const OWL_THING = 'http://www.w3.org/2002/07/owl#Thing'

export interface TreeNode { iri: string; label: string | null; children: TreeNode[] }

/** Build a nested tree from a flat class list using superClasses.
 *  Roots = classes with no named superclass (or only owl:Thing). Cyclic edges are skipped. */
export function buildTree(classes: ClassDto[]): TreeNode[] {
  const byIri = new Map<string, ClassDto>()
  for (const c of classes) byIri.set(c.iri, c)

  const parentsOf = (c: ClassDto): string[] =>
    c.superClasses.filter(s => s !== OWL_THING && byIri.has(s))

  const isRoot = (c: ClassDto): boolean => parentsOf(c).length === 0

  const childrenOf = (parentIri: string, ancestors: Set<string>): TreeNode[] => {
    if (ancestors.has(parentIri)) return []
    const path = new Set(ancestors).add(parentIri)
    return classes
      .filter(c => parentsOf(c).includes(parentIri))
      .map(c => ({ iri: c.iri, label: c.label, children: childrenOf(c.iri, path) }))
  }

  return classes
    .filter(isRoot)
    .map(c => ({ iri: c.iri, label: c.label, children: childrenOf(c.iri, new Set<string>()) }))
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/lib/buildTree.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
cd frontend && git add -A
git commit -m "feat(p2): buildTree 순수 함수 (평면→트리, orphan/다중부모/사이클)"
```

---

## Task 3: Pinia ontologyStore

**Files:**
- Create: `frontend/src/stores/ontologyStore.ts`
- Test: `frontend/src/stores/ontologyStore.test.ts`

**Interfaces:**
- Consumes: `apiGet/apiPost/apiPatch/apiDelete/apiUpload/apiDownload` from `../api/client`, `ClassDto/OntologyMetaDto` from `../api/types`, `buildTree/TreeNode` from `../lib/buildTree`
- Produces: `useOntologyStore()` with state `classes: ClassDto[]`, `selectedIri: string | null`, `meta: OntologyMetaDto | null`, `error: string | null`; getters `selected: ClassDto | null`, `tree: TreeNode[]`; actions `refresh(): Promise<void>`, `select(iri: string | null): void`, `createClass(label: string, superClass?: string): Promise<void>`, `saveClass(iri: string, patch: { label?: string; superClasses?: string[] }): Promise<void>`, `deleteClass(iri: string, cascade?: boolean): Promise<void>`, `loadFile(file: File): Promise<void>`, `exportTurtle(): Promise<Blob>`

- [ ] **Step 1: Write the failing test** — `frontend/src/stores/ontologyStore.test.ts`:
```typescript
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useOntologyStore } from './ontologyStore'
import * as client from '../api/client'
import type { ClassDto } from '../api/types'

const animal: ClassDto = { iri: 'e#Animal', label: 'Animal', superClasses: [], annotations: [] }

beforeEach(() => setActivePinia(createPinia()))
afterEach(() => vi.restoreAllMocks())

describe('ontologyStore', () => {
  it('refresh loads classes and meta', async () => {
    vi.spyOn(client, 'apiGet').mockImplementation(async (p: string) =>
      p === '/classes' ? [animal] : { counts: { classes: 1 } } as any)
    const s = useOntologyStore()
    await s.refresh()
    expect(s.classes).toEqual([animal])
    expect(s.tree.map(n => n.iri)).toEqual(['e#Animal'])
  })

  it('select sets selected getter', async () => {
    vi.spyOn(client, 'apiGet').mockImplementation(async (p: string) =>
      p === '/classes' ? [animal] : {} as any)
    const s = useOntologyStore()
    await s.refresh()
    s.select('e#Animal')
    expect(s.selected?.label).toBe('Animal')
  })

  it('createClass posts and refreshes', async () => {
    const post = vi.spyOn(client, 'apiPost').mockResolvedValue(animal as any)
    vi.spyOn(client, 'apiGet').mockResolvedValue([animal] as any)
    const s = useOntologyStore()
    await s.createClass('Animal')
    expect(post).toHaveBeenCalledWith('/classes', { label: 'Animal', superClass: undefined })
    expect(s.classes).toEqual([animal])
  })

  it('deleteClass surfaces ApiError message', async () => {
    vi.spyOn(client, 'apiDelete').mockRejectedValue(new client.ApiError('in_use', '사용 중', 'e#Animal'))
    vi.spyOn(client, 'apiGet').mockResolvedValue([] as any)
    const s = useOntologyStore()
    await s.deleteClass('e#Animal')
    expect(s.error).toBe('사용 중')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/stores/ontologyStore.test.ts`
Expected: FAIL — `./ontologyStore` not found.

- [ ] **Step 3: Implement** — `frontend/src/stores/ontologyStore.ts`:
```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiGet, apiPost, apiPatch, apiDelete, apiUpload, apiDownload, ApiError } from '../api/client'
import type { ClassDto, OntologyMetaDto } from '../api/types'
import { buildTree } from '../lib/buildTree'

export const useOntologyStore = defineStore('ontology', () => {
  const classes = ref<ClassDto[]>([])
  const selectedIri = ref<string | null>(null)
  const meta = ref<OntologyMetaDto | null>(null)
  const error = ref<string | null>(null)

  const selected = computed(() => classes.value.find(c => c.iri === selectedIri.value) ?? null)
  const tree = computed(() => buildTree(classes.value))

  function setError(e: unknown) {
    error.value = e instanceof ApiError ? e.message : (e instanceof Error ? e.message : String(e))
  }

  async function refresh() {
    classes.value = await apiGet<ClassDto[]>('/classes')
    try { meta.value = await apiGet<OntologyMetaDto>('/ontology/meta') } catch { /* meta optional */ }
  }

  function select(iri: string | null) { selectedIri.value = iri }

  async function createClass(label: string, superClass?: string) {
    error.value = null
    try { await apiPost<ClassDto>('/classes', { label, superClass }); await refresh() }
    catch (e) { setError(e) }
  }

  async function saveClass(iri: string, patch: { label?: string; superClasses?: string[] }) {
    error.value = null
    try { await apiPatch<ClassDto>(`/classes/${encodeURIComponent(iri)}`, patch); await refresh() }
    catch (e) { setError(e) }
  }

  async function deleteClass(iri: string, cascade = false) {
    error.value = null
    try {
      await apiDelete(`/classes/${encodeURIComponent(iri)}?cascade=${cascade}`)
      if (selectedIri.value === iri) selectedIri.value = null
      await refresh()
    } catch (e) { setError(e) }
  }

  async function loadFile(file: File) {
    error.value = null
    try { await apiUpload<OntologyMetaDto>('/ontology/load', file); selectedIri.value = null; await refresh() }
    catch (e) { setError(e) }
  }

  async function exportTurtle(): Promise<Blob> {
    return apiDownload('/ontology/export?format=turtle')
  }

  return { classes, selectedIri, meta, error, selected, tree,
           refresh, select, createClass, saveClass, deleteClass, loadFile, exportTurtle }
})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/stores/ontologyStore.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
cd frontend && git add -A
git commit -m "feat(p2): ontologyStore (load/select/create/save/delete/load/export)"
```

---

## Task 4: ClassTree + ClassTreeNode 컴포넌트

**Files:**
- Create: `frontend/src/components/ClassTreeNode.vue`, `frontend/src/components/ClassTree.vue`
- Test: `frontend/src/components/ClassTree.test.ts`

**Interfaces:**
- Consumes: `useOntologyStore` (`tree`, `selectedIri`, `select`), `TreeNode` from `../lib/buildTree`
- Produces: `ClassTree` renders the store's `tree`; clicking a node calls `store.select(iri)`. `ClassTreeNode` props `{ node: TreeNode }`, recursive, emits nothing (calls store directly).

- [ ] **Step 1: Write the failing test** — `frontend/src/components/ClassTree.test.ts`:
```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import ClassTree from './ClassTree.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

describe('ClassTree', () => {
  it('renders nested class labels and selects on click', async () => {
    const s = useOntologyStore()
    s.classes = [
      { iri: 'e#Animal', label: 'Animal', superClasses: [], annotations: [] },
      { iri: 'e#Dog', label: 'Dog', superClasses: ['e#Animal'], annotations: [] },
    ]
    const wrapper = mount(ClassTree)
    expect(wrapper.text()).toContain('Animal')
    expect(wrapper.text()).toContain('Dog')

    await wrapper.findAll('.node-label')[0].trigger('click')
    expect(s.selectedIri).toBe('e#Animal')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/ClassTree.test.ts`
Expected: FAIL — components not found.

- [ ] **Step 3: Implement**

`frontend/src/components/ClassTreeNode.vue`:
```vue
<script setup lang="ts">
import type { TreeNode } from '../lib/buildTree'
import { useOntologyStore } from '../stores/ontologyStore'
defineProps<{ node: TreeNode }>()
const store = useOntologyStore()
</script>

<template>
  <li class="tree-node">
    <span
      class="node-label"
      :class="{ selected: store.selectedIri === node.iri }"
      @click="store.select(node.iri)"
    >{{ node.label ?? node.iri }}</span>
    <ul v-if="node.children.length" class="tree-children">
      <ClassTreeNode v-for="child in node.children" :key="child.iri" :node="child" />
    </ul>
  </li>
</template>

<style scoped>
.tree-children { list-style: none; padding-left: 16px; margin: 0; }
.node-label { cursor: pointer; display: block; padding: 2px 6px; border-radius: 4px; }
.node-label:hover { background: #eef2ff; }
.node-label.selected { background: #c7d2fe; font-weight: 600; }
</style>
```
> 재귀 컴포넌트는 `<script setup>`에서 파일명(`ClassTreeNode`)으로 자기 참조 가능.

`frontend/src/components/ClassTree.vue`:
```vue
<script setup lang="ts">
import { useOntologyStore } from '../stores/ontologyStore'
import ClassTreeNode from './ClassTreeNode.vue'
const store = useOntologyStore()
</script>

<template>
  <div class="class-tree">
    <p v-if="!store.tree.length" class="empty">클래스가 없습니다. 파일을 불러오거나 클래스를 추가하세요.</p>
    <ul v-else class="tree-root">
      <ClassTreeNode v-for="node in store.tree" :key="node.iri" :node="node" />
    </ul>
  </div>
</template>

<style scoped>
.class-tree { overflow: auto; height: 100%; }
.tree-root { list-style: none; padding: 8px; margin: 0; }
.empty { color: #6b7280; padding: 12px; font-size: 14px; }
</style>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/ClassTree.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add -A
git commit -m "feat(p2): ClassTree + ClassTreeNode (재귀 트리, 선택)"
```

---

## Task 5: ClassDetail 편집 폼

**Files:**
- Create: `frontend/src/components/ClassDetail.vue`
- Test: `frontend/src/components/ClassDetail.test.ts`

**Interfaces:**
- Consumes: `useOntologyStore` (`selected`, `saveClass`)
- Produces: `ClassDetail` shows the selected class. Editable: label (text), superClasses (comma-separated IRIs). Read-only: 설명(rdfs:comment from annotations). Save button calls `store.saveClass(iri, { label, superClasses })`.

- [ ] **Step 1: Write the failing test** — `frontend/src/components/ClassDetail.test.ts`:
```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import ClassDetail from './ClassDetail.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

describe('ClassDetail', () => {
  it('shows empty state when nothing selected', () => {
    useOntologyStore()
    const wrapper = mount(ClassDetail)
    expect(wrapper.text()).toContain('선택된 클래스가 없습니다')
  })

  it('edits label and calls saveClass on save', async () => {
    const s = useOntologyStore()
    s.classes = [{ iri: 'e#Dog', label: 'Dog', superClasses: ['e#Animal'], annotations: [] }]
    s.select('e#Dog')
    const save = vi.spyOn(s, 'saveClass').mockResolvedValue()
    const wrapper = mount(ClassDetail)

    await wrapper.find('input.label-input').setValue('Doggo')
    await wrapper.find('button.save-btn').trigger('click')
    expect(save).toHaveBeenCalledWith('e#Dog', { label: 'Doggo', superClasses: ['e#Animal'] })
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/ClassDetail.test.ts`
Expected: FAIL — component not found.

- [ ] **Step 3: Implement** — `frontend/src/components/ClassDetail.vue`:
```vue
<script setup lang="ts">
import { ref, watch } from 'vue'
import { useOntologyStore } from '../stores/ontologyStore'

const RDFS_COMMENT = 'http://www.w3.org/2000/01/rdf-schema#comment'
const store = useOntologyStore()

const label = ref('')
const superClassesText = ref('')

watch(() => store.selected, (c) => {
  label.value = c?.label ?? ''
  superClassesText.value = (c?.superClasses ?? []).join(', ')
}, { immediate: true })

const comment = () =>
  store.selected?.annotations.find(a => a.property === RDFS_COMMENT)?.value ?? ''

function save() {
  const c = store.selected
  if (!c) return
  const superClasses = superClassesText.value.split(',').map(s => s.trim()).filter(Boolean)
  store.saveClass(c.iri, { label: label.value, superClasses })
}
</script>

<template>
  <div class="class-detail">
    <p v-if="!store.selected" class="empty">선택된 클래스가 없습니다.</p>
    <div v-else class="form">
      <h3 class="iri">{{ store.selected.iri }}</h3>
      <label>Label</label>
      <input class="label-input" v-model="label" />
      <label>상위 클래스 (IRI, 쉼표 구분)</label>
      <input class="superclasses-input" v-model="superClassesText" />
      <label>설명 (읽기 전용)</label>
      <p class="comment">{{ comment() || '—' }}</p>
      <button class="save-btn" @click="save">저장</button>
      <p v-if="store.error" class="error">{{ store.error }}</p>
    </div>
  </div>
</template>

<style scoped>
.class-detail { padding: 16px; overflow: auto; height: 100%; }
.empty { color: #6b7280; }
.iri { font-size: 13px; color: #6b7280; word-break: break-all; font-weight: 400; }
label { display: block; margin: 12px 0 4px; font-size: 13px; font-weight: 600; }
input { width: 100%; padding: 6px 8px; border: 1px solid #d1d5db; border-radius: 6px; box-sizing: border-box; }
.comment { background: #f9fafb; padding: 8px; border-radius: 6px; min-height: 20px; }
.save-btn { margin-top: 16px; padding: 8px 20px; background: #4f46e5; color: white; border: none; border-radius: 6px; cursor: pointer; }
.error { color: #dc2626; margin-top: 8px; }
</style>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/ClassDetail.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add -A
git commit -m "feat(p2): ClassDetail 편집 폼 (label/상위 편집, 설명 읽기전용)"
```

---

## Task 6: Toolbar (추가/삭제/로드/내보내기)

**Files:**
- Create: `frontend/src/components/Toolbar.vue`
- Test: `frontend/src/components/Toolbar.test.ts`

**Interfaces:**
- Consumes: `useOntologyStore` (`createClass`, `deleteClass`, `selectedIri`, `loadFile`, `exportTurtle`)
- Produces: `Toolbar` with buttons: 불러오기(file input → `loadFile`), 내보내기(`exportTurtle` → download), +클래스(prompt label → `createClass`), 삭제(selected → `deleteClass`).

- [ ] **Step 1: Write the failing test** — `frontend/src/components/Toolbar.test.ts`:
```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import Toolbar from './Toolbar.vue'
import { useOntologyStore } from '../stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

describe('Toolbar', () => {
  it('creates a class from prompt input', async () => {
    const s = useOntologyStore()
    const create = vi.spyOn(s, 'createClass').mockResolvedValue()
    vi.stubGlobal('prompt', vi.fn(() => 'Animal'))
    const wrapper = mount(Toolbar)
    await wrapper.find('button.add-class-btn').trigger('click')
    expect(create).toHaveBeenCalledWith('Animal')
    vi.unstubAllGlobals()
  })

  it('deletes the selected class', async () => {
    const s = useOntologyStore()
    s.classes = [{ iri: 'e#Dog', label: 'Dog', superClasses: [], annotations: [] }]
    s.select('e#Dog')
    const del = vi.spyOn(s, 'deleteClass').mockResolvedValue()
    const wrapper = mount(Toolbar)
    await wrapper.find('button.delete-btn').trigger('click')
    expect(del).toHaveBeenCalledWith('e#Dog')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/Toolbar.test.ts`
Expected: FAIL — component not found.

- [ ] **Step 3: Implement** — `frontend/src/components/Toolbar.vue`:
```vue
<script setup lang="ts">
import { useOntologyStore } from '../stores/ontologyStore'
const store = useOntologyStore()

function onFile(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) store.loadFile(file)
  input.value = ''
}

function addClass() {
  const label = window.prompt('새 클래스 이름')
  if (label && label.trim()) store.createClass(label.trim())
}

function removeClass() {
  if (store.selectedIri) store.deleteClass(store.selectedIri)
}

async function exportFile() {
  const blob = await store.exportTurtle()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = 'ontology.ttl'; a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="toolbar">
    <label class="file-btn">
      불러오기
      <input type="file" accept=".ttl,.owl,.rdf,.xml" @change="onFile" hidden />
    </label>
    <button class="export-btn" @click="exportFile">내보내기</button>
    <span class="spacer" />
    <button class="add-class-btn" @click="addClass">+ 클래스</button>
    <button class="delete-btn" :disabled="!store.selectedIri" @click="removeClass">삭제</button>
  </div>
</template>

<style scoped>
.toolbar { display: flex; gap: 8px; align-items: center; padding: 8px 12px; border-bottom: 1px solid #e5e7eb; background: #fafafa; }
.spacer { flex: 1; }
button, .file-btn { padding: 6px 14px; border: 1px solid #d1d5db; border-radius: 6px; background: white; cursor: pointer; font-size: 14px; }
button:disabled { opacity: 0.5; cursor: not-allowed; }
.add-class-btn { background: #4f46e5; color: white; border-color: #4f46e5; }
</style>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/Toolbar.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add -A
git commit -m "feat(p2): Toolbar (추가/삭제/로드/내보내기)"
```

---

## Task 7: App.vue 조립 + 초기 로드 + 수동 검증

**Files:**
- Modify: `frontend/src/App.vue`
- Test: `frontend/src/App.test.ts`

**Interfaces:**
- Consumes: `Toolbar`, `ClassTree`, `ClassDetail`, `useOntologyStore` (`refresh`)
- Produces: 2패인 레이아웃에 모든 컴포넌트 조립, 마운트 시 `store.refresh()` 호출.

- [ ] **Step 1: Write the failing test** — `frontend/src/App.test.ts`:
```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import App from './App.vue'
import { useOntologyStore } from './stores/ontologyStore'

beforeEach(() => setActivePinia(createPinia()))

describe('App', () => {
  it('renders toolbar + tree + detail and refreshes on mount', async () => {
    const s = useOntologyStore()
    const refresh = vi.spyOn(s, 'refresh').mockResolvedValue()
    const wrapper = mount(App)
    expect(wrapper.find('.toolbar').exists()).toBe(true)
    expect(wrapper.find('.class-tree').exists()).toBe(true)
    expect(wrapper.find('.class-detail').exists()).toBe(true)
    expect(refresh).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/App.test.ts`
Expected: FAIL — App has no toolbar/tree/detail yet.

- [ ] **Step 3: Implement** — `frontend/src/App.vue`:
```vue
<script setup lang="ts">
import { onMounted } from 'vue'
import Toolbar from './components/Toolbar.vue'
import ClassTree from './components/ClassTree.vue'
import ClassDetail from './components/ClassDetail.vue'
import { useOntologyStore } from './stores/ontologyStore'

const store = useOntologyStore()
onMounted(() => { store.refresh() })
</script>

<template>
  <div class="layout">
    <Toolbar />
    <div class="panes">
      <aside class="left"><ClassTree /></aside>
      <section class="right"><ClassDetail /></section>
    </div>
  </div>
</template>

<style>
* { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
</style>

<style scoped>
.layout { display: flex; flex-direction: column; height: 100vh; }
.panes { display: flex; flex: 1; min-height: 0; }
.left { width: 320px; border-right: 1px solid #e5e7eb; min-height: 0; }
.right { flex: 1; min-height: 0; }
</style>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/App.test.ts`
Expected: PASS.

- [ ] **Step 5: Run the FULL suite + typecheck**

Run: `cd frontend && npx vitest run && npx vue-tsc -b`
Expected: all tests PASS, no type errors.

- [ ] **Step 6: Manual verification (backend must be running on 8090)**

Run: `cd frontend && npm run dev` (separate terminal; backend on 8090)
Open `http://localhost:5173`. Verify: 빈 트리 → `+ 클래스`로 Animal 추가 → 트리에 표시 → 선택 → label 편집·저장 → `+ 클래스`로 Dog 추가(상위 Animal 입력) → Dog가 Animal 아래 표시 → 내보내기로 Turtle 다운로드. (인메모리이므로 백엔드 재시작 시 초기화됨.)

- [ ] **Step 7: Commit**

```bash
cd frontend && git add -A
git commit -m "feat(p2): App 조립 + 초기 로드 (클래스 편집기 초안 완료)"
```

---

## Self-Review 결과

- **스펙 커버리지**: 2패인 레이아웃(T7), 클래스 트리(T2 buildTree + T4), 상세/편집(T5), 추가·삭제·로드·내보내기(T6), API/프록시(T1), 상태(T3) — 스펙 1·2·5·7절 전부 매핑. 설명은 읽기전용(T5, 스펙대로). 트리 프론트 구성(T2, 스펙 4절). 백엔드 무수정(전 태스크).
- **점진성**: T1~T7이 F1(셋업)→F2(트리)→F3(상세)→F4(툴바)→조립 순. 각 태스크 독립 테스트.
- **타입 일관성**: `ClassDto/OntologyMetaDto/ApiError`(T1) → 스토어/컴포넌트에서 동일 사용. `TreeNode/buildTree/OWL_THING`(T2) → 스토어 getter·트리 컴포넌트. 스토어 액션 시그니처(T3)와 컴포넌트 호출(T4~T6) 일치(`createClass(label)`, `saveClass(iri,{label,superClasses})`, `deleteClass(iri)`).
- **알려진 주의점(실행 시)**:
  - 의존성 버전(Vue 3.5/Vite 6/Vitest 2 등)은 npm 최신 호환으로 조정 가능 — `npm install` 실패 시 가까운 안정 버전 사용, 동작이 기준.
  - 재귀 컴포넌트(`ClassTreeNode`) 자기 참조는 Vue SFC 파일명 기반 — 빌드 경고 시 `defineOptions({ name: 'ClassTreeNode' })` 추가.
  - 백엔드는 8090에서 실행 중이어야 수동 검증 가능(프록시 타깃).
  - 백엔드 클래스 PATCH는 label/superClasses만 수용 — 설명 편집은 본 플랜 범위 밖(읽기전용).
