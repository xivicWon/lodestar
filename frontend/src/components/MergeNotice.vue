<script setup lang="ts">
import { computed } from 'vue'
import { useOntologyStore } from '../stores/ontologyStore'

const store = useOntologyStore()

// 재임포트 병합 결과가 있고, 복원/미매칭 중 하나라도 있을 때만 표시.
const show = computed(() => {
  const m = store.lastMerge
  return !!m && (m.reapplied > 0 || m.stale > 0)
})
</script>

<template>
  <div v-if="show" class="merge-notice" role="status">
    확정 {{ store.lastMerge!.reapplied }}건 복원 · 미매칭 {{ store.lastMerge!.stale }}건
  </div>
</template>

<style scoped>
.merge-notice { padding: 6px 12px; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 6px; color: #065f46; font-size: 13px; margin: 0 12px 6px; }
</style>
