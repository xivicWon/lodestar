<script setup lang="ts">
import { onMounted, ref } from 'vue'
import Toolbar from './components/Toolbar.vue'
import ImportPanel from './components/ImportPanel.vue'
import EnrichPanel from './components/EnrichPanel.vue'
import RelationSuggestPanel from './components/RelationSuggestPanel.vue'
import ConsistencyBadge from './components/ConsistencyBadge.vue'
import ClassTree from './components/ClassTree.vue'
import ClassDetail from './components/ClassDetail.vue'
import RelationsView from './components/RelationsView.vue'
import { useOntologyStore } from './stores/ontologyStore'

const store = useOntologyStore()
const showImport = ref(false)
const showEnrich = ref(false)
const showRel = ref(false)
onMounted(() => { store.refresh() })
</script>

<template>
  <div class="layout">
    <Toolbar />
    <div class="import-toggle-bar">
      <button class="toggle-import-btn" @click="showImport = !showImport">
        {{ showImport ? 'RDB 가져오기 닫기' : 'RDB 가져오기' }}
      </button>
      <button class="toggle-enrich-btn" @click="showEnrich = !showEnrich">
        {{ showEnrich ? 'AI 의미 추정 닫기' : 'AI 의미 추정' }}
      </button>
      <button class="toggle-rel-btn" @click="showRel = !showRel">
        {{ showRel ? '관계 발굴 닫기' : '관계 발굴' }}
      </button>
    </div>
    <ImportPanel v-if="showImport" />
    <EnrichPanel v-if="showEnrich" />
    <RelationSuggestPanel v-if="showRel" />
    <div class="status-bar"><ConsistencyBadge /></div>
    <div v-if="store.error" class="error-banner" role="alert">
      <span>{{ store.error }}</span>
      <button class="dismiss-error" @click="store.clearError()">×</button>
    </div>
    <div class="panes">
      <aside class="left"><ClassTree /></aside>
      <section class="right">
        <div class="detail-pane"><ClassDetail /></div>
        <div class="relations-pane"><RelationsView /></div>
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
.right { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.detail-pane { flex: 0 0 auto; max-height: 40%; overflow: auto; border-bottom: 1px solid #e5e7eb; }
.relations-pane { flex: 1 1 auto; min-height: 0; }
.status-bar { padding: 6px 12px; }
.import-toggle-bar { padding: 6px 12px; }
.toggle-import-btn, .toggle-enrich-btn, .toggle-rel-btn { padding: 6px 14px; border: 1px solid #d1d5db; border-radius: 6px; background: white; cursor: pointer; font-size: 14px; margin-right: 6px; }
.error-banner { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; background: #fee2e2; border-bottom: 1px solid #fca5a5; color: #991b1b; font-size: 14px; }
.dismiss-error { background: none; border: none; cursor: pointer; font-size: 18px; color: #991b1b; padding: 0 4px; line-height: 1; }
</style>
