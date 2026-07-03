<script setup lang="ts">
import { onMounted } from 'vue'
import { useOntologyStore } from '../stores/ontologyStore'
const store = useOntologyStore()

onMounted(() => { store.fetchTrash() })

function fmt(ms: number): string {
  return new Date(ms).toLocaleDateString()
}
</script>

<template>
  <div class="trash-panel">
    <p v-if="!store.trash.length" class="trash-empty">휴지통이 비어 있습니다</p>
    <ul v-else class="trash-list">
      <li v-for="e in store.trash" :key="e.iri" class="trash-item">
        <span class="trash-item-label">{{ e.label }}</span>
        <span class="trash-item-date">{{ fmt(e.trashedAt) }}</span>
        <button class="trash-restore-btn" @click="store.restoreTrash(e.iri)">복구</button>
        <button class="trash-purge-btn" @click="store.purgeTrash(e.iri)">완전삭제</button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.trash-panel { padding: 12px 16px; border-top: 1px solid #e5e7eb; }
.trash-empty { font-size: 13px; color: #9ca3af; margin: 0; }
.trash-list { list-style: none; margin: 0; padding: 0; }
.trash-item { display: flex; align-items: center; gap: 8px; padding: 4px 8px; border-radius: 5px; font-size: 13px; }
.trash-item:hover { background: #f3f4f6; }
.trash-item-label { flex: 1; }
.trash-item-date { color: #9ca3af; font-size: 12px; }
.trash-restore-btn, .trash-purge-btn { padding: 4px 10px; border: 1px solid #d1d5db; border-radius: 5px; background: white; cursor: pointer; font-size: 12px; }
.trash-purge-btn { color: #b91c1c; border-color: #fca5a5; }
</style>
