import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiGet, apiPost, apiPatch, apiDelete, apiUpload, apiDownload, ApiError } from '../api/client'
import type { ClassDto, OntologyMetaDto, ReasonResult, ObjectPropertyDto, ConnectionInfo, EnrichmentCandidate, RelationCandidate } from '../api/types'
import { buildTree } from '../lib/buildTree'

export const useOntologyStore = defineStore('ontology', () => {
  const classes = ref<ClassDto[]>([])
  const selectedIri = ref<string | null>(null)
  const meta = ref<OntologyMetaDto | null>(null)
  const error = ref<string | null>(null)
  const reasonResult = ref<ReasonResult | null>(null)
  const objectProperties = ref<ObjectPropertyDto[]>([])
  const enrichCandidates = ref<EnrichmentCandidate[]>([])
  const enriching = ref(false)
  const relCandidates = ref<RelationCandidate[]>([])
  const suggesting = ref(false)

  const selected = computed(() => classes.value.find(c => c.iri === selectedIri.value) ?? null)
  const tree = computed(() => buildTree(classes.value))

  function setError(e: unknown) {
    error.value = e instanceof ApiError ? e.message : (e instanceof Error ? e.message : String(e))
  }

  async function refresh() {
    reasonResult.value = null
    classes.value = await apiGet<ClassDto[]>('/classes')
    try { objectProperties.value = await apiGet<ObjectPropertyDto[]>('/properties/object') }
    catch { objectProperties.value = [] }
    try { meta.value = await apiGet<OntologyMetaDto>('/ontology/meta') } catch { /* meta optional */ }
  }

  function select(iri: string | null) { selectedIri.value = iri }

  async function createClass(label: string, superClass?: string) {
    error.value = null
    try { await apiPost<ClassDto>('/classes', { label, superClass }); await refresh() }
    catch (e) { setError(e) }
  }

  async function saveClass(iri: string, patch: { label?: string; superClasses?: string[] }) {
    error.value = null
    try { await apiPatch<ClassDto>(`/classes/by-iri?iri=${encodeURIComponent(iri)}`, patch); await refresh() }
    catch (e) { setError(e) }
  }

  async function deleteClass(iri: string, cascade = false) {
    error.value = null
    try {
      await apiDelete(`/classes/by-iri?iri=${encodeURIComponent(iri)}&cascade=${cascade}`)
      if (selectedIri.value === iri) selectedIri.value = null
      await refresh()
    } catch (e) { setError(e) }
  }

  async function loadFile(file: File) {
    error.value = null
    try { await apiUpload<OntologyMetaDto>('/ontology/load', file); selectedIri.value = null; await refresh() }
    catch (e) { setError(e) }
  }

  async function exportTurtle(): Promise<Blob> {
    return apiDownload('/ontology/export?format=turtle')
  }

  async function importDdl(sql: string, schemaName?: string) {
    error.value = null
    try {
      await apiPost<OntologyMetaDto>('/rdb/import/ddl', { sql, schemaName })
      selectedIri.value = null
      await refresh()
    } catch (e) { setError(e) }
  }

  async function importSample() {
    error.value = null
    try {
      await apiPost<OntologyMetaDto>('/rdb/import/sample', {})
      selectedIri.value = null
      await refresh()
    } catch (e) { setError(e) }
  }

  async function enrichSample() {
    error.value = null
    enriching.value = true
    try {
      enrichCandidates.value = await apiPost<EnrichmentCandidate[]>('/ai/enrich/sample', {})
    } catch (e) { setError(e) }
    finally { enriching.value = false }
  }

  async function applyEnrichment(targetIri: string, label: string) {
    error.value = null
    try {
      await apiPatch<ClassDto>(`/classes/by-iri?iri=${encodeURIComponent(targetIri)}`, { label })
      enrichCandidates.value = enrichCandidates.value.filter(c => c.targetIri !== targetIri)
      await refresh()
    } catch (e) { setError(e) }
  }

  function dismissEnrichment(targetIri: string) {
    enrichCandidates.value = enrichCandidates.value.filter(c => c.targetIri !== targetIri)
  }

  async function renameRelation(iri: string, label: string) {
    error.value = null
    try {
      await apiPatch<ObjectPropertyDto>(`/properties/object/label?iri=${encodeURIComponent(iri)}`, { label })
      await refresh()
    } catch (e) { setError(e) }
  }

  async function importConnection(info: ConnectionInfo) {
    error.value = null
    try {
      await apiPost<OntologyMetaDto>('/rdb/import/connection', info)
      selectedIri.value = null
      await refresh()
    } catch (e) { setError(e) }
  }

  async function runReasoner() {
    error.value = null
    try { reasonResult.value = await apiPost<ReasonResult>('/reason', {}) }
    catch (e) { setError(e) }
  }

  function inferredChildrenOf(iri: string): { iri: string; label: string | null }[] {
    const edges = reasonResult.value?.inferredSubClassOf ?? []
    return edges
      .filter(e => e.sup === iri)
      .map(e => {
        const c = classes.value.find(k => k.iri === e.sub)
        return { iri: e.sub, label: c?.label ?? null }
      })
  }

  async function suggestRelations() {
    error.value = null
    suggesting.value = true
    try {
      relCandidates.value = await apiPost<RelationCandidate[]>('/rel/suggest', {})
    } catch (e) { setError(e) }
    finally { suggesting.value = false }
  }

  async function applyRelation(fromIri: string, toIri: string, name: string) {
    error.value = null
    try {
      await apiPost<ObjectPropertyDto>('/properties/object', { label: name, domains: [fromIri], ranges: [toIri] })
      relCandidates.value = relCandidates.value.filter(c => !(c.fromIri === fromIri && c.toIri === toIri && c.suggestedName === name))
      await refresh()
    } catch (e) { setError(e) }
  }

  function dismissRelation(idx: number) {
    relCandidates.value = relCandidates.value.filter((_, i) => i !== idx)
  }

  function clearError() { error.value = null }

  function reportError(e: unknown) { setError(e) }

  return { classes, selectedIri, meta, error, selected, tree,
           reasonResult, runReasoner, inferredChildrenOf,
           objectProperties, importDdl, importConnection, importSample, renameRelation,
           enrichCandidates, enriching, enrichSample, applyEnrichment, dismissEnrichment,
           relCandidates, suggesting, suggestRelations, applyRelation, dismissRelation,
           refresh, select, createClass, saveClass, deleteClass, loadFile, exportTurtle,
           clearError, reportError }
})
