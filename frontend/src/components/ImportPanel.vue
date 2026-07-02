<script setup lang="ts">
import { ref } from 'vue'
import { useOntologyStore } from '../stores/ontologyStore'

const store = useOntologyStore()
const tab = ref<'ddl' | 'connection'>('ddl')

const ddl = ref('')
const schemaName = ref('')

const vendor = ref<'postgresql' | 'mysql'>('postgresql')
const host = ref(''); const port = ref(5432); const database = ref('')
const user = ref(''); const password = ref('')

function onVendorChange() {
  port.value = vendor.value === 'mysql' ? 3306 : 5432
}

function runDdl() {
  if (!ddl.value.trim()) return
  store.importDdl(ddl.value, schemaName.value.trim() || undefined)
}
function runConnection() {
  store.importConnection({
    host: host.value, port: Number(port.value), database: database.value,
    user: user.value, password: password.value, vendor: vendor.value,
  })
}
</script>

<template>
  <div class="import-panel">
    <div class="sample-bar">
      <button class="import-sample-btn" @click="store.importSample()">🧪 샘플 레거시 주입 (27테이블)</button>
      <span class="sample-hint">FK 거의 없는 지저분한 샘플로 바로 체험</span>
    </div>
    <div class="tabs">
      <button class="tab-ddl" :class="{ active: tab === 'ddl' }" @click="tab = 'ddl'">DDL 스크립트</button>
      <button class="tab-connection" :class="{ active: tab === 'connection' }" @click="tab = 'connection'">DB 연결</button>
    </div>

    <div v-if="tab === 'ddl'" class="pane">
      <label>스키마 이름 (선택)</label>
      <input class="schema-input" v-model="schemaName" placeholder="shop" />
      <label>CREATE TABLE ... SQL</label>
      <textarea class="ddl-input" v-model="ddl" rows="10" placeholder="CREATE TABLE ..."></textarea>
      <button class="import-ddl-btn" @click="runDdl">가져오기</button>
    </div>

    <div v-else class="pane">
      <label>Vendor</label>
      <select class="vendor-select" v-model="vendor" @change="onVendorChange">
        <option value="postgresql">PostgreSQL</option>
        <option value="mysql">MySQL</option>
      </select>
      <label>Host</label><input class="host-input" v-model="host" placeholder="localhost" />
      <label>Port</label><input class="port-input" v-model="port" type="number" />
      <label>Database</label><input class="db-input" v-model="database" />
      <label>User</label><input class="user-input" v-model="user" />
      <label>Password</label><input class="pw-input" v-model="password" type="password" />
      <button class="import-conn-btn" @click="runConnection">연결 후 가져오기</button>
    </div>
  </div>
</template>

<style scoped>
.import-panel { padding: 12px; border-bottom: 1px solid #e5e7eb; }
.tabs { display: flex; gap: 4px; margin-bottom: 8px; }
.tabs button { padding: 4px 12px; border: 1px solid #d1d5db; background: white; border-radius: 6px; cursor: pointer; font-size: 13px; }
.tabs button.active { background: #4f46e5; color: white; border-color: #4f46e5; }
.pane { display: flex; flex-direction: column; }
label { font-size: 12px; font-weight: 600; margin: 8px 0 2px; }
input, textarea { padding: 6px 8px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; box-sizing: border-box; }
.import-ddl-btn, .import-conn-btn { margin-top: 10px; padding: 8px; background: #4f46e5; color: white; border: none; border-radius: 6px; cursor: pointer; }
.sample-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px dashed #e5e7eb; }
.import-sample-btn { padding: 6px 12px; background: #059669; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; }
.sample-hint { font-size: 12px; color: #6b7280; }
</style>
