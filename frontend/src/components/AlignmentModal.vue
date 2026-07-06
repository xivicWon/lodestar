<script setup lang="ts">
import { ref, computed } from 'vue'
import { useOntologyStore } from '../stores/ontologyStore'
import { shortName } from '../lib/shortName'
import type { MatchType } from '../api/types'

const store = useOntologyStore()
const emit = defineEmits<{ (e: 'close'): void }>()

const fromIri = ref<string>(store.selectedIri ?? '')
const toIri = ref<string>('')
const matchType = ref<MatchType>('CLOSE')
const confidence = ref<string>('')

const MATCHES: { value: MatchType; label: string }[] = [
  { value: 'EXACT', label: 'exactMatch (동일)' },
  { value: 'CLOSE', label: 'closeMatch (거의 같음)' },
  { value: 'BROAD', label: 'broadMatch (상위)' },
  { value: 'NARROW', label: 'narrowMatch (하위)' },
  { value: 'RELATED', label: 'relatedMatch (관련)' },
]

function opt(iri: string, label: string | null): string {
  const orig = shortName(iri)
  const l = label ?? orig
  return l === orig ? l : `${l} (${orig})`
}
const sourceOpts = computed(() => store.classes.map(c => ({ iri: c.iri, text: opt(c.iri, c.label) })))
const targetOpts = computed(() => store.referenceClasses.map(c => ({ iri: c.iri, text: opt(c.iri, c.label) })))

const canSubmit = computed(() => !!fromIri.value && !!toIri.value)

async function submit() {
  if (!canSubmit.value) return
  const conf = confidence.value.trim() === '' ? undefined : Number(confidence.value)
  await store.createAlignment(fromIri.value, toIri.value, matchType.value, conf)
  emit('close')
}
</script>

<template>
  <div class="overlay" @click.self="emit('close')">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="al-title">
      <div class="modal-head">
        <h3 id="al-title">온톨로지 정렬 — SKOS 매핑</h3>
        <p>복원 클래스를 참조 온톨로지 클래스에 연결합니다. 실 DB는 변경되지 않습니다.</p>
        <button class="modal-x" aria-label="닫기" @click="emit('close')">×</button>
      </div>
      <div class="modal-body">
        <div class="maprow">
          <div class="field">
            <label for="al-from">소스 클래스 (복원)</label>
            <select id="al-from" class="select from-select" v-model="fromIri">
              <option value="" disabled>클래스 선택…</option>
              <option v-for="o in sourceOpts" :key="o.iri" :value="o.iri">{{ o.text }}</option>
            </select>
          </div>
          <div class="mid" aria-hidden="true">→</div>
          <div class="field">
            <label for="al-to">참조 클래스</label>
            <select id="al-to" class="select to-select" v-model="toIri">
              <option value="" disabled>클래스 선택…</option>
              <option v-for="o in targetOpts" :key="o.iri" :value="o.iri">{{ o.text }}</option>
            </select>
          </div>
        </div>
        <div class="maprow">
          <div class="field">
            <label for="al-match">매치 타입</label>
            <select id="al-match" class="select match-select" v-model="matchType">
              <option v-for="m in MATCHES" :key="m.value" :value="m.value">{{ m.label }}</option>
            </select>
          </div>
          <div class="mid" aria-hidden="true"></div>
          <div class="field">
            <label for="al-conf">신뢰도 <span class="hint">(선택, 0~1)</span></label>
            <input id="al-conf" class="text conf-input" v-model="confidence" placeholder="예: 0.8" />
          </div>
        </div>
      </div>
      <div class="modal-foot">
        <button class="ghost" @click="emit('close')">취소</button>
        <button class="primary submit-btn" :disabled="!canSubmit" @click="submit">정렬 만들기</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overlay { position: fixed; inset: 0; z-index: 40; display: flex; align-items: center; justify-content: center; padding: 20px; background: rgba(15,23,41,.42); }
.modal { width: min(520px,100%); background: #fff; border: 1px solid #e3e7ee; border-radius: 16px; box-shadow: 0 12px 48px rgba(15,23,41,.22); overflow: hidden; }
.modal-head { position: relative; padding: 16px 20px 12px; border-bottom: 1px solid #eef1f5; }
.modal-head h3 { margin: 0; font-size: 15.5px; font-weight: 700; color: #0f1729; }
.modal-head p { margin: 5px 0 0; font-size: 12px; color: #47536b; max-width: 44ch; }
.modal-x { position: absolute; top: 12px; right: 14px; border: none; background: transparent; font-size: 22px; color: #8592a8; cursor: pointer; }
.modal-body { padding: 16px 20px; display: flex; flex-direction: column; gap: 14px; }
.field { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.field label { font-size: 11.5px; font-weight: 700; color: #47536b; }
.field label .hint { font-weight: 400; color: #8592a8; }
.select, .text { width: 100%; border: 1px solid #cdd4e0; border-radius: 9px; padding: 9px 11px; font-size: 13px; background: #f7f8fa; color: #0f1729; box-sizing: border-box; }
.select:focus, .text:focus { outline: 2px solid #4f46e5; outline-offset: -1px; background: #fff; }
.maprow { display: grid; grid-template-columns: 1fr auto 1fr; gap: 10px; align-items: end; }
.maprow .mid { color: #8592a8; font-size: 14px; padding-bottom: 9px; text-align: center; }
.modal-foot { padding: 14px 20px 18px; display: flex; justify-content: flex-end; gap: 9px; border-top: 1px solid #eef1f5; }
.modal-foot button { font-size: 13px; font-weight: 700; border-radius: 9px; padding: 9px 16px; cursor: pointer; }
.ghost { background: transparent; border: 1px solid #cdd4e0; color: #47536b; }
.primary { background: #4f46e5; border: 1px solid #4f46e5; color: #fff; }
.primary:disabled { opacity: .5; cursor: not-allowed; }
</style>
