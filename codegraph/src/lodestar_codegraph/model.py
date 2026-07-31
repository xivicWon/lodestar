from __future__ import annotations
from dataclasses import dataclass, field

EXTRACTED = "EXTRACTED"
INFERRED = "INFERRED"
AMBIGUOUS = "AMBIGUOUS"


# 수집 항목의 처리 종류 — 조용한 skip 을 없애기 위한 어휘(#114). DB 트랙 IssueKind 와 같은 뜻이다.
SKIPPED = "skipped"
FAILED = "failed"
PARTIAL = "partial"

# 사유 코드 — gold(#99) failures.json 의 reported[].kind 어휘와 같은 값을 쓴다(대조 가능해야 한다).
UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"
PARSE_ERROR = "PARSE_ERROR"
IGNORED_BY_CONFIG = "IGNORED_BY_CONFIG"


@dataclass(frozen=True)
class Issue:
    """수집기가 **하지 못한 일**. 사유 없이 건수만 세거나 로그에만 남기면 미보고다(gold R-F-2).

    locator 는 `rel/path#L12-L14`(한 행이면 `rel/path#L16`) 형식이며, 세는 단위는 파일이다(R-F-4).
    """
    kind: str            # SKIPPED | FAILED | PARTIAL
    reason_code: str
    reason: str
    locator: str
    target: str

    def doc(self) -> dict:
        return {"kind": self.kind, "reason_code": self.reason_code, "reason": self.reason,
                "locator": self.locator, "target": self.target}


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
    # 이 사실이 나온 파일의 수집 상태. "parsed" | "partial" — 부분 추출을 완전 추출로
    # 위장하지 않기 위해 산출물에 남긴다(#114 · I1 §3.3 의 confidence 상한 근거).
    status: str = "parsed"


@dataclass
class Edge:
    id: int
    src: str             # serialized as "from"
    dst: str             # serialized as "to"
    kind: str            # contains|imports|extends|implements|calls
    provenance: str      # EXTRACTED|INFERRED|AMBIGUOUS
    confidence: float
    alternatives: list[str] = field(default_factory=list)
