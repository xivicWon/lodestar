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
