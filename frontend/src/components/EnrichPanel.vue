<script setup lang="ts">
import { useOntologyStore } from '../stores/ontologyStore'
const store = useOntologyStore()

const RUNS = 5

function badge(agreement: number): { cls: string; text: string } {
  if (agreement >= 0.8) return { cls: 'badge-high', text: '확신' }
  if (agreement >= 0.5) return { cls: 'badge-mid', text: '보통' }
  return { cls: 'badge-low', text: '재확인' }
}

function pct(agreement: number): string {
  return Math.round(agreement * 100) + '%'
}
</script>

<template>
  <div class="enrich-panel">
    <div class="enrich-bar">
      <button class="enrich-run-btn" :disabled="store.enriching" @click="store.enrichSample()">
        {{ store.enriching ? 'AI 추정 중…' : '🧠 AI 의미 추정 (샘플)' }}
      </button>
      <button class="scored-run-btn" :disabled="store.enriching" @click="store.scoredEnrichSample(RUNS)">
        {{ store.enriching ? '평가 중…' : `📊 신뢰도 평가(${RUNS}회)` }}
      </button>
      <span class="enrich-hint">암호 같은 테이블 이름을 AI가 비즈니스 의미로 추정 → 승인 시 반영</span>
    </div>

    <ul v-if="store.scoredCandidates.length" class="scored-list">
      <li v-for="c in store.scoredCandidates" :key="c.targetIri" class="cand-row">
        <div class="cand-main">
          <span class="cand-cur">{{ c.currentName }}</span>
          <span class="arrow">→</span>
          <span class="cand-label">{{ c.consensusLabel }}</span>
          <span class="agree-badge" :class="badge(c.agreement).cls">
            {{ badge(c.agreement).text }} {{ pct(c.agreement) }}
          </span>
        </div>
        <div class="cand-desc">{{ c.description }}</div>
        <div class="variants">
          <span v-for="v in c.variants" :key="v.label" class="variant">{{ v.label }} ×{{ v.count }}</span>
        </div>
        <div class="cand-actions">
          <button class="approve-btn" @click="store.applyEnrichment(c.targetIri, c.consensusLabel)">승인</button>
          <button class="dismiss-btn" @click="store.dismissEnrichment(c.targetIri)">거부</button>
        </div>
      </li>
    </ul>

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
.scored-run-btn { padding: 6px 12px; background: #2563eb; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; }
.scored-run-btn:disabled { opacity: 0.6; cursor: default; }
.scored-list { list-style: none; margin: 10px 0 0; padding: 0; max-height: 320px; overflow: auto; }
.agree-badge { font-size: 11px; font-weight: 700; padding: 1px 8px; border-radius: 10px; margin-left: auto; }
.badge-high { background: #dcfce7; color: #166534; }
.badge-mid { background: #fef3c7; color: #92400e; }
.badge-low { background: #fee2e2; color: #991b1b; }
.variants { display: flex; flex-wrap: wrap; gap: 6px; margin: 2px 0 6px; }
.variant { font-size: 11px; color: #6b7280; background: #f1f5f9; border-radius: 4px; padding: 1px 6px; }
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
