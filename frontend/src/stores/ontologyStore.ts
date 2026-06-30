import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiGet, apiPost, apiPatch, apiDelete, apiUpload, apiDownload, ApiError } from '../api/client'
import type { ClassDto, OntologyMetaDto } from '../api/types'
import { buildTree } from '../lib/buildTree'

export const useOntologyStore = defineStore('ontology', () => {
  const classes = ref<ClassDto[]>([])
  const selectedIri = ref<string | null>(null)
  const meta = ref<OntologyMetaDto | null>(null)
  const error = ref<string | null>(null)

  const selected = computed(() => classes.value.find(c => c.iri === selectedIri.value) ?? null)
  const tree = computed(() => buildTree(classes.value))

  function setError(e: unknown) {
    error.value = e instanceof ApiError ? e.message : (e instanceof Error ? e.message : String(e))
  }

  async function refresh() {
    classes.value = await apiGet<ClassDto[]>('/classes')
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

  function clearError() { error.value = null }

  function reportError(e: unknown) { setError(e) }

  return { classes, selectedIri, meta, error, selected, tree,
           refresh, select, createClass, saveClass, deleteClass, loadFile, exportTurtle,
           clearError, reportError }
})
