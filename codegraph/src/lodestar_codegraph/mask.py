"""PII·시크릿 마스킹 단계 (#115 · L0-fix-5).

규칙은 이 패키지가 들고 있는 사본이 아니라 **리포 단일 원본**
(`docs/superpowers/specs/security/masking-rules.v0.json`)이 정한다. 사본은 배포 편의를 위한 것이며
표류하면 테스트가 붉어진다(tests/test_mask.py).

두 엔진(Kotlin `com.ontostudio.security.MaskingEngine` · 이 모듈)이 같은 입력에 같은 출력을 내야 한다.
그래서 정규식은 **ASCII 모드**로 컴파일한다 — Python 의 `\\b`·`[0-9]` 는 기본이 유니코드 인식이라
한글과 숫자가 붙은 자리에서 Java 와 경계 판정이 갈린다.

기록 원칙(#85): 마스킹 건수·규칙 id·클래스·좌표만 남기고 **원문은 어디에도 남기지 않는다.**
"""
from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass, field, replace

RULES_PATH = pathlib.Path(__file__).with_name("masking-rules.v0.json")


@dataclass(frozen=True)
class Rule:
    id: str
    cls: str
    regex: str
    value_group: int = 0
    luhn: bool = False
    kind: str = "ALLOW"
    # 대안 그룹 — 목록 순서대로 보고 처음 참여한 그룹을 가린다(따옴표 있는 값 / 없는 값 등).
    value_groups: tuple[int, ...] = ()

    def compiled(self) -> re.Pattern[str]:
        return re.compile(self.regex, re.ASCII)


@dataclass(frozen=True)
class Rules:
    spec_version: str
    template: str
    fill_char: str
    allowlist_default: bool
    allow: tuple[Rule, ...]
    detect: tuple[Rule, ...]
    # 명시적 시크릿 문맥이 이기는 allow 규칙 id. 여기 없는 allow 는 여전히 이긴다
    # (규칙 스펙 `policy.secretsOverrideAllowlist`).
    secrets_override_allowlist: bool = False
    secret_prefix: str = "SECRET."
    overridable_allow: frozenset[str] = frozenset()


@dataclass(frozen=True)
class MaskPolicy:
    """마스킹 정책. 기본값이 곧 수집 경로의 기본 동작이다."""

    disabled_classes: frozenset[str] = frozenset()
    allowlist_enabled: bool | None = None      # None = 규칙 스펙의 기본값
    length_preserving: bool = False            # SQL 리터럴처럼 길이 제약이 있는 자리
    # 경로 기반 예외는 두지 않는다 — 선언만 있고 아무도 읽지 않는 설정은 "지원한다" 는 거짓 신호다
    # (리뷰). 필요해지면 Kotlin `MaskPolicy` 와 함께 계약으로 추가한다.


@dataclass(frozen=True)
class MaskSpan:
    """마스킹 스팬.

    `start`·`end` 는 **이 엔진의 인덱스 단위(코드포인트)** 다 — Python 문자열을 그 좌표로 안전하게
    자르기 위해서다. Kotlin 엔진은 같은 자리를 UTF-16 코드 단위로 센다. 좌표를 **남기거나 두 엔진을
    비교할 때는** [spans_utf16]/[utf16_offset] 로 변환해야 한다(규칙 스펙 `spanContract`).
    """

    start: int
    end: int
    rule_id: str
    cls: str


@dataclass
class MaskResult:
    text: str
    spans: list[MaskSpan] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def masked(self) -> int:
        return len(self.spans)

    def by_class(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for s in self.spans:
            out[s.cls] = out.get(s.cls, 0) + 1
        return dict(sorted(out.items()))


_CACHE: dict[str, Rules] = {}


def load_rules(path: str | pathlib.Path | None = None) -> Rules:
    p = pathlib.Path(path) if path else RULES_PATH
    key = str(p)
    if key not in _CACHE:
        raw = json.loads(p.read_text(encoding="utf-8"))
        _CACHE[key] = Rules(
            spec_version=raw["specVersion"],
            template=raw["maskToken"]["template"],
            fill_char=raw["maskToken"]["lengthPreservingChar"],
            allowlist_default=bool(raw["policy"]["allowlistEnabled"]),
            allow=tuple(
                Rule(r["id"], r["class"], r["regex"], kind="ALLOW") for r in raw["allow"]
            ),
            detect=tuple(
                Rule(r["id"], r["class"], r["regex"], int(r.get("valueGroup", 0)),
                     bool(r.get("luhn", False)), r.get("kind", "DETECT"),
                     tuple(int(g) for g in r.get("valueGroups", ())))
                for r in raw["detect"]
            ),
            secrets_override_allowlist=bool(_sov(raw).get("enabled", False)),
            secret_prefix=str(_sov(raw).get("detectPrefix", "SECRET.")),
            overridable_allow=frozenset(_sov(raw).get("overridableAllow", ())),
        )
    return _CACHE[key]


def _sov(raw: dict) -> dict:
    """규칙 스펙의 `policy.secretsOverrideAllowlist` — 없으면 종전 동작(allow 가 항상 이긴다)."""
    return raw.get("policy", {}).get("secretsOverrideAllowlist", {}) or {}


def _luhn(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        if not ch.isdigit():
            return False
        d = int(ch)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def _token(rules: Rules, cls: str, original: str, length_preserving: bool) -> str:
    if not length_preserving:
        return rules.template.replace("{class}", cls)
    if not original:
        return rules.fill_char
    # 개행은 보존한다 — 여러 줄 값(PEM 개인 키 등)을 통째로 덮으면 뒤따르는 `path#Lnn` 좌표가 밀린다.
    return "".join("\n" if c == "\n" else rules.fill_char for c in original)


def detect(text: str, policy: MaskPolicy | None = None,
           rules: Rules | None = None) -> list[MaskSpan]:
    """탐지만 한다(치환 없음). allow 스팬과 겹치는 탐지는 버리고, 겹치는 탐지끼리는 스펙 순서가 이긴다."""
    rules = rules or load_rules()
    policy = policy or MaskPolicy()
    allow_on = rules.allowlist_default if policy.allowlist_enabled is None else policy.allowlist_enabled

    # allow 스팬은 **어느 규칙이 만들었는지** 와 함께 든다. 스팬만 모으면 시크릿이 이길 수 있는
    # allow 와 그러면 안 되는 allow(추적 근거·멱등 토큰)를 구분할 자리가 없다.
    allowed: list[tuple[str, int, int]] = []
    if allow_on:
        for rule in rules.allow:
            for m in rule.compiled().finditer(text):
                allowed.append((rule.id, m.start(), m.end()))

    kept: list[MaskSpan] = []
    for rule in rules.detect:
        if rule.cls in policy.disabled_classes:
            continue
        for m in rule.compiled().finditer(text):
            # 대안 그룹은 목록 순서대로 보고 처음 참여한 것을 쓴다(규칙 스펙 `maskToken.valueGroupsNote`).
            group = rule.value_group
            for g in rule.value_groups:
                if m.group(g) is not None:
                    group = g
                    break
            start, end = m.span(group)
            if start < 0 or start == end:
                continue
            if rule.luhn and not _luhn(text[start:end]):
                continue
            # 명시적 시크릿 문맥은 **스펙이 지목한** allow 규칙만 이긴다 — Kotlin 엔진과 같은 규칙이다.
            is_secret = rules.secrets_override_allowlist and rule.id.startswith(rules.secret_prefix)
            if any(a < end and start < b and not (is_secret and rid in rules.overridable_allow)
                   for rid, a, b in allowed):
                continue
            if any(s.start < end and start < s.end for s in kept):
                continue
            kept.append(MaskSpan(start, end, rule.id, rule.cls))
    kept.sort(key=lambda s: (s.start, s.end, s.rule_id))
    return kept


def mask_text(text: str, policy: MaskPolicy | None = None,
              rules: Rules | None = None) -> MaskResult:
    rules = rules or load_rules()
    policy = policy or MaskPolicy()
    spans = detect(text, policy, rules)
    out = text
    for s in reversed(spans):
        out = out[:s.start] + _token(rules, s.cls, text[s.start:s.end], policy.length_preserving) + out[s.end:]
    counts: dict[str, int] = {}
    for s in spans:
        counts[s.rule_id] = counts.get(s.rule_id, 0) + 1
    return MaskResult(out, spans, dict(sorted(counts.items())))


def mask_field(value: str | None, ledger: "MaskLedger | None" = None,
               policy: MaskPolicy | None = None) -> str | None:
    """산출물에 실리는 텍스트 필드 하나를 마스킹한다. 수집 경로가 쓰는 진입점."""
    if not value:
        return value
    r = mask_text(value, policy)
    if ledger is not None:
        ledger.add(r)
    return r.text


class MaskLedger:
    """한 수집 실행의 마스킹 집계 — 무엇을(클래스·규칙) 몇 건 가렸는지. 원문은 담지 않는다."""

    def __init__(self) -> None:
        self.by_rule: dict[str, int] = {}
        self.by_class: dict[str, int] = {}
        self.fields = 0

    def add(self, result: MaskResult) -> None:
        if result.spans:
            self.fields += 1
        for rule_id, n in result.counts.items():
            self.by_rule[rule_id] = self.by_rule.get(rule_id, 0) + n
        for cls, n in result.by_class().items():
            self.by_class[cls] = self.by_class.get(cls, 0) + n

    @property
    def total(self) -> int:
        return sum(self.by_rule.values())

    def summary(self) -> dict:
        return {
            "spec_version": load_rules().spec_version,
            "masked_total": self.total,
            "masked_fields": self.fields,
            "by_class": dict(sorted(self.by_class.items())),
            "by_rule": dict(sorted(self.by_rule.items())),
        }


def with_length_preserving(policy: MaskPolicy | None) -> MaskPolicy:
    return replace(policy or MaskPolicy(), length_preserving=True)


def spans_utf16(text: str, spans: list[MaskSpan]) -> list[MaskSpan]:
    """스팬 좌표를 UTF-16 코드 단위로 변환한다 — 기록·교차 엔진 비교용 진입점.

    이 변환을 빼면 BMP 밖 문자가 앞에 있는 입력에서 Kotlin 이 보는 좌표와 어긋난다.
    """
    return [MaskSpan(utf16_offset(text, s.start), utf16_offset(text, s.end), s.rule_id, s.cls)
            for s in spans]


def utf16_offset(text: str, index: int) -> int:
    """코드포인트 인덱스 → **UTF-16 코드 단위** 오프셋.

    스팬 좌표의 공식 단위는 UTF-16 코드 단위다(규칙 스펙 `spanContract`). Kotlin/Java 문자열
    인덱스가 그 단위이며, Python 은 코드포인트로 세므로 증거를 쓸 때 변환해야 BMP 밖 문자
    (이모지 등)가 앞에 있어도 두 엔진의 스팬이 같다.
    """
    return len(text[:index].encode("utf-16-le")) // 2
