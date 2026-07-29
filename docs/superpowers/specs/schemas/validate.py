#!/usr/bin/env python3
"""answer-shape v0 픽스처 적합성 확인기 (참조 구현).

이 스크립트의 목적은 **커밋된 스키마와 픽스처가 계약 문서(§4 A1~A18)와 일치함을
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
    """스키마로 표현할 수 없는 교차 필드 불변식. A5·A6·A11·A13·A14·A15·A16·A17·A18."""
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
        if state not in ("present", "absent", "not_collected"):
            continue  # 구조적으로 잘못된 값은 스키마(A4)의 몫 — 여기서 이중 보고하지 않는다
        absent_warned = (WARN_FOR_ABSENT[cls], f"coverage.{cls}") in warns
        nc_warned = ("NOT_COLLECTED", f"coverage.{cls}") in warns
        if state == "absent" and not absent_warned:
            errs.append(f"A11: coverage.{cls}=absent 인데 {WARN_FOR_ABSENT[cls]} 경고 없음")
        if state == "not_collected" and not nc_warned:
            errs.append(f"A11: coverage.{cls}=not_collected 인데 대응 경고 없음")
        # 역방향 — 경고가 상태와 모순되면 안 된다
        if state != "absent" and absent_warned:
            errs.append(f"A11: {WARN_FOR_ABSENT[cls]} 경고가 있는데 coverage.{cls}={state}")
        if state != "not_collected" and nc_warned:
            errs.append(f"A11: NOT_COLLECTED(coverage.{cls}) 경고가 있는데 coverage.{cls}={state}")
    needs_check = {c["id"] for c in d["conflicts"] if c["status"] == "NEEDS_CHECK"}
    warned_conflicts = {w["trigger"] for w in d["warnings"] if w["code"] == "CONFLICT_UNRESOLVED"}
    for cid in sorted(needs_check - warned_conflicts):
        errs.append(f"A11: 미해결 충돌 {cid} 에 대한 경고 없음")
    for cid in sorted(warned_conflicts - needs_check):
        errs.append(f"A11: CONFLICT_UNRESOLVED({cid}) 인데 그 충돌은 NEEDS_CHECK 가 아님")

    # A13 — evidence[].id ⊆ audit.evidenceIds (등호 아님: 탈락 후보는 정상)
    missing = [i for i in ev_ids if i not in d["audit"]["evidenceIds"]]
    if missing:
        errs.append(f"A13: audit.evidenceIds 에 없는 증거 {missing}")

    # A14 — supports/contradicts 공존이면 충돌이 선언돼야 한다
    stances = {e["stance"] for e in d["evidence"]}
    if {"supports", "contradicts"} <= stances and not d["conflicts"]:
        errs.append("A14: 반대 증거가 있는데 conflicts 가 비어 있음")

    # A15 — 상한 적용 시 사유를 audit 에 명시하고, 그 사유가 통제어휘이며 실제 경고로 존재해야 한다.
    #       스키마와 별개로 여기서도 완결적으로 검사한다 — C0 가 교차 규칙만 이식해도 구멍이 없어야 한다.
    reasons = d["audit"].get("ceilingReasons", [])
    if d["audit"]["ceilingApplied"]:
        if not reasons:
            errs.append("A15: ceilingApplied=true 인데 ceilingReasons 가 비어 있음")
        for r in reasons:
            if r not in CEILING_REASONS:
                errs.append(f"A15: {r} 는 상한 사유로 허용된 코드가 아님")
            elif r not in codes:
                errs.append(f"A15: ceilingReasons 의 {r} 가 실제 warnings 에 없음")
    elif reasons:
        errs.append("A15: ceilingApplied=false 인데 ceilingReasons 가 비어있지 않음")

    # A17 — null 신호 ⟺ SIGNAL_UNMEASURED 경고 (양방향)
    null_signals = {
        f"{e['id']}.signals.{name}"
        for e in d["evidence"]
        for name, v in e["signals"].items()
        if v is None
    }
    unmeasured_warned = {w["trigger"] for w in d["warnings"] if w["code"] == "SIGNAL_UNMEASURED"}
    for miss in sorted(null_signals - unmeasured_warned):
        errs.append(f"A17: {miss} 가 null 인데 SIGNAL_UNMEASURED 경고 없음")
    for extra in sorted(unmeasured_warned - null_signals):
        errs.append(f"A17: SIGNAL_UNMEASURED({extra}) 인데 해당 신호가 null 이 아님")

    # A18 — trigger 가 실재 대상을 가리키는가
    conflict_ids = {c["id"] for c in d["conflicts"]}
    for w in d["warnings"]:
        code, trg = w["code"], w["trigger"]
        if trg.startswith("coverage."):
            ok = trg.split(".", 1)[1] in d["coverage"]
        elif code == "SIGNAL_UNMEASURED":
            ok = trg.rsplit(".signals.", 1)[0] in ev_ids
        elif code == "CONFLICT_UNRESOLVED":
            ok = trg in conflict_ids
        elif code == "ABSTAIN":
            ok = trg in {"evidence", "coverage"} or trg in ev_ids or trg in conflict_ids
        else:
            ok = trg in ev_ids or trg in conflict_ids
        if not ok:
            errs.append(f"A18: 경고 {code} 의 trigger '{trg}' 가 실재 대상을 가리키지 않음")

    # A16 — abstention 조건 1~3 (계약 §6.2)
    core = CORE_CLASSES[d["task"]["intent"]]
    triggers = [
        not d["evidence"],
        all(d["coverage"][c] != "present" for c in core),
        any(c["status"] == "NEEDS_CHECK" for c in d["conflicts"]),
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
        try:
            cross_errs = cross_field_errors(doc)
        except (KeyError, TypeError, AttributeError):
            # 구조가 결손된 문서(필수 필드 누락 등)는 교차 검사가 정의되지 않는다.
            cross_errs = []
        accepted = not schema_errs and not cross_errs
        expected = case["expect"] == "valid"

        ok = accepted == expected
        detail = ""
        if schema_errs:
            detail = "schema: " + schema_errs[0].message
        elif cross_errs:
            detail = "cross:  " + cross_errs[0]

        # 승인 여부만 비교하면 '다른 오류' 때문에 목표 규칙 검사가 누락돼도 통과한다.
        # invalid 픽스처는 manifest 가 선언한 규칙 하나만, 그 이유로 걸려야 한다.
        if ok and not expected:
            # 같은 규칙이 스키마·교차 두 계층에서 함께 잡히는 것은 정상(의도된 이중 방어)이다.
            # 막아야 하는 것은 '다른 규칙'이 섞여 목표 검사의 누락을 가리는 경우다.
            cross_rules = {e.split(":", 1)[0] for e in cross_errs}
            layer = case["enforcedBy"]
            if layer == "schema" and not schema_errs:
                ok, detail = False, "enforcedBy=schema 인데 스키마가 잡지 못함 (교차 검사에만 걸림)"
            elif layer == "validator" and schema_errs:
                ok, detail = False, f"enforcedBy=validator 인데 스키마가 먼저 잡음: {schema_errs[0].message}"
            elif layer == "validator" and not cross_errs:
                ok, detail = False, "enforcedBy=validator 인데 교차 검사가 잡지 못함"
            elif cross_rules - {case["rule"]}:
                ok, detail = False, (f"다른 규칙 위반이 섞임 — 기대 {case['rule']}, "
                                     f"실제 {sorted(cross_rules)}: {cross_errs}")
            elif len(schema_errs) > 1:
                ok, detail = False, (f"스키마 위반 {len(schema_errs)}건 — 단일 위반이어야 함: "
                                     f"{[e.message for e in schema_errs]}")
            else:
                actual = [e.message for e in schema_errs] + cross_errs
                if not any(case["expectedError"] in a for a in actual):
                    ok, detail = False, f"기대 오류 '{case['expectedError']}' 미검출: {actual}"

        mismatches += not ok
        print(f"{'OK  ' if ok else 'FAIL'} {case['file']:<48} {detail}")

    print(f"\n{len(MANIFEST['cases'])} cases, {mismatches} mismatches")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
