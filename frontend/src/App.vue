<script setup lang="ts">
import { onMounted, ref } from 'vue'
import Toolbar from './components/Toolbar.vue'
import ImportPanel from './components/ImportPanel.vue'
import ConsistencyBadge from './components/ConsistencyBadge.vue'
import ClassTree from './components/ClassTree.vue'
import ClassDetail from './components/ClassDetail.vue'
import RelationsPanel from './components/RelationsPanel.vue'
import { useOntologyStore } from './stores/ontologyStore'

const store = useOntologyStore()
const showImport = ref(false)
onMounted(() => { store.refresh() })
</script>

<template>
  <div class="layout">
    <Toolbar />
    <div class="import-toggle-bar">
      <button class="toggle-import-btn" @click="showImport = !showImport">
        {{ showImport ? 'RDB 가져오기 닫기' : 'RDB 가져오기' }}
      </button>
    </div>
    <ImportPanel v-if="showImport" />
    <div class="status-bar"><ConsistencyBadge /></div>
    <div v-if="store.error" class="error-banner" role="alert">
      <span>{{ store.error }}</span>
      <button class="dismiss-error" @click="store.clearError()">×</button>
    </div>
    <div class="panes">
      <aside class="left"><ClassTree /></aside>
      <section class="right">
        <ClassDetail />
        <RelationsPanel />
      </section>
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
.import-toggle-bar { padding: 6px 12px; }
.toggle-import-btn { padding: 6px 14px; border: 1px solid #d1d5db; border-radius: 6px; background: white; cursor: pointer; font-size: 14px; }
.error-banner { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; background: #fee2e2; border-bottom: 1px solid #fca5a5; color: #991b1b; font-size: 14px; }
.dismiss-error { background: none; border: none; cursor: pointer; font-size: 18px; color: #991b1b; padding: 0 4px; line-height: 1; }
</style>
