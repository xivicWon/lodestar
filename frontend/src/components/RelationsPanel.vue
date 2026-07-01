<script setup lang="ts">
import { computed } from 'vue'
import { useOntologyStore } from '../stores/ontologyStore'

const store = useOntologyStore()

function short(iri: string | null): string {
  if (!iri) return '—'
  const hash = iri.split('#').pop() ?? iri
  return hash.split('/').pop() ?? hash
}

const rows = computed(() => store.objectProperties.map(p => ({
  iri: p.iri,
  label: p.label ?? short(p.iri),
  domain: p.domains.map(short).join(', ') || '?',
  range: p.ranges.map(short).join(', ') || '?',
  related: !!store.selectedIri &&
    (p.domains.includes(store.selectedIri) || p.ranges.includes(store.selectedIri)),
})))

const sorted = computed(() => [...rows.value].sort((a, b) => Number(b.related) - Number(a.related)))
</script>

<template>
  <div class="relations-panel">
    <h3>관계 (테이블 간)</h3>
    <p v-if="rows.length === 0" class="empty">관계가 없습니다.</p>
    <ul v-else class="relation-list">
      <li v-for="r in sorted" :key="r.iri" class="relation-row" :class="{ related: r.related }">
        <span class="dom">{{ r.domain }}</span>
        <span class="arrow">→</span>
        <span class="rng">{{ r.range }}</span>
        <span class="lbl">{{ r.label }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.relations-panel { padding: 16px; overflow: auto; height: 100%; }
h3 { margin: 0 0 12px; font-size: 14px; }
.empty { color: #6b7280; }
.relation-list { list-style: none; margin: 0; padding: 0; }
.relation-row { display: flex; gap: 8px; align-items: baseline; padding: 6px 8px; border-bottom: 1px solid #f1f5f9; font-size: 13px; }
.relation-row.related { background: #eef2ff; }
.dom, .rng { font-weight: 600; }
.arrow { color: #6b7280; }
.lbl { color: #6b7280; margin-left: auto; }
</style>
