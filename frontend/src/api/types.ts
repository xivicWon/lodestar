export interface AnnotationDto { property: string; value: string; lang: string | null }
export interface ClassDto { iri: string; label: string | null; superClasses: string[]; annotations: AnnotationDto[] }
export interface OntologyMetaDto { ontologyIri: string | null; baseIri: string; prefixes: Record<string, string>; counts: Record<string, number> }

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
}

export interface EnrichmentCandidate {
  targetIri: string
  currentName: string
  suggestedLabel: string
  description: string
}

export interface RelationCandidate {
  fromIri: string
  toIri: string
  viaColumn: string
  confidence: number
  suggestedName: string
}

export interface ImpactResult {
  iri: string
  upstream: string[]
  downstream: string[]
}

export interface ChatAnswer { answer: string }
