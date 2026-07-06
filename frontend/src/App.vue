<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import Toolbar from './components/Toolbar.vue'
import ImportPanel from './components/ImportPanel.vue'
import EnrichPanel from './components/EnrichPanel.vue'
import RelationSuggestPanel from './components/RelationSuggestPanel.vue'
import ProjectPanel from './components/ProjectPanel.vue'
import ChatPanel from './components/ChatPanel.vue'
import TrashPanel from './components/TrashPanel.vue'
import ConsistencyBadge from './components/ConsistencyBadge.vue'
import ClassTree from './components/ClassTree.vue'
import RelationsView from './components/RelationsView.vue'
import NodeSidePanel from './components/NodeSidePanel.vue'
import RelationLinkModal from './components/RelationLinkModal.vue'
import AlignmentModal from './components/AlignmentModal.vue'
import MergeNotice from './components/MergeNotice.vue'
import { useOntologyStore } from './stores/ontologyStore'

const store = useOntologyStore()
const showImport = ref(false)
const showEnrich = ref(false)
const showRel = ref(false)
const showProject = ref(false)
const showChat = ref(false)
const showTrash = ref(false)
// 관계 연동 레이어 팝업 / floating side panel 상태
const showLink = ref(false)
const showAlign = ref(false)
const panelDismissed = ref(false)
// 노드를 클릭(선택)하면 side panel 을 다시 연다. ×/Esc 로 닫아도 선택은 유지.
watch(() => store.selectedIri, () => { panelDismissed.value = false })
onMounted(() => {
  store.refresh()
  store.fetchConfirmations().catch(() => {})
  store.fetchAlignments().catch(() => {})
})

// 복원 파이프라인 5단계: 번호 → 이름 → 결과물. 왼쪽에서 오른쪽으로 흐른다.
const steps = [
  { key: 'import', no: '1', name: '가져오기', result: '테이블 → 클래스', color: '#0ea5e9',
    tip: '① 가져오기 — 운영 DB(JDBC)·DDL 스크립트·샘플에서 스키마를 읽어 온톨로지 클래스로 만듭니다 (테이블 → 클래스)' },
  { key: 'enrich', no: '2', name: '의미 복원', result: '암호명 → 라벨', color: '#8b5cf6',
    tip: '② 의미 복원 — 암호 같은 테이블 이름을 AI가 업무 의미로 추정해 라벨을 답니다 (암호명 → 비즈니스 라벨)' },
  { key: 'rel', no: '3', name: '관계 복원', result: '숨은 관계 → 연결', color: '#0891b2',
    tip: '③ 관계 복원 — FK가 없어도 컬럼 이름 패턴으로 숨은 관계를 찾고 AI로 진짜만 걸러 ObjectProperty를 만듭니다 (관계 → 연결)' },
  { key: 'reason', no: '4', name: '검증·추론', result: '일관성 · 분류', color: '#d97706',
    tip: '④ 검증·추론 — HermiT 추론기로 일관성 검사와 자동 계층 분류를 실행합니다 (일관성 · 자동분류)' },
  { key: 'chat', no: '5', name: '질문', result: '자연어 답변', color: '#059669',
    tip: '⑤ 질문 — 완성된 지식 그래프에 자연어로 질문합니다 (자연어 답변)' },
] as const

// 각 단계 진행 상태: done(완료) / progress(진행 중) / warn(주의) / idle(대기).
type StepStatus = { state: 'done' | 'progress' | 'warn' | 'idle'; label?: string }
function stepStatus(key: string): StepStatus {
  if (key === 'import') {
    const n = store.classes.length
    return n > 0 ? { state: 'done', label: `${n}개` } : { state: 'idle' }
  }
  if (key === 'enrich') {
    if (store.enriching) return { state: 'progress', label: '추정 중' }
    const c = store.confirmations.filter(x => x.kind === 'class').length
    if (c > 0) return { state: 'done', label: `${c}개 확정` }
    return store.enrichCandidates.length ? { state: 'progress', label: '검토 중' } : { state: 'idle' }
  }
  if (key === 'rel') {
    if (store.suggesting || store.judging) return { state: 'progress', label: '발굴 중' }
    const n = store.objectProperties.length
    if (n > 0) return { state: 'done', label: `${n}개` }
    return (store.relCandidates.length || store.judgedRelations.length)
      ? { state: 'progress', label: '검토 중' } : { state: 'idle' }
  }
  if (key === 'reason') {
    if (store.reasoning) return { state: 'progress', label: '추론 중' }
    if (store.reasonResult) {
      return store.reasonResult.consistent
        ? { state: 'done', label: '일관성 OK' } : { state: 'warn', label: '비일관' }
    }
    return { state: 'idle' }
  }
  return { state: 'idle' } // chat: 활용 단계 (완료 개념 없음)
}
const statusIcon: Record<string, string> = { done: '✓', warn: '⚠', progress: '●', idle: '' }

function onStep(key: string) {
  if (key === 'import') showImport.value = !showImport.value
  else if (key === 'enrich') showEnrich.value = !showEnrich.value
  else if (key === 'rel') showRel.value = !showRel.value
  else if (key === 'chat') showChat.value = !showChat.value
  else if (key === 'reason') store.runReasoner()
}

function isActive(key: string): boolean {
  if (key === 'import') return showImport.value
  if (key === 'enrich') return showEnrich.value
  if (key === 'rel') return showRel.value
  if (key === 'chat') return showChat.value
  if (key === 'reason') return store.reasoning
  return false
}

function resultText(key: string, result: string): string {
  return key === 'reason' && store.reasoning ? '추론 중…' : result
}
</script>

<template>
  <div class="layout">
    <!-- 복원 파이프라인: 번호 → 흐름(→) → 결과 캡션 -->
    <div class="pipeline-bar">
      <span class="pipeline-title">복원 파이프라인</span>
      <div class="steps">
        <template v-for="(s, i) in steps" :key="s.key">
          <span v-if="i > 0" class="flow" aria-hidden="true">→</span>
          <button
            class="step-chip"
            :class="[{ active: isActive(s.key) }, `st-${stepStatus(s.key).state}`]"
            :style="{ '--accent': s.color }"
            :data-tip="s.tip"
            :disabled="s.key === 'reason' && store.reasoning"
            @click="onStep(s.key)"
          >
            <span class="step-head">
              <span class="step-no">{{ s.no }}</span>
              <span class="step-name">{{ s.name }}</span>
              <span v-if="stepStatus(s.key).state !== 'idle'" class="step-status" :class="`badge-${stepStatus(s.key).state}`">
                {{ statusIcon[stepStatus(s.key).state] }}
              </span>
            </span>
            <span class="step-result">
              {{ resultText(s.key, s.result) }}<span v-if="stepStatus(s.key).label" class="step-count"> · {{ stepStatus(s.key).label }}</span>
            </span>
          </button>
        </template>
      </div>
    </div>

    <!-- 관리 도구: 저장·입출력·편집 (파이프라인 단계 아님) -->
    <div class="manage-bar">
      <span class="manage-title">관리</span>
      <button class="manage-btn" data-tip="현재 온톨로지를 프로젝트(세이브포인트)로 저장하거나 불러옵니다" @click="showProject = !showProject">
        {{ showProject ? '프로젝트 닫기' : '프로젝트 저장·열기' }}
      </button>
      <Toolbar />
      <button class="manage-btn" data-tip="삭제한 클래스(테이블)를 보관·복구·완전삭제합니다. 삭제는 온톨로지에서만 일어나며 실 DB는 불변입니다" data-tip-align="right" @click="showTrash = !showTrash">
        {{ showTrash ? '🗑 휴지통 닫기' : '🗑 휴지통' }}
      </button>
    </div>
    <MergeNotice />
    <ImportPanel v-if="showImport" />
    <EnrichPanel v-if="showEnrich" />
    <RelationSuggestPanel v-if="showRel" />
    <ProjectPanel v-if="showProject" />
    <ChatPanel v-if="showChat" />
    <TrashPanel v-if="showTrash" />
    <div class="status-bar"><ConsistencyBadge /></div>
    <div v-if="store.error" class="error-banner" role="alert">
      <span>{{ store.error }}</span>
      <button class="dismiss-error" @click="store.clearError()">×</button>
    </div>
    <div class="panes">
      <aside class="left"><ClassTree /></aside>
      <!-- 그래프가 기본 화면. side panel 은 그래프를 밀지 않고 위에 floating 으로 뜬다. -->
      <section class="right">
        <RelationsView />
        <button class="link-cta" data-tip="소스·타깃 클래스를 선택해 관계를 만듭니다 (레이어 팝업)" @click="showLink = true">
          ＋ 관계 연동
        </button>
        <Transition name="slide">
          <NodeSidePanel
            v-if="store.selectedIri && !panelDismissed"
            @close="panelDismissed = true"
            @add-relation="showLink = true"
            @add-alignment="showAlign = true"
          />
        </Transition>
      </section>
    </div>

    <RelationLinkModal v-if="showLink" @close="showLink = false" />
    <AlignmentModal v-if="showAlign" @close="showAlign = false" />
  </div>
</template>

<style>
* { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }

/* 즉시 뜨는 커스텀 툴팁 (native title의 지연 제거) — 전역 적용 */
[data-tip] { position: relative; }
[data-tip]:hover::after {
  content: attr(data-tip);
  position: absolute; top: 100%; left: 0; margin-top: 6px;
  background: #111827; color: #fff; font-size: 12px; line-height: 1.35;
  padding: 6px 9px; border-radius: 6px;
  white-space: normal; width: max-content; max-width: 300px;
  z-index: 100; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25); pointer-events: none;
}
[data-tip-align="right"]:hover::after { left: auto; right: 0; }
</style>

<style scoped>
.layout { display: flex; flex-direction: column; height: 100vh; }
.panes { display: flex; flex: 1; min-height: 0; }
.left { width: 400px; border-right: 1px solid #e5e7eb; min-height: 0; }
/* 우측 = 그래프 단일 메인. position: relative 로 floating side panel·CTA 의 기준이 된다. */
.right { flex: 1; min-height: 0; position: relative; }
.link-cta {
  position: absolute; bottom: 16px; left: 16px; z-index: 3;
  display: inline-flex; align-items: center; gap: 7px;
  padding: 8px 14px; border: none; border-radius: 9px;
  background: #4f46e5; color: #fff; font-size: 12.5px; font-weight: 700; cursor: pointer;
  box-shadow: 0 1px 2px rgba(15, 23, 41, 0.08), 0 6px 18px rgba(79, 70, 229, 0.25);
}
.link-cta:hover { background: #4338ca; }
/* side panel 슬라이드 인/아웃 (그래프는 그대로) */
.slide-enter-active, .slide-leave-active { transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.22s ease; }
.slide-enter-from, .slide-leave-to { transform: translateX(calc(100% + 24px)); opacity: 0; }
@media (prefers-reduced-motion: reduce) {
  .slide-enter-active, .slide-leave-active { transition: none; }
}
.status-bar { padding: 6px 12px; }

/* 복원 파이프라인 바 */
.pipeline-bar { display: flex; align-items: center; gap: 12px; padding: 8px 12px; border-bottom: 1px solid #e5e7eb; background: #fafafa; flex-wrap: wrap; }
.pipeline-title { font-size: 11px; font-weight: 700; color: #9ca3af; letter-spacing: 0.02em; }
.steps { display: flex; align-items: stretch; gap: 4px; flex-wrap: wrap; }
.flow { display: flex; align-items: center; color: #cbd5e1; font-size: 15px; }
.step-chip {
  display: flex; flex-direction: column; align-items: stretch; gap: 3px;
  width: 158px; padding: 7px 11px; border: 1px solid #e2e8f0;
  border-radius: 8px; background: white; cursor: pointer; text-align: left; box-sizing: border-box;
  transition: background 0.12s, border-color 0.12s, box-shadow 0.12s;
}
.step-chip:hover { background: #f8fafc; border-color: #cbd5e1; }
.step-chip:disabled { cursor: default; }
/* 완료 단계는 은은한 강조(accent 틴트 + 좌측 바) */
.step-chip.st-done { background: color-mix(in srgb, var(--accent) 6%, white); border-color: color-mix(in srgb, var(--accent) 35%, #e2e8f0); }
.step-chip.st-warn { background: #fef2f2; border-color: #fecaca; }
/* 현재 열려있는(활성) 단계는 accent 링으로 강조 */
.step-chip.active { border-color: var(--accent); box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 30%, transparent); }

.step-head { display: flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 700; color: #1f2937; line-height: 1.25; }
.step-no {
  display: inline-flex; align-items: center; justify-content: center;
  width: 18px; height: 18px; flex: 0 0 18px; border-radius: 50%;
  background: var(--accent); color: white; font-size: 11px; font-weight: 800;
}
.step-name { flex: 1 1 auto; }
.step-status { flex: 0 0 auto; font-size: 12px; line-height: 1; }
.badge-done { color: #16a34a; }
.badge-warn { color: #dc2626; }
.badge-progress { color: var(--accent); animation: pulse 1s ease-in-out infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }
.step-result { font-size: 11px; color: #94a3b8; line-height: 1.2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.step-count { color: color-mix(in srgb, var(--accent) 70%, #64748b); font-weight: 600; }

/* 관리 바 */
.manage-bar { display: flex; align-items: center; gap: 8px; padding: 6px 12px; border-bottom: 1px solid #e5e7eb; flex-wrap: wrap; }
.manage-title { font-size: 11px; font-weight: 700; color: #9ca3af; }
.manage-btn { display: inline-flex; align-items: center; height: 32px; padding: 0 12px; border: 1px solid #d1d5db; border-radius: 6px; background: white; cursor: pointer; font-size: 13px; box-sizing: border-box; }
.manage-btn:hover { background: #f9fafb; }
.error-banner { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; background: #fee2e2; border-bottom: 1px solid #fca5a5; color: #991b1b; font-size: 14px; }
.dismiss-error { background: none; border: none; cursor: pointer; font-size: 18px; color: #991b1b; padding: 0 4px; line-height: 1; }
</style>
