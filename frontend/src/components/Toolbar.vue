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
  if (!store.selectedIri) return
  if (window.confirm('휴지통으로 이동 — 컬럼·관계 포함')) store.trashClass(store.selectedIri)
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
    <label class="file-btn" title="Turtle/RDF/OWL 온톨로지 파일을 불러옵니다">
      불러오기
      <input type="file" accept=".ttl,.owl,.rdf,.xml" @change="onFile" hidden />
    </label>
    <button class="export-btn" title="현재 온톨로지를 Turtle 파일로 내보냅니다" @click="exportFile">내보내기</button>
    <button class="reason-btn" title="HermiT 추론기로 일관성 검사·자동 분류를 실행합니다" @click="store.runReasoner">추론 실행</button>
    <span class="spacer" />
    <button class="add-class-btn" title="새 클래스를 추가합니다" @click="addClass">+ 클래스</button>
    <button class="delete-btn" title="선택한 클래스를 휴지통으로 이동합니다(컬럼·관계 포함, 실 DB는 불변). 클래스를 먼저 선택하세요" :disabled="!store.selectedIri" @click="removeClass">삭제</button>
  </div>
</template>

<style scoped>
.toolbar { display: flex; gap: 8px; align-items: center; padding: 8px 12px; border-bottom: 1px solid #e5e7eb; background: #fafafa; }
.spacer { flex: 1; }
button, .file-btn { padding: 6px 14px; border: 1px solid #d1d5db; border-radius: 6px; background: white; cursor: pointer; font-size: 14px; }
button:disabled { opacity: 0.5; cursor: not-allowed; }
.add-class-btn { background: #4f46e5; color: white; border-color: #4f46e5; }
</style>
