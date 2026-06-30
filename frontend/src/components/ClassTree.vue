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
