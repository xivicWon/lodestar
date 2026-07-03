export interface AnnotationDto { property: string; value: string; lang: string | null }
export interface ClassDto { iri: string; label: string | null; superClasses: string[]; annotations: AnnotationDto[] }
export interface OntologyMetaDto { ontologyIri: string | null; baseIri: string; prefixes: Record<string, string>; counts: Record<string, number> }

export interface MergeSummary { reapplied: number; stale: number; staleIris: string[] }
export interface ImportResult { meta: OntologyMetaDto; merge: MergeSummary }

export interface InferredEdge { sub: string; sup: string }
export interface ReasonResult {
  consistent: boolean
  unsatisfiableClasses: string[]
  inferredSubClassOf: InferredEdge[]
}

export class ApiError extends Error {
  error: string
  targetIri: string | null
  constructor(error: string, message: string, targetIri: string | null) {
    super(message); this.name = 'ApiError'; this.error = error; this.targetIri = targetIri
  }
}

export interface ObjectPropertyDto {
  iri: string
  label: string | null
  domains: string[]
  ranges: string[]
  characteristics: string[]
  inverseOf: string | null
  annotations: AnnotationDto[]
}

export interface ConnectionInfo {
  host: string; port: number; database: string; user: string; password: string
  vendor?: string
}

export interface EnrichmentCandidate {
  targetIri: string
  currentName: string
  suggestedLabel: string
  description: string
}

export interface Variant {
  label: string
  count: number
}

export interface ScoredCandidate {
  targetIri: string
  currentName: string
  consensusLabel: string
  description: string
  agreement: number
  n: number
  variants: Variant[]
}

export interface ConfirmedFact {
  iri: string
  label: string
  kind: string
}

export interface AltTarget {
  toIri: string
  toLabel: string
  confidence: number
  matchType: string
}

export interface RelationEvidence {
  matchType: string
  matchStem: string
  matchedOn: string
  viaType: string | null
  viaFunctional: boolean
  targetHasSameColumn: boolean
  targetSimilarKeys: string[]
  cardinality: string
  cardinalityReason: string
  alternatives: AltTarget[]
  fromLabel: string
  toLabel: string
  fromColumns: string[]
  toColumns: string[]
}

export interface RelationCandidate {
  fromIri: string
  toIri: string
  viaColumn: string
  confidence: number
  suggestedName: string
  evidence: RelationEvidence
}

export interface JudgedCandidate {
  fromIri: string
  toIri: string
  viaColumn: string
  confidence: number
  suggestedName: string
  keep: boolean
  reason: string
  evidence: RelationEvidence
}

export interface ImpactResult {
  iri: string
  upstream: string[]
  downstream: string[]
}

export interface ChatAnswer { answer: string }

export interface TrashEntry { iri: string; label: string; trashedAt: number }
