#!/usr/bin/env python3
"""#115 마스킹 단계 프로브 — Python 엔진 + 코드 수집 경로.

이 프로브는 두 가지를 잰다.

1. **엔진 증거**(`runs/run-mask-gold-001/engine-python.json`): #99 gold PII 코퍼스 3파일을 Python
   엔진으로 마스킹해 스팬·클래스·규칙·마스킹 결과 해시를 남긴다. Kotlin 엔진이 같은 실행을 하고
   같은 형식으로 증거를 남기며(`engine-kotlin.json`), 두 증거의 일치는 `verify_masking.py` 가 본다.
   두 엔진이 다르면 "두 수집 경로에 같은 정책을 적용했다" 는 주장이 거짓이 된다.

2. **코드 수집 경로 증거**(`runs/run-mask-code-001/emit-code.json`): codegraph 산출 단계(emit)에
   마스킹이 실제로 걸려 있는지를, gold 양성 값을 산출물 텍스트 필드에 심어 확인한다.
   #88 F8 이 기록한 gold 공백(수집 확장자 `.kt/.java` 안에 양성이 없다) 때문에 실제 수집 실행으로는
   이 단계를 측정할 수 없다 — 픽스처를 임의로 만들어 gold 를 흉내내지 않고, **측정한 것이 무엇인지**
   증거에 명시한다.

원문은 증거에 적지 않는다(#85). 스팬은 좌표·규칙·클래스만 남긴다.

    python3 docs/superpowers/specs/bench/masking/probe_masking.py            # 증거 생성
    python3 docs/superpowers/specs/bench/masking/probe_masking.py --check    # 표류 검사
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[4]
GOLD = REPO / "docs/superpowers/specs/gold"
RUNS = HERE / "runs"
ENGINE_OUT = RUNS / "run-mask-gold-001" / "engine-python.json"
CODE_OUT = RUNS / "run-mask-code-001" / "emit-code.json"

sys.path.insert(0, str(REPO / "codegraph/src"))
from lodestar_codegraph.emit import build_and_write  # noqa: E402
from lodestar_codegraph.mask import (  # noqa: E402
    MaskPolicy, detect, load_rules, mask_text, spans_utf16, utf16_offset,
)
from lodestar_codegraph.model import EXTRACTED, Edge, Node  # noqa: E402


def sha256_bytes(b: bytes) -> str:
    return "sha256:" + hashlib.sha256(b).hexdigest()


def gold_pii() -> dict:
    return json.loads((GOLD / "pii.json").read_text(encoding="utf-8"))


def engine_evidence() -> dict:
    pii = gold_pii()
    files = []
    for f in pii["scope"]["files"]:
        raw = (REPO / f["path"]).read_text(encoding="utf-8")
        result = mask_text(raw)
        files.append({
            "sourceId": f["sourceId"],
            "contentHash": sha256_bytes(raw.encode("utf-8")),
            # 마스킹 결과는 해시로만 남긴다 — 원문·마스킹 텍스트를 증거에 적지 않는다(#85).
            "maskedTextHash": sha256_bytes(result.text.encode("utf-8")),
            "maskedSpans": len(result.spans),
            # 좌표 단위는 UTF-16 코드 단위다(규칙 스펙 `spanContract`) — Kotlin 문자열 인덱스와 맞춘다.
            "spans": [
                {
                    "start": utf16_offset(raw, s.start),
                    "end": utf16_offset(raw, s.end),
                    "ruleId": s.rule_id,
                    "class": s.cls,
                    "line": 1 + raw[: s.start].count("\n"),
                }
                for s in result.spans
            ],
            "byClass": result.by_class(),
            "byRule": result.counts,
        })
    return {
        "evidenceVersion": "mask-engine-evidence/v1",
        "engine": "python:lodestar_codegraph.mask",
        "specVersion": load_rules().spec_version,
        "goldSetVersion": pii["goldSetVersion"],
        "files": files,
    }


# 산출물이 텍스트를 실을 수 있는 모든 자리 — 하나라도 관문 밖이면 그 자리로 원문이 새어나간다.
# `meta_key` 는 메타데이터의 **문자열 키** 자리다. 값만 심으면 키를 가리지 않는 구현에서도
# "원문 잔존 0건" 증거가 통과한다 — 키에 원문을 넣는 것이 값 관문을 우회하는 경로다(리뷰 LOD-113).
SINKS = ("label", "qualified_name", "path", "alternatives", "meta", "meta_key")


def field_for(index: int) -> str:
    return SINKS[index % len(SINKS)]


def _plant(texts: list[str], meta_text: str) -> tuple[str, dict, bool]:
    """텍스트를 산출물의 텍스트 자리에 심고 emit 을 돌린 뒤 **기록된 파일**을 읽는다.

    각 양성을 **모든 sink 에** 심는다(양성 × sink 전 조합). 하나씩 돌려 심으면 sink 별 관문이
    대부분 미검증으로 남는다 — sink 목록만 증거에 적히고 실제로는 5분의 1만 지나간다(리뷰 LOD-070).
    """
    nodes, edges, meta_notes, meta_keys = [], [], [], {}
    for n, text in enumerate(texts):
        for k, field in enumerate(SINKS):
            nid = f"type:P{n:03d}S{k}"
            nodes.append(Node(
                id=nid,
                kind="type",
                label=text if field == "label" else f"P{n:03d}",
                qualified_name=text if field == "qualified_name" else f"com.acme.P{n:03d}",
                path=text if field == "path" else f"src/P{n:03d}.kt",
                lang="kotlin",
            ))
            if field == "alternatives":
                edges.append(Edge(len(edges) + 1, nid, nid, "calls", EXTRACTED, 1.0, [text]))
            if field == "meta":
                meta_notes.append(text)
            if field == "meta_key":
                # 키가 마스킹되면 서로 다른 키가 한 토큰으로 접힐 수 있으므로 값에 출처를 남긴다.
                meta_keys[text] = f"owner-count-{n:03d}" 
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "codegraph.json"
        # #113 은 노드마다 content_hash 를 요구한다(emit 이 없으면 예외를 던진다). 이 프로브의
        # 노드는 합성이라 실제 파일이 없으므로, **마스킹 전 원문 경로**를 키로 합성 해시를 준다 —
        # 마스킹된 경로로 키를 잡으면 PII 가 섞인 경로의 노드만 신원이 비어 계약이 깨진다.
        hashes = {n.path: "sha256:" + f"{i:064x}" for i, n in enumerate(nodes)}
        doc = build_and_write(
            nodes, edges,
            {"source_root": meta_text, "notes": meta_notes, "by_owner": meta_keys}, str(out),
            file_hashes=hashes,
        )
        # 반환값이 아니라 **디스크에 기록된 산출물**을 검사한다 — 새어나가는 자리는 파일이다.
        artifact = out.read_text(encoding="utf-8")
    ids_ok = [n["id"] for n in doc["nodes"]] == sorted(n.id for n in nodes)
    return artifact, doc["meta"]["masking"], ids_ok


def code_path_evidence() -> dict:
    """codegraph emit 단계에 마스킹이 걸려 있는가 — gold 양성을 산출물 텍스트 필드에 심어 확인한다.

    두 변형을 따로 잰다.

    - `withLineContext`: 원본 코퍼스의 **그 줄 전체**를 심는다. 수집된 문자열·설정 줄이 산출물에
      실리는 실제 형태이며, 이것이 코드 경로의 게이트 관측이다.
    - `bareValue`: 값만 떼어 심는다. 키 문맥에 의존하는 규칙(SECRET.KEYED_VALUE)은 여기서 발화할 수
      없다 — 문맥 없는 40자 난수는 결정론적 규칙으로 해시·토큰과 구별되지 않는다(gold 음성 GIT_SHA·
      CONTENT_HASH 가 정확히 그 함정이다). 미탐을 숨기지 않고 측정값으로 남긴다.
    """
    pii = gold_pii()
    positives = [i for i in pii["items"] if i["expect"] == "MASKED"]
    negatives = [i for i in pii["items"] if i["expect"] == "NOT_MASKED"]
    lines = {
        f["sourceId"]: (REPO / f["path"]).read_text(encoding="utf-8").split("\n")
        for f in pii["scope"]["files"]
    }

    def line_of(item: dict) -> str:
        no = int(item["ref"]["locator"].rsplit("#L", 1)[1])
        return lines[item["ref"]["sourceId"]][no - 1]

    variants = {}
    for name, texts in (
        ("withLineContext", [line_of(i) for i in positives]),
        ("bareValue", [i["value"]["text"] for i in positives]),
    ):
        artifact, summary, ids_ok = _plant(texts, "/tmp/" + negatives[0]["value"]["text"])
        survivors = [i["id"] for i in positives if i["value"]["text"] in artifact]
        variants[name] = {
            "plantedPositives": len(texts),
            "unmaskedInArtifact": survivors,
            "unmasked": len(survivors),
            "negativePreservedInMeta": negatives[0]["value"]["text"] in artifact,
            "idsPreserved": ids_ok,
            "maskingSummary": summary,
        }

    return {
        "evidenceVersion": "mask-emit-evidence/v2",
        "track": "code",
        "probe": "lodestar_codegraph.emit.build_and_write — 기록된 산출물 파일의 텍스트 자리 전부",
        "specVersion": load_rules().spec_version,
        "goldGap": "gold v0 의 양성 28건은 전부 .sql/.properties/.log 에 있어 코드 수집기가 읽는 확장자"
                   "(.kt/.java) 안에 양성이 없다(#88 F8). 따라서 실제 수집 실행이 아니라 산출 단계에"
                   " 양성을 심어 마스킹 관문의 동작을 측정한다 — gold 개정(I2 §8.2) 전까지의 한계다.",
        "gateVariant": "withLineContext",
        "variants": variants,
        "sinks": list(SINKS),
        "plantingNote": "각 양성을 모든 sink 에 심는다 — 양성 %d × sink %d 조합 전부가 관문을 지난다"
                        % (len(positives), len(SINKS)),
        "planted": [{"goldId": i["id"], "class": i["value"]["class"], "fields": list(SINKS)}
                    for i in positives],
    }


PARITY_FIXTURE = HERE / "fixtures/parity-cases.json"

# 픽스처의 정책 이름 → 정책. 두 엔진이 같은 이름에 같은 정책을 물려야 하므로 이름도 계약이다.
PARITY_POLICIES = {
    "default": MaskPolicy(),
    "lengthPreserving": MaskPolicy(length_preserving=True),
    "noAllowlist": MaskPolicy(allowlist_enabled=False),
    "namesDisabled": MaskPolicy(disabled_classes=frozenset({"NAME"})),
}
PARITY_OUT = RUNS / "run-mask-parity-001" / "engine-python.json"


def parity_evidence() -> dict:
    """교차 엔진 패리티 증거 — gold 가 지나가지 않는 분기를 두 엔진에 같은 입력으로 통과시킨다.

    정답은 없다(픽스처 설명 참조). 확정하는 것은 "두 엔진이 갈리지 않는다" 하나이며, 정확성 판정은
    gold 가 한다. 두 정책(기본 · 길이 보존)을 각각 잰다 — 길이 보존 토큰의 개행 처리도 두 엔진에서
    같아야 한다.
    """
    fixture = json.loads(PARITY_FIXTURE.read_text(encoding="utf-8"))
    cases = []
    for case in fixture["cases"]:
        text = case["text"]
        entry = {
            "id": case["id"],
            "inputHash": sha256_bytes(text.encode("utf-8")),
            # 문자 수도 UTF-16 코드 단위다 — 코드포인트로 세면 이모지가 든 케이스에서 Kotlin 과 갈린다.
            "inputChars": utf16_offset(text, len(text)),
            "inputLines": text.count("\n") + 1,
        }
        for policy_name in fixture["policies"]:
            policy = PARITY_POLICIES[policy_name]
            result = mask_text(text, policy)
            entry[policy_name] = {
                # 원문·마스킹 텍스트는 적지 않는다 — 해시와 좌표만 남긴다(#85).
                "maskedTextHash": sha256_bytes(result.text.encode("utf-8")),
                "maskedChars": utf16_offset(result.text, len(result.text)),
                "maskedLines": result.text.count("\n") + 1,
                "spans": [
                    {"start": s.start, "end": s.end, "ruleId": s.rule_id, "class": s.cls}
                    for s in spans_utf16(text, result.spans)
                ],
                "byRule": result.counts,
            }
        cases.append(entry)
    return {
        "evidenceVersion": "mask-parity-evidence/v1",
        "engine": "python:lodestar_codegraph.mask",
        "specVersion": load_rules().spec_version,
        "fixtureVersion": fixture["fixtureVersion"],
        "fixtureHash": sha256_bytes(PARITY_FIXTURE.read_bytes()),
        "policies": fixture["policies"],
        "cases": cases,
    }


def _occurrences(raw: str, text: str) -> list[tuple[int, int]]:
    out, idx = [], raw.find(text)
    while idx >= 0:
        out.append((idx, idx + len(text)))
        idx = raw.find(text, idx + 1)
    return out


def gold_item_verdicts() -> dict:
    """gold 항목별 판정 — 게이트(양성 미마스킹 0건)와 오탐(음성이 가려짐)을 항목 단위로 센다."""
    pii = gold_pii()
    masked_text, raw_text, spans = {}, {}, {}
    for f in pii["scope"]["files"]:
        raw = (REPO / f["path"]).read_text(encoding="utf-8")
        raw_text[f["sourceId"]] = raw
        masked_text[f["sourceId"]] = mask_text(raw).text
        spans[f["sourceId"]] = detect(raw)

    items = []
    for i in pii["items"]:
        src = i["ref"]["sourceId"]
        text = i["value"]["text"]
        raw = raw_text[src]
        # 이 항목의 원문 구간들이 마스킹 스팬에 완전히 덮였는가(부분 마스킹과 구별한다).
        occurrences = _occurrences(raw, text)
        covered = all(
            any(s.start <= a and s.end >= b for s in spans[src]) for a, b in occurrences
        ) if occurrences else False
        present = text in masked_text[src]
        items.append({
            "id": i["id"],
            "expect": i["expect"],
            "class": i["value"]["class"],
            "sourceId": src,
            "occurrences": len(occurrences),
            "plaintextPresentAfterMasking": present,
            "fullyCovered": covered,
            "verdict": (
                ("MASKED" if not present else "UNMASKED") if i["expect"] == "MASKED"
                else ("PRESERVED" if present else "FALSE_POSITIVE")
            ),
        })
    return {
        "evidenceVersion": "mask-gold-verdicts/v1",
        "goldSetVersion": pii["goldSetVersion"],
        "goldSetState": json.loads((GOLD / "manifest.json").read_text(encoding="utf-8"))["status"]["state"],
        "fixtureHash": json.loads((GOLD / "manifest.json").read_text(encoding="utf-8"))["fixtureHash"],
        "items": items,
        # 코퍼스 안에서 gold 에 등재되지 않은 스팬 = gold 로는 정오를 판정할 수 없는 마스킹이다.
        # 총계 차감으로 세면 '미등재 스팬 1개'와 '양성 1개 미탐'이 상쇄돼 0으로 보인다(리뷰 LOD-071).
        # 스팬 좌표를 gold 양성의 실제 구간과 대응시켜 센다.
        "spansOutsideGold": {
            src: sum(
                1 for s in sp
                if not any(
                    s.start <= a and s.end >= b
                    for i in pii["items"] if i["ref"]["sourceId"] == src and i["expect"] == "MASKED"
                    for a, b in _occurrences(raw_text[src], i["value"]["text"])
                )
            )
            for src, sp in spans.items()
        },
    }


def write(path: pathlib.Path, doc: dict, check: bool) -> int:
    text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    if check:
        if not path.exists():
            print(f"[FAIL] 커밋된 증거가 없다: {path}")
            return 1
        if path.read_text(encoding="utf-8") != text:
            print(f"[FAIL] 증거 표류: {path}")
            return 1
        print(f"[ok] {path.relative_to(REPO)}")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"[probe] {path.relative_to(REPO)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="커밋된 증거와 대조만 한다(쓰지 않는다)")
    args = ap.parse_args()

    rc = 0
    rc |= write(ENGINE_OUT, engine_evidence(), args.check)
    rc |= write(CODE_OUT, code_path_evidence(), args.check)
    rc |= write(RUNS / "run-mask-gold-001" / "gold-verdicts.json", gold_item_verdicts(), args.check)
    rc |= write(PARITY_OUT, parity_evidence(), args.check)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
