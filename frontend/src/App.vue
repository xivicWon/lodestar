<script setup lang="ts">
import { onMounted, ref } from 'vue'
import Toolbar from './components/Toolbar.vue'
import ImportPanel from './components/ImportPanel.vue'
import EnrichPanel from './components/EnrichPanel.vue'
import RelationSuggestPanel from './components/RelationSuggestPanel.vue'
import ProjectPanel from './components/ProjectPanel.vue'
import ChatPanel from './components/ChatPanel.vue'
import TrashPanel from './components/TrashPanel.vue'
import ConsistencyBadge from './components/ConsistencyBadge.vue'
import ClassTree from './components/ClassTree.vue'
import ClassDetail from './components/ClassDetail.vue'
import ImpactPanel from './components/ImpactPanel.vue'
import RelationsView from './components/RelationsView.vue'
import MergeNotice from './components/MergeNotice.vue'
import { useOntologyStore } from './stores/ontologyStore'

const store = useOntologyStore()
const showImport = ref(false)
const showEnrich = ref(false)
const showRel = ref(false)
const showProject = ref(false)
const showChat = ref(false)
const showTrash = ref(false)
onMounted(() => { store.refresh() })

// 복원 파이프라인 5단계: 번호 → 이름 → 결과물. 왼쪽에서 오른쪽으로 흐른다.
const steps = [
  { key: 'import', no: '①', name: '가져오기', result: '테이블 → 클래스', color: '#0ea5e9',
    tip: '운영 DB(JDBC)·DDL 스크립트·샘플에서 스키마를 읽어 온톨로지 클래스로 만듭니다' },
  { key: 'enrich', no: '②', name: '의미 복원', result: '암호명 → 비즈니스 라벨', color: '#8b5cf6',
    tip: '암호 같은 테이블 이름을 AI가 업무 의미(라벨)로 추정합니다' },
  { key: 'rel', no: '③', name: '관계 복원', result: '숨은 관계 → 연결', color: '#0891b2',
    tip: 'FK가 없어도 컬럼 이름 패턴으로 숨은 관계를 찾고 AI로 진짜만 걸러 ObjectProperty를 만듭니다' },
  { key: 'reason', no: '④', name: '검증·추론', result: '일관성 · 자동분류', color: '#d97706',
    tip: 'HermiT 추론기로 일관성 검사와 자동 계층 분류를 실행합니다' },
  { key: 'chat', no: '⑤', name: '질문', result: '자연어 답변', color: '#059669',
    tip: '완성된 지식 그래프에 자연어로 질문합니다' },
] as const

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
            :class="{ active: isActive(s.key) }"
            :style="{ '--accent': s.color }"
            :data-tip="s.tip"
            :disabled="s.key === 'reason' && store.reasoning"
            @click="onStep(s.key)"
          >
            <span class="step-head"><span class="step-no">{{ s.no }}</span>{{ s.name }}</span>
            <span class="step-result">{{ resultText(s.key, s.result) }}</span>
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
      <section class="right">
        <div class="detail-pane"><ClassDetail /><ImpactPanel /></div>
        <div class="relations-pane"><RelationsView /></div>
      </section>
    </div>
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
.left { width: 320px; border-right: 1px solid #e5e7eb; min-height: 0; }
.right { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.detail-pane { flex: 0 0 auto; max-height: 40%; overflow: auto; border-bottom: 1px solid #e5e7eb; }
.relations-pane { flex: 1 1 auto; min-height: 0; }
.status-bar { padding: 6px 12px; }

/* 복원 파이프라인 바 */
.pipeline-bar { display: flex; align-items: center; gap: 12px; padding: 8px 12px; border-bottom: 1px solid #e5e7eb; background: #fafafa; flex-wrap: wrap; }
.pipeline-title { font-size: 11px; font-weight: 700; color: #9ca3af; letter-spacing: 0.02em; }
.steps { display: flex; align-items: stretch; gap: 6px; flex-wrap: wrap; }
.flow { display: flex; align-items: center; color: #cbd5e1; font-size: 16px; }
.step-chip {
  display: flex; flex-direction: column; align-items: flex-start; gap: 2px;
  min-width: 104px; padding: 6px 12px; border: 1px solid #e2e8f0; border-left: 3px solid var(--accent);
  border-radius: 8px; background: white; cursor: pointer; text-align: left; box-sizing: border-box;
}
.step-chip:hover { background: #f8fafc; }
.step-chip:disabled { cursor: default; opacity: 0.75; }
.step-chip.active { background: color-mix(in srgb, var(--accent) 10%, white); border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent) inset; }
.step-head { display: flex; align-items: center; gap: 5px; font-size: 13px; font-weight: 700; color: #1f2937; line-height: 1.2; }
.step-no { display: inline-flex; align-items: center; justify-content: center; width: 16px; height: 16px; font-size: 12px; color: var(--accent); font-weight: 800; }
.step-result { font-size: 11px; color: #94a3b8; line-height: 1.2; }

/* 관리 바 */
.manage-bar { display: flex; align-items: center; gap: 8px; padding: 6px 12px; border-bottom: 1px solid #e5e7eb; flex-wrap: wrap; }
.manage-title { font-size: 11px; font-weight: 700; color: #9ca3af; }
.manage-btn { display: inline-flex; align-items: center; height: 32px; padding: 0 12px; border: 1px solid #d1d5db; border-radius: 6px; background: white; cursor: pointer; font-size: 13px; box-sizing: border-box; }
.manage-btn:hover { background: #f9fafb; }
.error-banner { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; background: #fee2e2; border-bottom: 1px solid #fca5a5; color: #991b1b; font-size: 14px; }
.dismiss-error { background: none; border: none; cursor: pointer; font-size: 18px; color: #991b1b; padding: 0 4px; line-height: 1; }
</style>
