import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiGet, apiPost, apiPatch, apiDelete, apiUpload, apiDownload, ApiError } from '../api/client'
import type { ClassDto, OntologyMetaDto, ReasonResult, ObjectPropertyDto, ConnectionInfo, EnrichmentCandidate, ScoredCandidate, ConfirmedFact, RelationCandidate, JudgedCandidate, ImpactResult, ChatAnswer, ImportResult, MergeSummary, CollectionReport, TrashEntry, ReferenceMetaDto, AlignmentDto, MatchType, RelationProvenance } from '../api/types'
import { buildTree } from '../lib/buildTree'

export const useOntologyStore = defineStore('ontology', () => {
  const classes = ref<ClassDto[]>([])
  const selectedIri = ref<string | null>(null)
  const meta = ref<OntologyMetaDto | null>(null)
  const error = ref<string | null>(null)
  const reasonResult = ref<ReasonResult | null>(null)
  const reasoning = ref(false)
  const objectProperties = ref<ObjectPropertyDto[]>([])
  const enrichCandidates = ref<EnrichmentCandidate[]>([])
  const enriching = ref(false)
  const scoredCandidates = ref<ScoredCandidate[]>([])
  const confirmations = ref<ConfirmedFact[]>([])
  const relCandidates = ref<RelationCandidate[]>([])
  const suggesting = ref(false)
  const judgedRelations = ref<JudgedCandidate[]>([])
  const judging = ref(false)
  const impact = ref<ImpactResult | null>(null)
  const projects = ref<string[]>([])
  const chatMessages = ref<{ role: 'user' | 'assistant'; text: string }[]>([])
  const asking = ref(false)
  const lastMerge = ref<MergeSummary | null>(null)
  /** 마지막 임포트가 **하지 못한 것**(#129). 세 입력 경로가 모두 여기에 싣는다. */
  const lastCollection = ref<CollectionReport | null>(null)
  const trash = ref<TrashEntry[]>([])
  const referenceClasses = ref<ClassDto[]>([])
  const referenceMeta = ref<ReferenceMetaDto | null>(null)
  const alignments = ref<AlignmentDto[]>([])

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
      const res = await apiPost<ImportResult>('/rdb/import/ddl', { sql, schemaName })
      lastMerge.value = res.merge
      lastCollection.value = res.collection ?? null
      selectedIri.value = null
      await refresh()
    } catch (e) { setError(e) }
  }

  async function importSample() {
    error.value = null
    try {
      const res = await apiPost<ImportResult>('/rdb/import/sample', {})
      lastMerge.value = res.merge
      lastCollection.value = res.collection ?? null
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

  async function scoredEnrichSample(runs = 5) {
    error.value = null
    enriching.value = true
    try {
      scoredCandidates.value = await apiPost<ScoredCandidate[]>('/ai/enrich/sample/scored?runs=' + runs, {})
    } catch (e) { setError(e) }
    finally { enriching.value = false }
  }

  /** E12: 현재 로드된 온톨로지(라이브/DDL/샘플)를 대상으로 AI 의미 추정. */
  async function enrichCurrent() {
    error.value = null
    enriching.value = true
    try {
      enrichCandidates.value = await apiPost<EnrichmentCandidate[]>('/ai/enrich', {})
    } catch (e) { setError(e) }
    finally { enriching.value = false }
  }

  /** E12+E7: 현재 온톨로지를 N회 반복 추론해 신뢰도(합의율)를 붙인다. */
  async function scoredEnrichCurrent(runs = 5) {
    error.value = null
    enriching.value = true
    try {
      scoredCandidates.value = await apiPost<ScoredCandidate[]>('/ai/enrich/scored?runs=' + runs, {})
    } catch (e) { setError(e) }
    finally { enriching.value = false }
  }

  async function applyEnrichment(targetIri: string, label: string) {
    error.value = null
    try {
      await apiPatch<ClassDto>(`/classes/by-iri?iri=${encodeURIComponent(targetIri)}`, { label })
      enrichCandidates.value = enrichCandidates.value.filter(c => c.targetIri !== targetIri)
      scoredCandidates.value = scoredCandidates.value.filter(c => c.targetIri !== targetIri)
      await refresh()
    } catch (e) { setError(e) }
  }

  function dismissEnrichment(targetIri: string) {
    enrichCandidates.value = enrichCandidates.value.filter(c => c.targetIri !== targetIri)
    scoredCandidates.value = scoredCandidates.value.filter(c => c.targetIri !== targetIri)
  }

  async function fetchConfirmations() {
    error.value = null
    try { confirmations.value = await apiGet<ConfirmedFact[]>('/confirmations') }
    catch (e) { setError(e) }
  }

  /** E8 승인(세이브포인트): 라벨 반영 + 확정 기록 후, 후보에서 제거하고 상태 갱신. */
  async function confirm(targetIri: string, label: string) {
    error.value = null
    try {
      await apiPost<ClassDto>('/enrich/confirm', { targetIri, label })
      enrichCandidates.value = enrichCandidates.value.filter(c => c.targetIri !== targetIri)
      scoredCandidates.value = scoredCandidates.value.filter(c => c.targetIri !== targetIri)
      await refresh()
      await fetchConfirmations()
    } catch (e) { setError(e) }
  }

  async function deleteConfirmation(iri: string) {
    error.value = null
    try {
      await apiDelete(`/confirmations?iri=${encodeURIComponent(iri)}`)
      await fetchConfirmations()
    } catch (e) { setError(e) }
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
      const res = await apiPost<ImportResult>('/rdb/import/connection', info)
      lastMerge.value = res.merge
      lastCollection.value = res.collection ?? null
      selectedIri.value = null
      await refresh()
    } catch (e) { setError(e) }
  }

  async function runReasoner() {
    error.value = null
    reasoning.value = true
    try { reasonResult.value = await apiPost<ReasonResult>('/reason', {}) }
    catch (e) { setError(e) }
    finally { reasoning.value = false }
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

  async function judgeRelations() {
    error.value = null
    judging.value = true
    try {
      judgedRelations.value = await apiPost<JudgedCandidate[]>('/rel/suggest/judged', {})
    } catch (e) { setError(e) }
    finally { judging.value = false }
  }

  async function applyRelation(fromIri: string, toIri: string, name: string, prov?: RelationProvenance) {
    error.value = null
    try {
      const body: Record<string, unknown> = { label: name, domains: [fromIri], ranges: [toIri] }
      if (prov) { body.kind = prov.kind; body.provenance = prov.provenance; if (prov.confidence != null) body.confidence = prov.confidence }
      await apiPost<ObjectPropertyDto>('/properties/object', body)
      relCandidates.value = relCandidates.value.filter(c => !(c.fromIri === fromIri && c.toIri === toIri && c.suggestedName === name))
      judgedRelations.value = judgedRelations.value.filter(c => !(c.fromIri === fromIri && c.toIri === toIri && c.suggestedName === name))
      await refresh()
    } catch (e) { setError(e) }
  }

  function dismissRelation(idx: number) {
    relCandidates.value = relCandidates.value.filter((_, i) => i !== idx)
  }

  /** 판정 후보를 목록에서 제외(등록하지 않음). 사람이 AI 판정을 뒤집는 '거부'. */
  function dismissJudged(fromIri: string, toIri: string, viaColumn: string) {
    judgedRelations.value = judgedRelations.value.filter(
      c => !(c.fromIri === fromIri && c.toIri === toIri && c.viaColumn === viaColumn))
  }

  async function fetchImpact(iri: string) {
    error.value = null
    try {
      impact.value = await apiGet<ImpactResult>('/impact?iri=' + encodeURIComponent(iri))
    } catch (e) { setError(e) }
  }

  async function listProjects() {
    error.value = null
    try { projects.value = await apiGet<string[]>('/projects') }
    catch (e) { setError(e) }
  }

  async function saveProject(name: string) {
    error.value = null
    try { projects.value = await apiPost<string[]>('/projects/save?name=' + encodeURIComponent(name), {}) }
    catch (e) { setError(e) }
  }

  async function loadProject(name: string) {
    error.value = null
    try {
      await apiPost<OntologyMetaDto>('/projects/load?name=' + encodeURIComponent(name), {})
      await refresh()
      select(null)
    } catch (e) { setError(e) }
  }

  async function askChat(question: string) {
    const q = question.trim()
    if (!q) return
    error.value = null
    chatMessages.value.push({ role: 'user', text: q })
    asking.value = true
    try {
      const res = await apiPost<ChatAnswer>('/ai/chat', { question: q })
      chatMessages.value.push({ role: 'assistant', text: res.answer })
    } catch (e) { setError(e) }
    finally { asking.value = false }
  }

  async function fetchTrash() {
    error.value = null
    try { trash.value = await apiGet<TrashEntry[]>('/trash') }
    catch (e) { setError(e) }
  }

  /** E11: 클래스를 휴지통으로 이동(컬럼·관계 포함 soft delete) 후 상태 갱신. */
  async function trashClass(iri: string) {
    error.value = null
    try {
      await apiPost('/trash', { iri })
      if (selectedIri.value === iri) selectedIri.value = null
      await refresh()
      await fetchTrash()
    } catch (e) { setError(e) }
  }

  async function restoreTrash(iri: string) {
    error.value = null
    try {
      await apiPost('/trash/restore?iri=' + encodeURIComponent(iri), {})
      await refresh()
      await fetchTrash()
    } catch (e) { setError(e) }
  }

  async function purgeTrash(iri: string) {
    error.value = null
    try {
      await apiDelete('/trash?iri=' + encodeURIComponent(iri))
      await fetchTrash()
    } catch (e) { setError(e) }
  }

  function clearError() { error.value = null }

  function reportError(e: unknown) { setError(e) }

  async function fetchReference() {
    error.value = null
    try {
      referenceMeta.value = await apiGet<ReferenceMetaDto>('/reference/meta')
      referenceClasses.value = await apiGet<ClassDto[]>('/reference/classes')
    } catch (e) { setError(e) }
  }

  async function loadReference(file: File) {
    error.value = null
    try { await apiUpload<ReferenceMetaDto>('/reference/load', file); await fetchReference() }
    catch (e) { setError(e) }
  }

  async function clearReference() {
    error.value = null
    try {
      await apiDelete('/reference')
      referenceClasses.value = []
      referenceMeta.value = null
    } catch (e) { setError(e) }
  }

  async function fetchAlignments() {
    error.value = null
    try { alignments.value = await apiGet<AlignmentDto[]>('/alignments') }
    catch (e) { setError(e) }
  }

  async function createAlignment(sourceIri: string, targetIri: string, matchType: MatchType, confidence?: number) {
    error.value = null
    try {
      await apiPost<AlignmentDto>('/alignments', { sourceIri, targetIri, matchType, confidence: confidence ?? null })
      await fetchAlignments()
    } catch (e) { setError(e) }
  }

  async function deleteAlignment(sourceIri: string, targetIri: string, matchType: MatchType) {
    error.value = null
    try {
      await apiDelete(`/alignments?sourceIri=${encodeURIComponent(sourceIri)}&targetIri=${encodeURIComponent(targetIri)}&matchType=${matchType}`)
      await fetchAlignments()
    } catch (e) { setError(e) }
  }

  function alignmentsOf(iri: string): AlignmentDto[] {
    return alignments.value.filter(a => a.sourceIri === iri)
  }

  return { classes, selectedIri, meta, error, selected, tree,
           reasonResult, reasoning, runReasoner, inferredChildrenOf,
           objectProperties, importDdl, importConnection, importSample, renameRelation,
           lastMerge, lastCollection,
           enrichCandidates, enriching, enrichSample, enrichCurrent, applyEnrichment, dismissEnrichment,
           scoredCandidates, scoredEnrichSample, scoredEnrichCurrent,
           confirmations, fetchConfirmations, confirm, deleteConfirmation,
           relCandidates, suggesting, suggestRelations, applyRelation, dismissRelation,
           judgedRelations, judging, judgeRelations, dismissJudged,
           impact, fetchImpact,
           projects, listProjects, saveProject, loadProject,
           chatMessages, asking, askChat,
           trash, fetchTrash, trashClass, restoreTrash, purgeTrash,
           referenceClasses, referenceMeta, alignments, fetchReference, loadReference, clearReference,
           fetchAlignments, createAlignment, deleteAlignment, alignmentsOf,
           refresh, select, createClass, saveClass, deleteClass, loadFile, exportTurtle,
           clearError, reportError }
})
