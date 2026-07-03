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
</script>

<template>
  <div class="layout">
    <Toolbar />
    <div class="import-toggle-bar">
      <button class="toggle-btn toggle-import-btn" title="운영 DB(JDBC)·DDL 스크립트·샘플에서 스키마를 읽어 온톨로지로 가져옵니다" @click="showImport = !showImport">
        {{ showImport ? 'RDB 가져오기 닫기' : 'RDB 가져오기' }}
      </button>
      <button class="toggle-btn toggle-enrich-btn" title="암호 같은 테이블 이름을 AI가 비즈니스 의미(라벨)로 추정합니다" @click="showEnrich = !showEnrich">
        {{ showEnrich ? 'AI 의미 추정 닫기' : 'AI 의미 추정' }}
      </button>
      <button class="toggle-btn toggle-rel-btn" title="FK가 없어도 컬럼 이름 패턴으로 숨은 관계를 찾고, AI로 진짜 관계만 걸러냅니다" @click="showRel = !showRel">
        {{ showRel ? '관계 발굴 닫기' : '관계 발굴' }}
      </button>
      <button class="toggle-btn toggle-project-btn" title="현재 온톨로지를 프로젝트로 저장하거나 불러옵니다" @click="showProject = !showProject">
        {{ showProject ? '프로젝트 닫기' : '프로젝트' }}
      </button>
      <button class="toggle-btn toggle-chat-btn" title="온톨로지를 근거로 자연어 질문에 답합니다" @click="showChat = !showChat">
        {{ showChat ? 'AI 챗 닫기' : 'AI 챗' }}
      </button>
      <button class="toggle-btn toggle-trash-btn" title="삭제한 클래스(테이블)를 보관·복구·완전삭제합니다. 삭제는 온톨로지에서만 일어나며 실 DB는 불변입니다" @click="showTrash = !showTrash">
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
</style>

<style scoped>
.layout { display: flex; flex-direction: column; height: 100vh; }
.panes { display: flex; flex: 1; min-height: 0; }
.left { width: 320px; border-right: 1px solid #e5e7eb; min-height: 0; }
.right { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.detail-pane { flex: 0 0 auto; max-height: 40%; overflow: auto; border-bottom: 1px solid #e5e7eb; }
.relations-pane { flex: 1 1 auto; min-height: 0; }
.status-bar { padding: 6px 12px; }
.import-toggle-bar { padding: 6px 12px; }
.import-toggle-bar { display: flex; flex-wrap: wrap; gap: 6px; }
.toggle-btn { display: inline-flex; align-items: center; justify-content: center; height: 32px; padding: 0 14px; border: 1px solid #d1d5db; border-radius: 6px; background: white; cursor: pointer; font-size: 14px; line-height: 1; box-sizing: border-box; }
.toggle-btn:hover { background: #f9fafb; }
.error-banner { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; background: #fee2e2; border-bottom: 1px solid #fca5a5; color: #991b1b; font-size: 14px; }
.dismiss-error { background: none; border: none; cursor: pointer; font-size: 18px; color: #991b1b; padding: 0 4px; line-height: 1; }
</style>
