"""#115 마스킹 단계 — 규칙 엔진 단위 검증.

gold(#99) 코퍼스 전수 검증은 tests/test_mask_gold.py 가 맡는다. 여기서는 엔진의 계약을 본다:
결정성 · allowlist 우선 · 길이 보존 모드 · 클래스 비활성화 · 원문 미기록.
"""
from __future__ import annotations

import pathlib

from lodestar_codegraph.mask import MaskPolicy, load_rules, mask_text

SPEC = pathlib.Path(__file__).resolve().parents[2] / "docs/superpowers/specs/security/masking-rules.v0.json"


def test_rule_spec_copy_matches_canonical():
    """사본이 원본과 다르면 두 엔진이 다른 규칙으로 마스킹한다 — 그 자체가 결함이다."""
    import hashlib

    from lodestar_codegraph import mask as m

    canonical = hashlib.sha256(SPEC.read_bytes()).hexdigest()
    shipped = hashlib.sha256(m.RULES_PATH.read_bytes()).hexdigest()
    assert canonical == shipped, f"규칙 사본 표류: {m.RULES_PATH}"


def test_masks_email_and_reports_rule_id():
    r = mask_text("contact hong@example.com now")
    assert "hong@example.com" not in r.text
    assert r.text == "contact [MASKED:EMAIL] now"
    assert r.counts == {"PII.EMAIL": 1}
    assert [(s.rule_id, s.cls) for s in r.spans] == [("PII.EMAIL", "EMAIL")]


def test_never_records_plaintext():
    """마스킹 기록에 원문이 남으면 마스킹이 아니라 이전(移轉)이다(#85)."""
    r = mask_text("password=P@ssw0rd-not-real-123")
    blob = repr(r.counts) + repr([(s.start, s.end, s.rule_id, s.cls) for s in r.spans])
    assert "P@ssw0rd" not in blob


def test_deterministic():
    text = "rrn=900101-1234567 mail=a.b@c.co.kr ip=203.0.113.47"
    assert mask_text(text).text == mask_text(text).text


def test_allowlist_beats_detection():
    sha = "3c27259fe6c979e00912c5e3686c611a28cb977e"
    assert mask_text(f"build={sha}").text == f"build={sha}"
    # allowlist 를 끄면 같은 값이 가려진다 — allowlist 가 실제로 판정을 바꾼다는 증거
    off = MaskPolicy(allowlist_enabled=False)
    assert mask_text(f"token={sha}", off).text != f"token={sha}"


def test_length_preserving_mode_keeps_width():
    r = mask_text("'900101-1234567'", MaskPolicy(length_preserving=True))
    assert r.text == "'" + "*" * len("900101-1234567") + "'"


def test_disabled_class_is_not_masked():
    p = MaskPolicy(disabled_classes=frozenset({"NAME"}))
    assert mask_text("owner=홍길동", p).text == "owner=홍길동"
    assert mask_text("owner=홍길동").text == "owner=[MASKED:NAME]"


def test_luhn_guard_on_undelimited_16_digits():
    assert mask_text("no=4111111111111111").text == "no=[MASKED:CARD_NO]"
    assert mask_text("qty=1234567812345678").text == "qty=1234567812345678"  # Luhn 실패 → 카드 아님


def test_overlapping_detections_resolve_by_spec_order():
    r = mask_text("aws.accessKeyId=AKIAIOSFODNN7EXAMPLE")
    assert r.counts == {"SECRET.AWS_ACCESS_KEY_ID": 1}


def test_url_credential_keeps_structure():
    r = mask_text("jdbc:postgresql://app:s3cr3t-pw@db:5432/lodestar")
    assert "s3cr3t-pw" not in r.text
    assert r.text.startswith("jdbc:postgresql://app:")
    assert r.text.endswith("@db:5432/lodestar")


def test_rules_are_portable_ascii_boundary():
    """\\b 의 의미가 두 엔진에서 같아야 한다 — Python 은 ASCII 모드로 컴파일한다."""
    rules = load_rules()
    for r in rules.allow + rules.detect:
        assert "\\d" not in r.regex and "\\w" not in r.regex, r.id
        assert "(?P<" not in r.regex, r.id
