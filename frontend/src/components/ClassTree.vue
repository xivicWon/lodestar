<script setup lang="ts">
import { ref, computed } from 'vue'
import { useOntologyStore } from '../stores/ontologyStore'
import ClassTreeNode from './ClassTreeNode.vue'
import type { TreeNode } from '../lib/buildTree'
import { shortName } from '../lib/shortName'

const store = useOntologyStore()
const query = ref('')

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
  </div>
</template>

<style scoped>
.class-tree { overflow: auto; height: 100%; }
.tree-search { width: calc(100% - 16px); margin: 8px; padding: 6px 8px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; box-sizing: border-box; }
.tree-root { list-style: none; padding: 8px; margin: 0; }
.empty { color: #6b7280; padding: 12px; font-size: 14px; }
</style>
