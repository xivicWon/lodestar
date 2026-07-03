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
  <!-- 관리 도구 (입출력·편집). 복원 파이프라인 단계는 App.vue 의 pipeline-bar 에 있다. -->
  <div class="toolbar">
    <label class="file-btn" data-tip="Turtle/RDF/OWL 온톨로지 파일을 불러옵니다">
      파일 불러오기
      <input type="file" accept=".ttl,.owl,.rdf,.xml" @change="onFile" hidden />
    </label>
    <button class="export-btn" data-tip="현재 온톨로지를 Turtle 파일로 내보냅니다" @click="exportFile">내보내기</button>
    <button class="add-class-btn" data-tip="새 클래스를 추가합니다" @click="addClass">＋클래스</button>
    <button class="delete-btn" data-tip="선택한 클래스를 휴지통으로 이동합니다(컬럼·관계 포함, 실 DB는 불변). 클래스를 먼저 선택하세요" :disabled="!store.selectedIri" @click="removeClass">삭제</button>
  </div>
</template>

<style scoped>
/* 관리 바 안에서 인라인으로 자연스럽게 배치되도록 컨테이너 스타일은 부모(manage-bar)에 맡긴다. */
.toolbar { display: inline-flex; gap: 8px; align-items: center; }
button, .file-btn { display: inline-flex; align-items: center; height: 32px; padding: 0 12px; border: 1px solid #d1d5db; border-radius: 6px; background: white; cursor: pointer; font-size: 13px; box-sizing: border-box; }
button:hover, .file-btn:hover { background: #f9fafb; }
button:disabled { opacity: 0.5; cursor: not-allowed; }
.delete-btn { color: #b91c1c; border-color: #fecaca; }
.delete-btn:hover:not(:disabled) { background: #fef2f2; }
</style>
