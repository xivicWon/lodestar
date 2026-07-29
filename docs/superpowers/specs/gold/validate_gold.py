#!/usr/bin/env python3
"""M0 I2 Gold Set 적합성 확인기 (참조 구현).

목적은 **커밋된 gold 와 픽스처가 계약 문서(§5 G1~G14)와 서로, 그리고 고정 revision 의
실제 원본과 일치함을 누구나 재현할 수 있게 하는 것**이다. 제품 검증기가 아니다 —
실행 경로에 붙는 채점기는 #88~#91 의 범위이며, 그때 이 규칙들을 백엔드 언어로 옮긴다.

    pip install jsonschema && python3 validate_gold.py

계약: ../2026-07-29-m0-i2-gold-set.md
"""
import hashlib
import json
import pathlib
import re
import subprocess
import sys

from jsonschema import Draft202012Validator

HERE = pathlib.Path(__file__).parent
REPO = HERE.parents[3]
SCHEMA = json.loads((HERE / "gold.v0.schema.json").read_text())
MANIFEST = json.loads((HERE / "manifest.json").read_text())
CONTRACT_DOC = (HERE.parent / "2026-07-29-m0-i2-gold-set.md").read_text()

ITEM_FILES = ["l1/db.json", "l1/code.json", "l2/links.json", "pii.json"]
OTHER_FILES = ["l3/claims.json", "evl/questions.json", "failures.json"]

COVERAGE_KEYS = {"code", "issue", "adr", "test", "runtime"}
WARNING_CODES = {
    "NO_CODE", "NO_ISSUE", "NO_ADR", "NO_TEST", "NO_RUNTIME", "NOT_COLLECTED",
    "CONFLICT_UNRESOLVED", "LOW_CORROBORATION", "STALE_EVIDENCE",
    "SIGNAL_UNMEASURED", "DEGRADED_SOURCE", "ABSTAIN",
}
# EVL 계약 §6.2 의 v0 매핑. 조건 2 의 핵심 클래스 후보군은 OR 이다.
CORE_CLASSES = {
    "EXPLAIN": {"adr", "issue"}, "VERIFY": {"test", "runtime"},
    "IMPACT": {"code"}, "LOCATE": {"code"}, "HISTORY": {"issue"},
}

errors = []
covered = set()


def rule(rid):
    """규칙 하나를 실행하고, 실행됐다는 사실을 기록한다(커버리지 과대보고 방지)."""
    def deco(fn):
        covered.add(rid)
        for msg in fn() or []:
            errors.append(f"[{rid}] {msg}")
        return fn
    return deco


def sha(path):
    return "sha256:" + hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def load(rel):
    return json.loads((HERE / rel).read_text())


def _digest(lines):
    return hashlib.sha256(("\n".join(sorted(lines)) + "\n").encode()).hexdigest()


def derive_fixture_hash(m):
    """I3 계약 `run.fixtureHash` 가 요구하는 **단일 값**.

    I3 는 실행 하나당 해시 하나를 적게 돼 있는데(sha256:<64hex> 또는 UNPINNED),
    I2 가 고정하는 것은 픽스처 15개의 개별 해시다. 그 사이를 잇는 집계 규칙이
    없으면 각 실행이 제멋대로 대표값을 골라 적게 되고, 그러면 `fixtureHash` 가
    같다는 것이 같은 입력이었음을 보장하지 못한다(I3 §비교가능성 조건 2).

    규칙: `"<경로> <sha256:...>"` 줄을 **경로 사전순**으로 정렬해 개행으로 잇고
    마지막에 개행 하나를 붙인 뒤 sha256. 정렬을 못박는 이유는 파일 열거 순서가
    파일시스템마다 다르기 때문이다 — 순서가 흔들리면 같은 픽스처가 다른 해시를 낸다.
    """
    return "sha256:" + _digest(f"{e['path']} {e['sha256']}" for e in m["fixtures"])


def derive_gold_set_id(m):
    """I3 계약 `evl.conflictDetection.goldSetId` 가 요구하는 정답셋 신원.

    정답 데이터뿐 아니라 **판정 규칙(스키마·확인기)까지** 포함해 계산한다.
    같은 데이터라도 판정 규칙이 바뀌면 같은 산출물의 정오가 뒤집히므로,
    규칙 변경이 신원에 드러나지 않으면 서로 다른 기준으로 잰 수치가 같은
    goldSetId 아래 비교된다.
    """
    parts = [f"gold {e['path']} {e['sha256']}" for e in m["goldFiles"]]
    parts += [f"fixture {e['path']} {e['sha256']}" for e in m["fixtures"]]
    parts += [f"source {e['sourceId']} {e['contentHash']}" for e in m["pinnedSources"]]
    return f"{m['goldSetVersion']}+{_digest(parts)[:12]}"


DOCS = {rel: load(rel) for rel in ITEM_FILES + OTHER_FILES}
ALL_ITEMS = [(rel, it) for rel in ITEM_FILES for it in DOCS[rel]["items"]]
ITEM_BY_ID = {it["id"]: it for _, it in ALL_ITEMS}
SOURCES = {s["sourceId"]: s for s in MANIFEST["pinnedSources"]}


# --- G1 스키마 --------------------------------------------------------------
@rule("G1")
def _g1():
    v = Draft202012Validator(SCHEMA)
    for rel in ITEM_FILES:
        for e in sorted(v.iter_errors(DOCS[rel]), key=lambda e: list(e.path)):
            yield f"{rel}: {'/'.join(str(p) for p in e.path)}: {e.message}"


# --- G2 id 단일 네임스페이스 ------------------------------------------------
@rule("G2")
def _g2():
    seen = {}
    for rel, it in ALL_ITEMS:
        if it["id"] in seen:
            yield f"중복 id {it['id']} ({seen[it['id']]} · {rel})"
        seen[it["id"]] = rel


# --- G3 선언 개수 = 실제 개수 -----------------------------------------------
@rule("G3")
def _g3():
    for rel in ITEM_FILES:
        d = DOCS[rel]
        # 파일마다 세는 축이 다르다: expect 별(l2·pii) 또는 type 별(l1).
        # type 축은 **정답 집합**(산출되어야 하는 항목)만 센다 — 음성 항목을 섞으면
        # '닫힌 범위 27건' 같은 선언이 오탐 방지용 항목 때문에 부풀어 의미를 잃는다.
        NEG = {"ABSENT", "NOT_MASKED"}
        by_type, by_expect = {}, {}
        for it in d["items"]:
            if it["expect"] not in NEG:
                by_type[it["type"]] = by_type.get(it["type"], 0) + 1
            by_expect[it["expect"]] = by_expect.get(it["expect"], 0) + 1
        n_neg = sum(1 for it in d["items"] if it["expect"] in NEG)
        if "negatives" not in d["counts"]:
            yield f"{rel}: counts 에 negatives 선언이 없다 — 음성 항목 수가 조용히 변할 수 있다"
        for key, want in d["counts"].items():
            got = n_neg if key == "negatives" else by_type.get(key, by_expect.get(key))
            if got is None:
                yield f"{rel}: counts 의 '{key}' 가 type·expect 어느 축에도 없다"
            elif got != want:
                yield f"{rel}: counts['{key}']={want} 인데 실제 {got}건"


# --- G4 매니페스트 완전성 · 해시 일치 ---------------------------------------
@rule("G4")
def _g4():
    for entry in MANIFEST["goldFiles"] + MANIFEST["fixtures"]:
        p = HERE / entry["path"]
        if not p.exists():
            yield f"매니페스트에 있으나 파일이 없다: {entry['path']}"
        elif sha(p) != entry["sha256"]:
            yield f"해시 불일치: {entry['path']} (매니페스트 {entry['sha256']}, 실제 {sha(p)})"
    pinned = {e["path"] for e in MANIFEST["fixtures"]}
    for p in sorted((HERE / "fixtures").rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(HERE))
            if rel not in pinned:
                yield f"고정되지 않은 픽스처: {rel} (I1 §1.3 — fixture hash 없는 실행은 baseline 이 아니다)"
    listed = {e["path"] for e in MANIFEST["goldFiles"]}
    for rel in ITEM_FILES + OTHER_FILES + ["gold.v0.schema.json"]:
        if rel not in listed:
            yield f"매니페스트 goldFiles 에서 누락: {rel}"
    # I3 로 넘기는 파생값은 **재계산 가능해야** 한다. 손으로 적어 둔 값이 내용과
    # 어긋나면 Run Quality Report 가 실제와 다른 입력을 가리키게 되고, 그 보고서끼리의
    # 비교가 성립하지 않는다(I3 §비교가능성).
    for key, fn in (("fixtureHash", derive_fixture_hash), ("goldSetId", derive_gold_set_id)):
        want = fn(MANIFEST)
        if key not in MANIFEST:
            yield f"매니페스트에 {key} 가 없다 — I3 계약이 요구하는 값이다 (기대: {want})"
        elif MANIFEST[key] != want:
            yield f"{key} 가 내용과 어긋난다 (선언 {MANIFEST[key]}, 재계산 {want})"
        # 계약 문서가 이 값들을 본문에 적어 두므로(§6.1) 문서도 함께 검사한다.
        # 파생값은 내용이 바뀔 때마다 달라지는데, 문서에 옛 값이 남아 있으면
        # 보고서 작성자가 그것을 그대로 인용해 존재하지 않는 입력을 가리키게 된다.
        elif want not in CONTRACT_DOC:
            yield f"계약 문서 §6.1 의 {key} 가 낡았다 — 현재 값 {want} 로 갱신할 것"


# --- G5 고정 revision 의 실제 원본과 대조 -----------------------------------
@rule("G5")
def _g5():
    for sid, s in SOURCES.items():
        if s.get("origin") != "repo":
            continue
        rev = s["revision"]
        try:
            blob = subprocess.run(["git", "show", f"{rev}:{s['path']}"], cwd=REPO,
                                  capture_output=True, check=True).stdout
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            yield f"{sid}: 고정 revision 에서 원본을 읽을 수 없다 ({s['path']}): {e}"
            continue
        got = "sha256:" + hashlib.sha256(blob).hexdigest()
        if got != s["contentHash"]:
            yield f"{sid}: {rev} 의 실제 해시 {got} ≠ 고정값 {s['contentHash']}"


# --- G6 항목의 contentHash = 매니페스트의 소스 해시 --------------------------
@rule("G6")
def _g6():
    for rel, it in ALL_ITEMS:
        for r in [it["ref"]] if "ref" in it else it["refs"]:
            sid = r["sourceId"]
            if sid not in SOURCES:
                yield f"{it['id']}: 등록되지 않은 sourceId '{sid}'"
                continue
            if "contentHash" in r and r["contentHash"] != SOURCES[sid]["contentHash"]:
                yield f"{it['id']}: contentHash 가 {sid} 의 고정값과 다르다"
            if "revision" in r and r["revision"] != SOURCES[sid].get("revision"):
                yield f"{it['id']}: revision 이 {sid} 의 고정 revision 과 다르다"


# --- G7 좌표가 실재하는 행을 가리킨다 ---------------------------------------
@rule("G7")
def _g7():
    for rel, it in ALL_ITEMS:
        for r in [it["ref"]] if "ref" in it else it["refs"]:
            sid = r["sourceId"]
            if sid not in SOURCES:
                continue
            path, frag = r["locator"].split("#")
            if path != SOURCES[sid]["path"]:
                yield f"{it['id']}: locator 경로 {path} ≠ {sid} 의 등록 경로 {SOURCES[sid]['path']}"
                continue
            n = SOURCES[sid]["lines"]
            nums = [int(x) for x in re.findall(r"L(\d+)", frag)]
            if any(x < 1 or x > n for x in nums):
                yield f"{it['id']}: {frag} 가 파일 범위(1..{n})를 벗어난다 — 유령 좌표"
            if len(nums) == 2 and nums[0] > nums[1]:
                yield f"{it['id']}: {frag} 의 시작 행이 끝 행보다 크다"
    # EVL 질문의 근거 좌표도 같은 기준으로 본다 — 여기서 유령 좌표를 허용하면
    # '좌표를 지어내 커버리지를 present 로 위조' 하는 실패를 gold 자신이 저지르게 된다.
    by_path = {s["path"]: s for s in SOURCES.values()}
    for q in DOCS["evl/questions.json"]["questions"]:
        for ev in q["requiredEvidence"]:
            path, frag = ev["locator"].split("#")
            if path not in by_path:
                yield f"{q['id']}: 고정되지 않은 근거 파일 {path} (매니페스트 pinnedSources 에 없다)"
                continue
            n = by_path[path]["lines"]
            if any(x < 1 or x > n for x in [int(x) for x in re.findall(r"L(\d+)", frag)]):
                yield f"{q['id']}: {ev['locator']} 가 파일 범위(1..{n})를 벗어난다"


# --- G8 PII: 원문 조각이 그 행에 실재한다 -----------------------------------
@rule("G8")
def _g8():
    for it in DOCS["pii.json"]["items"]:
        r = it["ref"]
        path = REPO / r["locator"].split("#")[0]
        ln = int(re.search(r"L(\d+)", r["locator"]).group(1))
        lines = path.read_text().splitlines()
        # 범위를 먼저 본다 — 여기서 색인 예외가 나면 확인기가 죽고, 죽은 확인기의
        # 침묵은 '문제 없음' 과 구분되지 않는다.
        if ln > len(lines):
            yield f"{it['id']}: {path.name}#L{ln} 이 파일 범위(1..{len(lines)})를 벗어난다"
        elif it["value"]["text"] not in lines[ln - 1]:
            yield f"{it['id']}: '{it['value']['text']}' 가 {path.name}#L{ln} 에 없다"


# --- G9 L1 DB: 인용한 행에 그 이름이 실제로 있다 -----------------------------
@rule("G9")
def _g9():
    src = SOURCES["db:legacy-sample"]
    lines = (REPO / src["path"]).read_text().splitlines()
    for it in DOCS["l1/db.json"]["items"]:
        if it["expect"] != "PRESENT":
            continue
        name = it["value"].get("name") or it["value"].get("constraintName") \
            or (it["value"]["columns"][0] if it["type"] == "PRIMARY_KEY" else None)
        if not name:
            continue
        ln = int(re.search(r"L(\d+)", it["ref"]["locator"]).group(1))
        if ln > len(lines):
            yield f"{it['id']}: 인용 행 L{ln} 이 파일 범위(1..{len(lines)})를 벗어난다"
        elif name not in lines[ln - 1]:
            yield f"{it['id']}: '{name}' 가 인용 행 L{ln} 에 없다 — gold 좌표가 원본과 어긋난다"


# --- G10 상호참조가 해소된다 -------------------------------------------------
@rule("G10")
def _g10():
    def check(where, ident):
        # 리포 심볼 FQN·픽스처 좌표는 gold id 가 아니다. gold id 형태만 대조한다.
        if re.match(r"^L[0-3]\.(DB|CODE|DRIFT)\.", ident) and ident not in ITEM_BY_ID:
            yield f"{where}: 존재하지 않는 gold id 참조 '{ident}'"

    for it in DOCS["l2/links.json"]["items"]:
        for key in ("left", "right"):
            v = it["value"].get(key)
            if isinstance(v, str):
                yield from check(it["id"], v)
        for c in it["value"].get("candidates", []):
            yield from check(it["id"], c)
    for tier in DOCS["evl/questions.json"]["calibrationPool"]["tiers"]:
        for m in tier["members"]:
            if m not in ITEM_BY_ID:
                yield f"calibrationPool/{tier['tier']}: 존재하지 않는 gold id '{m}'"


# --- G11 EVL: coverage 어휘 · 경고 어휘 · 보류 양방향 ------------------------
@rule("G11")
def _g11():
    evl = DOCS["evl/questions.json"]
    conflict_ids = {c["id"] for c in evl["conflictGold"]["positive"]}
    # 보류를 강제하는 것은 **미해결(NEEDS_CHECK) 충돌뿐**이다(EVL §6.2 조건 3).
    # COEXIST·RESOLVED 는 이미 닫힌 상태라 보류 사유가 아니다 — 이 구분을 잃으면
    # 충돌 탐지가 보류 스위치로 전락하고, 허위 보류가 정답으로 굳는다.
    unresolved = {c["id"] for c in evl["conflictGold"]["positive"]
                  if c.get("status", "NEEDS_CHECK") == "NEEDS_CHECK"}
    for q in evl["questions"]:
        qid = q["id"]
        if set(q["coverage"]) != COVERAGE_KEYS:
            yield f"{qid}: coverage 키가 5개 클래스와 다르다"
        for v in q["coverage"].values():
            if v not in ("present", "absent", "not_collected"):
                yield f"{qid}: coverage 값 '{v}' 는 3값 열거 밖이다"
        codes = [w["code"] for w in q["expectedWarnings"]]
        for c in codes:
            if c not in WARNING_CODES:
                yield f"{qid}: 통제어휘 밖 경고 코드 '{c}'"
        # A11: absent/not_collected 클래스마다 대응 경고가 있고, 그 역도 성립한다.
        for k, v in q["coverage"].items():
            want = {"absent": f"NO_{k.upper()}", "not_collected": "NOT_COLLECTED"}.get(v)
            trig = f"coverage.{k}"
            has = any(w["code"] == want and w["trigger"] == trig for w in q["expectedWarnings"])
            if want and not has:
                yield f"{qid}: coverage.{k}={v} 인데 {want}(trigger={trig}) 경고가 없다"
            if not want and any(w["trigger"] == trig for w in q["expectedWarnings"]
                                if w["code"].startswith("NO_") or w["code"] == "NOT_COLLECTED"):
                yield f"{qid}: coverage.{k}=present 인데 부재 경고가 붙어 있다"
        # A16: 보류 선언과 ABSTAIN 경고가 양방향 일치하고, trigger 가 성립한 조건을 가리킨다.
        abstain = [w for w in q["expectedWarnings"] if w["code"] == "ABSTAIN"]
        if q["expectAbstain"] != bool(abstain):
            yield f"{qid}: expectAbstain={q['expectAbstain']} 인데 ABSTAIN 경고는 {len(abstain)}건"
        if q["expectAbstain"] and abstain:
            cond = q.get("abstainCondition")
            trig = abstain[0]["trigger"]
            if cond == 1:
                if q["requiredEvidence"]:
                    yield f"{qid}: 조건 1(근거 0건)인데 requiredEvidence 가 비어 있지 않다"
                if trig != "evidence":
                    yield f"{qid}: 조건 1 의 trigger 는 'evidence' 여야 한다 (got {trig})"
            elif cond == 2:
                core = CORE_CLASSES[q["task"]["intent"]]
                if any(q["coverage"][c] == "present" for c in core):
                    yield f"{qid}: 조건 2 라는데 핵심 클래스 {core} 중 present 가 있다"
                if trig.replace("coverage.", "") not in core:
                    yield f"{qid}: 조건 2 의 trigger 는 부재한 핵심 클래스를 가리켜야 한다 (got {trig})"
            elif cond == 3:
                if not set(q["expectedConflicts"]) & unresolved:
                    yield f"{qid}: 조건 3 인데 NEEDS_CHECK 충돌이 없다 (COEXIST·RESOLVED 는 보류 사유가 아니다)"
            else:
                yield f"{qid}: abstainCondition 이 1~3 이 아니다 ({cond})"
        elif not q["expectAbstain"]:
            # 허위 보류의 반대 — 보류하지 않기로 했는데 조건이 성립하면 gold 자체가 모순이다.
            core = CORE_CLASSES[q["task"]["intent"]]
            if not q["requiredEvidence"]:
                yield f"{qid}: 비보류인데 근거가 0건이다 (조건 1 성립)"
            if not any(q["coverage"][c] == "present" for c in core):
                yield f"{qid}: 비보류인데 핵심 클래스 {core} 가 전면 부재다 (조건 2 성립)"
            if set(q["expectedConflicts"]) & unresolved:
                yield f"{qid}: 비보류인데 NEEDS_CHECK 충돌이 있다 (조건 3 성립)"
            # 닫힌 충돌은 보류를 면제받는 대신 **상태를 명시**해야 한다. 상태 없이
            # 비보류로 넘어가면 '충돌을 못 본 것' 과 '보고 닫은 것' 이 구분되지 않는다.
            for cid in q["expectedConflicts"]:
                if q.get("expectedConflictStatus", {}).get(cid) not in ("COEXIST", "RESOLVED"):
                    yield f"{qid}: 비보류 질문의 충돌 '{cid}' 에 닫힌 상태(COEXIST/RESOLVED) 선언이 없다"
        for cid in q["expectedConflicts"]:
            if cid not in conflict_ids:
                yield f"{qid}: conflictGold 에 없는 충돌 id '{cid}'"
    for c in evl["conflictGold"]["positive"] + evl["conflictGold"]["negative"]:
        if c["question"] not in {q["id"] for q in evl["questions"]}:
            yield f"conflictGold/{c['id']}: 존재하지 않는 질문 '{c['question']}'"


# --- G12 EVL 선언 개수 -------------------------------------------------------
@rule("G12")
def _g12():
    evl = DOCS["evl/questions.json"]
    c = evl["counts"]
    got = {
        "QUESTION": len(evl["questions"]),
        "ABSTAIN_TRUE": sum(1 for q in evl["questions"] if q["expectAbstain"]),
        "ABSTAIN_FALSE": sum(1 for q in evl["questions"] if not q["expectAbstain"]),
        "CONFLICT_POSITIVE": len(evl["conflictGold"]["positive"]),
        "CONFLICT_NEGATIVE": len(evl["conflictGold"]["negative"]),
    }
    for k, want in c.items():
        if got[k] != want:
            yield f"evl counts['{k}']={want} 인데 실제 {got[k]}건"


# --- G13 L3 시나리오 구조 ----------------------------------------------------
@rule("G13")
def _g13():
    d = DOCS["l3/claims.json"]
    cases = set()
    if d["counts"]["SCENARIO"] != len(d["scenarios"]):
        yield f"l3 counts 선언 {d['counts']['SCENARIO']} ≠ 실제 {len(d['scenarios'])}"
    for s in d["scenarios"]:
        cases.add(s["case"])
        for f in ("id", "case", "title", "why", "steps"):
            if not s.get(f):
                yield f"{s.get('id', '?')}: 필수 필드 '{f}' 누락"
        # step 은 비규범적 표식이 아니라 실행 순서다 — 중복·누락·역순을 허용하면
        # 'step2 뒤에' 같은 참조가 무엇을 가리키는지 모호해진다(재등장 시나리오가 실제로 참조한다).
        nums = [st.get("step") for st in s["steps"]]
        if nums != list(range(1, len(nums) + 1)):
            yield f"{s['id']}: step 이 배열 순서대로 1..{len(nums)} 가 아니다 (got {nums})"
        for st in s["steps"]:
            if not st.get("mustHold"):
                yield f"{s['id']} step{st.get('step')}: mustHold 가 비어 있다 — 판정할 것이 없는 단계"
        # 다른 시나리오의 단계를 이어받는 경우, 그 단계가 실재해야 한다.
        for st in s["steps"]:
            inp = st.get("input", {})
            if inp.get("action") == "CONTINUE_FROM":
                tgt = next((x for x in d["scenarios"] if x["id"] == inp.get("scenario")), None)
                if tgt is None:
                    yield f"{s['id']}: 존재하지 않는 시나리오를 이어받는다 '{inp.get('scenario')}'"
                elif inp.get("afterStep") not in [x["step"] for x in tgt["steps"]]:
                    yield (f"{s['id']}: {inp['scenario']} 에 step{inp.get('afterStep')} 이 없다 "
                           f"— 이어받을 종료 상태가 정의되지 않는다")
    for need in ("정상", "변경", "충돌", "삭제", "재등장"):
        if need not in cases:
            yield f"이슈 #99 가 요구한 L3 케이스 '{need}' 가 없다"


# --- G14 실패 픽스처 ---------------------------------------------------------
@rule("G14")
def _g14():
    d = DOCS["failures.json"]
    if d["counts"]["FIXTURE"] != len(d["fixtures"]):
        yield f"failures counts 선언 {d['counts']['FIXTURE']} ≠ 실제 {len(d['fixtures'])}"
    kinds = set()
    for f in d["fixtures"]:
        kinds.add(f["kind"])
        p = REPO / f["path"]
        if not p.exists():
            yield f"{f['id']}: 픽스처 파일이 없다 {f['path']}"
            continue
        if sha(p) != f["contentHash"]:
            yield f"{f['id']}: contentHash 불일치"
        if not f["reported"]:
            yield f"{f['id']}: reported 가 비어 있다 — 실패 픽스처인데 보고 기대치가 없다"
        for r in f["reported"]:
            if not r.get("reasonRequired"):
                yield f"{f['id']}: reported 항목에 reasonRequired 가 없다 (사유 없는 보고는 보고가 아니다)"
    for need in ("파싱 실패", "미지원 문법", "부분 추출"):
        if need not in kinds:
            yield f"이슈 #99 가 요구한 실패 종류 '{need}' 가 없다"


def rehash():
    """gold 파일·픽스처 해시를 현재 내용으로 다시 고정한다(유지보수용).

    이것은 검사가 아니라 **재고정**이다. gold 를 의도적으로 고친 뒤에만 쓰고,
    실행 후 반드시 `validate_gold.py` 를 다시 돌린 다음 리뷰어 승인을 받는다.
    검사 실패를 이걸로 덮으면 fixture hash 고정이 하는 일이 없어진다(I1 §1.3).
    """
    m = json.loads((HERE / "manifest.json").read_text())
    for e in m["goldFiles"] + m["fixtures"]:
        e["sha256"] = sha(HERE / e["path"])
    for s in m["pinnedSources"]:
        if s.get("origin") == "fixture":
            p = REPO / s["path"]
            s["contentHash"] = sha(p)
            s["lines"] = len(p.read_text().splitlines())
    # 파생값은 파일 해시가 갱신된 **뒤에** 계산한다.
    m["fixtureHash"] = derive_fixture_hash(m)
    m["goldSetId"] = derive_gold_set_id(m)
    (HERE / "manifest.json").write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n")
    print("manifest 재고정 완료 — validate_gold.py 를 다시 실행하고 리뷰어 승인을 받을 것")
    return 0


def main():
    expected = {f"G{i}" for i in range(1, 15)}
    missing = expected - covered
    if missing:
        errors.append(f"[META] 실행되지 않은 규칙: {sorted(missing)}")
    if errors:
        print(f"FAIL — {len(errors)}건\n")
        for e in errors:
            print("  " + e)
        return 1
    n_items = len(ALL_ITEMS)
    n_q = len(DOCS["evl/questions.json"]["questions"])
    n_s = len(DOCS["l3/claims.json"]["scenarios"])
    n_f = len(DOCS["failures.json"]["fixtures"])
    print(f"OK — 규칙 {len(covered)}개 · gold 항목 {n_items} · EVL 질문 {n_q} · "
          f"L3 시나리오 {n_s} · 실패 픽스처 {n_f}")
    print(f"     고정 revision {MANIFEST['sourceRevision'][:7]} · "
          f"픽스처 {len(MANIFEST['fixtures'])}개 해시 고정")
    # Run Quality Report(#100) 작성자가 그대로 인용할 값이다.
    print(f"     run.fixtureHash = {MANIFEST['fixtureHash']}")
    print(f"     goldSetId       = {MANIFEST['goldSetId']}")
    return 0


if __name__ == "__main__":
    sys.exit(rehash() if "--rehash" in sys.argv else main())
