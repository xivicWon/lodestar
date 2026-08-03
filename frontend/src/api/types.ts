export interface AnnotationDto { property: string; value: string; lang: string | null }
export interface ClassDto { iri: string; label: string | null; superClasses: string[]; annotations: AnnotationDto[] }
export interface OntologyMetaDto { ontologyIri: string | null; baseIri: string; prefixes: Record<string, string>; counts: Record<string, number> }

export interface MergeSummary { reapplied: number; stale: number; staleIris: string[] }

/** 수집기가 **하지 못한 일** 한 항목(#114 → #129). 종류·사유코드·사유문·좌표·대상 다섯을 항상 갖는다. */
export type IssueKind = 'SKIPPED' | 'FAILED' | 'PARTIAL'
export interface CollectionIssue {
  kind: IssueKind
  reasonCode: string
  reason: string
  /** 좌표. `locatorScheme` 이 `line` 이면 `path#L11-L14`, `jdbc` 면 `jdbc://catalog/schema/object`. */
  locator: string
  target: string
}

/** 입력 경로와 그 좌표 규약. 백엔드 `SchemaSource.KIND_*` · `CollectionReport.locatorScheme` 과 짝이다. */
export type SourceKind = 'ddl' | 'jdbc' | 'sample'
export type LocatorScheme = 'line' | 'jdbc'

/**
 * 임포트 응답의 수집 보고(#129). `complete` 는 **실패·부분수집이 없다**는 뜻이고, 정당한 제외(SKIPPED)는
 * 완전 수집을 깨지 않는다 — 그래도 화면에는 사유와 함께 남는다.
 */
export interface CollectionReport {
  sourceKind: SourceKind
  locatorScheme: LocatorScheme
  collected: number
  skipped: number
  failed: number
  partial: number
  complete: boolean
  issues: CollectionIssue[]
  partials: CollectionIssue[]
}

export interface ImportResult { meta: OntologyMetaDto; merge: MergeSummary; collection: CollectionReport }

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

export type MatchType = 'EXACT' | 'CLOSE' | 'BROAD' | 'NARROW' | 'RELATED'
export interface ReferenceMetaDto { ontologyIri: string | null; source: string | null; classCount: number }
export interface AlignmentDto {
  sourceIri: string; targetIri: string; matchType: MatchType; confidence: number | null; provenance: string
}

export type Provenance = 'EXTRACTED' | 'INFERRED' | 'AMBIGUOUS'
export type RelationKind = 'FK' | 'NAMEPATTERN' | 'AI' | 'MANUAL'
export interface RelationProvenance { kind: RelationKind; provenance: Provenance; confidence?: number }
