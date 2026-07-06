<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useOntologyStore } from '../stores/ontologyStore'
import { shortName } from '../lib/shortName'

const store = useOntologyStore()
const emit = defineEmits<{ (e: 'close'): void }>()

// 소스는 현재 선택된 클래스를 기본값으로. 타깃·이름은 사용자가 채운다.
const fromIri = ref<string>(store.selectedIri ?? '')
const toIri = ref<string>('')
const name = ref<string>('')

// 모달이 열리는 동안 선택이 바뀌면 소스 기본값을 갱신(아직 사용자가 안 골랐을 때만).
watch(() => store.selectedIri, (iri) => { if (!fromIri.value && iri) fromIri.value = iri })

interface Opt { iri: string; text: string }
const options = computed<Opt[]>(() =>
  [...store.classes]
    .map(c => {
      const orig = shortName(c.iri)
      const label = c.label ?? orig
      return { iri: c.iri, text: label === orig ? label : `${label} (${orig})` }
    })
    .sort((a, b) => a.text.localeCompare(b.text, 'ko')),
)

const canSubmit = computed(() =>
  !!fromIri.value && !!toIri.value && fromIri.value !== toIri.value && !!name.value.trim(),
)

async function submit() {
  if (!canSubmit.value) return
  await store.applyRelation(fromIri.value, toIri.value, name.value.trim())
  emit('close')
}
</script>

<template>
  <div class="overlay" @click.self="emit('close')" @keydown.esc="emit('close')">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="rl-title">
      <div class="modal-head">
        <h3 id="rl-title">관계 연동 — 데이터 선택</h3>
        <p>소스·타깃 클래스와 관계 이름을 선택해 관계(ObjectProperty)를 만듭니다. 실 DB는 변경되지 않습니다.</p>
        <button class="modal-x" aria-label="닫기" @click="emit('close')">×</button>
      </div>
      <div class="modal-body">
        <div class="maprow">
          <div class="field">
            <label for="rl-from">소스 클래스 <span class="hint">(from)</span></label>
            <select id="rl-from" class="select from-select" v-model="fromIri">
              <option value="" disabled>클래스 선택…</option>
              <option v-for="o in options" :key="o.iri" :value="o.iri">{{ o.text }}</option>
            </select>
          </div>
          <div class="mid" aria-hidden="true">→</div>
          <div class="field">
            <label for="rl-to">타깃 클래스 <span class="hint">(to)</span></label>
            <select id="rl-to" class="select to-select" v-model="toIri">
              <option value="" disabled>클래스 선택…</option>
              <option v-for="o in options" :key="o.iri" :value="o.iri">{{ o.text }}</option>
            </select>
          </div>
        </div>
        <div class="field">
          <label for="rl-name">관계 이름 <span class="hint">(예: hasUser)</span></label>
          <input id="rl-name" class="text name-input" v-model="name" placeholder="관계 이름 입력…" @keydown.enter="submit" />
        </div>
        <p v-if="fromIri && toIri && fromIri === toIri" class="warn">소스와 타깃이 같습니다. 다른 클래스를 선택하세요.</p>
      </div>
      <div class="modal-foot">
        <button class="ghost" @click="emit('close')">취소</button>
        <button class="primary submit-btn" :disabled="!canSubmit" @click="submit">관계 만들기</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed; inset: 0; z-index: 40; display: flex;
  align-items: center; justify-content: center; padding: 20px;
  background: rgba(15, 23, 41, 0.42);
}
.modal {
  width: min(520px, 100%); background: #fff; border: 1px solid #e3e7ee;
  border-radius: 16px; box-shadow: 0 12px 48px rgba(15, 23, 41, 0.22); overflow: hidden;
}
.modal-head { position: relative; padding: 16px 20px 12px; border-bottom: 1px solid #eef1f5; }
.modal-head h3 { margin: 0; font-size: 15.5px; font-weight: 700; color: #0f1729; }
.modal-head p { margin: 5px 0 0; font-size: 12px; color: #47536b; max-width: 44ch; }
.modal-x { position: absolute; top: 12px; right: 14px; border: none; background: transparent; font-size: 22px; line-height: 1; color: #8592a8; cursor: pointer; }
.modal-body { padding: 16px 20px; display: flex; flex-direction: column; gap: 14px; }
.field { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.field label { font-size: 11.5px; font-weight: 700; color: #47536b; }
.field label .hint { font-weight: 400; color: #8592a8; }
.select, .text {
  width: 100%; border: 1px solid #cdd4e0; border-radius: 9px; padding: 9px 11px;
  font-size: 13px; background: #f7f8fa; color: #0f1729; box-sizing: border-box;
}
.select:focus, .text:focus { outline: 2px solid #4f46e5; outline-offset: -1px; background: #fff; }
.maprow { display: grid; grid-template-columns: 1fr auto 1fr; gap: 10px; align-items: end; }
.maprow .mid { color: #8592a8; font-size: 14px; padding-bottom: 9px; text-align: center; }
.warn { margin: 0; font-size: 12px; color: #b45309; }
.modal-foot { padding: 14px 20px 18px; display: flex; justify-content: flex-end; gap: 9px; border-top: 1px solid #eef1f5; }
.modal-foot button { font-size: 13px; font-weight: 700; border-radius: 9px; padding: 9px 16px; cursor: pointer; }
.ghost { background: transparent; border: 1px solid #cdd4e0; color: #47536b; }
.primary { background: #4f46e5; border: 1px solid #4f46e5; color: #fff; }
.primary:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
