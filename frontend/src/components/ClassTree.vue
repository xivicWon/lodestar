<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useOntologyStore } from '../stores/ontologyStore'
import ClassTreeNode from './ClassTreeNode.vue'
import type { TreeNode } from '../lib/buildTree'
import { shortName } from '../lib/shortName'

const store = useOntologyStore()
const query = ref('')
const fileInput = ref<HTMLInputElement | null>(null)

onMounted(() => { store.fetchReference().catch(() => {}) })

function onPickFile(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (f) store.loadReference(f)
}

function matches(node: TreeNode, q: string): boolean {
  const label = (node.label ?? node.iri).toLowerCase()
  const table = shortName(node.iri).toLowerCase()
  if (label.includes(q) || table.includes(q)) return true
  return node.children.some(c => matches(c, q))
}

function prune(nodes: TreeNode[], q: string): TreeNode[] {
  return nodes
    .filter(n => matches(n, q))
    .map(n => ({ ...n, children: prune(n.children, q) }))
}

const shown = computed<TreeNode[]>(() => {
  const q = query.value.trim().toLowerCase()
  return q ? prune(store.tree, q) : store.tree
})

// depth-first 표시 순서로 각 클래스에 번호를 매긴다.
const indexMap = computed<Map<string, number>>(() => {
  const m = new Map<string, number>()
  let n = 0
  const walk = (nodes: TreeNode[]) => {
    for (const node of nodes) {
      m.set(node.iri, ++n)
      walk(node.children)
    }
  }
  walk(shown.value)
  return m
})
</script>

<template>
  <div class="class-tree">
    <input class="tree-search" v-model="query" placeholder="클래스 · 테이블명 검색…" />
    <p v-if="!store.tree.length" class="empty">클래스가 없습니다. 파일을 불러오거나 클래스를 추가하세요.</p>
    <p v-else-if="!shown.length" class="empty">검색 결과가 없습니다.</p>
    <ul v-else class="tree-root">
      <ClassTreeNode v-for="node in shown" :key="node.iri" :node="node" :index-map="indexMap" />
    </ul>

    <div class="reference-section">
      <div class="reference-head">
        <span class="reference-title">참조 온톨로지<span v-if="store.referenceMeta"> · {{ store.referenceMeta.classCount }}</span></span>
        <button v-if="store.referenceMeta" class="reference-clear" title="참조 비우기" @click="store.clearReference()">×</button>
      </div>
      <button v-if="!store.referenceMeta" class="reference-load-btn" @click="fileInput?.click()">＋ 참조 온톨로지 로드</button>
      <input ref="fileInput" type="file" accept=".ttl,.owl,.rdf,.xml,.n3" hidden @change="onPickFile" />
      <ul v-if="store.referenceClasses.length" class="reference-list">
        <li v-for="rc in store.referenceClasses" :key="rc.iri" class="reference-item">
          {{ rc.label ?? rc.iri }}
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.class-tree { overflow: auto; height: 100%; }
.tree-search { width: calc(100% - 16px); margin: 8px; padding: 6px 8px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; box-sizing: border-box; }
.tree-root { list-style: none; padding: 8px; margin: 0; }
.empty { color: #6b7280; padding: 12px; font-size: 14px; }
.reference-section { border-top: 1px solid #e5e7eb; margin-top: 8px; padding: 8px; }
.reference-head { display: flex; align-items: center; justify-content: space-between; padding: 2px 4px 6px; }
.reference-title { font-size: 11px; font-weight: 800; letter-spacing: 0.04em; color: #64748b; text-transform: uppercase; }
.reference-clear { border: none; background: transparent; color: #94a3b8; font-size: 15px; cursor: pointer; line-height: 1; }
.reference-load-btn { width: 100%; padding: 8px; border: 1px dashed #cbd5e1; border-radius: 8px; background: #f8fafc; color: #475569; font-size: 12.5px; cursor: pointer; }
.reference-load-btn:hover { background: #f1f5f9; }
.reference-list { list-style: none; margin: 6px 0 0; padding: 0; }
.reference-item { padding: 7px 10px; border-radius: 7px; font-size: 13px; color: #334155; background: #f8fafc; border: 1px solid #eef2f7; margin-bottom: 4px; }
</style>
