#!/usr/bin/env python3
"""answer-shape v0 조합 스윕 — 손으로 쓴 픽스처가 닿지 못하는 공간을 훑는다.

manifest 픽스처는 "이 규칙이 걸리는가", fuzz.py 는 "안 걸리는 게 있는가"를 본다.
이 스크립트는 셋째 질문을 본다: **"규칙들이 서로 모순되지 않는가"**.

  1) 충족가능성  intent × 소스 클래스 조합마다 **적합한 응답이 존재하는가**.
                존재하지 않으면 규칙끼리 충돌해 그 상황을 표현할 방법이 없다는 뜻이다.
  2) 결정성      같은 입력을 여러 번 판정해도 같은 결과인가 (I1 H1 의 자기적용).
  3) 순서 무관   배열·키 순서를 바꿔도 판정이 같은가.
                랭킹은 의미를 갖지만 **어떤 규칙도 순서에 의존해서는 안 된다**.
  4) 경계값      수치·식별자 경계에서 스키마가 의도대로 갈리는가.
  5) 결손 내성   한 곳이 깨져도 독립적인 다른 위반이 그대로 보고되는가.
  6) 충돌 상태   NEEDS_CHECK·COEXIST·RESOLVED 세 상태가 모두 표현 가능한가.
  7) 무작위      임의 변형에 예외로 죽지 않고 같은 입력에 같은 판정을 내는가.

여기서 만드는 문서는 **규칙 검사용 입력**이지 예제 픽스처가 아니다. 그래서
리포에 실재하지 않는 소스 클래스(issue·adr·runtime)에는 합성 좌표를 쓴다 —
커밋되는 예제(`examples/`)에만 실좌표 규칙이 적용된다.

    pip install jsonschema && python3 sweep.py
"""
import copy
import itertools
import json
import random
import pathlib
import sys

from jsonschema import Draft202012Validator

sys.dont_write_bytecode = True
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from validate import CORE_CLASSES, WARN_FOR_ABSENT, cross_field_errors  # noqa: E402

HERE = pathlib.Path(__file__).parent
SCHEMA = json.loads((HERE / "answer-shape.v0.schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA)

CLASSES = ["code", "issue", "adr", "test", "runtime"]
SQL = "backend/src/main/resources/com/ontostudio/rdb/legacy-sample.sql"
KT = "backend/src/main/kotlin/com/ontostudio/rel/RelationService.kt"
TESTF = "backend/src/test/kotlin/com/ontostudio/rel/RelationJudgeTest.kt"
LOCATOR = {                       # 실재하는 것은 실좌표, 없는 클래스는 합성 좌표
    "code": f"{SQL}#L122-L128",
    "test": f"{TESTF}#L36-L57",
    "issue": "issue:432#comment-7",
    "adr": "docs/adr/0001-fk-policy.md#L10-L20",
    "runtime": "log:payment-svc/2026-07-29#L1-L5",
}
HASH = "sha256:" + "0" * 64


def judge(doc):
    se = [e.message for e in VALIDATOR.iter_errors(doc)]
    ce = cross_field_errors(doc)
    return (not se and not ce), se + ce


def evidence(i, cls, stance="supports"):
    return {
        "id": f"ev-{i}", "source": cls,
        "ref": {"sourceId": f"src-{cls}", "locator": LOCATOR[cls], "revision": "3c27259"},
        "confidence": 0.6,
        "signals": {"finality": 0.6, "freshness": 0.6, "authority": 0.6,
                    "corroboration": 0.4, "contradicted": 0.2},
        "reason": [{"text": f"{cls} 근거", "basis": [{"layer": "L1", "id": f"obs-{cls}"}]}],
        "stance": stance,
    }


def build(intent, present, absent_state="absent", with_conflict=False,
          conflict_status="NEEDS_CHECK"):
    """(intent, present 클래스 집합) 에 대해 계약을 만족하는 응답을 구성한다."""
    evs, warns = [], []
    for n, cls in enumerate(sorted(present), start=1):
        evs.append(evidence(n, cls))
    if with_conflict and len(evs) >= 2:
        evs[-1]["stance"] = "contradicts"

    cov = {c: ("present" if c in present else absent_state) for c in CLASSES}
    for c in CLASSES:
        if cov[c] == "absent":
            warns.append({"code": WARN_FOR_ABSENT[c], "message": f"{c} 없음",
                          "trigger": f"coverage.{c}"})
        elif cov[c] == "not_collected":
            warns.append({"code": "NOT_COLLECTED", "message": f"{c} 미수집",
                          "trigger": f"coverage.{c}"})

    conflicts, ceiling_reasons = [], []
    if with_conflict and len(evs) >= 2:
        c = {"id": "cf-1", "between": [evs[0]["id"], evs[-1]["id"]],
             "claim": "상충", "status": conflict_status}
        if conflict_status == "RESOLVED":
            c["resolvedBy"] = {"layer": "L3", "id": "claim-confirmed"}
        conflicts = [c]
        if conflict_status == "NEEDS_CHECK":
            warns.append({"code": "CONFLICT_UNRESOLVED", "message": "미해결", "trigger": "cf-1"})
            ceiling_reasons = ["CONFLICT_UNRESOLVED"]

    # 보류 조건 (§6.2) — 성립하면 ABSTAIN 과 그 사유를 가리키는 trigger 가 필요하다
    core = CORE_CLASSES[intent]
    cond1 = not evs
    cond2 = all(cov[c] != "present" for c in core)
    cond3 = any(c["status"] == "NEEDS_CHECK" for c in conflicts)
    if cond1 or cond2 or cond3:
        if cond3:
            trg = "cf-1"
        elif cond2:
            trg = f"coverage.{[c for c in core if cov[c] != 'present'][0]}"
        else:
            trg = "evidence"
        warns.append({"code": "ABSTAIN", "message": "보류", "trigger": trg})

    audit = {"bundleId": "bnd-sweep", "promptHash": HASH,
             "evidenceIds": [e["id"] for e in evs], "revision": "3c27259",
             "createdAt": "2026-07-29T03:00:00Z",
             "ceilingApplied": bool(ceiling_reasons)}
    if ceiling_reasons:
        audit["ceilingReasons"] = ceiling_reasons

    return {
        "schemaVersion": "answer-shape/v0",
        "task": {"intent": intent, "target": {"kind": "TABLE", "ref": "TB_X"}},
        "evidence": evs, "conflicts": conflicts, "coverage": cov,
        "confidence_overall": 0.5, "warnings": warns, "audit": audit,
    }


def sweep_satisfiable():
    """intent × 소스 조합마다 적합한 응답이 존재해야 한다."""
    bad, n = [], 0
    for intent in CORE_CLASSES:
        for k in range(0, len(CLASSES) + 1):
            for present in itertools.combinations(CLASSES, k):
                for absent_state in ("absent", "not_collected"):
                    for wc in (False, True):
                        if wc and len(present) < 2:
                            continue
                        doc = build(intent, set(present), absent_state, wc)
                        n += 1
                        ok, why = judge(doc)
                        if not ok:
                            bad.append((intent, present, absent_state, wc, why[0]))
    return n, bad


def sweep_determinism(docs, runs=5):
    """같은 입력 -> 같은 판정 (I1 H1)."""
    bad = []
    for name, d in docs:
        verdicts = {json.dumps(sorted(judge(copy.deepcopy(d))[1])) for _ in range(runs)}
        if len(verdicts) != 1:
            bad.append((name, len(verdicts)))
    return len(docs) * runs, bad


def sweep_order_invariance(docs):
    """배열·키 순서를 바꿔도 판정이 같아야 한다. 어떤 규칙도 순서에 의존하면 안 된다."""
    bad, n = [], 0
    for name, d in docs:
        base = sorted(judge(d)[1])
        variants = {
            "warnings 역순": lambda x: x["warnings"].reverse(),
            "evidence 역순": lambda x: x["evidence"].reverse(),
            "conflicts 역순": lambda x: x["conflicts"].reverse(),
            "evidenceIds 역순": lambda x: x["audit"]["evidenceIds"].reverse(),
            "coverage 키 역순": lambda x: x.__setitem__(
                "coverage", dict(reversed(list(x["coverage"].items())))),
            "최상위 키 역순": None,
        }
        for label, fn in variants.items():
            v = copy.deepcopy(d)
            if fn is None:
                v = dict(reversed(list(v.items())))
            else:
                fn(v)
            n += 1
            if sorted(judge(v)[1]) != base:
                bad.append((name, label))
    return n, bad


def sweep_boundaries():
    """수치·식별자 경계에서 의도대로 갈리는가. (입력, 승인되어야 하는가)"""
    base = build("IMPACT", {"code"})
    cases = []
    for v, want in [(0.0, True), (1.0, True), (0.5, True), (1.0000001, False),
                    (-0.0, True), (-0.0001, False), (2, False), (1, True), (0, True)]:
        d = copy.deepcopy(base); d["evidence"][0]["confidence"] = v
        cases.append((f"confidence={v!r}", d, want))
    for v, want in [("ev-1", True), ("EV_1", True), ("ev.1:a-b", True),
                    ("-ev", False), ("ev 1", False), ("", False), ("ev\n1", False)]:
        d = copy.deepcopy(base)
        d["evidence"][0]["id"] = v
        d["audit"]["evidenceIds"] = [v]
        cases.append((f"id={v!r}", d, want))
    for v, want in [("sha256:" + "a" * 64, True), ("sha256:" + "A" * 64, False),
                    ("sha256:" + "a" * 63, False), ("md5:" + "a" * 32, False)]:
        d = copy.deepcopy(base); d["audit"]["promptHash"] = v
        cases.append((f"promptHash={v[:14]}…", d, want))
    bad = []
    for label, doc, want in cases:
        got = judge(doc)[0]
        if got != want:
            bad.append((label, "승인" if got else "거부", "승인" if want else "거부"))
    return len(cases), bad


def sweep_partial_damage():
    """구조가 깨진 문서에서도 **독립적인 다른 위반이 그대로 보고돼야** 한다.

    한 곳의 결손 때문에 규칙 하나가 통째로 멈추면, 그 문서에 있는 다른 위반이
    사라져 '단일 위반' 판정과 회귀 검출이 동시에 무너진다. 스키마가 잡아주는
    입력이라도 교차 계층은 자기 몫을 계속 해야 한다.
    """
    base = build("IMPACT", {"code", "test"})
    probes = []

    def p(label, damage, expect_rule):
        d = copy.deepcopy(base)
        damage(d)
        probes.append((label, d, expect_rule))

    def drop_no_issue(d):
        d["warnings"] = [w for w in d["warnings"] if w["code"] != "NO_ISSUE"]

    # 결손을 '앞쪽'에 두어, 순서 의존이 있으면 뒤쪽 검사가 사라지도록 만든다
    p("알 수 없는 coverage 키(맨 앞) + NO_ISSUE 누락",
      lambda d: (d.__setitem__("coverage", dict([("slack", "absent")] + list(d["coverage"].items()))),
                 drop_no_issue(d)), "A11")
    p("coverage 값 타입 오류 + NO_ISSUE 누락",
      lambda d: (d["coverage"].__setitem__("code", 1), drop_no_issue(d)), "A11")
    p("evidence.source 객체 + 커버리지 위조",
      lambda d: (d["evidence"][0].__setitem__("source", {"x": 1}),
                 d["coverage"].__setitem__("runtime", "present")), "A5")
    p("audit 제거 + 커버리지 위조",
      lambda d: (d.pop("audit"), d["coverage"].__setitem__("runtime", "present")), "A5")
    p("warnings 를 배열 아닌 값으로 + 증거 id 중복",
      lambda d: (d.__setitem__("warnings", "not-an-array"),
                 d["evidence"].append(copy.deepcopy(d["evidence"][0]))), "A19")
    p("evidence[0] id 제거 + 충돌 유령 참조",
      lambda d: (d["evidence"][0].pop("id"),
                 d.__setitem__("conflicts", [{"id": "cf-x", "between": ["ghost-1", "ghost-2"],
                                              "claim": "x", "status": "COEXIST"}])), "A6")

    bad = []
    for label, doc, rule in probes:
        try:
            got = cross_field_errors(doc)
        except Exception as exc:                      # 교차 검사가 죽으면 그 자체가 실패다
            bad.append((label, rule, f"예외 {type(exc).__name__}"))
            continue
        if not any(e.startswith(rule + ":") for e in got):
            bad.append((label, rule, f"보고된 것: {got or '없음'}"))
    return len(probes), bad


def sweep_conflict_states():
    """intent × 충돌 상태 전수 — 세 상태 모두 표현 가능해야 한다.

    NEEDS_CHECK 는 보류를 부르고, COEXIST·RESOLVED 는 '충돌을 닫는' 비보류
    경로다(§6.2). 이 경로가 실제로 열려 있지 않으면 A16 은 사실상
    '충돌이 있으면 영원히 보류'가 되어 답할 수 있는 질문을 막는다.
    """
    bad, n = [], 0
    for intent in CORE_CLASSES:
        for present in (("code", "test"), ("code", "issue"), ("adr", "issue"),
                        ("code", "issue", "adr", "test", "runtime")):
            for status in ("NEEDS_CHECK", "COEXIST", "RESOLVED"):
                for absent_state in ("absent", "not_collected"):
                    doc = build(intent, set(present), absent_state, True, status)
                    n += 1
                    ok, why = judge(doc)
                    if not ok:
                        bad.append((intent, present, status, why[0]))
                    # COEXIST·RESOLVED 는 그 충돌만으로 보류를 부르지 않아야 한다
                    core_ok = any(doc["coverage"][c] == "present" for c in CORE_CLASSES[intent])
                    abstained = any(w["code"] == "ABSTAIN" for w in doc["warnings"])
                    if status != "NEEDS_CHECK" and core_ok and abstained:
                        bad.append((intent, present, status, "충돌을 닫았는데도 보류가 필요해짐"))
    return n, bad


def sweep_random(seed=20260729, rounds=3000):
    """무작위 변형 — 판정이 죽지 않고, 같은 입력에 같은 결과를 내는가.

    임의 입력에 대한 적합/부적합은 단정할 수 없다. 여기서 요구하는 것은 두 가지다:
    **예외로 죽지 않을 것**, 그리고 **같은 입력에 같은 판정을 낼 것**(I1 H1).
    seed 를 고정해 실패를 재현할 수 있게 한다.
    """
    rnd = random.Random(seed)
    bases = [json.loads(p.read_text()) for p in sorted((HERE / "examples").glob("valid.*.json"))]
    VALUES = [None, True, False, 0, 1, -1, 2.5, "", "x", [], {}, [1, 2], {"a": 1},
              "1990-12-31T23:59:60Z", "present", "ABSTAIN", "ev-1", 1e309]

    def walk(o, path=None):
        path = path or []
        out = [(path, o)]
        if isinstance(o, dict):
            for k, v in o.items():
                out += walk(v, path + [k])
        elif isinstance(o, list):
            for i, v in enumerate(o):
                out += walk(v, path + [i])
        return out

    def setp(doc, path, val, delete=False):
        cur = doc
        for k in path[:-1]:
            cur = cur[k]
        if delete:
            if isinstance(cur, dict):
                cur.pop(path[-1], None)
            elif isinstance(cur, list) and isinstance(path[-1], int) and path[-1] < len(cur):
                cur.pop(path[-1])
        else:
            cur[path[-1]] = val

    crashes, flaky = [], []
    for _ in range(rounds):
        d = copy.deepcopy(rnd.choice(bases))
        for _ in range(rnd.randint(1, 3)):
            paths = [p for p, _ in walk(d) if p]
            path = rnd.choice(paths)
            try:
                if rnd.random() < 0.25:
                    setp(d, path, None, delete=True)
                else:
                    setp(d, path, rnd.choice(VALUES))
            except (KeyError, IndexError, TypeError):
                break
        try:
            v1 = sorted(judge(d)[1])
            v2 = sorted(judge(copy.deepcopy(d))[1])
        except Exception as exc:
            crashes.append((type(exc).__name__, str(exc)[:70], json.dumps(d)[:120]))
            continue
        if v1 != v2:
            flaky.append(json.dumps(d)[:120])
    return rounds, crashes, flaky


def main():
    fails = 0
    n, bad = sweep_satisfiable()
    print(f"1) 충족가능성  {n:>5}건 — {'전부 표현 가능' if not bad else f'★표현 불가 {len(bad)}건'}")
    for b in bad[:8]:
        print(f"     intent={b[0]} present={b[1]} 부재상태={b[2]} 충돌={b[3]}\n       -> {b[4]}")
    fails += len(bad)

    docs = [(p.name, json.loads(p.read_text())) for p in sorted((HERE / "examples").glob("valid.*.json"))]
    docs += [(f"생성:{i}", build(it, set(c)))
             for i, (it, c) in enumerate([("VERIFY", ["code", "test"]), ("EXPLAIN", ["adr"]),
                                          ("HISTORY", ["issue"]), ("LOCATE", ["code"])])]
    n, bad = sweep_determinism(docs)
    print(f"2) 결정성      {n:>5}건 — {'동일 입력 동일 판정' if not bad else f'★흔들림 {bad}'}")
    fails += len(bad)

    n, bad = sweep_order_invariance(docs)
    print(f"3) 순서 무관   {n:>5}건 — {'순서 비의존' if not bad else f'★순서 의존 {len(bad)}건'}")
    for b in bad[:8]:
        print(f"     {b[0]} / {b[1]}")
    fails += len(bad)

    n, bad = sweep_boundaries()
    print(f"4) 경계값      {n:>5}건 — {'의도대로 갈림' if not bad else f'★불일치 {len(bad)}건'}")
    for b in bad:
        print(f"     {b[0]}: 실제 {b[1]} / 기대 {b[2]}")
    fails += len(bad)

    n, bad = sweep_partial_damage()
    print(f"5) 결손 내성   {n:>5}건 — {'다른 위반이 살아남음' if not bad else f'★삼켜짐 {len(bad)}건'}")
    for b in bad:
        print(f"     {b[0]} (기대 {b[1]}) -> {b[2]}")
    fails += len(bad)

    n, bad = sweep_conflict_states()
    print(f"6) 충돌 상태   {n:>5}건 — {'세 상태 모두 표현 가능' if not bad else f'★문제 {len(bad)}건'}")
    for b in bad[:6]:
        print(f"     intent={b[0]} present={b[1]} status={b[2]} -> {b[3]}")
    fails += len(bad)

    n, crashes, flaky = sweep_random()
    msg = "예외 0 · 흔들림 0" if not crashes and not flaky else f"★예외 {len(crashes)} · 흔들림 {len(flaky)}"
    print(f"7) 무작위      {n:>5}건 — {msg}")
    for c in crashes[:6]:
        print(f"     {c[0]}: {c[1]}\n       입력 {c[2]}")
    for f in flaky[:3]:
        print(f"     비결정: {f}")
    fails += len(crashes) + len(flaky)

    print()
    print("스윕 통과" if not fails else f"스윕 실패 {fails}건")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
