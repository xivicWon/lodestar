<script setup lang="ts">
import { onMounted } from 'vue'
import Toolbar from './components/Toolbar.vue'
import ConsistencyBadge from './components/ConsistencyBadge.vue'
import ClassTree from './components/ClassTree.vue'
import ClassDetail from './components/ClassDetail.vue'
import { useOntologyStore } from './stores/ontologyStore'

const store = useOntologyStore()
onMounted(() => { store.refresh() })
</script>

<template>
  <div class="layout">
    <Toolbar />
    <div class="status-bar"><ConsistencyBadge /></div>
    <div v-if="store.error" class="error-banner" role="alert">
      <span>{{ store.error }}</span>
      <button class="dismiss-error" @click="store.clearError()">×</button>
    </div>
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
.status-bar { padding: 6px 12px; }
.error-banner { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; background: #fee2e2; border-bottom: 1px solid #fca5a5; color: #991b1b; font-size: 14px; }
.dismiss-error { background: none; border: none; cursor: pointer; font-size: 18px; color: #991b1b; padding: 0 4px; line-height: 1; }
</style>
