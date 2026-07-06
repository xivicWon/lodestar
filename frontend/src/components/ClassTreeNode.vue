<script setup lang="ts">
import { computed } from 'vue'
import type { TreeNode } from '../lib/buildTree'
import { useOntologyStore } from '../stores/ontologyStore'
import { shortName } from '../lib/shortName'
defineOptions({ name: 'ClassTreeNode' })
const props = defineProps<{ node: TreeNode; indexMap: Map<string, number> }>()
const store = useOntologyStore()

// 원본 테이블명(IRI 프래그먼트). 라벨이 업무명으로 복원돼 원본과 다를 때만 노출.
const origName = computed(() => shortName(props.node.iri))
const showOrig = computed(() => !!props.node.label && props.node.label !== origName.value)
</script>

<template>
  <li class="tree-node">
    <div class="node-row" :class="{ selected: store.selectedIri === node.iri }" @click="store.select(node.iri)">
      <span class="node-num">{{ indexMap.get(node.iri) }}</span>
      <span class="node-text">
        <span class="node-label">{{ node.label ?? node.iri }}</span>
        <span v-if="showOrig" class="node-orig"><span class="node-orig-tag">TBL</span>{{ origName }}</span>
      </span>
      <button class="node-del" title="삭제(휴지통으로 이동)" @click.stop="store.trashClass(node.iri)">×</button>
    </div>
    <ul v-if="node.children.length" class="tree-children">
      <ClassTreeNode v-for="child in node.children" :key="child.iri" :node="child" :index-map="indexMap" />
    </ul>
    <ul v-if="store.inferredChildrenOf(node.iri).length" class="tree-children inferred">
      <li v-for="ic in store.inferredChildrenOf(node.iri)" :key="'inf-' + ic.iri" class="inferred-child">
        {{ ic.label ?? ic.iri }} <span class="inferred-tag">(추론됨)</span>
      </li>
    </ul>
  </li>
</template>

<style scoped>
.tree-children { list-style: none; padding-left: 18px; margin: 0; }
.node-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
}
.node-row:hover { background: #eef2ff; }
.node-row.selected { background: #c7d2fe; }
.node-num {
  flex: 0 0 auto;
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  color: #4338ca;
  background: #e0e7ff;
  border-radius: 11px;
}
.node-text {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.node-label {
  font-size: 15px;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.node-row.selected .node-label { font-weight: 600; }
.node-orig {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
  font-size: 11px;
  color: #8592a8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.node-orig-tag {
  flex: 0 0 auto;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 8.5px;
  font-weight: 800;
  letter-spacing: 0.05em;
  color: #8592a8;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  padding: 1px 4px;
  border-radius: 4px;
}
.node-del {
  flex: 0 0 auto;
  width: 24px;
  height: 24px;
  padding: 0;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #9ca3af;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.12s, background 0.12s, color 0.12s;
}
.node-row:hover .node-del { opacity: 1; }
.node-del:hover { background: #fee2e2; color: #dc2626; }
.inferred-child { padding: 4px 8px; color: #6d28d9; font-style: italic; font-size: 14px; }
.inferred-tag { font-size: 11px; background: #ede9fe; color: #6d28d9; border-radius: 8px; padding: 0 6px; font-style: normal; }
</style>
