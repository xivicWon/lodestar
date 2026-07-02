<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useOntologyStore } from '../stores/ontologyStore'
const store = useOntologyStore()
const name = ref('')

onMounted(() => { store.listProjects() })

async function save() {
  const n = name.value.trim()
  if (!n) return
  await store.saveProject(n)
}
</script>

<template>
  <div class="project-panel">
    <div class="project-bar">
      <input class="project-name-input" v-model="name" placeholder="프로젝트 이름"
             @keyup.enter="save" />
      <button class="project-save-btn" :disabled="!name.trim()" @click="save">저장</button>
    </div>

    <p v-if="!store.projects.length" class="project-empty">저장된 프로젝트가 없습니다</p>
    <ul v-else class="project-list">
      <li v-for="p in store.projects" :key="p" class="project-item">
        <span class="project-item-name">{{ p }}</span>
        <button class="project-load-btn" @click="store.loadProject(p)">로드</button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.project-panel { padding: 12px 16px; border-top: 1px solid #e5e7eb; }
.project-bar { display: flex; align-items: center; gap: 8px; }
.project-name-input { flex: 1; padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; }
.project-save-btn { padding: 6px 12px; background: #2563eb; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; }
.project-save-btn:disabled { opacity: 0.5; cursor: default; }
.project-empty { font-size: 13px; color: #9ca3af; margin: 10px 0 0; }
.project-list { list-style: none; margin: 10px 0 0; padding: 0; }
.project-item { display: flex; align-items: center; justify-content: space-between; padding: 4px 8px; border-radius: 5px; font-size: 13px; }
.project-item:hover { background: #f3f4f6; }
.project-load-btn { padding: 4px 10px; border: 1px solid #d1d5db; border-radius: 5px; background: white; cursor: pointer; font-size: 12px; }
</style>
