#!/usr/bin/env python3
"""#115 마스킹 실행 보고서 생성 — 증거의 **순수 함수**.

보고서의 모든 수치는 `runs/` 의 증거에서 파생된다. 손으로 고친 수치는 `verify_masking.py` 가
같은 함수로 재생성해 대조하며 잡는다(L0 벤치 V2 와 같은 장치).

이 보고서는 **Run Quality Report(I3)가 아니다.** L0 레이어 판정을 갱신하지 않으며 #88 의 두
보고서를 대체하지도 않는다 — L0 재측정은 gold 의 `sourceRevision` 재고정과 승인이 선행돼야 한다
(I2 §10.4 · I1 §7.4). 여기서 확정하는 것은 "마스킹 단계가 무엇을 몇 건 가렸는가" 하나다.

    python3 docs/superpowers/specs/bench/masking/build_masking_report.py
    python3 docs/superpowers/specs/bench/masking/build_masking_report.py --check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[4]
GOLD = REPO / "docs/superpowers/specs/gold"
RUNS = HERE / "runs"
REPORT = HERE / "report.json"

EVIDENCE = {
    "engineKotlin": RUNS / "run-mask-gold-001/engine-kotlin.json",
    "enginePython": RUNS / "run-mask-gold-001/engine-python.json",
    "goldVerdicts": RUNS / "run-mask-gold-001/gold-verdicts.json",
    "emitCode": RUNS / "run-mask-code-001/emit-code.json",
    "ingestDb": RUNS / "run-mask-ingest-001/ingest-db.json",
    "parityKotlin": RUNS / "run-mask-parity-001/engine-kotlin.json",
    "parityPython": RUNS / "run-mask-parity-001/engine-python.json",
    "parityFixture": HERE / "fixtures/parity-cases.json",
    "ruleSpec": REPO / "docs/superpowers/specs/security/masking-rules.v0.json",
}

# 이 두 클래스의 오탐은 게이트가 아니라도 별도 표기 대상이다(gold gate 선언 · I1 §1.3).
CRITICAL_FP_CLASSES = ("GIT_SHA", "CONTENT_HASH")


def sha256_file(p: pathlib.Path) -> str:
    return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()


def load(key: str) -> dict:
    return json.loads(EVIDENCE[key].read_text(encoding="utf-8"))


def span_view(evidence: dict) -> list:
    """엔진 비교용 정규화 — 엔진 이름만 다르고 나머지가 같아야 한다."""
    return [
        {
            "sourceId": f["sourceId"],
            "contentHash": f["contentHash"],
            "maskedTextHash": f["maskedTextHash"],
            "spans": f["spans"],
            "byClass": f["byClass"],
            "byRule": f["byRule"],
        }
        for f in evidence["files"]
    ]


def parity_view(evidence: dict) -> list:
    """패리티 비교용 정규화 — 엔진 이름만 다르고 케이스별 관측이 전부 같아야 한다."""
    return [{k: v for k, v in case.items()} for case in evidence["cases"]]


def merge_counts(evidence: dict, key: str) -> dict:
    out: dict[str, int] = {}
    for f in evidence["files"]:
        for k, v in f[key].items():
            out[k] = out.get(k, 0) + v
    return dict(sorted(out.items()))


def build() -> dict:
    pii = json.loads((GOLD / "pii.json").read_text(encoding="utf-8"))
    manifest = json.loads((GOLD / "manifest.json").read_text(encoding="utf-8"))
    kotlin, python = load("engineKotlin"), load("enginePython")
    verdicts, code, db = load("goldVerdicts"), load("emitCode"), load("ingestDb")

    items = verdicts["items"]
    positives = [i for i in items if i["expect"] == "MASKED"]
    negatives = [i for i in items if i["expect"] == "NOT_MASKED"]
    unmasked = [i["id"] for i in positives if i["verdict"] == "UNMASKED"]
    false_positives = [i["id"] for i in negatives if i["verdict"] == "FALSE_POSITIVE"]

    parity = span_view(kotlin) == span_view(python)
    pk, pp = load("parityKotlin"), load("parityPython")
    branch_parity = (parity_view(pk) == parity_view(pp)
                     and pk["fixtureHash"] == pp["fixtureHash"] == sha256_file(EVIDENCE["parityFixture"]))
    code_gate = code["variants"][code["gateVariant"]]
    partial = [i["id"] for i in positives if not i["fullyCovered"]]

    gates = [
        {
            "id": "gate-security-masking",
            "name": "테스트 시크릿·PII 미마스킹 0건 + 부분 마스킹 0건 (gold 코퍼스)",
            "required": 0,
            # 원문 소멸만으로는 부족하다 — 스팬이 양성 구간을 **완전히** 덮었는지도 게이트에 넣는다.
            # 부분 마스킹은 값의 일부가 남는 것이며 "가렸다" 고 부를 수 없다(리뷰 질문 3).
            "observed": len(unmasked) + len(partial),
            "status": "PASS" if not unmasked and not partial else "FAIL",
            "scope": "gold PII 코퍼스 3파일 전문(문맥 포함) · 양성 %d건 · 좌표 완전 피복 요구" % len(positives),
        },
        {
            "id": "gate-engine-parity",
            "name": "두 수집 경로가 같은 규칙으로 같은 결과를 낸다 (Kotlin ↔ Python)",
            "required": True,
            "observed": parity,
            "status": "PASS" if parity else "FAIL",
            "scope": "gold 코퍼스 3파일 · 스팬 좌표·클래스·규칙 id·마스킹 결과 해시",
        },
        {
            "id": "gate-engine-parity-branches",
            "name": "gold 가 지나가지 않는 분기에서도 두 엔진이 같다",
            "required": True,
            "observed": branch_parity,
            "status": "PASS" if branch_parity else "FAIL",
            "scope": "패리티 픽스처 %d케이스 × 정책 %d종(기본·길이보존) · 대안 그룹·PEM·BMP 밖 문자·개행 보존"
                     % (len(pk["cases"]), len(pk["policies"])),
        },
        {
            "id": "gate-db-ingest-masking",
            "name": "적재 저장소에 미마스킹 PII 0건 (#88 F7 노출 지점)",
            "required": 0,
            "observed": db["retrievableUnmaskedPiiValues"],
            "status": "PASS" if db["retrievableUnmaskedPiiValues"] == 0 else "FAIL",
            "scope": "legacy-sample 적재 후 PII 형태 컬럼 질의",
        },
        {
            "id": "gate-code-emit-masking",
            "name": "코드 산출물 텍스트 필드에 미마스킹 양성 0건",
            "required": 0,
            "observed": code_gate["unmasked"],
            "status": "PASS" if code_gate["unmasked"] == 0 else "FAIL",
            "scope": "emit 단계 · %s 변형 · 심은 양성 %d건" % (code["gateVariant"], code_gate["plantedPositives"]),
        },
    ]

    body = {
        "reportVersion": "masking-run-report/v0",
        "issue": 115,
        "note": "이 보고서는 Run Quality Report(I3)가 아니며 L0 레이어 판정을 갱신하지 않는다. "
                "#88 의 두 보고서는 수정 전 기준선으로 남는다 — L0 재측정은 gold sourceRevision "
                "재고정과 승인이 선행된다(I2 §10.4 · I1 §7.4).",
        "specVersion": load("ruleSpec")["specVersion"],
        "goldSetVersion": pii["goldSetVersion"],
        "goldSetState": manifest["status"]["state"],
        "fixtureHash": manifest["fixtureHash"],
        "goldSetId": manifest["goldSetId"],
        "gates": gates,
        "gold": {
            "positives": len(positives),
            "masked": sum(1 for i in positives if i["verdict"] == "MASKED"),
            "unmasked": unmasked,
            "fullyCovered": sum(1 for i in positives if i["fullyCovered"]),
            "partiallyCovered": [i["id"] for i in positives if not i["fullyCovered"]],
            "negatives": len(negatives),
            "preserved": sum(1 for i in negatives if i["verdict"] == "PRESERVED"),
            "falsePositives": false_positives,
            "falsePositiveRate": round(len(false_positives) / len(negatives), 4),
            "criticalClassFalsePositives": {
                c: sum(1 for i in negatives if i["class"] == c and i["verdict"] == "FALSE_POSITIVE")
                for c in CRITICAL_FP_CLASSES
            },
            "spansOutsideGold": verdicts["spansOutsideGold"],
            "byClass": merge_counts(python, "byClass"),
            "byRule": merge_counts(python, "byRule"),
        },
        "engines": {
            "kotlin": {"engine": kotlin["engine"], "spans": sum(f["maskedSpans"] for f in kotlin["files"])},
            "python": {"engine": python["engine"], "spans": sum(f["maskedSpans"] for f in python["files"])},
            "parity": parity,
            "branchParity": {
                "fixtureVersion": pk["fixtureVersion"],
                "fixtureHash": pk["fixtureHash"],
                "cases": len(pk["cases"]),
                "policies": pk["policies"],
                "identical": branch_parity,
                "spans": {
                    name: sum(len(c[name]["spans"]) for c in pk["cases"]) for name in pk["policies"]
                },
                "note": "이 픽스처에는 정답이 없다 — 확정하는 것은 두 엔진이 갈리지 않는다는 사실 하나이며,"
                        " 정확성 판정은 gold(#99)가 한다",
            },
            "ruleSpecHash": sha256_file(EVIDENCE["ruleSpec"]),
        },
        "collectionPaths": {
            "db": {
                "probe": db["probe"],
                "input": db["input"],
                "maskedTotal": db["maskedTotal"],
                "byClass": db["byClass"],
                "retrievableUnmaskedPiiValues": db["retrievableUnmaskedPiiValues"],
                "unmaskedByPolicyValues": db["unmaskedByPolicyValues"],
                "policyExclusionNote": db["policyExclusionNote"],
                "collectedTables": db["collectedTables"],
                "ddlTextPath": db["ddlTextPath"],
                "minimizePolicy": db["minimizePolicy"],
            },
            "code": {
                "probe": code["probe"],
                "gateVariant": code["gateVariant"],
                "goldGap": code["goldGap"],
                "variants": {
                    name: {"unmasked": v["unmasked"], "unmaskedInArtifact": v["unmaskedInArtifact"],
                           "maskedTotal": v["maskingSummary"]["masked_total"],
                           "idsPreserved": v["idsPreserved"]}
                    for name, v in code["variants"].items()
                },
            },
        },
        "evidenceRefs": {
            k: {"path": str(p.relative_to(REPO)), "contentHash": sha256_file(p)}
            for k, p in sorted(EVIDENCE.items())
        },
    }

    # 원문 미기록 게이트는 **계산한다** — 고정 PASS 로 적으면 게이트가 아니라 주장이다(리뷰 질문 5).
    # 대상: 증거 5종(규칙 스펙은 정규식이며 값이 아니다) + 이 보고서의 나머지 전문.
    scanned = {k: json.dumps(load(k), ensure_ascii=False)
               for k in EVIDENCE if k not in ("ruleSpec", "parityFixture")}
    scanned["report(body)"] = json.dumps(body, ensure_ascii=False)
    plaintexts = [i["value"]["text"] for i in pii["items"] if i["expect"] == "MASKED"]
    # 패리티 픽스처의 입력 텍스트도 증거에 실려서는 안 된다 — 해시·좌표만 남기는 계약이다.
    plaintexts += [c["text"] for c in load("parityFixture")["cases"]]
    hits = sorted(
        f"{name}:{text[:4]}…"  # 어느 문서에서 걸렸는지만 남긴다 — 여기에 원문을 적으면 같은 위반이다
        for name, blob in scanned.items() for text in plaintexts if text in blob
    )
    gates.append({
        "id": "gate-no-plaintext-in-records",
        "name": "증거·보고서에 원문 미기록 (#85)",
        "required": 0,
        "observed": len(hits),
        "status": "PASS" if not hits else "FAIL",
        "scope": "증거 %d종 + 보고서 전문 × 양성 %d건 = %d회 대조"
                 % (len(scanned) - 1, len(plaintexts), len(scanned) * len(plaintexts)),
        "hits": hits,
    })
    body["gates"] = gates
    return body


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--update", action="store_true",
                    help="기존 보고서와 다르면 갱신한다(변경은 diff 에 의도로 남는다)")
    args = ap.parse_args()

    text = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not REPORT.exists():
            print(f"[FAIL] 보고서가 없다: {REPORT}")
            return 1
        if REPORT.read_text(encoding="utf-8") != text:
            print("[FAIL] 보고서가 증거의 순수 함수가 아니다 — 수치가 손으로 바뀌었거나 증거가 갱신됐다")
            return 1
        print("[ok] 보고서 = 증거의 순수 함수")
        return 0
    if REPORT.exists() and REPORT.read_text(encoding="utf-8") != text and not args.update:
        print("[FAIL] 기존 보고서와 결과가 다르다 — 의도한 갱신이면 --update 로 다시 실행한다")
        return 1
    REPORT.write_text(text, encoding="utf-8")
    print(f"[report] {REPORT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
