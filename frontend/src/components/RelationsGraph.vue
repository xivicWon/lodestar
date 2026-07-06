<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { Network, DataSet } from 'vis-network/standalone'
import { useOntologyStore } from '../stores/ontologyStore'
import { buildGraphData, focusSubgraph } from '../lib/buildGraphData'
import { alignmentGraph } from '../lib/alignmentGraph'

const store = useOntologyStore()
const container = ref<HTMLDivElement | null>(null)
const focused = ref(false)
const linking = ref(false)
const linkFrom = ref<string | null>(null)
let network: Network | null = null
let nodes: DataSet<any> | null = null
let edges: DataSet<any> | null = null
// 그래프 "구조"(노드 집합 + 간선 수)의 서명. 이게 바뀔 때만 물리 재배치를 돌린다.
// 라벨 변경·선택 같은 비구조 변경에서는 물리를 켜지 않아 노드가 흔들리지 않는다.
let lastSig = ''
let relayoutTimer: ReturnType<typeof setTimeout> | null = null

function signature(g: { nodes: { id: string }[]; edges: unknown[] }): string {
  return g.nodes.map(n => n.id).sort().join('|') + '#' + g.edges.length
}

function rebuild() {
  if (!nodes || !edges) return
  let g = buildGraphData(store.classes, store.objectProperties)
  if (focused.value && store.selectedIri) g = focusSubgraph(g, store.selectedIri)
  if (store.alignments.length) {
    const refLabelOf = (iri: string) => store.referenceClasses.find(c => c.iri === iri)?.label ?? iri
    // 정렬된 소스가 현재 그래프에 있는 것만
    const present = new Set(g.nodes.map(n => n.id))
    const visible = store.alignments.filter(a => present.has(a.sourceIri))
    const extra = alignmentGraph(visible, refLabelOf)
    g = { nodes: [...g.nodes, ...extra.nodes], edges: [...g.edges, ...extra.edges] }
  }
  const sig = signature(g)
  const structureChanged = sig !== lastSig
  lastSig = sig
  nodes.clear(); nodes.add(g.nodes)
  edges.clear(); edges.add(g.edges)
  highlight()
  if (structureChanged) relayout()
}

// 물리를 잠깐 켜고 stabilize()로 숨은 반복을 돌려 안정 위치로 배치한 뒤,
// stabilizationIterationsDone 에서 다시 끈다. 연속 시뮬레이션(계속 떠다님)을 막는다.
function relayout() {
  if (!network) return
  network.setOptions({ physics: { enabled: true } })
  network.stabilize()
  // 안전장치: 어떤 이유로 done 이벤트가 안 와도 강제로 멈춘다.
  if (relayoutTimer) clearTimeout(relayoutTimer)
  relayoutTimer = setTimeout(() => freeze(), 2500)
}

function freeze() {
  if (relayoutTimer) { clearTimeout(relayoutTimer); relayoutTimer = null }
  network?.setOptions({ physics: { enabled: false } })
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
    groups: { ref: { color: { background: '#ecfeff', border: '#0891b2' }, shape: 'ellipse', font: { color: '#0e7490' } } },
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
    freeze()
    network?.fit({ animation: false })
  })
  rebuild()
})

onBeforeUnmount(() => {
  if (relayoutTimer) clearTimeout(relayoutTimer)
  network?.destroy(); network = null
})

watch(() => [store.classes, store.objectProperties, store.alignments, store.referenceClasses], rebuild, { deep: true })
watch(() => store.selectedIri, () => { focused.value ? rebuild() : highlight() })
</script>

<template>
  <div class="relations-graph-wrap">
    <div class="graph-tools">
      <button
        class="relayout-btn"
        title="노드를 보기 좋게 다시 배치합니다 (배치 후 자동으로 멈춥니다)"
        @click="relayout"
      >재배치</button>
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
.focus-toggle, .link-toggle, .relayout-btn {
  padding: 5px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #ffffff;
  color: #374151;
  font-size: 13px;
  cursor: pointer;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}
.focus-toggle:hover:not(:disabled), .link-toggle:hover, .relayout-btn:hover { background: #f3f4f6; }
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
