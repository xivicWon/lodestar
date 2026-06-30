<script setup lang="ts">
import type { TreeNode } from '../lib/buildTree'
import { useOntologyStore } from '../stores/ontologyStore'
defineOptions({ name: 'ClassTreeNode' })
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
