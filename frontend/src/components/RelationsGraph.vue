<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { Network, DataSet } from 'vis-network/standalone'
import { useOntologyStore } from '../stores/ontologyStore'
import { buildGraphData, focusSubgraph } from '../lib/buildGraphData'

const store = useOntologyStore()
const container = ref<HTMLDivElement | null>(null)
const focused = ref(false)
const linking = ref(false)
const linkFrom = ref<string | null>(null)
let network: Network | null = null
let nodes: DataSet<any> | null = null
let edges: DataSet<any> | null = null

function rebuild() {
  if (!nodes || !edges) return
  let g = buildGraphData(store.classes, store.objectProperties)
  if (focused.value && store.selectedIri) g = focusSubgraph(g, store.selectedIri)
  // 구조가 바뀌었으니 물리를 잠깐 켜서 재배치(안정화되면 다시 꺼짐)
  network?.setOptions({ physics: { enabled: true } })
  nodes.clear(); nodes.add(g.nodes)
  edges.clear(); edges.add(g.edges)
  highlight()
}

function highlight() {
  if (!nodes) return
  const sel = store.selectedIri
  for (const n of nodes.get() as Array<{ id: string }>) {
    const color = n.id === linkFrom.value ? '#bbf7d0' : n.id === sel ? '#c7d2fe' : '#e5e7eb'
    nodes.update({ id: n.id, color })
  }
}

function toggleFocus() {
  focused.value = !focused.value
  rebuild()
  network?.fit({ animation: false })
}

function toggleLinking() {
  linking.value = !linking.value
  linkFrom.value = null
  highlight()
}

// 관계 추가 모드에서 노드 클릭 처리: 첫 클릭=출발, 둘째 클릭=도착 → 관계 생성
function handleLinkClick(iri: string) {
  if (!linkFrom.value) { linkFrom.value = iri; highlight(); return }
  if (iri === linkFrom.value) { linkFrom.value = null; highlight(); return } // 같은 노드 재클릭 = 취소
  const name = window.prompt('관계 이름 (예: placedBy)', '')
  const from = linkFrom.value
  linkFrom.value = null
  highlight()
  if (name && name.trim()) store.applyRelation(from, iri, name.trim())
}

function onNodeClick(iri: string) {
  if (linking.value) handleLinkClick(iri)
  else store.select(iri)
}

onMounted(() => {
  nodes = new DataSet<any>([])
  edges = new DataSet<any>([])
  network = new Network(container.value as HTMLElement, { nodes, edges }, {
    nodes: { shape: 'box', color: '#e5e7eb', font: { size: 14 }, margin: { top: 8, right: 12, bottom: 8, left: 12 } as any },
    edges: {
      arrows: 'to',
      color: '#9ca3af',
      length: 220,
      font: { align: 'top', size: 12, background: '#ffffff', strokeWidth: 0 },
      smooth: { enabled: true, type: 'dynamic', roundness: 0.5 } as any,
    },
    physics: {
      enabled: true,
      stabilization: { enabled: true, iterations: 300, fit: true },
      barnesHut: { springLength: 220, avoidOverlap: 0.6, gravitationalConstant: -12000 },
    },
    layout: { improvedLayout: true },
    interaction: { hover: true, dragNodes: true, zoomView: true, dragView: true },
  })
  network.on('click', (params: { nodes: string[] }) => {
    if (params.nodes && params.nodes.length > 0) onNodeClick(params.nodes[0])
  })
  // 안정화가 끝나면 물리를 꺼서 그래프를 고정한다(계속 떠다니는 현상 방지).
  // 이후 클릭·드래그·관계추가 중에는 노드가 흔들리지 않는다.
  network.on('stabilizationIterationsDone', () => {
    network?.setOptions({ physics: { enabled: false } })
    network?.fit({ animation: false })
  })
  rebuild()
})

onBeforeUnmount(() => { network?.destroy(); network = null })

watch(() => [store.classes, store.objectProperties], rebuild, { deep: true })
watch(() => store.selectedIri, () => { focused.value ? rebuild() : highlight() })
</script>

<template>
  <div class="relations-graph-wrap">
    <div class="graph-tools">
      <button
        class="focus-toggle"
        :class="{ active: focused }"
        :disabled="!store.selectedIri"
        :title="store.selectedIri ? '선택한 노드와 직접 연결된 관계만 표시' : '먼저 노드를 선택하세요'"
        @click="toggleFocus"
      >{{ focused ? '전체 보기' : '선택 노드 포커스' }}</button>
      <button
        class="link-toggle"
        :class="{ active: linking }"
        title="두 노드를 차례로 클릭해 관계를 만듭니다"
        @click="toggleLinking"
      >{{ linking ? '관계 추가 종료' : '관계 추가' }}</button>
    </div>
    <div v-if="linking" class="link-hint">
      {{ linkFrom ? '도착 노드를 클릭하세요' : '출발 노드를 클릭하세요' }}
    </div>
    <div ref="container" class="relations-graph"></div>
  </div>
</template>

<style scoped>
.relations-graph-wrap { position: relative; width: 100%; height: 100%; min-height: 420px; }
.graph-tools { position: absolute; top: 8px; right: 8px; z-index: 2; display: flex; gap: 6px; }
.focus-toggle, .link-toggle {
  padding: 5px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #ffffff;
  color: #374151;
  font-size: 13px;
  cursor: pointer;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}
.focus-toggle:hover:not(:disabled), .link-toggle:hover { background: #f3f4f6; }
.focus-toggle.active { background: #4f46e5; color: #ffffff; border-color: #4f46e5; }
.link-toggle.active { background: #059669; color: #ffffff; border-color: #059669; }
.focus-toggle:disabled { opacity: 0.5; cursor: not-allowed; }
.link-hint {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 2;
  padding: 5px 12px;
  border-radius: 6px;
  background: #ecfdf5;
  color: #065f46;
  border: 1px solid #a7f3d0;
  font-size: 13px;
}
.relations-graph { width: 100%; height: 100%; }
</style>
