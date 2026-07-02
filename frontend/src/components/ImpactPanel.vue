<script setup lang="ts">
import { useOntologyStore } from '../stores/ontologyStore'
const store = useOntologyStore()

function shortName(iri: string): string {
  const c = store.classes.find(k => k.iri === iri)
  return c?.label ?? iri.split(/[#/]/).pop() ?? iri
}

function analyze() {
  if (store.selectedIri) store.fetchImpact(store.selectedIri)
}
</script>

<template>
  <div class="impact-panel">
    <div class="impact-bar">
      <button class="impact-run-btn" :disabled="!store.selectedIri" @click="analyze">영향 분석</button>
      <span class="impact-hint">선택한 클래스가 의존하는(하류)·클래스를 참조하는(상류) 클래스를 계산</span>
    </div>

    <div v-if="store.impact" class="impact-result">
      <h4 class="impact-iri">{{ shortName(store.impact.iri) }}</h4>

      <section class="impact-section">
        <div class="impact-label">상류 (upstream)</div>
        <p v-if="!store.impact.upstream.length" class="impact-empty">없음</p>
        <ul v-else class="impact-list upstream-list">
          <li v-for="u in store.impact.upstream" :key="u" class="impact-item"
              @click="store.select(u)">{{ shortName(u) }}</li>
        </ul>
      </section>

      <section class="impact-section">
        <div class="impact-label">하류 (downstream)</div>
        <p v-if="!store.impact.downstream.length" class="impact-empty">없음</p>
        <ul v-else class="impact-list downstream-list">
          <li v-for="d in store.impact.downstream" :key="d" class="impact-item"
              @click="store.select(d)">{{ shortName(d) }}</li>
        </ul>
      </section>
    </div>
  </div>
</template>

<style scoped>
.impact-panel { padding: 12px 16px; border-top: 1px solid #e5e7eb; }
.impact-bar { display: flex; align-items: center; gap: 8px; }
.impact-run-btn { padding: 6px 12px; background: #7c3aed; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; }
.impact-run-btn:disabled { opacity: 0.5; cursor: default; }
.impact-hint { font-size: 12px; color: #6b7280; }
.impact-result { margin-top: 10px; }
.impact-iri { margin: 0 0 8px; font-size: 14px; }
.impact-section { margin-bottom: 10px; }
.impact-label { font-size: 12px; font-weight: 700; color: #6b7280; margin-bottom: 4px; }
.impact-empty { font-size: 13px; color: #9ca3af; margin: 0; }
.impact-list { list-style: none; margin: 0; padding: 0; }
.impact-item { padding: 4px 8px; border-radius: 5px; cursor: pointer; font-size: 13px; }
.impact-item:hover { background: #f3f4f6; }
</style>
