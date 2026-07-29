#!/usr/bin/env python3
"""answer-shape v0 픽스처 적합성 확인기 (참조 구현).

이 스크립트의 목적은 **커밋된 스키마와 픽스처가 계약 문서(§4 A1~A16)와 일치함을
누구나 재현할 수 있게 하는 것**이다. 제품 검증기가 아니다 — 실행 경로에 붙는
검증기·CI 연결은 하위 이슈 C0의 범위이며, 그때 이 규칙들을 백엔드 언어로 옮긴다.

    pip install jsonschema && python3 validate.py

계약: ../2026-07-29-evl-answer-shape-contract.md
"""
import json
import pathlib
import sys

from jsonschema import Draft202012Validator

HERE = pathlib.Path(__file__).parent
SCHEMA = json.loads((HERE / "answer-shape.v0.schema.json").read_text())
MANIFEST = json.loads((HERE / "examples" / "manifest.json").read_text())

# coverage 클래스 -> absent 일 때 요구되는 경고 코드 (계약 §2.6)
WARN_FOR_ABSENT = {
    "code": "NO_CODE",
    "issue": "NO_ISSUE",
    "adr": "NO_ADR",
    "test": "NO_TEST",
    "runtime": "NO_RUNTIME",
}
# intent -> 그 의도에 필수인 소스 클래스 (계약 §6.2 조건 2)
CORE_CLASSES = {
    "EXPLAIN": ["adr", "issue"],
    "VERIFY": ["test", "runtime"],
    "IMPACT": ["code"],
    "LOCATE": ["code"],
    "HISTORY": ["issue"],
}
# ceilingApplied=true 일 때 상한 사유로 인정되는 경고 (계약 A15)
CEILING_REASONS = {"DEGRADED_SOURCE", "CONFLICT_UNRESOLVED", "NOT_COLLECTED"} | set(
    WARN_FOR_ABSENT.values()
)


def cross_field_errors(d):
    """스키마로 표현할 수 없는 교차 필드 불변식. A5·A6·A11·A13·A14·A15·A16."""
    errs = []
    ev_ids = [e["id"] for e in d["evidence"]]
    sources = {e["source"] for e in d["evidence"]}
    warns = {(w["code"], w["trigger"]) for w in d["warnings"]}
    codes = {w["code"] for w in d["warnings"]}

    # A5 — coverage[X]=present ⟺ source=X 증거가 존재
    for cls, state in d["coverage"].items():
        if (state == "present") != (cls in sources):
            errs.append(f"A5: coverage.{cls}={state} 인데 해당 소스 증거 존재={cls in sources}")

    # A6 — conflicts[].between ⊆ evidence[].id
    for c in d["conflicts"]:
        for ref in c["between"]:
            if ref not in ev_ids:
                errs.append(f"A6: conflict {c['id']} 가 없는 증거 {ref} 를 참조")

    # A11 — 부재·미수집 클래스마다, 미해결 충돌마다 대응 경고(+trigger)
    for cls, state in d["coverage"].items():
        if state == "absent" and (WARN_FOR_ABSENT[cls], f"coverage.{cls}") not in warns:
            errs.append(f"A11: coverage.{cls}=absent 인데 {WARN_FOR_ABSENT[cls]} 경고 없음")
        if state == "not_collected" and ("NOT_COLLECTED", f"coverage.{cls}") not in warns:
            errs.append(f"A11: coverage.{cls}=not_collected 인데 대응 경고 없음")
    for c in d["conflicts"]:
        if c["status"] == "NEEDS_CHECK" and ("CONFLICT_UNRESOLVED", c["id"]) not in warns:
            errs.append(f"A11: 미해결 충돌 {c['id']} 에 대한 경고 없음")

    # A13 — evidence[].id ⊆ audit.evidenceIds (등호 아님: 탈락 후보는 정상)
    missing = [i for i in ev_ids if i not in d["audit"]["evidenceIds"]]
    if missing:
        errs.append(f"A13: audit.evidenceIds 에 없는 증거 {missing}")

    # A14 — supports/contradicts 공존이면 충돌이 선언돼야 한다
    stances = {e["stance"] for e in d["evidence"]}
    if {"supports", "contradicts"} <= stances and not d["conflicts"]:
        errs.append("A14: 반대 증거가 있는데 conflicts 가 비어 있음")

    # A15 — 상한 적용 시 사유 경고 필수
    if d["audit"]["ceilingApplied"] and not (codes & CEILING_REASONS):
        errs.append("A15: ceilingApplied=true 인데 상한 사유 경고 없음")

    # A16 — abstention 조건 1~3 (계약 §6.2)
    core = CORE_CLASSES[d["task"]["intent"]]
    triggers = [
        not d["evidence"],
        all(d["coverage"][c] != "present" for c in core),
        any(
            c["status"] == "NEEDS_CHECK" and ev_ids and ev_ids[0] in c["between"]
            for c in d["conflicts"]
        ),
    ]
    if any(triggers) and "ABSTAIN" not in codes:
        fired = [i + 1 for i, t in enumerate(triggers) if t]
        errs.append(f"A16: abstention 조건 {fired} 성립인데 ABSTAIN 경고 없음")

    return errs


def main():
    Draft202012Validator.check_schema(SCHEMA)
    validator = Draft202012Validator(SCHEMA)
    mismatches = 0

    for case in MANIFEST["cases"]:
        doc = json.loads((HERE / "examples" / case["file"]).read_text())
        schema_errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        cross_errs = [] if schema_errs else cross_field_errors(doc)
        accepted = not schema_errs and not cross_errs
        expected = case["expect"] == "valid"

        ok = accepted == expected
        mismatches += not ok
        detail = ""
        if schema_errs:
            detail = "schema: " + schema_errs[0].message
        elif cross_errs:
            detail = "cross:  " + cross_errs[0]
        print(f"{'OK  ' if ok else 'FAIL'} {case['file']:<48} {detail}")

    print(f"\n{len(MANIFEST['cases'])} cases, {mismatches} mismatches")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
