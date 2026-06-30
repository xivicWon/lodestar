<script setup lang="ts">
import { useOntologyStore } from '../stores/ontologyStore'
const store = useOntologyStore()

function onFile(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) store.loadFile(file)
  input.value = ''
}

function addClass() {
  const label = window.prompt('새 클래스 이름')
  if (label && label.trim()) store.createClass(label.trim())
}

function removeClass() {
  if (store.selectedIri) store.deleteClass(store.selectedIri)
}

async function exportFile() {
  try {
    const blob = await store.exportTurtle()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'ontology.ttl'; a.click()
    URL.revokeObjectURL(url)
  } catch (e) { store.reportError(e) }
}
</script>

<template>
  <div class="toolbar">
    <label class="file-btn">
      불러오기
      <input type="file" accept=".ttl,.owl,.rdf,.xml" @change="onFile" hidden />
    </label>
    <button class="export-btn" @click="exportFile">내보내기</button>
    <span class="spacer" />
    <button class="add-class-btn" @click="addClass">+ 클래스</button>
    <button class="delete-btn" :disabled="!store.selectedIri" @click="removeClass">삭제</button>
  </div>
</template>

<style scoped>
.toolbar { display: flex; gap: 8px; align-items: center; padding: 8px 12px; border-bottom: 1px solid #e5e7eb; background: #fafafa; }
.spacer { flex: 1; }
button, .file-btn { padding: 6px 14px; border: 1px solid #d1d5db; border-radius: 6px; background: white; cursor: pointer; font-size: 14px; }
button:disabled { opacity: 0.5; cursor: not-allowed; }
.add-class-btn { background: #4f46e5; color: white; border-color: #4f46e5; }
</style>
