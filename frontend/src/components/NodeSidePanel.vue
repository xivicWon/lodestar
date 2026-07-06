<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useOntologyStore } from '../stores/ontologyStore'
import { shortName } from '../lib/shortName'
import ImpactPanel from './ImpactPanel.vue'

const RDFS_COMMENT = 'http://www.w3.org/2000/01/rdf-schema#comment'
const store = useOntologyStore()
const emit = defineEmits<{ (e: 'close'): void; (e: 'add-relation'): void; (e: 'add-alignment'): void }>()

const label = ref('')
const superClassesText = ref('')

watch(() => store.selected, (c) => {
  label.value = c?.label ?? ''
  superClassesText.value = (c?.superClasses ?? []).join(', ')
}, { immediate: true })

const sel = computed(() => store.selected)
const origName = computed(() => (sel.value ? shortName(sel.value.iri) : ''))
const showOrig = computed(() => !!sel.value?.label && sel.value.label !== origName.value)
const comment = computed(() => sel.value?.annotations.find(a => a.property === RDFS_COMMENT)?.value ?? '')
const confirmed = computed(() => !!store.selectedIri && store.confirmations.some(c => c.iri === store.selectedIri))

function classLabel(iri: string): string {
  return store.classes.find(c => c.iri === iri)?.label ?? shortName(iri)
}
function classOrig(iri: string): string { return shortName(iri) }

// 연결된 데이터 맵핑: 선택 클래스가 domain(나가는)·range(들어오는)인 관계.
const outgoing = computed(() => {
  const iri = store.selectedIri
  if (!iri) return []
  return store.objectProperties
    .filter(p => p.domains[0] === iri && p.ranges[0])
    .map(p => ({ iri: p.iri, rel: p.label ?? shortName(p.iri), other: p.ranges[0] }))
})
const incoming = computed(() => {
  const iri = store.selectedIri
  if (!iri) return []
  return store.objectProperties
    .filter(p => p.ranges[0] === iri && p.domains[0])
    .map(p => ({ iri: p.iri, rel: p.label ?? shortName(p.iri), other: p.domains[0] }))
})
const mappingCount = computed(() => outgoing.value.length + incoming.value.length)

const SKOS_LABEL: Record<string, string> = { EXACT: 'exactMatch', CLOSE: 'closeMatch', BROAD: 'broadMatch', NARROW: 'narrowMatch', RELATED: 'relatedMatch' }
const myAlignments = computed(() => (store.selectedIri ? store.alignmentsOf(store.selectedIri) : []))
function refLabel(iri: string): string {
  return store.referenceClasses.find(c => c.iri === iri)?.label ?? shortName(iri)
}

function save() {
  const c = sel.value
  if (!c) return
  const superClasses = superClassesText.value.split(',').map(s => s.trim()).filter(Boolean)
  store.saveClass(c.iri, { label: label.value, superClasses })
}
</script>

<template>
  <aside v-if="sel" class="side-panel">
    <div class="sp-head">
      <div class="sp-title">
        <div class="sp-label">{{ sel.label ?? origName }}</div>
        <div v-if="showOrig" class="sp-orig"><span class="k">원본 테이블</span>{{ origName }}</div>
      </div>
      <button class="sp-close" aria-label="닫기" @click="emit('close')">×</button>
    </div>

    <div class="sp-body">
      <div class="sec-title">노드 정보</div>
      <dl class="kv">
        <dt>원본 테이블</dt><dd class="mono">{{ origName }}</dd>
        <dt>IRI</dt><dd class="mono">{{ sel.iri }}</dd>
        <dt>상위 클래스</dt><dd>{{ sel.superClasses.map(classOrig).join(', ') || '—' }}</dd>
        <dt>확정 상태</dt>
        <dd><span class="chip" :class="confirmed ? 'ok' : 'idle'">{{ confirmed ? '의미 복원 확정 ✓' : '미확정' }}</span></dd>
      </dl>
      <p v-if="comment" class="comment">{{ comment }}</p>

      <div class="sec-title">라벨 편집</div>
      <label class="fl">라벨</label>
      <input class="fin label-input" v-model="label" />
      <label class="fl">상위 클래스 (IRI, 쉼표 구분)</label>
      <input class="fin superclasses-input" v-model="superClassesText" />
      <button class="save-btn" @click="save">저장</button>

      <div class="sec-title">연결된 데이터 맵핑 · {{ mappingCount }}</div>
      <p v-if="mappingCount === 0" class="empty">연결된 관계가 없습니다.</p>
      <div v-else class="maps">
        <div v-for="m in outgoing" :key="'out-' + m.iri" class="map">
          <span class="dir out">나감</span>
          <span class="rel">{{ m.rel }}</span>
          <span class="arrow">→</span>
          <span class="other">{{ classLabel(m.other) }}<span class="other-orig">{{ classOrig(m.other) }}</span></span>
        </div>
        <div v-for="m in incoming" :key="'in-' + m.iri" class="map">
          <span class="dir in">들어옴</span>
          <span class="other">{{ classLabel(m.other) }}<span class="other-orig">{{ classOrig(m.other) }}</span></span>
          <span class="arrow">→</span>
          <span class="rel">{{ m.rel }}</span>
        </div>
      </div>

      <div class="sec-title">온톨로지 정렬 · {{ myAlignments.length }}</div>
      <p v-if="myAlignments.length === 0" class="empty">정렬된 참조 클래스가 없습니다.</p>
      <div v-else class="alignments">
        <div v-for="a in myAlignments" :key="a.targetIri + a.matchType" class="alignment">
          <span class="al-match" :class="'m-' + a.matchType.toLowerCase()">{{ SKOS_LABEL[a.matchType] }}</span>
          <span class="al-target">→ {{ refLabel(a.targetIri) }}</span>
          <span v-if="a.confidence != null" class="al-conf">{{ a.confidence.toFixed(2) }}</span>
          <button class="al-del" title="정렬 삭제" @click="store.deleteAlignment(a.sourceIri, a.targetIri, a.matchType)">×</button>
        </div>
      </div>

      <div class="sec-title">영향 분석</div>
      <ImpactPanel />
    </div>

    <div class="sp-actions">
      <button class="act add-rel-btn" @click="emit('add-relation')">＋ 관계 연동</button>
      <button class="act ghost align-add-btn" @click="emit('add-alignment')">＋ 온톨로지 정렬</button>
    </div>
  </aside>
</template>

<style scoped>
.side-panel {
  position: absolute; top: 56px; right: 16px; bottom: 16px; width: 372px;
  background: #fff; border: 1px solid #e3e7ee; border-radius: 14px;
  box-shadow: 0 12px 48px rgba(15, 23, 41, 0.18);
  display: flex; flex-direction: column; overflow: hidden; z-index: 5;
}
.sp-head { display: flex; align-items: flex-start; gap: 10px; padding: 14px 16px 12px; border-bottom: 1px solid #eef1f5; }
.sp-title { flex: 1; min-width: 0; }
.sp-label { font-size: 16px; font-weight: 700; color: #0f1729; letter-spacing: -0.01em; overflow-wrap: anywhere; }
.sp-orig { margin-top: 4px; font-family: ui-monospace, 'SF Mono', Menlo, Consolas, monospace; font-size: 12px; color: #47536b; display: inline-flex; align-items: center; gap: 6px; }
.sp-orig .k { font-family: -apple-system, sans-serif; font-size: 8.5px; font-weight: 800; letter-spacing: 0.05em; color: #8592a8; background: #f1f5f9; border: 1px solid #e2e8f0; padding: 1px 5px; border-radius: 4px; }
.sp-close { border: none; background: transparent; color: #8592a8; font-size: 20px; line-height: 1; cursor: pointer; padding: 2px 4px; }

.sp-body { flex: 1; overflow-y: auto; padding: 4px 16px 18px; }
.sec-title { font-size: 10.5px; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase; color: #8592a8; margin: 18px 0 9px; }
.kv { display: grid; grid-template-columns: 84px 1fr; gap: 7px 12px; font-size: 12.5px; margin: 0; }
.kv dt { color: #8592a8; }
.kv dd { margin: 0; color: #0f1729; overflow-wrap: anywhere; }
.kv dd.mono { font-family: ui-monospace, 'SF Mono', Menlo, Consolas, monospace; font-size: 11.5px; }
.chip { display: inline-block; font-size: 11.5px; padding: 2px 8px; border-radius: 999px; }
.chip.ok { background: #dcfce7; color: #166534; }
.chip.idle { background: #f1f5f9; color: #64748b; }
.comment { margin: 10px 0 0; background: #f8fafc; padding: 9px 10px; border-radius: 8px; font-size: 12.5px; color: #334155; }

.fl { display: block; margin: 10px 0 4px; font-size: 12px; font-weight: 600; color: #47536b; }
.fin { width: 100%; padding: 7px 9px; border: 1px solid #cdd4e0; border-radius: 8px; font-size: 13px; box-sizing: border-box; }
.fin:focus { outline: 2px solid #4f46e5; outline-offset: -1px; }
.save-btn { margin-top: 12px; padding: 8px 18px; background: #4f46e5; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 600; }

.empty { color: #94a3b8; font-size: 12.5px; margin: 0; }
.maps { display: flex; flex-direction: column; gap: 7px; }
.map { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border: 1px solid #eef1f5; border-radius: 9px; background: #f8fafc; font-size: 12.5px; }
.dir { flex: 0 0 auto; font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 5px; }
.dir.out { background: #eef0fe; color: #3730a3; }
.dir.in { background: #ecfdf5; color: #065f46; }
.rel { font-family: ui-monospace, 'SF Mono', Menlo, Consolas, monospace; font-weight: 700; color: #3730a3; }
.arrow { color: #8592a8; }
.other { display: inline-flex; flex-direction: column; line-height: 1.25; font-weight: 600; min-width: 0; }
.other-orig { font-family: ui-monospace, 'SF Mono', Menlo, Consolas, monospace; font-size: 10.5px; font-weight: 400; color: #8592a8; }

.sp-actions { padding: 12px 16px; border-top: 1px solid #eef1f5; }
.act { width: 100%; padding: 9px; border-radius: 8px; border: 1px solid #4f46e5; background: #4f46e5; color: #fff; font-size: 13px; font-weight: 700; cursor: pointer; }

.alignments { display: flex; flex-direction: column; gap: 7px; }
.alignment { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border: 1px solid #eef1f5; border-radius: 9px; background: #f8fafc; font-size: 12.5px; }
.al-match { flex: 0 0 auto; font-family: ui-monospace, Menlo, monospace; font-size: 11px; font-weight: 700; padding: 1px 6px; border-radius: 5px; background: #eef0fe; color: #3730a3; }
.al-match.m-related, .al-match.m-broad, .al-match.m-narrow { background: #f1f5f9; color: #64748b; }
.al-target { flex: 1; min-width: 0; font-weight: 600; }
.al-conf { flex: 0 0 auto; font-variant-numeric: tabular-nums; color: #8592a8; font-size: 11.5px; }
.al-del { flex: 0 0 auto; border: none; background: transparent; color: #94a3b8; font-size: 15px; cursor: pointer; line-height: 1; }
.al-del:hover { color: #dc2626; }
.act.ghost { background: #fff; color: #4f46e5; border: 1px solid #c7d2fe; margin-top: 8px; }
</style>
