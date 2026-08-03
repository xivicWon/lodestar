<script setup lang="ts">
import { useOntologyStore } from '../stores/ontologyStore'
import { shortName } from '../lib/shortName'
const store = useOntologyStore()
</script>

<template>
  <span v-if="store.reasonResult" class="badge" :class="store.reasonResult.consistent ? 'ok' : 'bad'">
    <template v-if="store.reasonResult.consistent">🟢 일관성 OK</template>
    <template v-else>🔴 모순: {{ store.reasonResult.unsatisfiableClasses.map(shortName).join(', ') || '있음' }}</template>
  </span>
</template>

<style scoped>
.badge { padding: 4px 10px; border-radius: 12px; font-size: 13px; font-weight: 600; }
.ok { background: #dcfce7; color: #166534; }
.bad { background: #fee2e2; color: #991b1b; }
</style>
