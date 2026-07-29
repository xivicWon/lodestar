#!/usr/bin/env python3
"""answer-shape v0 변이 하네스 — 손으로 쓴 픽스처가 놓친 구멍을 찾는다.

manifest 의 픽스처는 "이 규칙이 걸리는가"를 확인한다. 이 스크립트는 반대로
**"걸려야 하는데 안 걸리는 게 있는가"** 를 찾는다. 정상 픽스처에 기계적으로
변이를 가해 두 방향을 모두 검사한다.

  MUST-REJECT : 계약상 위반이 되는 변이 -> 반드시 거부돼야 한다.
                통과하면 그것이 미검출 구멍이다(= 새 결함).
  MUST-ACCEPT : 계약상 여전히 적합한 변이 -> 반드시 승인돼야 한다.
                거부되면 그것이 과잉 검출이다(= 정상 응답을 막는 오탐).

    pip install jsonschema && python3 fuzz.py

계약: ../2026-07-29-evl-answer-shape-contract.md
"""
import copy
import json
import pathlib
import sys

from jsonschema import Draft202012Validator

sys.dont_write_bytecode = True
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from validate import cross_field_errors  # noqa: E402

HERE = pathlib.Path(__file__).parent
SCHEMA = json.loads((HERE / "answer-shape.v0.schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA)
EX = HERE / "examples"

SIGNALS = ["finality", "freshness", "authority", "corroboration", "contradicted"]


def judge(doc):
    """확인기 전체(스키마 + 교차)의 판정과 사유."""
    se = [e.message for e in VALIDATOR.iter_errors(doc)]
    ce = cross_field_errors(doc)
    return (not se and not ce), se + ce


def judge_cross_only(doc):
    """교차 규칙만으로 판정한다 — C0 가 교차 규칙만 이식한 상황의 재현.

    스키마가 대신 잡아주는 덕분에 교차 규칙의 구멍이 가려지는 것을 막는다.
    """
    ce = cross_field_errors(doc)
    return (not ce), ce


# --------------------------------------------------------------------------
# 변이 생성기: (라벨, 문서) 를 내놓는다
# --------------------------------------------------------------------------

def _paths(o, p=""):
    """문서 안의 모든 (경로, 부모, 키) — 필드 삭제 변이에 쓴다."""
    if isinstance(o, dict):
        for k, v in o.items():
            yield f"{p}.{k}", o, k
            yield from _paths(v, f"{p}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _paths(v, f"{p}[{i}]")


def _apply(base, label, fn):
    """변이가 **실제로 문서를 바꿨을 때만** 내놓는다.

    빈 배열 등으로 변이가 no-op 이 되면 원본이 그대로 나오는데, 그것을
    '통과해서는 안 되는데 통과'로 세면 하네스가 스스로 거짓 결함을 만든다.
    """
    d = copy.deepcopy(base)
    try:
        fn(d)
    except (KeyError, IndexError, TypeError, AttributeError):
        return None
    return (label, d) if d != base else None


def _mutators(base):
    """(라벨, 변이함수, 계층) 을 내놓는다.

    문서가 아니라 **함수**를 내놓는 이유: 2중 변이를 만들 때 문서를 병합하면
    같은 최상위 키를 건드린 두 변이 중 하나가 덮어써져 라벨과 실제 내용이
    달라진다. 함수를 순차 적용해야 두 변이가 모두 살아 있는 문서가 된다.
    """
    def m(label, fn):
        yield label, fn, "any"

    # 1) 필수 필드 삭제 — 스키마가 required 로 지정한 것 전부
    def required_paths(doc, schema, path=""):
        if not isinstance(schema, dict):
            return
        for r in schema.get("required", []):
            yield f"{path}.{r}"
        for k, sub in (schema.get("properties") or {}).items():
            if isinstance(doc, dict) and k in doc:
                ref = sub.get("$ref")
                sub = SCHEMA["$defs"][ref.split("/")[-1]] if ref else sub
                yield from required_paths(doc[k], sub, f"{path}.{k}")

    def _del_path(keys):
        def f(d):
            cur = d
            for k in keys[:-1]:
                cur = cur.get(k) if isinstance(cur, dict) else None
                if cur is None:
                    return
            if isinstance(cur, dict):
                cur.pop(keys[-1], None)
        return f

    for rp in dict.fromkeys(required_paths(base, SCHEMA)):
        keys = [k for k in rp.split(".") if k]
        yield f"필수필드 삭제 {rp}", _del_path(keys), "any"

    # 배열 원소 안의 필수 필드도 삭제해 본다
    for arr, fields in (("evidence", ["id", "source", "ref", "confidence", "signals", "reason", "stance"]),
                        ("warnings", ["code", "message", "trigger"]),
                        ("conflicts", ["id", "between", "claim", "status"])):
        for f in fields:
            def _del_item(a=arr, key=f):
                def g(d):
                    if d.get(a) and isinstance(d[a], list) and d[a] and isinstance(d[a][0], dict):
                        d[a][0].pop(key, None)
                return g
            yield f"필수필드 삭제 {arr}[0].{f}", _del_item(), "any"

    # 2) 타입·범위 위반
    for lbl, fn in [
        ("confidence 범위 초과", lambda d: d["evidence"] and d["evidence"][0].__setitem__("confidence", 1.01)),
        ("confidence 음수", lambda d: d["evidence"] and d["evidence"][0].__setitem__("confidence", -0.01)),
        ("confidence_overall 범위 초과", lambda d: d.__setitem__("confidence_overall", 1.5)),
        ("confidence 문자열", lambda d: d["evidence"] and d["evidence"][0].__setitem__("confidence", "0.5")),
        ("schemaVersion 변조", lambda d: d.__setitem__("schemaVersion", "answer-shape/v1")),
        ("최상위 추가 필드", lambda d: d.__setitem__("__extra", 1)),
        ("evidence 추가 필드", lambda d: d["evidence"] and d["evidence"][0].__setitem__("__x", 1)),
        ("audit 추가 필드", lambda d: d["audit"].__setitem__("__x", 1)),
        ("intent 미정의 값", lambda d: d["task"].__setitem__("intent", "SUMMARIZE")),
        ("source 미정의 값", lambda d: d["evidence"] and d["evidence"][0].__setitem__("source", "slack")),
        ("stance 미정의 값", lambda d: d["evidence"] and d["evidence"][0].__setitem__("stance", "neutral")),
        ("coverage 미정의 값", lambda d: d["coverage"].__setitem__("adr", "maybe")),
        ("coverage 퍼센트", lambda d: d["coverage"].__setitem__("adr", 0.7)),
        ("coverage 미정의 키", lambda d: d["coverage"].__setitem__("slack", "absent")),
        ("warning 미정의 코드", lambda d: d["warnings"] and d["warnings"][0].__setitem__("code", "LOOKS_FINE")),
        ("conflict 미정의 status", lambda d: d["conflicts"] and d["conflicts"][0].__setitem__("status", "MAYBE")),
        ("promptHash 원문", lambda d: d["audit"].__setitem__("promptHash", "왜 FK가 없나요?")),
        ("promptHash 짧은 해시", lambda d: d["audit"].__setitem__("promptHash", "sha256:1a4d7e90")),
        ("createdAt 불가능한 날짜", lambda d: d["audit"].__setitem__("createdAt", "2026-02-30T00:00:00Z")),
        ("createdAt 13월", lambda d: d["audit"].__setitem__("createdAt", "2026-13-01T00:00:00Z")),
        ("createdAt 형식 붕괴", lambda d: d["audit"].__setitem__("createdAt", "2026/07/29 02:00")),
        ("createdAt 소문자 t/z", lambda d: d["audit"].__setitem__("createdAt", "2026-07-29t02:00:11z")),
        ("reason 빈 배열", lambda d: d["evidence"] and d["evidence"][0].__setitem__("reason", [])),
        ("basis 빈 배열", lambda d: d["evidence"] and d["evidence"][0]["reason"][0].__setitem__("basis", [])),
        ("basis layer 오류", lambda d: d["evidence"] and d["evidence"][0]["reason"][0]["basis"][0].__setitem__("layer", "L9")),
        ("locator 빈 문자열", lambda d: d["evidence"] and d["evidence"][0]["ref"].__setitem__("locator", "")),
        ("between 1개", lambda d: d["conflicts"] and d["conflicts"][0].__setitem__("between", ["ev-1"])),
        ("between 중복", lambda d: d["conflicts"] and d["conflicts"][0].__setitem__("between", ["ev-1", "ev-1"])),
    ]:
        yield lbl, fn, "any"

    # 3) 교차 필드 관계 파괴
    def _inject_false_abstain(d):
        """조건 1~3 을 모두 끄고 ABSTAIN 만 남긴다 -> A16 역방향에 걸려야 한다."""
        if any(w["code"] == "ABSTAIN" for w in d["warnings"]):
            for c in d["conflicts"]:                 # 미해결 충돌을 닫는다
                if c["status"] == "NEEDS_CHECK":
                    c["status"] = "COEXIST"
            d["warnings"] = [w for w in d["warnings"] if w["code"] != "CONFLICT_UNRESOLVED"]
            d["audit"]["ceilingApplied"] = False
            d["audit"].pop("ceilingReasons", None)
            return
        d["warnings"].append({"code": "ABSTAIN", "message": "근거 없는 보류",
                              "trigger": "evidence"})

    def _drop_sole_source(d):
        counts = {}
        for e in d["evidence"]:
            counts[e["source"]] = counts.get(e["source"], 0) + 1
        for i, e in enumerate(d["evidence"]):
            if counts[e["source"]] == 1:
                d["evidence"].pop(i)
                return
        return False

    def flip_cov(state):
        def f(d):
            for k, v in list(d["coverage"].items()):
                if v != state:
                    d["coverage"][k] = state
                    return
            return False
        return f

    for lbl, fn in [
        ("커버리지를 present 로 위조", flip_cov("present")),
        ("증거 있는데 absent 로 은폐", lambda d: d["evidence"] and d["coverage"].__setitem__(d["evidence"][0]["source"], "absent")),
        ("증거 있는데 미수집으로", lambda d: d["evidence"] and d["coverage"].__setitem__(d["evidence"][0]["source"], "not_collected")),
        ("경고 전부 삭제", lambda d: d.__setitem__("warnings", [])),
        ("첫 경고 삭제", lambda d: d["warnings"] and d["warnings"].pop(0)),
        ("경고 trigger 유령", lambda d: d["warnings"] and d["warnings"][0].__setitem__("trigger", "does-not-exist")),
        ("충돌 참조 유령", lambda d: d["conflicts"] and d["conflicts"][0].__setitem__("between", ["ev-1", "ghost"])),
        ("증거 id 중복", lambda d: len(d["evidence"]) > 1 and d["evidence"][1].__setitem__("id", d["evidence"][0]["id"])),
        ("충돌 id = 증거 id", lambda d: d["conflicts"] and d["evidence"] and d["conflicts"][0].__setitem__("id", d["evidence"][0]["id"])),
        ("audit.evidenceIds 비움", lambda d: d["audit"].__setitem__("evidenceIds", [])),
        ("응답 증거를 감사에서 제외", lambda d: d["evidence"] and d["audit"].__setitem__(
            "evidenceIds", [i for i in d["audit"]["evidenceIds"] if i != d["evidence"][0]["id"]])),
        ("상한 적용 해제", lambda d: d["audit"]["ceilingApplied"] and (
            d["audit"].__setitem__("ceilingApplied", False), d["audit"].pop("ceilingReasons", None))),
        ("상한 사유 위조", lambda d: d["audit"].get("ceilingReasons") is not None and
            d["audit"].__setitem__("ceilingReasons", ["DEGRADED_SOURCE"])),
        ("상한 사유 비움", lambda d: d["audit"].get("ceilingReasons") is not None and
            d["audit"].__setitem__("ceilingReasons", [])),
        ("신호 null 인데 경고 없음", lambda d: d["evidence"] and (
            d["evidence"][0]["signals"].__setitem__("corroboration", None),
            d.__setitem__("warnings", [w for w in d["warnings"] if w["code"] != "SIGNAL_UNMEASURED"]))),
        ("미측정 경고만 있고 값은 숫자", lambda d: d["evidence"] and d["warnings"].append(
            {"code": "SIGNAL_UNMEASURED", "message": "x", "trigger": f"{d['evidence'][0]['id']}.signals.finality"})),
        ("반대 증거를 충돌에서 분리", lambda d: any(e["stance"] == "contradicts" for e in d["evidence"])
            and d.__setitem__("conflicts", [])),
        ("반대 증거로 뒤집기", lambda d: d["evidence"] and d["evidence"][0].__setitem__("stance", "contradicts")),
        ("미해결 충돌인데 보류 안 함", lambda d: any(c["status"] == "NEEDS_CHECK" for c in d["conflicts"])
            and d.__setitem__("warnings", [w for w in d["warnings"] if w["code"] != "ABSTAIN"])),
        # 보류 조건이 하나도 성립하지 않는 문서에 ABSTAIN 을 끼워 넣는다(허위 보류).
        # 이전 구현은 조건식의 boolean 만 반환해 문서를 바꾸지 않는 죽은 항목이었다.
        ("허위 보류(ABSTAIN 과잉)", _inject_false_abstain),
        ("충돌 해소 근거 없이 RESOLVED", lambda d: d["conflicts"] and d["conflicts"][0].__setitem__("status", "RESOLVED")),
        ("미해결에 해소 근거 부착", lambda d: d["conflicts"] and d["conflicts"][0].__setitem__(
            "resolvedBy", {"layer": "L3", "id": "x"})),
        # 같은 소스 클래스가 여럿이면 하나를 빼도 커버리지는 여전히 참이다(정상).
        # 그 클래스의 **유일한** 증거를 빼야 coverage 가 거짓이 된다.
        ("유일 소스 증거 제거", _drop_sole_source),
    ]:
        yield lbl, fn, "cross"          # 교차 계층 단독으로도 잡아야 한다

    # 4) 신호별 개별 파괴
    def _sig(name, val=None, drop=False):
        def f(d):
            if d.get("evidence") and isinstance(d["evidence"][0].get("signals"), dict):
                if drop:
                    d["evidence"][0]["signals"].pop(name, None)
                else:
                    d["evidence"][0]["signals"][name] = val
        return f

    for s in SIGNALS:
        yield f"신호 {s} 누락", _sig(s, drop=True), "any"
        yield f"신호 {s} 범위 초과", _sig(s, 2.0), "any"


def must_reject(base):
    """변이를 실제로 적용해 (라벨, 문서, 계층) 으로 내놓는다."""
    for label, fn, layer in _mutators(base):
        r = _apply(base, label, fn)
        if r:
            yield r[0], r[1], layer


def must_accept(base):
    """계약상 여전히 적합한 변이 — 거부되면 오탐이다."""
    def m(label, fn):
        r = _apply(base, label, fn)
        if r:
            yield r

    for lbl, fn in [
        ("message 문구 변경", lambda d: d["warnings"] and d["warnings"][0].__setitem__("message", "다른 설명 문구")),
        ("경고 순서 뒤집기", lambda d: d["warnings"].reverse()),
        ("증거 순서 유지한 채 감사 id 순서 변경", lambda d: d["audit"]["evidenceIds"].reverse()),
        ("탈락 후보 id 추가", lambda d: d["audit"]["evidenceIds"].append("ev-99-dropped")),
        ("target.raw 제거(선택 필드)", lambda d: d["task"]["target"].pop("raw", None) is not None),
        ("contentHash 제거(선택 필드)", lambda d: d["evidence"] and d["evidence"][0]["ref"].pop("contentHash", None) is not None),
        ("confidence 경계 0.0", lambda d: d["evidence"] and d["evidence"][0].__setitem__("confidence", 0.0)),
        ("confidence 경계 1.0", lambda d: d["evidence"] and d["evidence"][0].__setitem__("confidence", 1.0)),
        ("신호 경계 0.0/1.0", lambda d: d["evidence"] and d["evidence"][0]["signals"].update(
            {"finality": 0.0, "freshness": 1.0})),
        ("윤초 표기", lambda d: d["audit"].__setitem__("createdAt", "1990-12-31T23:59:60Z")),
        ("오프셋 표기", lambda d: d["audit"].__setitem__("createdAt", "2026-07-29T11:00:11+09:00")),
        ("소수점 초", lambda d: d["audit"].__setitem__("createdAt", "2026-07-29T02:00:11.123Z")),
        ("reason 하나 추가(근거 있음)", lambda d: d["evidence"] and d["evidence"][0]["reason"].append(
            {"text": "추가 근거", "basis": [{"layer": "L1", "id": "obs-extra"}]})),
        ("observedAt 부여", lambda d: d["evidence"] and d["evidence"][0]["ref"].__setitem__(
            "observedAt", "2026-07-29T02:00:00Z")),
    ]:
        yield from m(lbl, fn)


def pairwise(base, cap=60):
    """두 위반을 **함수로 순차 적용**한 문서 — 여전히 거부돼야 한다.

    각각은 걸리는데 둘을 합치면 통과하는 조합이 있으면(= 서로의 전제를 없애
    상쇄하면) '두 번 틀리면 맞는' 구멍이다. 문서 병합이 아니라 순차 적용이라
    같은 최상위 키를 건드리는 두 변이도 온전히 합성된다.
    """
    muts = list(_mutators(base))[:cap]
    seen = set()
    for i in range(len(muts)):
        for j in range(i + 1, len(muts)):
            (l1, f1, _), (l2, f2, _) = muts[i], muts[j]
            d = copy.deepcopy(base)
            try:
                f1(d)
                after1 = copy.deepcopy(d)
                f2(d)
            except (KeyError, IndexError, TypeError, AttributeError):
                continue  # 앞 변이가 지운 자리를 뒤 변이가 건드린 경우 — 그 쌍만 건너뛴다
            if d == base or d == after1:      # 둘째 변이가 실제로 먹지 않았다
                continue
            key = json.dumps(d, sort_keys=True, ensure_ascii=False, default=str)
            if key in seen:
                continue
            seen.add(key)
            yield f"{l1} + {l2}", d


def main():
    bases = {p.name: json.loads(p.read_text())
             for p in sorted(EX.glob("valid.*.json"))}
    survivors, false_alarms, n = [], [], 0

    for name, base in bases.items():
        ok, why = judge(base)
        if not ok:
            print(f"FAIL 기준 픽스처가 이미 부적합: {name} -> {why}")
            return 1

        for label, doc, layer in must_reject(base):
            n += 1
            accepted, _ = judge(doc)
            if accepted:
                survivors.append((name, label, "전체"))
            elif layer == "cross":
                # 스키마가 대신 잡아주는 것에 기대면 C0 이식 시 구멍이 된다
                acc_x, _ = judge_cross_only(doc)
                if acc_x:
                    survivors.append((name, label, "교차 단독"))
        for label, doc in must_accept(base):
            n += 1
            accepted, why = judge(doc)
            if not accepted:
                false_alarms.append((name, label, why[0]))

    # 2중 변이 — 서로 상쇄해 통과하는 조합이 있는가
    pair_n, pair_bad = 0, []
    for name, base in bases.items():
        for label, doc in pairwise(base):
            pair_n += 1
            if judge(doc)[0]:
                pair_bad.append((name, label))

    print(f"단일 변이 {n}건 · 2중 변이 {pair_n}건 · 기준 픽스처 {len(bases)}종\n")
    if pair_bad:
        print(f"★ 상쇄(둘 다 위반인데 합치면 통과) {len(pair_bad)}건")
        for f, l in pair_bad[:10]:
            print(f"    {f:30} {l}")
    survivors += [(f, l, "2중") for f, l in pair_bad]
    if survivors:
        print(f"★ 미검출(통과해서는 안 되는데 통과) {len(survivors)}건")
        for f, l, scope in survivors:
            print(f"    [{scope}] {f:30} {l}")
    if false_alarms:
        print(f"★ 오탐(적합한데 거부) {len(false_alarms)}건")
        for f, l, w in false_alarms:
            print(f"    {f:32} {l}\n        -> {w}")
    if not survivors and not false_alarms:
        print("미검출 0 · 오탐 0")
    return 1 if (survivors or false_alarms) else 0


if __name__ == "__main__":
    sys.exit(main())
