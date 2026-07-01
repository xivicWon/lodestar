<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { Network, DataSet } from 'vis-network/standalone'
import { useOntologyStore } from '../stores/ontologyStore'
import { buildGraphData } from '../lib/buildGraphData'

const store = useOntologyStore()
const container = ref<HTMLDivElement | null>(null)
let network: Network | null = null
let nodes: DataSet<any> | null = null
let edges: DataSet<any> | null = null

function rebuild() {
  if (!nodes || !edges) return
  const g = buildGraphData(store.classes, store.objectProperties)
  nodes.clear(); nodes.add(g.nodes)
  edges.clear(); edges.add(g.edges)
  highlight()
}

function highlight() {
  if (!nodes) return
  const sel = store.selectedIri
  for (const n of nodes.get() as Array<{ id: string }>) {
    nodes.update({ id: n.id, color: n.id === sel ? '#c7d2fe' : '#e5e7eb' })
  }
}

onMounted(() => {
  nodes = new DataSet<any>([])
  edges = new DataSet<any>([])
  network = new Network(container.value as HTMLElement, { nodes, edges }, {
    nodes: { shape: 'box', color: '#e5e7eb', font: { size: 14 } },
    edges: { arrows: 'to', font: { align: 'top', size: 12 }, color: '#9ca3af' },
    physics: { stabilization: true },
    layout: { improvedLayout: true },
    interaction: { hover: true, dragNodes: true, zoomView: true, dragView: true },
  })
  network.on('click', (params: { nodes: string[] }) => {
    if (params.nodes && params.nodes.length > 0) store.select(params.nodes[0])
  })
  // 물리 안정화가 끝날 때마다(최초 로드 + 데이터 변경 후) 그래프를 화면에 맞춤
  network.on('stabilizationIterationsDone', () => network?.fit({ animation: false }))
  rebuild()
})

onBeforeUnmount(() => { network?.destroy(); network = null })

watch(() => [store.classes, store.objectProperties], rebuild, { deep: true })
watch(() => store.selectedIri, highlight)
</script>

<template>
  <div ref="container" class="relations-graph"></div>
</template>

<style scoped>
.relations-graph { width: 100%; height: 100%; min-height: 420px; }
</style>
