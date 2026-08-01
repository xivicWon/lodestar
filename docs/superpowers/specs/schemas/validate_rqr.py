#!/usr/bin/env python3
"""Run Quality Report v0 픽스처 적합성 확인기 (참조 구현).

목적은 **커밋된 스키마·템플릿·픽스처가 계약 문서(§4 R1~R20)와 일치함을 누구나
재현할 수 있게 하는 것**이다. 제품 검증기가 아니다 — 실행 경로·CI 연결은 각 레이어
이슈(#88~#91)가 이 규칙들을 백엔드 언어로 옮기면서 한다.

    pip install jsonschema && python3 validate_rqr.py

계약: ../2026-07-29-m0-i3-run-quality-report-contract.md
"""
import json
import pathlib
import re
import sys
from datetime import datetime

from jsonschema import Draft202012Validator

HERE = pathlib.Path(__file__).parent
EX = HERE / "rqr-examples"
REPO = HERE.parents[3]  # docs/superpowers/specs/schemas -> 리포 루트
# 계약 버전마다 스키마가 하나다. 한 파일을 고쳐 여러 버전을 겸하게 하면 §7.3(통제어휘·규칙 변경 시
# 버전 상승)이 형식만 남고, 옛 버전으로 쓰인 보고서가 새 어휘를 쓸 수 있게 되어 버전이 뜻을 잃는다.
SCHEMAS = {v: json.loads((HERE / f"run-quality-report.{v}.schema.json").read_text())
           for v in ("v0", "v1")}
CURRENT = "v1"
SCHEMA = SCHEMAS[CURRENT]


def schema_for(report):
    """보고서가 **선언한** 버전의 스키마를 돌려준다.

    선언과 다른 스키마로 재면 두 방향 모두 거짓이 된다: 옛 보고서가 새 어휘를 안 썼다는 이유로
    통과하거나(느슨), 새 어휘를 쓴 보고서가 옛 스키마에서 위반으로 잡힌다(엄격). 선언이 이상하면
    그 자체를 위반으로 보고해야 하므로 모르는 버전은 현재 스키마로 재서 const 위반을 내게 한다.
    """
    v = report.get("schemaVersion", "") if isinstance(report, dict) else ""
    return SCHEMAS.get(str(v).rsplit("/", 1)[-1], SCHEMA)
MANIFEST = json.loads((EX / "manifest.json").read_text())
# 계약 §4 가 정의한 불변식 개수 — 규칙이 늘면 여기도 올린다(커버리지 검사에 쓰인다).
MAX_RULE = 20
# coverage 산식 대조 허용 오차 — 소수 4자리 반올림까지만 허용한다(R20).
COVERAGE_TOLERANCE = 0.00005

# 규칙 -> 그 규칙이 스키마에서 강제되는 위치의 표지. schema 계층 픽스처는
# expectedError 문자열뿐 아니라 **실제 위반 위치가 선언된 rule 과 맞는지**까지 대조한다.
# 그러지 않으면 잘못 라벨링된 픽스처가 다른 규칙의 검증 실적으로 집계된다.
RULE_SCHEMA_MARKERS = {
    "R1": ["additionalProperties", "const", "required", "pattern", "$defs/measurement"],
    "R5": ["verdict/properties/value/enum"],
}

METRIC_KEYS = ["precision", "recall", "scopeCoverage", "determinism", "provenanceCompleteness"]
COVERAGE_CLASSES = ["code", "issue", "adr", "test", "runtime"]
# code -> 그 코드가 가리킬 수 있는 trigger 의 종류(R18). 형식은 스키마가, 대상 실재는 여기가 본다.
TRIGGER_KIND = {
    "UNPINNED_FIXTURE": "fixture",
    "VERSION_UNPINNED": "version",
    "METRIC_UNMEASURED": "metric",
    "CALIBRATION_RAW_MISSING": "calibration",
    "GATE_FAILED": "gate",
    "BASELINE_NOT_COMPARABLE": "baseline",
    "PATH_RESTRICTED": "verdict",
    # 승인되지 않은 정답셋·입력 축으로 잰 실행(I1 §7 · I2 §6). 재현할 수 있어도 기준선이 아니다 —
    # 그 사실이 보고서 안에 남아야 읽는 쪽이 승인 상태를 따로 조회하지 않고도 안다.
    "GOLD_UNAPPROVED": "gold",
}
TIME_RE = re.compile(r"(T\d{2}:\d{2}:)60")


def _calendar(v):
    """윤초(:60)는 스키마가 허용하므로 :59 로 치환해 '실재하는 날짜인가' 만 본다."""
    return datetime.fromisoformat(TIME_RE.sub(r"\g<1>59", v).replace("Z", "+00:00"))


def cross_field_errors(d):
    """스키마로 표현할 수 없는 교차 필드 불변식. R1(달력·시각 순서)·R2~R4·R6~R20.

    각 규칙은 **독립적으로** 실행한다. 한 규칙이 구조 결손으로 예외를 내도 이미
    검출된 다른 규칙의 위반이 사라지면 안 된다 — 그러면 복수 위반 픽스처가 단일
    위반으로 오인되고 manifest 의 단일 규칙 보장이 무너진다.
    """
    errs = []

    def rule(fn):
        try:
            fn()
        except (KeyError, TypeError, AttributeError, IndexError, ValueError):
            pass  # 구조 자체의 결손은 스키마(R1)가 잡는다

    def _objs(key, container=None):
        v = (container if container is not None else d).get(key)
        return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []

    def _dict(key, container=None):
        v = (container if container is not None else d).get(key)
        return v if isinstance(v, dict) else {}

    run = _dict("run")
    versions = _dict("versions")
    counts = _dict("counts")
    metrics = _dict("metrics")
    evl = _dict("evl")
    calib = _dict("confidenceCalibration", evl)
    conflict = _dict("conflictDetection", evl)
    baseline = _dict("baseline")
    verdict = _dict("verdict")
    exclusions = _objs("exclusions")
    failures = _objs("failures")
    gates = _objs("gates")
    judgments = _objs("featureJudgments")
    warnings_ = _objs("warnings")
    cov_classes = _objs("coverageClasses", evl)

    warns = {(w.get("code"), w.get("trigger")) for w in warnings_}
    codes = {w.get("code") for w in warnings_}

    def _status(m):
        return m.get("status") if isinstance(m, dict) else None

    # R1 — 스키마가 자릿수·범위까지만 막는 부분: 달력 유효성과 시각 순서.
    def _r1():
        for label in ("startedAt", "completedAt"):
            v = run.get(label)
            if not isinstance(v, str):
                continue
            try:
                _calendar(v)
            except ValueError:
                errs.append(f"R1: run.{label} 이 실재하지 않는 시각 '{v}'")
        if isinstance(run.get("startedAt"), str) and isinstance(run.get("completedAt"), str):
            try:
                if _calendar(run["completedAt"]) < _calendar(run["startedAt"]):
                    errs.append("R1: completedAt 이 startedAt 보다 이르다")
            except ValueError:
                pass  # 위에서 이미 보고했다
    rule(_r1)

    # R2 — input = output + failed + excluded. 맞지 않으면 어딘가를 세지 않은 것이다.
    def _r2():
        total = counts["output"] + counts["failed"] + counts["excluded"]
        if counts["input"] != total:
            errs.append(f"R2: counts.input {counts['input']} != output+failed+excluded {total}")
    rule(_r2)

    # R3 — 제외 사유 집계가 counts.excluded 와 일치하고, 사유마다 제외된 **모든** 대상의
    #      좌표가 남으며, 같은 사유가 두 번 나오지 않는다.
    def _r3():
        s = sum(e["count"] for e in exclusions)
        if s != counts["excluded"]:
            errs.append(f"R3: exclusions 합 {s} != counts.excluded {counts['excluded']}")
        for e in exclusions:
            n = len(e["examples"])
            if n != e["count"]:
                errs.append(f"R3: 제외 사유 '{e['reason']}' 의 count {e['count']} != 좌표 수 {n} "
                            f"(제외된 대상은 전부 좌표를 남긴다)")
        reasons = [e["reason"] for e in exclusions]
        dup = sorted({r for r in reasons if reasons.count(r) > 1})
        if dup:
            errs.append(f"R3: 같은 제외 사유가 여러 항목으로 흩어짐 {dup}")
    rule(_r3)

    # R4 — 실패 건수와 실패 사례의 수가 **정확히** 일치한다. R3(제외 좌표)과 같은 원칙이다:
    #      집계만 남기고 사례를 일부만 적으면 나머지 실패는 재현도 회귀 검증도 되지 않는다.
    def _r4():
        if counts["failed"] != len(failures):
            errs.append(f"R4: counts.failed={counts['failed']} != failures 사례 수 {len(failures)} "
                        f"(실패는 전부 사례와 재현 fixture 를 남긴다)")
    rule(_r4)

    # R6 — BLOCKED ⟺ haltRules 가 비어있지 않다.
    def _r6():
        blocked = verdict["value"] == "BLOCKED"
        has_halt = bool(verdict["haltRules"])
        if blocked and not has_halt:
            errs.append("R6: BLOCKED 인데 haltRules 가 비어 있음 (중단 근거 없음)")
        if not blocked and has_halt:
            errs.append(f"R6: haltRules {verdict['haltRules']} 가 있는데 판정이 {verdict['value']}")
    rule(_r6)

    # R7 — PASS_RESTRICTED ⟺ restrictions(H4) + PATH_RESTRICTED 경고. PASS 는 둘 다 비어야 한다.
    def _r7():
        v = verdict["value"]
        has_rst = bool(verdict["restrictions"])
        warned = ("PATH_RESTRICTED", "verdict") in warns
        if v == "PASS_RESTRICTED":
            if not has_rst:
                errs.append("R7: PASS_RESTRICTED 인데 restrictions 가 비어 있음")
            if not warned:
                errs.append("R7: PASS_RESTRICTED 인데 PATH_RESTRICTED 경고가 없음")
        else:
            if has_rst:
                errs.append(f"R7: restrictions 가 있는데 판정이 {v}")
            if warned:
                errs.append(f"R7: PATH_RESTRICTED 경고가 있는데 판정이 {v}")
    rule(_r7)

    # R8 — 결정성 실패(H1)는 협상 불가 게이트다. 1.0 미만이면 H1 을 기록해야 한다.
    def _r8():
        det = metrics["determinism"]
        if det["status"] == "MEASURED" and det["value"] < 1.0:
            if "H1" not in verdict["haltRules"]:
                errs.append(f"R8: determinism={det['value']} < 1.0 인데 haltRules 에 H1 이 없음")
        elif "H1" in verdict["haltRules"] and det["status"] == "MEASURED" and det["value"] >= 1.0:
            errs.append("R8: determinism=1.0 인데 H1 이 기록됨")
    rule(_r8)

    # R9 — 게이트 실패는 경고로 드러나고, 판정 PASS 를 막는다(양방향).
    def _r9():
        failed = {g["id"] for g in gates if g["status"] == "FAIL"}
        warned = {w["trigger"].split(".", 1)[1] for w in warnings_
                  if w["code"] == "GATE_FAILED" and w["trigger"].startswith("gates.")}
        for gid in sorted(failed - warned):
            errs.append(f"R9: 게이트 {gid} 가 FAIL 인데 GATE_FAILED 경고 없음")
        for gid in sorted(warned - failed):
            errs.append(f"R9: GATE_FAILED({gid}) 인데 그 게이트는 FAIL 이 아님")
        if failed and verdict["value"] == "PASS":
            errs.append(f"R9: 무조건 게이트 {sorted(failed)} 실패인데 판정이 PASS")
    rule(_r9)

    # R10 — 미측정은 0으로 채우지 않고 경고로 드러낸다(양방향). **게이트의 미측정도 같다** —
    #       측정하지 않은 게이트가 조용히 지나가면 '통과한 게이트' 와 구분되지 않는다.
    def _r10():
        unmeasured = {f"metrics.{k}" for k in METRIC_KEYS
                      if _status(metrics.get(k)) == "NOT_MEASURED"}
        if _status(calib) == "NOT_MEASURED":
            unmeasured.add("evl.confidenceCalibration")
        for k in ("precision", "recall"):
            if _status(conflict.get(k)) == "NOT_MEASURED":
                unmeasured.add(f"evl.conflictDetection.{k}")
        unmeasured |= {f"gates.{g['id']}" for g in gates if g.get("status") == "NOT_MEASURED"}
        warned = {w["trigger"] for w in warnings_ if w["code"] == "METRIC_UNMEASURED"}
        for miss in sorted(unmeasured - warned):
            errs.append(f"R10: {miss} 가 NOT_MEASURED 인데 METRIC_UNMEASURED 경고 없음")
        for extra in sorted(warned - unmeasured):
            errs.append(f"R10: METRIC_UNMEASURED({extra}) 인데 그 지표는 NOT_MEASURED 가 아님")
    rule(_r10)

    # R11 — 버전 미확정(UNPINNED)만 경고 대상이다(양방향). 그 레이어가 쓰지 않는 요소는
    #       NOT_APPLICABLE 이며 경고 대상이 아니다 — 둘을 합치면 '버전을 모르는 상태' 가
    #       '해당 없음' 에 섞여 재현 실패의 원인을 잃는다.
    def _r11():
        unpinned = {f"versions.{k}" for k, v in versions.items()
                    if isinstance(v, dict) and v.get("status") == "UNPINNED"}
        warned = {w["trigger"] for w in warnings_ if w["code"] == "VERSION_UNPINNED"}
        for miss in sorted(unpinned - warned):
            errs.append(f"R11: {miss} 가 UNPINNED 인데 VERSION_UNPINNED 경고 없음")
        for extra in sorted(warned - unpinned):
            errs.append(f"R11: VERSION_UNPINNED({extra}) 인데 그 버전은 UNPINNED 가 아님")
    rule(_r11)

    # R12 — fixture 미고정·예시 보고서는 baseline 이 될 수 없다(I1 §1.3).
    def _r12():
        unpinned = run["fixtureHash"] == "UNPINNED"
        warned = ("UNPINNED_FIXTURE", "run.fixtureHash") in warns
        if unpinned and not warned:
            errs.append("R12: fixtureHash=UNPINNED 인데 UNPINNED_FIXTURE 경고 없음")
        if not unpinned and warned:
            errs.append("R12: UNPINNED_FIXTURE 경고가 있는데 fixtureHash 는 고정돼 있음")
        # 적용 대상 버전이 하나라도 미고정이면 그 실행은 재현할 수 없고, 재현할 수 없는
        # 실행은 기준선이 아니다. NOT_APPLICABLE(그 레이어가 안 쓰는 요소)은 대상이 아니다.
        unpinned_versions = sorted(k for k, v in versions.items()
                                   if isinstance(v, dict) and v.get("status") == "UNPINNED")
        # 재현 가능성만으로는 부족하다: 정답셋(또는 그 입력 축)이 승인되지 않았으면 그 위에서 잰
        # 수치는 기준선이 아니다(I1 §7). 승인 상태는 보고서 밖에 있으므로 GOLD_UNAPPROVED 경고를
        # 그 사실의 자리로 쓴다 — 경고가 실제 gold 상태와 맞는지는 각 레이어의 확인기가 본다
        # (L0 은 verify_l0.py V4).
        unapproved_gold = ("GOLD_UNAPPROVED", "evl.conflictDetection.goldSetId") in warns
        eligible = ((not unpinned) and run["reportKind"] == "BASELINE"
                    and not unpinned_versions and not unapproved_gold)
        if baseline["eligibleAsBaseline"] != eligible:
            errs.append(
                f"R12: eligibleAsBaseline={baseline['eligibleAsBaseline']} 인데 "
                f"fixtureHash={'UNPINNED' if unpinned else 'pinned'} · "
                f"reportKind={run['reportKind']} · "
                f"미고정 버전={unpinned_versions or '없음'} · "
                f"gold 미승인={unapproved_gold} (기대 {eligible})")
    rule(_r12)

    # R13 — calibration 은 원자료가 완전할 때만 수치를 인용한다(EVL §3.3).
    def _r13():
        st, missing = calib["status"], calib["missingRawCount"]
        if st == "MEASURED":
            if missing > 0:
                errs.append(f"R13: 원자료 누락 {missing}건인데 calibration status=MEASURED")
            if calib["population"] is None:
                errs.append("R13: calibration MEASURED 인데 population 이 없음 (모집단 불명)")
            if calib["ece"] is None:
                errs.append("R13: calibration MEASURED 인데 ece 가 없음")
            if not calib["bins"]:
                errs.append("R13: calibration MEASURED 인데 bins 가 비어 있음")
            s = sum(b["sampleCount"] for b in calib["bins"] if isinstance(b, dict))
            if s != calib["sampleCount"]:
                errs.append(f"R13: bins 표본 합 {s} != sampleCount {calib['sampleCount']}")
        warned = ("CALIBRATION_RAW_MISSING", "evl.confidenceCalibration") in warns
        if missing > 0 and not warned:
            errs.append(f"R13: 원자료 누락 {missing}건인데 CALIBRATION_RAW_MISSING 경고 없음")
        if missing == 0 and warned:
            errs.append("R13: CALIBRATION_RAW_MISSING 경고가 있는데 missingRawCount=0")
    rule(_r13)

    # R14 — 충돌 탐지 성능은 gold 충돌셋 없이 측정할 수 없다(EVL §8).
    def _r14():
        for k in ("precision", "recall"):
            if _status(conflict.get(k)) == "MEASURED" and conflict["goldSetId"] is None:
                errs.append(f"R14: conflictDetection.{k} 가 MEASURED 인데 goldSetId 가 없음")
    rule(_r14)

    # R15 — 커버리지 5클래스 체크리스트는 전부·한 번씩. 경고 여부는 상태와 일치한다.
    def _r15():
        seen = [c["class"] for c in cov_classes]
        for cls in COVERAGE_CLASSES:
            n = seen.count(cls)
            if n != 1:
                errs.append(f"R15: coverageClasses 의 {cls} 항목이 {n}개 (정확히 1개여야 함)")
        for c in cov_classes:
            should = c["state"] != "present"
            if c["warned"] != should:
                errs.append(f"R15: {c['class']}={c['state']} 인데 warned={c['warned']}")
    rule(_r15)

    # R16 — 측정하지 않은 기능을 Core 로 판정하지 않는다(I1 §5.3). 근거 링크는 필수다(G5).
    def _r16():
        for j in judgments:
            if j["judgment"] == "Core" and not j["measured"]:
                errs.append(f"R16: {j['featureId']} 는 measured=false 인데 Core 로 판정됨")
            for ref in j["evidenceRefs"]:
                if ref != run.get("runId") and not re.fullmatch(r"report:run-[A-Za-z0-9][\w.-]*", ref):
                    errs.append(f"R16: {j['featureId']} 의 근거 '{ref}' 가 실행 보고서를 가리키지 않음")
    rule(_r16)

    # R17 — 비교 가능성은 신원이 같을 때만 성립하고, 비교 불가를 '변화 없음' 으로
    #       표기하지 않는다(I1 §7.4). runId 만으로는 '같은 것을 쟀는지' 판정할 수 없다.
    def _r17():
        comparable = baseline["comparable"]
        warned = ("BASELINE_NOT_COMPARABLE", "baseline") in warns
        prev = baseline["previous"]
        if comparable:
            if prev is None:
                errs.append("R17: comparable=true 인데 previous 가 없음")
            else:
                for f in ("projectId", "layer", "track", "sourceRevision"):
                    if prev[f] != run[f]:
                        errs.append(f"R17: comparable=true 인데 {f} 가 다름 "
                                    f"(이전 {prev[f]!r} / 현재 {run[f]!r})")
                if prev["schemaVersion"] != d["schemaVersion"]:
                    errs.append(f"R17: comparable=true 인데 schemaVersion 이 다름 "
                                f"(이전 {prev['schemaVersion']!r} / 현재 {d['schemaVersion']!r})")
                if run["fixtureHash"] == "UNPINNED" or prev["fixtureHash"] == "UNPINNED":
                    errs.append("R17: comparable=true 인데 fixture 가 고정돼 있지 않음 "
                                "(미고정 실행은 비교 기준선이 아니다 — I1 §1.3)")
                elif prev["fixtureHash"] != run["fixtureHash"]:
                    errs.append("R17: comparable=true 인데 fixtureHash 가 다름 "
                                "(다른 fixture 의 수치는 직접 비교하지 않는다 — I1 §7.4)")
            if not baseline["deltas"]:
                errs.append("R17: comparable=true 인데 deltas 가 비어 있음")
            if warned:
                errs.append("R17: BASELINE_NOT_COMPARABLE 경고가 있는데 comparable=true")
        else:
            if baseline["deltas"]:
                errs.append("R17: comparable=false 인데 deltas 가 채워져 있음")
            if not baseline["reason"].strip():
                errs.append("R17: comparable=false 인데 reason 이 비어 있음")
            if not warned:
                errs.append("R17: comparable=false 인데 BASELINE_NOT_COMPARABLE 경고 없음")
    rule(_r17)

    # R18 — 경고의 trigger 가 그 code 가 가리키도록 정해진 종류의 대상을 실제로 가리킨다.
    def _r18():
        gate_ids = {g["id"] for g in gates if isinstance(g.get("id"), str)}
        for w in warnings_:
            code, trg = w["code"], w["trigger"]
            kind = TRIGGER_KIND.get(code)
            if kind is None:
                continue  # 통제어휘 위반은 스키마(R1)의 몫
            if kind == "fixture":
                ok = trg == "run.fixtureHash"
            elif kind == "version":
                ok = trg.startswith("versions.") and trg.split(".", 1)[1] in versions
            elif kind == "metric":
                ok = (trg in {f"metrics.{k}" for k in METRIC_KEYS}
                      or trg == "evl.confidenceCalibration"
                      or trg in {"evl.conflictDetection.precision", "evl.conflictDetection.recall"}
                      # 게이트의 미측정도 같은 코드로 보고한다(R10) — 대상은 실재 게이트여야 한다.
                      or (trg.startswith("gates.") and trg.split(".", 1)[1] in gate_ids))
            elif kind == "calibration":
                ok = trg == "evl.confidenceCalibration"
            elif kind == "gate":
                ok = trg.startswith("gates.") and trg.split(".", 1)[1] in gate_ids
            elif kind == "gold":
                ok = trg == "evl.conflictDetection.goldSetId"
            elif kind == "baseline":
                ok = trg == "baseline"
            else:
                ok = trg == "verdict"
            if not ok:
                errs.append(f"R18: 경고 {code} 의 trigger '{trg}' 가 실재 대상을 가리키지 않음")
    rule(_r18)

    # R19 — 식별자는 보고서 안에서 유일하다. 중복이면 경고 하나가 여러 대상을 충족한 것처럼 보인다.
    def _r19():
        for label, ids in (("failures[].id", [f["id"] for f in failures]),
                           ("gates[].id", [g["id"] for g in gates]),
                           ("featureJudgments[].featureId", [j["featureId"] for j in judgments])):
            dup = sorted({i for i in ids if ids.count(i) > 1})
            if dup:
                errs.append(f"R19: {label} 가 보고서 안에서 중복됨 {dup}")
    rule(_r19)

    # R20 — scopeCoverage 는 산식이 있는 값이다: counts.output / counts.input.
    #       정의 없이 적힌 비율은 보고서마다 분모가 달라져 비교가 성립하지 않는다.
    #       스코프에 대상이 없는 실행(input=0)은 비율이 정의되지 않으므로 NOT_APPLICABLE 이다
    #       — 0/0 을 0.0 이나 1.0 으로 적으면 '아무것도 못 했다' 와 '다 했다' 가 같은 자리에 온다.
    def _r20():
        cov = metrics["scopeCoverage"]
        if counts["input"] == 0:
            if cov["status"] != "NOT_APPLICABLE":
                errs.append(f"R20: counts.input=0 인데 scopeCoverage.status={cov['status']} "
                            f"(대상이 없는 실행의 비율은 정의되지 않는다 — NOT_APPLICABLE)")
            return
        if cov["status"] != "MEASURED":
            return
        expected = counts["output"] / counts["input"]
        if abs(cov["value"] - expected) > COVERAGE_TOLERANCE:
            errs.append(f"R20: scopeCoverage={cov['value']} 가 산식 output/input "
                        f"({counts['output']}/{counts['input']} = {expected:.4f}) 과 다름")
    rule(_r20)

    return errs


def required_paths(schema, prefix=""):
    """스키마가 요구하는 키 경로를 모두 펼친다. 빈 템플릿의 완전성 검사에 쓴다."""
    out = []
    if "$ref" in schema:
        ref = schema["$ref"].split("/")[-1]
        schema = {**SCHEMA["$defs"][ref], **{k: v for k, v in schema.items() if k != "$ref"}}
    if schema.get("type") == "array" or "items" in schema:
        return out + required_paths(schema.get("items", {}), prefix + "[]")
    for key in schema.get("required", []):
        sub = schema.get("properties", {}).get(key, {})
        path = f"{prefix}.{key}" if prefix else key
        out.append(path)
        out += required_paths(sub, path)
    return out


def template_errors(doc):
    """빈 템플릿 검사 — 스키마가 요구하는 자리가 전부 있고, 값은 placeholder 여야 한다.

    템플릿은 스키마 적합 문서가 아니다(수치 자리가 비어 있다). 대신 **스키마와 함께
    낡지 않는지**를 본다: 필드가 추가됐는데 템플릿에 자리가 없으면 작성자는 그 필드를
    영원히 모른다.
    """
    errs = []
    # 고정값이라 placeholder 로 둘 수 없는 자리 — 값 자체가 계약이다.
    literal_ok = re.compile(r"^(schemaVersion|evl\.coverageClasses\[\d+\]\.class)$")

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
        else:
            if node in (None, "", 0, False, True) or literal_ok.match(path):
                return
            if not (isinstance(node, str) and node.startswith("<") and node.endswith(">")):
                errs.append(f"템플릿: {path} 에 실제 값 {node!r} 이 들어 있음 (placeholder 여야 함)")

    walk(doc, "")

    for p in required_paths(SCHEMA):
        cur = doc
        for seg in p.split("."):
            if seg.endswith("[]"):
                seg = seg[:-2]
                cur = cur.get(seg) if isinstance(cur, dict) else None
                if not isinstance(cur, list) or not cur:
                    errs.append(f"템플릿: {p} 의 배열 자리가 비어 있어 하위 필드를 보여주지 못함")
                    cur = None
                    break
                cur = cur[0]
            else:
                if not isinstance(cur, dict) or seg not in cur:
                    errs.append(f"템플릿: 스키마 필수 경로 {p} 가 없음")
                    cur = None
                    break
                cur = cur[seg]
    return errs


def fixture_errors(doc):
    """재현 fixture 파일 자체의 최소 계약.

    보고서가 실패를 '재현 fixture' 로 가리키는데 그 파일이 무엇을 재현하는지 적혀 있지
    않으면, 다음 실행에서 그것이 회귀했는지 판정할 수 없다 — 경로 문자열만으로는
    #100 의 '실패 사례 링크 + 재현 fixture' 수용기준을 충족하지 않는다.
    """
    errs = []
    for k in ("fixtureId", "reproduces", "layer", "input", "expected"):
        if k not in doc:
            errs.append(f"재현 fixture: 필수 키 {k} 가 없음")
    rep = doc.get("reproduces")
    if isinstance(rep, dict):
        for k in ("runId", "failureId"):
            if not rep.get(k):
                errs.append(f"재현 fixture: reproduces.{k} 가 없음 (어느 실행의 어느 실패인지 불명)")
    elif "reproduces" in doc:
        errs.append("재현 fixture: reproduces 는 {runId, failureId} 객체여야 함")
    if "expected" in doc:
        exp = doc["expected"]
        if not isinstance(exp, dict):
            errs.append(f"재현 fixture: expected 는 객체여야 함 (실제 {type(exp).__name__}) — "
                        f"문자열·배열이면 어느 규칙의 무엇이 기대값인지 기계적으로 읽을 수 없다")
        elif not exp.get("rule"):
            errs.append("재현 fixture: expected.rule 이 없음 (어느 계약 규칙의 위반인지 불명)")
    return errs


def referenced_fixture_errors(registered):
    """정상 픽스처가 가리키는 재현 fixture 가 실재하고 manifest 에 등록돼 있는가.

    경로만 적고 파일이 없으면 그 실패는 재현 불가이며, manifest 에 없으면 이 스위트가
    그 파일의 형식 붕괴를 잡지 못한다.
    """
    errs = []
    for case in MANIFEST["cases"]:
        if case.get("expect") != "valid":
            continue
        doc = json.loads((EX / case["file"]).read_text())
        for f in doc.get("failures", []):
            path = f.get("fixture")
            if not isinstance(path, str):
                continue
            if not (REPO / path).exists():
                errs.append(f"{case['file']}: 재현 fixture '{path}' 가 실재하지 않음")
            elif path not in registered:
                errs.append(f"{case['file']}: 재현 fixture '{path}' 가 manifest 에 등록되지 않음")
    return errs


def manifest_errors():
    """manifest 자체의 무결성. 통제값이 아닌 expect/enforcedBy 는 오타여도 우연히 실제
    결과와 맞아떨어져 통과할 수 있으므로 먼저 거른다.

    반환: (오류 메시지 목록, 무결성 실패한 case 인덱스 집합).
    """
    errs, bad = [], set()
    seen = set()
    for i, c in enumerate(MANIFEST["cases"]):
        where = c.get("file", f"[{i}]")
        if c.get("expect") not in ("valid", "invalid", "template", "fixture"):
            errs.append(f"{where}: expect 는 valid|invalid|template|fixture 여야 함 (실제 {c.get('expect')!r})")
            bad.add(i)
        if c.get("file") in seen:
            errs.append(f"{where}: 중복 등록")
        seen.add(c.get("file"))
        if not (EX / str(c.get("file"))).exists():
            errs.append(f"{where}: 파일이 존재하지 않음")
            bad.add(i)
        if c.get("expect") == "invalid":
            if c.get("enforcedBy") not in ("schema", "validator"):
                errs.append(f"{where}: enforcedBy 는 schema|validator 여야 함 (실제 {c.get('enforcedBy')!r})")
                bad.add(i)
            rule = c.get("rule", "")
            if not (isinstance(rule, str) and rule.startswith("R")
                    and rule[1:].isdigit() and 1 <= int(rule[1:]) <= MAX_RULE):
                errs.append(f"{where}: rule 은 R1~R{MAX_RULE} 여야 함 (실제 {rule!r})")
                bad.add(i)
            if not c.get("expectedError"):
                errs.append(f"{where}: expectedError 가 비어 있음")
                bad.add(i)
            if c.get("enforcedBy") == "schema" and rule not in RULE_SCHEMA_MARKERS:
                errs.append(f"{where}: schema 케이스의 rule {rule!r} 에 위치 표지가 없어 "
                            f"라벨 대조가 수행되지 않는다 (RULE_SCHEMA_MARKERS 에 추가 필요)")
                bad.add(i)
    if not any(c.get("expect") == "template" for c in MANIFEST["cases"]):
        errs.append("manifest: 빈 템플릿 케이스가 없다 (#100 산출물 요구사항)")
    # 총계를 manifest 안에 못박는다 — 계약 문서의 완료조건("N cases")이 인용하는 수이며,
    # 픽스처가 늘거나 줄었는데 문서의 N 이 그대로면 완료조건이 실제와 어긋난다.
    if MANIFEST.get("ruleRange") != f"R1~R{MAX_RULE}":
        errs.append(f"manifest: ruleRange {MANIFEST.get('ruleRange')!r} 가 확인기의 규칙 범위 "
                    f"R1~R{MAX_RULE} 와 다름 (계약 §4 제목·manifest $comment 도 함께 갱신할 것)")
    if MANIFEST.get("caseCount") != len(MANIFEST["cases"]):
        errs.append(f"manifest: caseCount {MANIFEST.get('caseCount')!r} 가 실제 케이스 수 "
                    f"{len(MANIFEST['cases'])} 와 다름 (계약 §4.1·§8 의 'N cases' 도 함께 갱신할 것)")
    return errs, bad


def main():
    for v, s in SCHEMAS.items():
        Draft202012Validator.check_schema(s)
    mismatches = 0
    verified_rules = set()  # 라벨·계층·위치·메시지 대조까지 통과한 규칙만 집계한다

    man_errs, bad_cases = manifest_errors()
    for e in man_errs:
        mismatches += 1
        print(f"FAIL manifest 무결성 — {e}")

    for i, case in enumerate(MANIFEST["cases"]):
        if i in bad_cases:
            continue
        doc = json.loads((EX / case["file"]).read_text())

        if case["expect"] in ("template", "fixture"):
            sub = template_errors(doc) if case["expect"] == "template" else fixture_errors(doc)
            ok = not sub
            mismatches += not ok
            print(f"{'OK  ' if ok else 'FAIL'} {case['file']:<44} "
                  f"{'' if ok else sub[0]}")
            continue

        # 픽스처가 **선언한 버전**의 스키마로 잰다 — 옛 버전 보고서를 새 스키마로 재면 그 자체가
        # 버전 정책(§7.3)을 무의미하게 만든다.
        schema_errs = sorted(Draft202012Validator(schema_for(doc)).iter_errors(doc),
                             key=lambda e: list(e.path))
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
        if ok and not expected:
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
                mk in "/".join(map(str, se.absolute_schema_path)) or mk in se.message
                for se in schema_errs for mk in RULE_SCHEMA_MARKERS[case["rule"]]
            ):
                ok, detail = False, (
                    f"규칙 라벨 불일치 — {case['rule']} 의 표지 "
                    f"{RULE_SCHEMA_MARKERS[case['rule']]} 가 실제 위반 위치 "
                    f"{['/'.join(map(str, se.absolute_schema_path)) for se in schema_errs]} 에 없음")
            elif len(schema_errs) > 1:
                ok, detail = False, (f"스키마 위반 {len(schema_errs)}건 — 단일 위반이어야 함: "
                                     f"{[e.message for e in schema_errs]}")
            else:
                actual = [e.message for e in schema_errs] + cross_errs
                if not any(case["expectedError"] in a for a in actual):
                    ok, detail = False, f"기대 오류 '{case['expectedError']}' 미검출: {actual}"

        if ok and not expected:
            verified_rules.add(case["rule"])
        mismatches += not ok
        print(f"{'OK  ' if ok else 'FAIL'} {case['file']:<44} {detail}")

    registered = {f"docs/superpowers/specs/schemas/rqr-examples/{c['file']}"
                  for c in MANIFEST["cases"] if c.get("expect") == "fixture"}
    for e in referenced_fixture_errors(registered):
        mismatches += 1
        print(f"FAIL 재현 fixture 참조 — {e}")

    uncovered = [f"R{i}" for i in range(1, MAX_RULE + 1) if f"R{i}" not in verified_rules]
    if uncovered:
        mismatches += 1
        print(f"FAIL 규칙 커버리지 — 음성 픽스처가 없는 불변식: {uncovered}")

    print(f"\n{len(MANIFEST['cases'])} cases, {mismatches} mismatches")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
