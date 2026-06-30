<script setup lang="ts">
import { ref, watch } from 'vue'
import { useOntologyStore } from '../stores/ontologyStore'

const RDFS_COMMENT = 'http://www.w3.org/2000/01/rdf-schema#comment'
const store = useOntologyStore()

const label = ref('')
const superClassesText = ref('')

watch(() => store.selected, (c) => {
  label.value = c?.label ?? ''
  superClassesText.value = (c?.superClasses ?? []).join(', ')
}, { immediate: true })

const comment = () =>
  store.selected?.annotations.find(a => a.property === RDFS_COMMENT)?.value ?? ''

function save() {
  const c = store.selected
  if (!c) return
  const superClasses = superClassesText.value.split(',').map(s => s.trim()).filter(Boolean)
  store.saveClass(c.iri, { label: label.value, superClasses })
}
</script>

<template>
  <div class="class-detail">
    <p v-if="!store.selected" class="empty">선택된 클래스가 없습니다.</p>
    <div v-else class="form">
      <h3 class="iri">{{ store.selected.iri }}</h3>
      <label>Label</label>
      <input class="label-input" v-model="label" />
      <label>상위 클래스 (IRI, 쉼표 구분)</label>
      <input class="superclasses-input" v-model="superClassesText" />
      <label>설명 (읽기 전용)</label>
      <p class="comment">{{ comment() || '—' }}</p>
      <button class="save-btn" @click="save">저장</button>
      <p v-if="store.error" class="error">{{ store.error }}</p>
    </div>
  </div>
</template>

<style scoped>
.class-detail { padding: 16px; overflow: auto; height: 100%; }
.empty { color: #6b7280; }
.iri { font-size: 13px; color: #6b7280; word-break: break-all; font-weight: 400; }
label { display: block; margin: 12px 0 4px; font-size: 13px; font-weight: 600; }
input { width: 100%; padding: 6px 8px; border: 1px solid #d1d5db; border-radius: 6px; box-sizing: border-box; }
.comment { background: #f9fafb; padding: 8px; border-radius: 6px; min-height: 20px; }
.save-btn { margin-top: 16px; padding: 8px 20px; background: #4f46e5; color: white; border: none; border-radius: 6px; cursor: pointer; }
.error { color: #dc2626; margin-top: 8px; }
</style>
