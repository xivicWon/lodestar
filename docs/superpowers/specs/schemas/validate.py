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
# 계약 §4 가 정의한 불변식 개수 — 규칙이 늘면 여기도 올린다(커버리지 검사에 쓰인다).
MAX_RULE = 19

# 규칙 -> 그 규칙이 스키마에서 강제되는 위치의 표지.
# schema 계층 픽스처는 expectedError 문자열뿐 아니라 **실제 위반 위치가 선언된 rule 과
# 맞는지**까지 대조한다. 그러지 않으면 잘못 라벨링된 픽스처가 다른 규칙의 검증 실적으로
# 집계되어 규칙 커버리지가 과대 보고된다.
RULE_SCHEMA_MARKERS = {
    "A1": ["additionalProperties"],
    "A2": ["schemaVersion"],
    "A3": ["reason"],
    "A4": ["coverage"],
    "A7": ["conflicts"],
    "A8": ["signals"],
    "A9": ["confidence"],
    "A10": ["stance"],
    "A12": ["warnings", "'audit' is a required property"],
    "A15": ["ceilingReasons"],
}

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
# 이 경고가 있으면 상한 적용은 선택이 아니다 (I1 §3.3 의 직접 대상).
# 커버리지 부재는 경고로 드러내되 상한을 강제하지는 않는다 — 그러면 사실상 모든 응답이 상한이다.
MANDATORY_CEILING = {"DEGRADED_SOURCE", "CONFLICT_UNRESOLVED"}


def cross_field_errors(d):
    """스키마로 표현할 수 없는 교차 필드 불변식. A5·A6·A11·A13·A14·A15·A16·A17·A18.

    각 규칙은 **독립적으로** 실행한다. 한 규칙이 구조 결손(필수 필드 누락 등)으로
    예외를 내도 이미 검출된 다른 규칙의 위반이 사라지면 안 된다 — 그러면 복수 위반
    픽스처가 단일 위반으로 오인되고 manifest 의 단일 규칙 보장이 무너진다.
    """
    errs = []

    def rule(fn):
        """규칙 하나를 격리 실행한다. 검사 불가(구조 결손)면 그 규칙만 건너뛴다."""
        try:
            fn()
        except (KeyError, TypeError, AttributeError, IndexError):
            pass  # 구조 자체의 결손은 스키마(A1)가 잡는다

    # 파생값 구성도 방어적으로 — 여기서 예외가 나면 규칙 격리가 무의미해지고
    # 실행 전체가 죽어 나머지 픽스처까지 검증할 수 없게 된다.
    evidence = [e for e in d.get("evidence", []) if isinstance(e, dict)]
    warnings_ = [w for w in d.get("warnings", []) if isinstance(w, dict)]
    conflicts = [c for c in d.get("conflicts", []) if isinstance(c, dict)]
    coverage = d.get("coverage") if isinstance(d.get("coverage"), dict) else {}
    audit = d.get("audit") if isinstance(d.get("audit"), dict) else {}

    ev_ids = [e["id"] for e in evidence if "id" in e]
    sources = {e["source"] for e in evidence if "source" in e}
    warns = {(w["code"], w["trigger"]) for w in warnings_
             if "code" in w and "trigger" in w}
    codes = {w["code"] for w in warnings_ if "code" in w}

    # A5 — coverage[X]=present ⟺ source=X 증거가 존재
    def _a5():
        for cls, state in coverage.items():
            if (state == "present") != (cls in sources):
                errs.append(f"A5: coverage.{cls}={state} 인데 해당 소스 증거 존재={cls in sources}")
    rule(_a5)

    # A19 — id 는 응답 내에서 유일해야 한다. §2.3 은 "응답 내 유일"이라 적어두었지만
    #       어디서도 강제하지 않았다. 중복 id 는 경고 하나가 여러 대상을 충족시키는
    #       것처럼 보이게 만들어 A11·A16·A18 의 집계를 통째로 무너뜨린다.
    def _a19():
        cf_ids = [c["id"] for c in conflicts if "id" in c]
        for label, ids in (("evidence", ev_ids), ("conflicts", cf_ids)):
            dup = sorted({i for i in ids if ids.count(i) > 1})
            if dup:
                errs.append(f"A19: {label}[].id 가 응답 내에서 중복됨 {dup}")
        # id 는 단일 네임스페이스다 — trigger 하나가 증거와 충돌 중 무엇을 가리키는지
        # 모호해지면 A16·A18 의 참조 검사가 잘못 통과한다.
        collision = sorted(set(ev_ids) & set(cf_ids))
        if collision:
            errs.append(f"A19: 같은 id 를 evidence 와 conflicts 가 함께 사용함 {collision}")
    rule(_a19)

    # A6 — conflicts[].between ⊆ evidence[].id
    def _a6():
        for c in conflicts:
            for ref in c["between"]:
                if ref not in ev_ids:
                    errs.append(f"A6: conflict {c['id']} 가 없는 증거 {ref} 를 참조")
    rule(_a6)

    # A11 — 부재·미수집 클래스마다, 미해결 충돌마다 대응 경고(+trigger)
    def _a11():
        for cls, state in coverage.items():
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
        needs_check = {c["id"] for c in conflicts if c["status"] == "NEEDS_CHECK"}
        warned_conflicts = {w["trigger"] for w in warnings_ if w["code"] == "CONFLICT_UNRESOLVED"}
        for cid in sorted(needs_check - warned_conflicts):
            errs.append(f"A11: 미해결 충돌 {cid} 에 대한 경고 없음")
        for cid in sorted(warned_conflicts - needs_check):
            errs.append(f"A11: CONFLICT_UNRESOLVED({cid}) 인데 그 충돌은 NEEDS_CHECK 가 아님")
    rule(_a11)

    # A13 — evidence[].id ⊆ audit.evidenceIds (등호 아님: 탈락 후보는 정상)
    def _a13():
        missing = [i for i in ev_ids if i not in audit["evidenceIds"]]
        if missing:
            errs.append(f"A13: audit.evidenceIds 에 없는 증거 {missing}")
    rule(_a13)

    # A14 — 반대 증거는 '어떤 충돌이든 하나 있으면' 되는 게 아니라,
    #       그 증거 자신이 supports 증거와 함께 충돌로 연결돼야 한다.
    def _a14():
        supports = {e["id"] for e in evidence if e["stance"] == "supports"}
        for e in evidence:
            if e["stance"] != "contradicts":
                continue
            linked = any(
                e["id"] in c["between"] and (set(c["between"]) & supports)
                for c in conflicts
            )
            if not linked:
                errs.append(f"A14: 반대 증거 {e['id']} 가 supports 증거와 함께 충돌로 연결되지 않음")
    rule(_a14)

    # A15 — 상한 적용 시 사유를 audit 에 명시하고, 그 사유가 통제어휘이며 실제 경고로 존재해야 한다.
    #       스키마와 별개로 여기서도 완결적으로 검사한다 — C0 가 교차 규칙만 이식해도 구멍이 없어야 한다.
    def _a15():
        reasons = audit.get("ceilingReasons", [])
        if audit["ceilingApplied"]:
            if not reasons:
                errs.append("A15: ceilingApplied=true 인데 ceilingReasons 가 비어 있음")
            for r in reasons:
                if r not in CEILING_REASONS:
                    errs.append(f"A15: {r} 는 상한 사유로 허용된 코드가 아님")
                elif r not in codes:
                    errs.append(f"A15: ceilingReasons 의 {r} 가 실제 warnings 에 없음")
        elif reasons:
            errs.append("A15: ceilingApplied=false 인데 ceilingReasons 가 비어있지 않음")
        # 역방향 — 상한을 반드시 유발하는 사유가 있으면 적용하고 기록해야 한다.
        # (커버리지 부재 NO_*·NOT_COLLECTED 는 경고 대상이지 상한 강제 사유는 아니다.)
        for code in sorted(codes & MANDATORY_CEILING):
            if not audit["ceilingApplied"]:
                errs.append(f"A15: {code} 경고가 있는데 ceilingApplied=false")
            elif code not in reasons:
                errs.append(f"A15: {code} 경고가 있는데 ceilingReasons 에 빠짐")
    rule(_a15)

    # A17 — null 신호 ⟺ SIGNAL_UNMEASURED 경고 (양방향)
    def _a17():
        null_signals = {
            f"{e['id']}.signals.{name}"
            for e in evidence
            for name, v in e["signals"].items()
            if v is None
        }
    # 신호명이 실재하지 않는 trigger 는 A18 의 몫이다 — 여기서 이중 보고하지 않는다.
        def _valid_target(trg):
            ev_id, _, sig = trg.rpartition(".signals.")
            owner = next((e for e in evidence if e.get("id") == ev_id), None)
            return owner is not None and sig in (owner.get("signals") or {})

        unmeasured_warned = {w["trigger"] for w in warnings_
                             if w["code"] == "SIGNAL_UNMEASURED" and _valid_target(w["trigger"])}
        for miss in sorted(null_signals - unmeasured_warned):
            errs.append(f"A17: {miss} 가 null 인데 SIGNAL_UNMEASURED 경고 없음")
        for extra in sorted(unmeasured_warned - null_signals):
            errs.append(f"A17: SIGNAL_UNMEASURED({extra}) 인데 해당 신호가 null 이 아님")
    rule(_a17)

    # A18 — trigger 가 실재 대상을 가리키는가.
    #       **코드 기준으로 분기**한다. 예전에는 'coverage.' 접두사를 먼저 보고 통과시켜
    #       DEGRADED_SOURCE 같은 증거 참조 코드가 coverage.* 를 가리켜도 승인됐다.
    #       형식 자체가 code 계약(§2.6)과 어긋나는 경우는 스키마(A12)의 몫이므로 여기서는
    #       형식이 맞는 trigger 의 '대상 실재'만 본다 — 이중 보고를 피하기 위해서다.
    def _a18():
        conflict_ids = {c["id"] for c in conflicts}
        cov_codes = set(WARN_FOR_ABSENT.values()) | {"NOT_COLLECTED"}
        ev_scoped = {"LOW_CORROBORATION", "STALE_EVIDENCE", "DEGRADED_SOURCE"}
        for w in warnings_:
            code, trg = w["code"], w["trigger"]
            if code in cov_codes:
                if not trg.startswith("coverage."):
                    continue  # 형식 위반 — A12(스키마)
                ok = trg.split(".", 1)[1] in coverage
            elif code == "SIGNAL_UNMEASURED":
                if ".signals." not in trg:
                    continue
                ev_id, _, sig = trg.rpartition(".signals.")
                owner = next((e for e in evidence if e.get("id") == ev_id), None)
                ok = owner is not None and sig in (owner.get("signals") or {})
            elif code == "CONFLICT_UNRESOLVED":
                ok = trg in conflict_ids
            elif code in ev_scoped:
                if trg.startswith("coverage."):
                    continue  # 형식 위반 — A12(스키마)
                ok = trg in ev_ids
            elif code == "ABSTAIN":
                # 보류 '사유'로서 유효한지는 A16 이 본다. 여기서는 대상 실재만.
                ok = (trg == "evidence"
                      or (trg.startswith("coverage.") and trg.split(".", 1)[1] in coverage)
                      or trg in ev_ids or trg in conflict_ids)
            else:
                ok = trg in ev_ids or trg in conflict_ids
            if not ok:
                errs.append(f"A18: 경고 {code} 의 trigger '{trg}' 가 실재 대상을 가리키지 않음")
    rule(_a18)

    # A16 — abstention 조건 1~3 (계약 §6.2)
    def _a16():
        core = CORE_CLASSES[d["task"]["intent"]]
        triggers = [
            not evidence,
            all(coverage[c] != "present" for c in core),
            any(c["status"] == "NEEDS_CHECK" for c in conflicts),
        ]
    
        fired = [i + 1 for i, x in enumerate(triggers) if x]
        if fired and "ABSTAIN" not in codes:
            errs.append(f"A16: abstention 조건 {fired} 성립인데 ABSTAIN 경고 없음")
        elif fired:
            # 보류 '사유'가 기계적으로 식별돼야 한다 — 관계없는 id 를 trigger 로 써서는 안 된다.
            valid_targets = set()
            if 1 in fired:
                valid_targets.add("evidence")
            if 2 in fired:
                valid_targets |= {f"coverage.{c}" for c in core if coverage.get(c) != "present"}
            if 3 in fired:
                valid_targets |= {c["id"] for c in conflicts if c["status"] == "NEEDS_CHECK"}
            got = {w["trigger"] for w in warnings_ if w["code"] == "ABSTAIN"}
            if not (got & valid_targets):
                errs.append(f"A16: ABSTAIN 의 trigger {sorted(got)} 가 성립한 조건 {fired} "
                            f"중 무엇도 가리키지 않음 (유효: {sorted(valid_targets)})")
        elif "ABSTAIN" in codes:
            errs.append("A16: 보류 조건이 하나도 성립하지 않는데 ABSTAIN 경고가 있음 (허위 보류)")

    rule(_a16)

    return errs


def main():
    Draft202012Validator.check_schema(SCHEMA)
    validator = Draft202012Validator(SCHEMA)
    mismatches = 0

    for case in MANIFEST["cases"]:
        doc = json.loads((HERE / "examples" / case["file"]).read_text())
        schema_errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        cross_errs = cross_field_errors(doc)
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
            elif schema_errs and case["rule"] in RULE_SCHEMA_MARKERS and not any(
                mk in "/".join(map(str, schema_errs[0].absolute_schema_path))
                or mk in schema_errs[0].message
                for mk in RULE_SCHEMA_MARKERS[case["rule"]]
            ):
                ok, detail = False, (
                    f"규칙 라벨 불일치 — {case['rule']} 의 표지 "
                    f"{RULE_SCHEMA_MARKERS[case['rule']]} 가 실제 위반 위치 "
                    f"'{'/'.join(map(str, schema_errs[0].absolute_schema_path))}' 에 없음")
            elif len(schema_errs) > 1:
                ok, detail = False, (f"스키마 위반 {len(schema_errs)}건 — 단일 위반이어야 함: "
                                     f"{[e.message for e in schema_errs]}")
            else:
                actual = [e.message for e in schema_errs] + cross_errs
                if not any(case["expectedError"] in a for a in actual):
                    ok, detail = False, f"기대 오류 '{case['expectedError']}' 미검출: {actual}"

        mismatches += not ok
        print(f"{'OK  ' if ok else 'FAIL'} {case['file']:<48} {detail}")

    # 규칙 커버리지 — 불변식이 하나라도 음성 픽스처 없이 남으면 그 규칙은
    # 구현되지 않거나 나중에 제거돼도 이 스위트가 통과한다.
    covered = {c["rule"] for c in MANIFEST["cases"] if c["expect"] == "invalid"}
    uncovered = [f"A{i}" for i in range(1, MAX_RULE + 1) if f"A{i}" not in covered]
    if uncovered:
        mismatches += 1
        print(f"FAIL 규칙 커버리지 — 음성 픽스처가 없는 불변식: {uncovered}")

    print(f"\n{len(MANIFEST['cases'])} cases, {mismatches} mismatches")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
