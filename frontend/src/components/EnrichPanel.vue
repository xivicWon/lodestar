<script setup lang="ts">
import { useOntologyStore } from '../stores/ontologyStore'
const store = useOntologyStore()
</script>

<template>
  <div class="enrich-panel">
    <div class="enrich-bar">
      <button class="enrich-run-btn" :disabled="store.enriching" @click="store.enrichSample()">
        {{ store.enriching ? 'AI 추정 중…' : '🧠 AI 의미 추정 (샘플)' }}
      </button>
      <span class="enrich-hint">암호 같은 테이블 이름을 AI가 비즈니스 의미로 추정 → 승인 시 반영</span>
    </div>

    <ul v-if="store.enrichCandidates.length" class="cand-list">
      <li v-for="c in store.enrichCandidates" :key="c.targetIri" class="cand-row">
        <div class="cand-main">
          <span class="cand-cur">{{ c.currentName }}</span>
          <span class="arrow">→</span>
          <span class="cand-label">{{ c.suggestedLabel }}</span>
        </div>
        <div class="cand-desc">{{ c.description }}</div>
        <div class="cand-actions">
          <button class="approve-btn" @click="store.applyEnrichment(c.targetIri, c.suggestedLabel)">승인</button>
          <button class="dismiss-btn" @click="store.dismissEnrichment(c.targetIri)">거부</button>
        </div>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.enrich-panel { padding: 12px; border-bottom: 1px solid #e5e7eb; }
.enrich-bar { display: flex; align-items: center; gap: 8px; }
.enrich-run-btn { padding: 6px 12px; background: #7c3aed; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; }
.enrich-run-btn:disabled { opacity: 0.6; cursor: default; }
.enrich-hint { font-size: 12px; color: #6b7280; }
.cand-list { list-style: none; margin: 10px 0 0; padding: 0; max-height: 260px; overflow: auto; }
.cand-row { padding: 8px; border-bottom: 1px solid #f1f5f9; }
.cand-main { display: flex; gap: 8px; align-items: baseline; font-size: 13px; }
.cand-cur { color: #6b7280; font-family: monospace; }
.arrow { color: #9ca3af; }
.cand-label { font-weight: 700; }
.cand-desc { font-size: 12px; color: #6b7280; margin: 2px 0 6px; }
.cand-actions { display: flex; gap: 6px; }
.approve-btn { padding: 3px 12px; background: #059669; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 12px; }
.dismiss-btn { padding: 3px 12px; background: white; color: #6b7280; border: 1px solid #d1d5db; border-radius: 5px; cursor: pointer; font-size: 12px; }
</style>
