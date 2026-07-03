<script setup lang="ts">
import { useOntologyStore } from '../stores/ontologyStore'
const store = useOntologyStore()

function labelOf(iri: string): string {
  const c = store.classes.find(k => k.iri === iri)
  return c?.label ?? iri.split(/[#/]/).pop() ?? iri
}
</script>

<template>
  <div class="rel-panel">
    <div class="rel-bar">
      <button class="rel-run-btn" :disabled="store.suggesting" @click="store.suggestRelations()">
        {{ store.suggesting ? '발굴 중…' : '🔗 관계 발굴' }}
      </button>
      <button class="rel-judge-btn" :disabled="store.judging" @click="store.judgeRelations()">
        {{ store.judging ? '판정 중…' : '🧠 AI 판정' }}
      </button>
      <span class="rel-hint">FK 없는 컬럼 이름 패턴으로 클래스 간 숨은 관계를 찾아 제안 → 승인 시 ObjectProperty 생성</span>
    </div>

    <ul v-if="store.judgedRelations.length" class="cand-list judged-list">
      <li v-for="c in store.judgedRelations" :key="`j|${c.fromIri}|${c.toIri}|${c.viaColumn}`" class="cand-row">
        <div class="cand-main">
          <span class="judge-badge" :class="c.keep ? 'badge-keep' : 'badge-drop'">{{ c.keep ? '관계' : '제외' }}</span>
          <span class="cand-from">{{ labelOf(c.fromIri) }}</span>
          <span class="arrow">→</span>
          <span class="cand-to">{{ labelOf(c.toIri) }}</span>
          <span class="cand-via">via {{ c.viaColumn }}</span>
        </div>
        <div class="cand-reason">{{ c.reason }}</div>
        <div v-if="c.keep" class="cand-actions">
          <button class="approve-btn" @click="store.applyRelation(c.fromIri, c.toIri, c.suggestedName)">승인</button>
        </div>
      </li>
    </ul>

    <ul v-if="store.relCandidates.length" class="cand-list">
      <li v-for="(c, i) in store.relCandidates" :key="`${c.fromIri}|${c.toIri}|${c.viaColumn}`" class="cand-row">
        <div class="cand-main">
          <span class="cand-from">{{ labelOf(c.fromIri) }}</span>
          <span class="arrow">→</span>
          <span class="cand-to">{{ labelOf(c.toIri) }}</span>
          <span class="cand-via">via {{ c.viaColumn }}</span>
          <span class="cand-conf">{{ c.confidence.toFixed(2) }}</span>
        </div>
        <div class="cand-name">{{ c.suggestedName }}</div>
        <div class="cand-actions">
          <button class="approve-btn" @click="store.applyRelation(c.fromIri, c.toIri, c.suggestedName)">승인</button>
          <button class="dismiss-btn" @click="store.dismissRelation(i)">거부</button>
        </div>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.rel-panel { padding: 12px; border-bottom: 1px solid #e5e7eb; }
.rel-bar { display: flex; align-items: center; gap: 8px; }
.rel-run-btn { padding: 6px 12px; background: #0ea5e9; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; }
.rel-run-btn:disabled { opacity: 0.6; cursor: default; }
.rel-judge-btn { padding: 6px 12px; background: #8b5cf6; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; }
.rel-judge-btn:disabled { opacity: 0.6; cursor: default; }
.judged-list { margin-top: 10px; }
.judge-badge { font-size: 11px; padding: 1px 8px; border-radius: 10px; font-weight: 700; }
.badge-keep { background: #dcfce7; color: #166534; }
.badge-drop { background: #f3f4f6; color: #6b7280; }
.cand-reason { font-size: 12px; color: #4b5563; margin: 2px 0 6px; }
.rel-hint { font-size: 12px; color: #6b7280; }
.cand-list { list-style: none; margin: 10px 0 0; padding: 0; max-height: 260px; overflow: auto; }
.cand-row { padding: 8px; border-bottom: 1px solid #f1f5f9; }
.cand-main { display: flex; gap: 8px; align-items: baseline; font-size: 13px; }
.cand-from { font-weight: 700; }
.arrow { color: #9ca3af; }
.cand-to { font-weight: 700; }
.cand-via { color: #6b7280; font-family: monospace; font-size: 12px; }
.cand-conf { color: #0ea5e9; font-size: 12px; margin-left: auto; }
.cand-name { font-size: 12px; color: #6b7280; margin: 2px 0 6px; font-family: monospace; }
.cand-actions { display: flex; gap: 6px; }
.approve-btn { padding: 3px 12px; background: #059669; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 12px; }
.dismiss-btn { padding: 3px 12px; background: white; color: #6b7280; border: 1px solid #d1d5db; border-radius: 5px; cursor: pointer; font-size: 12px; }
</style>
