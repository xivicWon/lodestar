"""#115 마스킹 단계 — 규칙 엔진 단위 검증.

gold(#99) 코퍼스 전수 검증은 tests/test_mask_gold.py 가 맡는다. 여기서는 엔진의 계약을 본다:
결정성 · allowlist 우선 · 길이 보존 모드 · 클래스 비활성화 · 원문 미기록.
"""
from __future__ import annotations

import pathlib
import re

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
    """텍스트만 비교하면 좌표·규칙 집계의 비결정성을 놓친다(리뷰 LOD-064)."""
    text = "rrn=900101-1234567 mail=a.b@c.co.kr ip=203.0.113.47"
    a, b = mask_text(text), mask_text(text)
    assert a.text == b.text
    assert a.counts == b.counts
    assert [(s.start, s.end, s.rule_id, s.cls) for s in a.spans] == \
           [(s.start, s.end, s.rule_id, s.cls) for s in b.spans]


def test_github_fine_grained_pat_is_masked():
    """classic 토큰만 보면 fine-grained PAT 가 원문으로 남는다(리뷰 LOD-078)."""
    pat = "github_pat_" + "1" * 22 + "_" + "a" * 59
    out = mask_text(f"github.token={pat}").text
    assert pat not in out
    assert out == "github.token=[MASKED:GITHUB_TOKEN]"


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


def test_url_credential_with_at_sign_is_fully_masked():
    """값에 '@' 가 있으면 첫 '@' 에서 끊겨 나머지가 평문으로 남는다 — 부분 마스킹은 누출이다."""
    r = mask_text("postgres://user:p@ssw0rd-x@host:5432/db")
    assert "ssw0rd" not in r.text, r.text
    assert r.text == "postgres://user:[MASKED:URL_CREDENTIAL]@host:5432/db"
    # 콜론이 들어간 값도 통째로 가린다
    assert "my:pass" not in mask_text("mysql://admin:my:pass@host/db").text


def test_quoted_secret_with_space_is_fully_masked():
    """따옴표 안 공백이 있는 시크릿은 첫 공백에서 끊겨 뒤가 남는다."""
    for text, leaked in (
        ('password = "abc def"', "def"),
        ("app.secret = 'abc def'", "def"),
        ('{"apiKey": "tok en 123"}', "en 123"),
    ):
        out = mask_text(text).text
        assert leaked not in out, f"{text} -> {out}"


def test_rules_are_portable_ascii_boundary():
    """\\b 의 의미가 두 엔진에서 같아야 한다 — Python 은 ASCII 모드로 컴파일한다."""
    rules = load_rules()
    for r in rules.allow + rules.detect:
        assert "\\d" not in r.regex and "\\w" not in r.regex, r.id
        assert "(?P<" not in r.regex, r.id
        # Java/Kotlin 형식의 이름있는 그룹도 거부한다 — Python 에서 컴파일되지 않는다(리뷰 LOD-053).
        # 역참조 lookbehind `(?<!`·`(?<=` 는 허용해야 하므로 '<' 뒤에 문자가 오는 경우만 잡는다.
        assert not re.search(r"\(\?<[A-Za-z]", r.regex), r.id


def test_rule_set_is_exactly_the_contracted_one():
    """사본 3종을 똑같이 잘못 바꾸면 해시 검사는 통과한다 — 규칙 구성 자체를 못박는다(리뷰 LOD-054)."""
    rules = load_rules()
    assert [r.id for r in rules.allow] == [
        "ALLOW.MASK_TOKEN", "ALLOW.GIT_SHA", "ALLOW.CONTENT_HASH", "ALLOW.UUID",
        "ALLOW.JDBC_URL", "ALLOW.TIMESTAMP", "ALLOW.INTERNAL_ID",
    ]
    assert [r.id for r in rules.detect] == [
        "SECRET.AWS_ACCESS_KEY_ID", "SECRET.AWS_SECRET_ACCESS_KEY", "SECRET.GITHUB_TOKEN",
        "SECRET.SLACK_TOKEN", "SECRET.JWT",
        "SECRET.PRIVATE_KEY_BLOCK", "SECRET.URL_CREDENTIAL", "SECRET.KEYED_VALUE",
        "PII.KR_RRN", "PII.EMAIL", "PII.KR_PHONE", "PII.CARD_NO_DELIMITED", "PII.CARD_NO_PLAIN",
        "PII.KR_BANK_ACCOUNT", "PII.KR_BIZ_NO", "PII.IP_ADDRESS", "PII.KR_ADDRESS", "PII.KR_NAME",
    ]


PEM = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAxTOaWJ7fake0000000000000000000000000000000000000
AAAAB3NzaC1yc2EAAAADAQABAAABgQfake111111111111111111111111111111
-----END RSA PRIVATE KEY-----"""


def test_private_key_block_body_is_masked_not_just_the_header():
    """헤더만 가리면 본문이 그대로 남는다 — 리뷰 LOD-052 의 회귀 테스트."""
    r = mask_text(f"key = '''{PEM}'''")
    assert "MIIEowIBAAKCAQEA" not in r.text
    assert "-----END RSA PRIVATE KEY-----" not in r.text
    assert r.counts == {"SECRET.PRIVATE_KEY_BLOCK": 1}


def test_private_key_variants_are_masked():
    for kind in ("RSA ", "EC ", "OPENSSH ", "PGP ", ""):
        body = f"-----BEGIN {kind}PRIVATE KEY-----\nSECRETBODY0000\n-----END {kind}PRIVATE KEY-----"
        assert "SECRETBODY0000" not in mask_text(body).text, kind


def test_truncated_private_key_masks_the_header_only():
    """END 가 없는 잘린 입력에서 뒤를 끝까지 삼키면 무관한 내용까지 지운다."""
    out = mask_text("-----BEGIN PRIVATE KEY-----\nTAIL_MARKER").text
    assert "BEGIN PRIVATE KEY" not in out
    assert "TAIL_MARKER" in out


def test_utf16_offset_matches_kotlin_string_indexing():
    """스팬 좌표의 단위는 UTF-16 코드 단위다(규칙 스펙 `spanContract`).

    Kotlin/Java 의 String 인덱스가 그 단위이고 Python 은 코드포인트로 센다. BMP 안에서는 두 값이
    같아 차이가 드러나지 않으므로, **BMP 밖 문자**로 계약을 고정한다 — 이 검사가 없으면 증거의
    좌표 변환을 지워도 gold 코퍼스(BMP 전용)로는 아무것도 붉어지지 않는다.
    """
    from lodestar_codegraph.mask import utf16_offset

    # BMP 전용 텍스트: 코드포인트 인덱스와 같다
    assert utf16_offset("abc홍길동", 4) == 4
    # 이모지(서로게이트 페어)는 UTF-16 에서 2단위를 차지한다
    assert utf16_offset("😀ab", 1) == 2
    assert utf16_offset("😀😀x", 2) == 4

    # 탐지 스팬을 그 단위로 옮기면 Kotlin 이 같은 문자열에서 보는 인덱스와 일치한다
    text = "😀 mail=hong@example.com"
    span = mask_text(text).spans[0]
    assert text[span.start:span.end] == "hong@example.com"
    assert utf16_offset(text, span.start) == span.start + 1


def test_spans_utf16_converts_for_records_and_cross_engine_compare():
    """엔진의 raw 스팬은 코드포인트 단위다 — 기록·비교 전에 변환해야 Kotlin 좌표와 같다."""
    from lodestar_codegraph.mask import detect, spans_utf16

    text = "😀 mail=hong@example.com"
    raw = detect(text)
    conv = spans_utf16(text, raw)
    assert [(s.start, s.end) for s in raw] == [(7, 23)]      # 코드포인트
    assert [(s.start, s.end) for s in conv] == [(8, 24)]     # UTF-16 (Kotlin 이 보는 값)
    assert text[raw[0].start:raw[0].end] == "hong@example.com"
    # BMP 전용 입력에서는 두 좌표가 같다 — 그래서 gold 코퍼스만으로는 이 계약이 검증되지 않는다
    bmp = "mail=hong@example.com"
    assert [(s.start, s.end) for s in detect(bmp)] == [(s.start, s.end) for s in spans_utf16(bmp, detect(bmp))]


def test_length_preserving_keeps_newlines_so_line_numbers_hold():
    """여러 줄 값을 '*' 로 통째로 덮으면 개행이 사라져 뒤따르는 행 좌표가 밀린다."""
    text = f"a\n'{PEM}'\nMARKER"
    out = mask_text(text, MaskPolicy(length_preserving=True)).text
    assert len(out) == len(text)
    assert out.count("\n") == text.count("\n")
    assert out.split("\n").index("MARKER") == text.split("\n").index("MARKER")
    assert "MIIEowIBAAKCAQEA" not in out


# ---- allowlist 우선순위 · 부분 마스킹 0건 (리뷰 후속) --------------------------------------


def test_explicit_secret_context_beats_the_allowlist():
    """allowlist 의 근거는 전부 **식별성**이다 — 그 논거로 명시적 시크릿 문맥을 덮으면 안 된다.

    `ABC123456` 은 ALLOW.INTERNAL_ID(`[A-Z]{1,4}[0-9]{6,15}`)와 겹치지만 `password=` 문맥에서는
    비밀이다. 문맥이 없으면 여전히 음성이다 — allowlist 를 통째로 끄는 변경이 아니다.
    """
    from lodestar_codegraph.mask import mask_field

    assert mask_field("password=ABC123456", None, None) == "password=[MASKED:PASSWORD]"
    assert mask_field("apikey=AB1234567890", None, None) == "apikey=[MASKED:PASSWORD]"
    assert mask_field("order=ORD202401000001", None, None) == "order=ORD202401000001"


def test_already_masked_token_is_never_re_masked_in_secret_context():
    """멱등성은 예외다 — 이미 가려진 자리를 다시 가리면 토큰이 중첩된다(#85)."""
    from lodestar_codegraph.mask import mask_field

    once = mask_field("password=ABC123456", None, None)
    assert mask_field(once, None, None) == once


def test_every_detected_span_is_fully_replaced():
    """스팬의 모든 문자가 치환돼야 한다 — 원문 부재만 보면 한 글자 남기는 구현이 통과한다(LOD-107)."""
    from lodestar_codegraph.mask import MaskPolicy, mask_field, detect

    policy = MaskPolicy(length_preserving=True)
    for text in ("password=ABC123456",
                 "aws_secret_access_key = " + "A" * 41,
                 "contact hong@example.com now",
                 "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA1234\n"):
        out = mask_field(text, None, policy)
        for s in detect(text, policy):
            assert set(out[s.start:s.end]) <= {"*", "\n"}, (text, out[s.start:s.end])


def test_aws_secret_longer_than_forty_chars_leaves_no_plaintext_suffix():
    from lodestar_codegraph.mask import mask_field

    out = mask_field("aws_secret_access_key = " + "A" * 41, None, None)
    assert out == "aws_secret_access_key = [MASKED:AWS_SECRET_ACCESS_KEY]"


def test_truncated_private_key_masks_body_but_stops_at_non_base64():
    """종료 표식이 없어도 Base64 본문까지는 가린다. 뒤를 무한정 삼키지는 않는다."""
    from lodestar_codegraph.mask import mask_field

    text = ("-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA1234\nabcdEFGH0123\n"
            "무관한 뒷내용은 남는다")
    out = mask_field(text, None, None)
    assert "MIIEowIBAAKCAQEA1234" not in out
    assert "abcdEFGH0123" not in out
    assert "무관한 뒷내용은 남는다" in out


def test_secret_keyword_must_be_a_whole_token_inside_the_key():
    """키워드 뒤에 아무 소문자나 붙여도 되면 `secret`+`ary` 가 비밀 키로 읽혀 무관한 값이 가려진다."""
    from lodestar_codegraph.mask import mask_field

    assert mask_field("secretary=Kim", None, None) == "secretary=Kim"
    assert mask_field("tokenizer=bert", None, None) == "tokenizer=bert"
    # 진짜 비밀 키는 계속 가린다 — camelCase·`_` 경계를 넘은 접미사는 인정한다
    assert mask_field("aws.secretAccessKey=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                      None, None) == "aws.secretAccessKey=[MASKED:AWS_SECRET_ACCESS_KEY]"
    assert mask_field("password_hash=abc123", None, None) == "password_hash=[MASKED:PASSWORD]"


def test_quoted_secret_value_does_not_cross_a_line():
    """개행을 넘으면 다음 줄의 닫는 따옴표까지 한 값이 되어 그 사이 설정이 통째로 사라진다."""
    from lodestar_codegraph.mask import mask_field

    out = mask_field('password="abc\nunrelated_setting=keep-me\nother="', None, None)
    assert "unrelated_setting=keep-me" in out, out
    # 반대편 구멍도 막는다: 닫히지 않은 값을 매칭 실패로 두면 그 값이 평문으로 남는다
    assert out == 'password="[MASKED:PASSWORD]\nunrelated_setting=keep-me\nother="', out
