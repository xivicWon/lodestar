from __future__ import annotations
from dataclasses import dataclass, field

EXTRACTED = "EXTRACTED"
INFERRED = "INFERRED"
AMBIGUOUS = "AMBIGUOUS"


@dataclass
class Node:
    id: str
    kind: str            # "file" | "type" | "function"
    label: str
    qualified_name: str
    path: str
    lang: str            # "java" | "kotlin" | ""
    community: int | None = None
    degree: int = 0
    god_node: bool = False


@dataclass
class Edge:
    id: int
    src: str             # serialized as "from"
    dst: str             # serialized as "to"
    kind: str            # contains|imports|extends|implements|calls
    provenance: str      # EXTRACTED|INFERRED|AMBIGUOUS
    confidence: float
    alternatives: list[str] = field(default_factory=list)
