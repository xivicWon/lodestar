<script setup lang="ts">
import { computed } from 'vue'
import { useOntologyStore } from '../stores/ontologyStore'
import type { CollectionIssue } from '../api/types'

const store = useOntologyStore()

const report = computed(() => store.lastCollection)

// 보고할 것이 없으면 띄우지 않는다 — 항상 뜨는 알림은 신호이기를 그친다.
const show = computed(() => {
  const r = report.value
  return !!r && (r.issues.length > 0 || r.partials.length > 0)
})

/** 실패·부분수집이 하나라도 있으면 완전 성공으로 표시하지 않는다(#88 조용한 skip). */
const partial = computed(() => !!report.value && !report.value.complete)

const headline = computed(() => (partial.value ? '부분 수집' : '완전 수집'))

const counts = computed(() => {
  const r = report.value!
  const parts = [`수집 ${r.collected}건`]
  if (r.skipped > 0) parts.push(`제외 ${r.skipped}건`)
  if (r.failed > 0) parts.push(`실패 ${r.failed}건`)
  return parts.join(' · ')
})

// 사유별 요약 — '고칠 것'(PARSE_ERROR)과 '지원 범위'(UNSUPPORTED_*)를 한눈에 가른다.
const byReason = computed(() => {
  const by = new Map<string, number>()
  for (const i of report.value!.issues) by.set(i.reasonCode, (by.get(i.reasonCode) ?? 0) + 1)
  return [...by.entries()].map(([reasonCode, count]) => ({ reasonCode, count }))
})

// 항목은 **자기 완결적**이다 — 사유코드 없이 좌표만 있는 줄은 그것만 떼어 보면 무엇인지 알 수 없다.
const issues = computed<CollectionIssue[]>(() =>
  [...report.value!.issues].sort((a, b) =>
    a.reasonCode.localeCompare(b.reasonCode) || a.locator.localeCompare(b.locator)))
</script>

<template>
  <div v-if="show" class="collection-notice" :class="{ partial }" :role="partial ? 'alert' : 'status'">
    <div class="head">
      <strong>{{ headline }}</strong> — {{ counts }}
    </div>

    <!-- 부분수집은 성공 표시와 함께 '부분임' 을 명시한다 -->
    <div v-for="(p, pi) in report!.partials" :key="'p' + pi" class="partial-line" data-test="partial">
      부분수집 · {{ p.reasonCode }} — {{ p.reason }}
      <span class="loc">{{ p.locator }}</span>
    </div>

    <div v-if="byReason.length" class="group-head">
      사유별: <span v-for="(g, gi) in byReason" :key="g.reasonCode">
        <template v-if="gi > 0"> · </template>{{ g.reasonCode }} {{ g.count }}건</span>
    </div>

    <ul>
      <li v-for="(i, ii) in issues" :key="ii" data-test="issue">
        <span class="kind" :class="i.kind.toLowerCase()">{{ i.kind }}</span>
        <span class="code">{{ i.reasonCode }}</span>
        <code class="loc">{{ i.locator }}</code>
        <code class="target">{{ i.target }}</code>
        <span class="reason">{{ i.reason }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.collection-notice { padding: 8px 12px; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; color: #1e3a8a; font-size: 13px; margin: 0 12px 6px; }
.collection-notice.partial { background: #fffbeb; border-color: #fcd34d; color: #78350f; }
.head { margin-bottom: 4px; }
.partial-line { margin: 2px 0 6px; font-weight: 600; }
.group-head { font-size: 12px; opacity: .85; }
ul { margin: 4px 0 0; padding-left: 16px; }
li { margin: 1px 0; display: flex; gap: 6px; flex-wrap: wrap; align-items: baseline; }
.kind { font-size: 11px; padding: 0 4px; border-radius: 3px; background: #e5e7eb; color: #374151; }
.kind.failed { background: #fecaca; color: #7f1d1d; }
.code { font-size: 11px; padding: 0 4px; border-radius: 3px; background: #e0e7ff; color: #3730a3; }
.kind.partial { background: #fde68a; color: #78350f; }
.loc { font-size: 12px; opacity: .9; }
.target { font-size: 12px; }
.reason { opacity: .9; }
</style>
