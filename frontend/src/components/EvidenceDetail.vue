<script setup lang="ts">
import { computed } from 'vue'
import type { RelationEvidence } from '../api/types'

const props = defineProps<{ evidence: RelationEvidence; viaColumn: string }>()

const isExact = computed(() => props.evidence.matchType === 'exact')

function colPreview(cols: string[]): string {
  const head = cols.slice(0, 8).join(', ')
  return cols.length > 8 ? `${head} … (+${cols.length - 8})` : head
}
function altLabel(t: string): string {
  return t === 'exact' ? '완전일치' : '부분일치'
}
</script>

<template>
  <div class="evi">
    <div class="evi-row">
      <span class="evi-k">매칭</span>
      <span>{{ isExact ? '완전일치' : '토큰 부분일치' }}</span>
      <div class="evi-sub mono">{{ viaColumn }} → 스템 "{{ evidence.matchStem }}" → 대상 "{{ evidence.matchedOn }}"</div>
      <div v-if="!isExact" class="evi-warn">⚠ 완전일치 아님 — 대상 이름 일부만 겹침</div>
    </div>

    <div class="evi-row">
      <span class="evi-k">조인컬럼</span>
      <span class="mono">{{ viaColumn }}</span>
      <span class="evi-dim"> · 타입 {{ evidence.viaType ?? '미상' }} · {{ evidence.viaFunctional ? '함수형' : '함수형 아님' }}</span>
      <div v-if="!evidence.targetHasSameColumn" class="evi-warn">
        ⚠ 대상에 '{{ viaColumn }}' 컬럼 없음
        <span v-if="evidence.targetSimilarKeys.length" class="mono"> · 유사키: {{ evidence.targetSimilarKeys.join(', ') }}</span>
      </div>
      <div v-else class="evi-ok">✓ 대상에 동일 컬럼 존재</div>
    </div>

    <div class="evi-row">
      <span class="evi-k">카디널리티</span>
      <span>{{ evidence.cardinality }}</span>
      <span class="evi-dim"> ({{ evidence.cardinalityReason }})</span>
    </div>

    <div v-if="evidence.alternatives.length" class="evi-row">
      <span class="evi-k">모호성</span>
      <span>이 컬럼 → {{ evidence.alternatives.length + 1 }}개 대상과 매칭</span>
      <ul class="evi-alts">
        <li v-for="a in evidence.alternatives" :key="a.toIri" :class="{ strong: a.matchType === 'exact' }">
          {{ a.toLabel }} <span class="evi-dim">({{ altLabel(a.matchType) }} {{ a.confidence.toFixed(2) }})</span>
          <span v-if="a.matchType === 'exact'" class="evi-hint"> ← 더 유력</span>
        </li>
      </ul>
    </div>

    <div class="evi-row">
      <span class="evi-k">소스컬럼({{ evidence.fromColumns.length }})</span>
      <span class="evi-cols mono">{{ colPreview(evidence.fromColumns) }}</span>
    </div>
    <div class="evi-row">
      <span class="evi-k">대상컬럼({{ evidence.toColumns.length }})</span>
      <span class="evi-cols mono">{{ colPreview(evidence.toColumns) }}</span>
    </div>
  </div>
</template>

<style scoped>
.evi { margin: 6px 0 8px; padding: 8px 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 12px; color: #334155; }
.evi-row { margin: 4px 0; line-height: 1.5; }
.evi-k { display: inline-block; min-width: 78px; font-weight: 700; color: #475569; }
.evi-sub { margin: 2px 0 0 78px; color: #64748b; }
.evi-dim { color: #94a3b8; }
.evi-warn { margin: 2px 0 0 78px; color: #b45309; }
.evi-ok { margin: 2px 0 0 78px; color: #15803d; }
.evi-cols { color: #475569; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px; }
.evi-alts { margin: 3px 0 0 78px; padding: 0; list-style: none; }
.evi-alts li { padding: 1px 0; }
.evi-alts li.strong { color: #1d4ed8; font-weight: 600; }
.evi-hint { color: #1d4ed8; font-weight: 600; }
</style>
