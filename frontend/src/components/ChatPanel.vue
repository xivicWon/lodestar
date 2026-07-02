<script setup lang="ts">
import { ref } from 'vue'
import { useOntologyStore } from '../stores/ontologyStore'

const store = useOntologyStore()
const draft = ref('')

async function send() {
  const q = draft.value
  if (!q.trim() || store.asking) return
  draft.value = ''
  await store.askChat(q)
}
</script>

<template>
  <div class="chat-panel">
    <ul class="chat-messages">
      <li v-for="(m, i) in store.chatMessages" :key="i" class="chat-msg" :class="m.role">
        <span class="chat-role">{{ m.role === 'user' ? '나' : 'AI' }}</span>
        <span class="chat-text">{{ m.text }}</span>
      </li>
      <li v-if="!store.chatMessages.length" class="chat-empty">온톨로지에 대해 질문해 보세요.</li>
    </ul>
    <div class="chat-input-bar">
      <input
        class="chat-input"
        v-model="draft"
        placeholder="온톨로지에 대해 질문…"
        @keyup.enter="send"
      />
      <button class="chat-send-btn" :disabled="store.asking" @click="send">
        {{ store.asking ? '전송 중…' : '전송' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.chat-panel { padding: 12px; border-bottom: 1px solid #e5e7eb; display: flex; flex-direction: column; gap: 8px; }
.chat-messages { list-style: none; margin: 0; padding: 0; max-height: 260px; overflow: auto; display: flex; flex-direction: column; gap: 6px; }
.chat-msg { display: flex; gap: 8px; font-size: 13px; align-items: baseline; }
.chat-msg.user .chat-role { color: #2563eb; font-weight: 700; }
.chat-msg.assistant .chat-role { color: #7c3aed; font-weight: 700; }
.chat-role { flex: 0 0 auto; min-width: 24px; }
.chat-text { white-space: pre-wrap; }
.chat-empty { font-size: 12px; color: #9ca3af; }
.chat-input-bar { display: flex; gap: 6px; }
.chat-input { flex: 1; padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; }
.chat-send-btn { padding: 6px 14px; background: #7c3aed; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; }
.chat-send-btn:disabled { opacity: 0.6; cursor: default; }
</style>
