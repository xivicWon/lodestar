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
from datetime import datetime

from jsonschema import Draft202012Validator

HERE = pathlib.Path(__file__).parent
REPO = HERE.parents[3]
SCHEMA = json.loads((HERE / "gold.v0.schema.json").read_text())
DOC_SCHEMA = json.loads((HERE / "gold.docs.v0.schema.json").read_text())
MANIFEST_SCHEMA = json.loads((HERE / "manifest.v0.schema.json").read_text())
MANIFEST = json.loads((HERE / "manifest.json").read_text())
CONTRACT_DOC = (HERE.parent / "2026-07-29-m0-i2-gold-set.md").read_text()

ITEM_FILES = ["l1/db.json", "l1/code.json", "l2/links.json", "pii.json"]
OTHER_FILES = ["l3/claims.json", "evl/questions.json", "failures.json"]

COVERAGE_KEYS = {"code", "issue", "adr", "test", "runtime"}
# 모양만으로 분류가 결정되는 값들. 마스킹 분류가 틀리면 탐지했더라도 **어느 등급으로
# 가릴지가 달라지므로** 분류 자체가 정답의 일부다 — RRN 을 INTERNAL_ID 로 적으면
# '개인식별정보를 찾았다' 는 집계가 통째로 거짓이 된다.
PII_SHAPES = {
    "KR_RRN": r"\d{6}-\d{7}",
    "EMAIL": r"[^@\s']+@[^@\s']+\.[A-Za-z]{2,}",
    # 구분자 있는 형태만 모양으로 단정한다. 맨 16자리는 송장·일련번호와 구분되지
    # 않아 정상 식별자를 오분류로 몰기 때문에, 그쪽은 Luhn 검사로 따로 본다.
    "CARD_NO": r"(?:\d{4}-){3}\d{4}",
    "IP_ADDRESS": r"\d{1,3}(?:\.\d{1,3}){3}",
    "GIT_SHA": r"[0-9a-f]{40}",
    "CONTENT_HASH": r"sha256:[0-9a-f]{64}",
    "TRACE_ID": r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}",
    "AWS_ACCESS_KEY_ID": r"AKIA[0-9A-Z]{16}",
    "SLACK_TOKEN": r"xox[bpasr]-[\w-]+",
    "GITHUB_TOKEN": r"gh[pousr]_[A-Za-z0-9]+",
    "JWT": r"eyJ[\w-]+\.[\w-]+\.[\w-]+",
    "CONNECTION_URL": r"jdbc:[^\s]+",
}
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

# ── OCP/SRP: 규칙이 무엇을 검사하는지를 **코드가 선언**하고, 계약 문서가 그것을
# 그대로 담고 있는지 확인기가 대조한다.
#
# 왜 필요한가: 문서 §5 의 표를 손으로 관리하다 보니 새 불변식을 추가할 때마다 표를
# 고쳐야 했고, 그 비용 때문에 새 검사를 기존 규칙 본문에 밀어 넣었다. 그 결과
# G11 은 117줄·G14 는 128줄짜리 잡동사니가 됐고, "그 규칙이 무엇을 보는가" 를
# 아무도 추적할 수 없게 됐다 — 실제로 리뷰가 "문서가 검사를 누락했다" 를 두 번 지적했다.
# 하위 불변식마다 id 를 주고 문서에 그 id 가 있어야만 통과하게 하면, 검사를 몰래
# 늘리는 것이 불가능해지고 새 id 를 만드는 비용도 사라진다.
SUBCHECKS = {
    "G1": ["G1.1 매니페스트 스키마(사전 게이트)", "G1.2 항목 파일 스키마",
           "G1.3 문서형 파일 스키마"],
    "G2": ["G2.1 id 전역 유일"],
    "G3": ["G3.1 파일별 총량 = expectedCounts", "G3.2 negatives 선언 존재",
           "G3.3 type·expect 별 counts 일치"],
    "G4": ["G4.1 gold·픽스처 파일 실재와 해시 일치", "G4.2 고정되지 않은 픽스처 없음",
           "G4.3 필수 gold 파일 목록 완비(확인기 자신 포함)",
           "G4.4 approvedAt 달력 유효성", "G4.5 파생값 재계산 일치",
           "G4.6 계약 문서의 파생값 최신"],
    "G5": ["G5.1 픽스처 해시·행수 실물 대조", "G5.2 fixtures[] ↔ pinnedSources 교차",
           "G5.3 repo 원본 해시 = 고정 revision blob", "G5.4 repo 원본 행수 = blob 실제",
           "G5.5 revision 이 선언 축(axis)과 일치",
           "G5.6 probe 축 원본 해시·행수 = probeRevision blob",
           "G5.7 probe 축 revision = probeAxis.revision",
           "G5.8 sameAsAnswerAxis 재계산 일치",
           "G5.9 probe 축 sourceId·answerAxisSourceId 유일",
           "G5.10 probe 축 ↔ scopeRoots 범위 양방향 완전성"],
    "G6": ["G6.1 ref 의 sourceId 등록", "G6.2 ref 의 contentHash·revision = 소스 고정값"],
    "G7": ["G7.1 좌표 경로 = 등록 경로", "G7.2 좌표가 blob 범위 안·시작≤끝",
           "G7.3 EVL 근거 좌표도 동일 기준"],
    "G8": ["G8.1 PII 원문이 인용 행에 실재", "G8.2 PII class 가 값의 모양과 일치"],
    "G9": ["G9.1 항목 타입별 검증 명세 완비", "G9.2 DB 좌표가 빈 줄이 아님",
           "G9.3 DB 실재 항목의 이름이 인용 행에", "G9.4 코드 인용 구간이 비어있지 않음",
           "G9.5 코드 항목 토큰이 인용 구간에 실재", "G9.6 FILE 의 package 선언 실재"],
    "G10": ["G10.1 상호참조 해소", "G10.2 refs endpoint ↔ value 대상 일치",
            "G10.3 L2 좌표 = L1 항목 좌표", "G10.4 gold id 아닌 대상의 심볼 실재",
            "G10.5 relation ↔ left/right 정합", "G10.6 R-L2-5 DB EXTRACTED 1건",
            "G10.7 trap 계층 = 전 음성 − 명시 제외",
            "G10.8 calibration tier ↔ 항목 정오"],
    "G11": ["G11.1 coverage 키 집합·어휘", "G11.2 collectionScope ↔ coverage 양방향",
            "G11.3 경고 통제어휘", "G11.4 coverage ↔ 경고 양방향(A11)",
            "G11.5 보류 양방향·조건별 trigger(A16)", "G11.6 충돌 ↔ 반대 증거 양방향(A14)",
            "G11.7 비보류 충돌의 닫힌 상태 선언",
            "G11.8 expectedConflictStatus = conflictGold", "G11.9 집계 주장 대조",
            "G11.10 conflictGold 의 question 실재"],
    "G12": ["G12.1 EVL 선언 개수"],
    "G13": ["G13.1 시나리오 개수·필수 필드", "G13.2 step 연속성",
            "G13.3 CONTINUE_FROM 대상 실재", "G13.4 산문 안의 gold id 실재",
            "G13.5 요구 5케이스 존재"],
    "G14": ["G14.1 픽스처 sourceId 등록·해시 선언 일치", "G14.2 reported 존재·사유 필수",
            "G14.3 보고 좌표 범위", "G14.4 extracted 이름이 픽스처에 실재",
            "G14.5 kind ↔ 보고 종류·추출 유무 정합", "G14.6 요구 3종 존재"],
}

errors = []
covered = set()
# 규칙이 실제로 **몇 개를 들여다봤는지**. covered 만으로는 본문이 빈 규칙도 통과한다 —
# '규칙이 실행됐다' 와 '규칙이 검사했다' 는 다르며, 후자를 세지 않으면 커버리지가 거짓이 된다.
inspected = {}


def touched(rid, n):
    inspected[rid] = inspected.get(rid, 0) + n


def rule(rid):
    """규칙 하나를 실행하고, 실행됐다는 사실을 기록한다(커버리지 과대보고 방지)."""
    def deco(fn):
        covered.add(rid)
        # 규칙이 예외로 죽으면 그 규칙의 결과가 사라질 뿐 아니라 **뒤의 규칙이
        # 아예 실행되지 않는다.** 손상된 gold 일수록 예외가 잘 나므로, 가장 검사가
        # 필요한 순간에 확인기가 침묵하게 된다. 예외도 그 규칙의 실패로 기록한다.
        try:
            for msg in fn() or []:
                errors.append(f"[{rid}] {msg}")
        except Exception as e:
            errors.append(f"[{rid}] 규칙 실행 중 예외 — 입력이 규칙의 전제를 깨뜨렸다: "
                          f"{type(e).__name__}: {e}")
        return fn
    return deco


def luhn(s):
    """카드번호 판정용. 맨 16자리 숫자를 모양만으로 카드로 단정하면 송장번호 같은
    정상 식별자가 오분류로 몰린다 — 체크섬까지 맞아야 카드라고 말한다."""
    ds = [int(c) for c in s if c.isdigit()]
    if len(ds) < 13:
        return False
    tot = 0
    for i, d in enumerate(reversed(ds)):
        if i % 2:
            d *= 2
            if d > 9:
                d -= 9
        tot += d
    return tot % 10 == 0


def sha(path):
    return "sha256:" + hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def load(rel):
    return json.loads((HERE / rel).read_text())


_BLOB = {}


def blob(sid):
    """고정된 원본 바이트를 돌려준다 — **작업 트리가 아니라 고정 revision 에서** 읽는다.

    gold 는 특정 revision 의 원본에 대한 정답이다. 확인기가 작업 트리를 읽으면
    검사 결과가 체크아웃 상태에 따라 달라진다: 원본이 뒤에서 바뀌면 틀린 gold 가
    통과하고, 브랜치를 옮기면 맞는 gold 가 실패한다. 어느 쪽이든 '검증 통과' 가
    '고정 revision 과 일치' 를 뜻하지 않게 되므로 확인기 전체의 의미가 사라진다.

    픽스처(origin=fixture)는 revision 이 아니라 해시로 고정되므로 디스크에서
    읽되, 그 내용의 무결성은 G4 가 매니페스트 해시로 따로 보장한다.
    """
    if sid in _BLOB:
        return _BLOB[sid]
    s = SOURCES[sid]
    if s.get("origin") == "repo":
        r = subprocess.run(["git", "show", f"{s['revision']}:{s['path']}"],
                           cwd=REPO, capture_output=True, check=True)
        data = r.stdout
    else:
        data = (REPO / s["path"]).read_bytes()
    _BLOB[sid] = data
    return data


def blob_lines(sid):
    return blob(sid).decode().splitlines()


def seg(sid, locator):
    """좌표가 가리키는 **고정 원본의 구간**을 돌려준다: (시작, 끝, 전체행수, 본문).

    좌표 파싱이 규칙마다 흩어져 있으면 규칙마다 다른 실수를 한다 — 실제로 한 곳만
    작업 트리를 읽어 검증이 체크아웃 상태에 의존했고(LOD-037), 다른 곳은 매니페스트의
    `lines` 를 믿어 숫자 하나로 범위 검사가 무력해졌다. 원본 접근과 좌표 해석을
    여기 한 군데로 모아 그런 편차가 생길 자리를 없앤다.
    """
    nums = [int(x) for x in re.findall(r"L(\d+)", locator)]
    lines = blob_lines(sid)
    a = nums[0]
    b = nums[1] if len(nums) > 1 else a
    return a, b, len(lines), "\n".join(lines[a - 1:b])


# ── LSP/ISP: 항목 타입별로 '무엇이 인용 구간에 실재해야 하는가' 를 선언으로 둔다.
#    if 체인으로 흩어져 있으면 새 타입이 조용히 아무 검사도 안 받는다 — FILE 의
#    package 대조가 좌표 L1 일 때만 돌던 것이 그 예다.
def _tokens_type(v):
    return [v["fqn"].split(".")[-1]] + list(v.get("members", []))


def _tokens_call(v):
    tail = v["callee"].split(".")
    return [tail[-2] if tail[-1] == "<init>" else tail[-1]]


# 타입 -> 인용 구간에 실재해야 하는 토큰들. None 은 '구간 대조 없음(다른 규칙이 본다)'.
VERIFY_TOKENS = {
    "FILE": None,          # package 선언은 파일 전체에서 찾는다(구간 한정이 아니다)
    "TYPE": _tokens_type,
    "METHOD": lambda v: [v["name"]],
    "PROPERTY": lambda v: [v["name"]],
    "CALL": _tokens_call,
    "TABLE": lambda v: [v["name"]],
    "COLUMN": lambda v: [v["name"]],
    "PRIMARY_KEY": lambda v: v["columns"][:1],
    "FOREIGN_KEY": lambda v: [v["constraintName"]],
    "VIEW": lambda v: [v["name"]],
    "LINK": None,          # G10 이 endpoint 기준으로 본다
    "MASK_SPAN": None,     # G8 이 원문·분류로 본다
}


def _digest(lines):
    return hashlib.sha256(("\n".join(sorted(lines)) + "\n").encode()).hexdigest()


def derive_fixture_hash(m):
    """I3 계약 `run.fixtureHash` 가 요구하는 **단일 값**.

    I3 는 실행 하나당 해시 하나를 적게 돼 있는데(sha256:<64hex> 또는 UNPINNED),
    I2 가 고정하는 것은 픽스처 15개의 개별 해시다. 그 사이를 잇는 집계 규칙이
    없으면 각 실행이 제멋대로 대표값을 골라 적게 되고, 그러면 `fixtureHash` 가
    같다는 것이 같은 입력이었음을 보장하지 못한다(I3 §3.8 의 비교가능 조건 2).

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


# 매니페스트는 고정(pinning)의 정본이고 아래 모든 구조가 여기서 파생된다. 그래서
# **다른 무엇보다 먼저** 검사한다 — 최상위 키에 오타가 나면(`pinedSources`) 규칙이
# 돌기도 전에 확인기가 죽어 아무것도 보고되지 않는다. 여기서 걸러 이유를 남기고 멈춘다.
_ms = sorted(Draft202012Validator(MANIFEST_SCHEMA).iter_errors(MANIFEST),
             key=lambda e: list(e.path))
if _ms:
    print(f"FAIL — {len(_ms)}건 (매니페스트가 형식 계약을 어겨 나머지 검사를 진행할 수 없다)\n")
    for e in _ms:
        print(f"  [G1] manifest.json: {'/'.join(str(x) for x in e.path) or '<root>'}: "
              f"{e.message[:200]}")
    sys.exit(1)

DOCS = {rel: load(rel) for rel in ITEM_FILES + OTHER_FILES}
# 파생 구조를 만들 때 필수 키를 단정하지 않는다. 단정하면 항목 하나에 `id` 가
# 빠졌을 때 규칙이 돌기도 전에 모듈 로드에서 KeyError 로 죽고, 사용자는 구조화된
# [G1] 대신 raw traceback 을 본다 — 매니페스트에는 사전 게이트를 뒀으면서
# 항목 파일에는 같은 보호가 없었다. 결함은 G1 이 스키마 위반으로 보고한다.
ALL_ITEMS = [(rel, it) for rel in ITEM_FILES for it in DOCS[rel].get("items", [])
             if isinstance(it, dict)]
ITEM_BY_ID = {it["id"]: it for _, it in ALL_ITEMS if "id" in it}
SOURCES = {s["sourceId"]: s for s in MANIFEST["pinnedSources"]}


# --- G1 스키마 --------------------------------------------------------------
@rule("G1")
def _g1():
    # 항목 파일과 문서형 파일은 구조가 다르지만 **둘 다** 스키마 검사를 받는다.
    # 문서형을 빼두면 교차 필드 규칙이 손으로 짚는 필드만 검사되어, 오타 난 키는
    # 조용히 무시되고 필수 필드 누락은 구조화된 오류 대신 예외가 된다.
    item_v = Draft202012Validator(SCHEMA)
    # 문서형 스키마는 oneOf 로 세 갈래라 최상위 오류가 "셋 다 안 맞음" 으로만 나온다.
    # 어느 갈래인지는 파일이 정해져 있으므로 해당 $defs 로 직접 검사해 원인을 보이게 한다.
    branch = {"l3/claims.json": "l3", "evl/questions.json": "evl", "failures.json": "failures"}
    doc_v = {k: Draft202012Validator({"$schema": DOC_SCHEMA["$schema"],
                                      "$defs": DOC_SCHEMA["$defs"],
                                      "$ref": f"#/$defs/{k}"})
             for k in set(branch.values())}
    for rel in ITEM_FILES + OTHER_FILES:
        v = doc_v[branch[rel]] if rel in branch else item_v
        touched("G1", 1)
        for e in sorted(v.iter_errors(DOCS[rel]), key=lambda e: list(e.path)):
            # 최상위 제약(anyOf 등)이 실패하면 jsonschema 가 문서 전체를 메시지에 담는다.
            # 읽을 수 없는 오류는 보고되지 않은 것과 크게 다르지 않으므로 잘라낸다.
            msg = e.message if len(e.message) <= 200 else e.message[:200] + " …(생략)"
            yield f"{rel}: {'/'.join(str(x) for x in e.path) or '<root>'}: {msg}"


# --- G2 id 단일 네임스페이스 ------------------------------------------------
@rule("G2")
def _g2():
    seen = {}
    for rel, it in ALL_ITEMS:
        if it["id"] in seen:
            yield f"중복 id {it['id']} ({seen[it['id']]} · {rel})"
        seen[it["id"]] = rel
        touched("G2", 1)


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
        want_n = MANIFEST["expectedCounts"].get(rel)
        if want_n is None:
            yield f"{rel}: expectedCounts 에 고정값이 없다 — 조용히 줄어들 수 있다"
        elif want_n != len(d["items"]):
            yield (f"{rel}: 항목 총량이 고정값과 다르다 (고정 {want_n}, 실제 {len(d['items'])}) "
                   f"— 정답셋이 늘거나 줄었다면 expectedCounts 도 함께 고쳐 의도를 남길 것")
        if "negatives" not in d["counts"]:
            yield f"{rel}: counts 에 negatives 선언이 없다 — 음성 항목 수가 조용히 변할 수 있다"
        for key, want in d["counts"].items():
            touched("G3", 1)
            got = n_neg if key == "negatives" else by_type.get(key, by_expect.get(key))
            if got is None:
                yield f"{rel}: counts 의 '{key}' 가 type·expect 어느 축에도 없다"
            elif got != want:
                yield f"{rel}: counts['{key}']={want} 인데 실제 {got}건"


# --- G4 매니페스트 완전성 · 해시 일치 ---------------------------------------
@rule("G4")
def _g4():
    for entry in MANIFEST["goldFiles"] + MANIFEST["fixtures"]:
        touched("G4", 1)
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
    # 확인기 자신도 필수다. 빠지면 goldSetId 가 판정 규칙을 더는 덮지 않게 되고,
    # 그 뒤로는 규칙을 고쳐도 신원이 그대로여서 다른 기준으로 잰 수치가 같은 id 로 비교된다.
    for rel in (ITEM_FILES + OTHER_FILES + ["gold.v0.schema.json",
                                            "gold.docs.v0.schema.json",
                                            "manifest.v0.schema.json",
                                            "validate_gold.py",
                                            "fire.py", "firing.json"]):
        if rel not in listed:
            yield f"매니페스트 goldFiles 에서 누락: {rel}"
    # I3 로 넘기는 파생값은 **재계산 가능해야** 한다. 손으로 적어 둔 값이 내용과
    # 어긋나면 Run Quality Report 가 실제와 다른 입력을 가리키게 되고, 그 보고서끼리의
    # 비교가 성립하지 않는다(I3 §3.8).
    at = MANIFEST["status"].get("approvedAt")
    if at:
        try:
            datetime.fromisoformat(at.replace("Z", "+00:00").replace(":60", ":59"))
        except ValueError:
            yield f"status.approvedAt 이 달력상 실재하지 않는 시각이다 ({at})"
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
    by_path = {e["path"]: e for e in MANIFEST["fixtures"]}
    for sid, s in SOURCES.items():
        if s.get("origin") != "repo":
            # 픽스처 소스도 **선언된 해시를 실제 파일과 대조**한다. 이걸 건너뛰면
            # pinnedSources 의 해시와 항목의 contentHash 가 서로 같기만 하면(G6) 둘 다
            # 틀린 값이어도 통과한다 — gold 가 실제와 다른 입력을 가리킨 채 승인된다.
            p = REPO / s["path"]
            if not p.exists():
                yield f"{sid}: 픽스처 파일이 없다 ({s['path']})"
                continue
            got = sha(p)
            if got != s["contentHash"]:
                yield f"{sid}: 실제 해시 {got} ≠ 고정값 {s['contentHash']}"
            n = len(p.read_text().splitlines())
            if s.get("lines") != n:
                yield f"{sid}: lines 선언 {s.get('lines')} ≠ 실제 {n} (좌표 범위 검사가 헐거워진다)"
            # 같은 파일이 fixtures[] 와 pinnedSources 두 곳에 적혀 있다. 두 값이
            # 갈리면 어느 쪽이 정본인지 알 수 없고, fixtureHash 집계와 항목 대조가
            # 서로 다른 파일을 뜻하게 된다.
            rel = str(pathlib.Path(s["path"]).relative_to("docs/superpowers/specs/gold"))
            fx = by_path.get(rel)
            if fx is None:
                yield f"{sid}: fixtures[] 에 같은 경로 항목이 없다 ({rel})"
            elif fx["sha256"] != s["contentHash"]:
                yield (f"{sid}: fixtures[].sha256({fx['sha256']}) 와 "
                       f"pinnedSources.contentHash({s['contentHash']}) 가 다르다")
            touched("G5", 1)
            continue
        # 고정 축은 둘뿐이다(§6). 항목별 revision 과 contentHash 를 함께 다른 커밋 값으로
        # 바꾸면 해시는 맞아떨어지므로, 축 자체를 검사하지 않으면 임의 커밋으로 슬쩍
        # 옮겨진 원본이 통과한다 — 그 순간 "고정 revision 의 gold" 라는 주장이 거짓이 된다.
        want = MANIFEST["sourceRevision"] if s["axis"] == "source" else MANIFEST["docsRevision"]
        if s["revision"] != want:
            yield (f"{sid}: axis={s['axis']} 인데 revision 이 그 축({want[:7]})과 다르다 "
                   f"({s['revision'][:7]})")
        try:
            data = blob(sid)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            yield f"{sid}: 고정 revision 에서 원본을 읽을 수 없다 ({s['path']}): {e}"
            continue
        got = "sha256:" + hashlib.sha256(data).hexdigest()
        if got != s["contentHash"]:
            yield f"{sid}: {s['revision']} 의 실제 해시 {got} ≠ 고정값 {s['contentHash']}"
        # G7 은 좌표 범위를 이 `lines` 로 판정한다. 여기서 대조하지 않으면 매니페스트의
        # 큰 숫자 하나로 모든 범위 검사가 무력해진다.
        real = len(data.decode().splitlines())
        if s.get("lines") != real:
            yield f"{sid}: lines 선언 {s.get('lines')} ≠ 실제 {real} (G7 의 범위 판정이 헐거워진다)"
        touched("G5", 1)

    # L0 수집 입력 축(#125)도 같은 대조를 받는다. 여기서 검사하지 않으면 축을 하나 더
    # 만든 것이 곧 **아무도 보지 않는 고정값**을 하나 더 만든 것이 된다 — 프로브가 그 값을
    # 입력 신원의 근거로 쓰므로, 대조 없는 축은 "고정 revision 을 쟀다" 를 다시 거짓으로 만든다.
    by_answer_id = {s["sourceId"]: s for s in MANIFEST["pinnedSources"]}
    axis = MANIFEST["probeAxis"]
    # 신원은 **유일해야** 한다. 같은 파일이 두 번 고정되면 어느 항목이 정본인지 알 수 없고, 한쪽만
    # 고쳐도 검사가 통과한다. 정답 축 매핑이 겹치면 서로 다른 입력이 같은 정답 소스를 주장한다.
    for key in ("sourceId", "answerAxisSourceId"):
        seen_ids = [s[key] for s in axis["sources"]]
        for dup in sorted({i for i in seen_ids if seen_ids.count(i) > 1}):
            yield f"probeAxis.sources 의 {key} 가 중복된다: {dup}"
    # 선언한 범위와 실제 고정 목록을 **양방향으로** 대조한다. 한 방향만 보면 항목을 빼도(범위에 있는데
    # 고정되지 않은 파일) 조용히 통과해 프로브의 입력 신원 검사가 그만큼 줄어든다.
    roots = [(r["track"], r["root"]) for r in axis["scopeRoots"]]
    in_scope = {s["sourceId"]: t for s in MANIFEST["pinnedSources"]
                if s.get("origin") == "repo" and s.get("axis") == "source"
                for t, root in roots if s["path"].startswith(root)}
    declared = {s["answerAxisSourceId"]: s for s in axis["sources"]}
    for missing in sorted(set(in_scope) - set(declared)):
        yield (f"probeAxis 범위(scopeRoots) 안의 {missing} 가 sources 에 고정되지 않았다 — "
               "프로브가 그 파일의 입력 신원을 대조하지 않게 된다")
    for extra in sorted(set(declared) - set(in_scope)):
        yield f"probeAxis.sources 의 {extra} 가 선언한 범위(scopeRoots) 밖이다"
    for sid, track in sorted(in_scope.items()):
        s = declared.get(sid)
        if s is not None and s["track"] != track:
            yield (f"{s['sourceId']}: track 선언 {s['track']} ≠ 범위가 정한 트랙 {track}")
    touched("G5", len(roots))
    for s in axis["sources"]:
        sid = s["sourceId"]
        if s["revision"] != axis["revision"]:
            yield (f"{sid}: probe 축 소스인데 revision 이 그 축"
                   f"({axis['revision'][:7]})과 다르다 ({s['revision'][:7]})")
        answer = by_answer_id.get(s["answerAxisSourceId"])
        if answer is None:
            yield f"{sid}: answerAxisSourceId '{s['answerAxisSourceId']}' 가 pinnedSources 에 없다"
        elif answer["path"] != s["path"]:
            yield (f"{sid}: 정답 축의 같은 id 가 다른 파일을 가리킨다 "
                   f"({answer['path']} / {s['path']})")
        try:
            data = subprocess.run(["git", "show", f"{s['revision']}:{s['path']}"],
                                  cwd=REPO, capture_output=True, check=True).stdout
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            yield f"{sid}: probe revision 에서 원본을 읽을 수 없다 ({s['path']}): {e}"
            continue
        got = "sha256:" + hashlib.sha256(data).hexdigest()
        if got != s["contentHash"]:
            yield f"{sid}: {s['revision'][:7]} 의 실제 해시 {got} ≠ 고정값 {s['contentHash']}"
        real = len(data.decode().splitlines())
        if s["lines"] != real:
            yield f"{sid}: lines 선언 {s['lines']} ≠ 실제 {real}"
        # 두 축의 관계는 **재계산**한다. 손으로 적은 true 는 "입력이 정답과 같다" 는
        # 거짓 안심을 만들고, 그 위에서 재고정의 영향 범위가 보이지 않게 된다.
        if answer is not None and s["sameAsAnswerAxis"] != (got == answer["contentHash"]):
            yield (f"{sid}: sameAsAnswerAxis 선언 {s['sameAsAnswerAxis']} ≠ 재계산 "
                   f"{got == answer['contentHash']}")
        touched("G5", 1)


# --- G6 항목의 contentHash = 매니페스트의 소스 해시 --------------------------
@rule("G6")
def _g6():
    for rel, it in ALL_ITEMS:
        for r in [it["ref"]] if "ref" in it else it["refs"]:
            sid = r["sourceId"]
            if sid not in SOURCES:
                yield f"{it['id']}: 등록되지 않은 sourceId '{sid}'"
                continue
            touched("G6", 1)
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
            a, b, n, _ = seg(sid, r["locator"])
            if a < 1 or b > n:
                yield f"{it['id']}: {frag} 가 파일 범위(1..{n})를 벗어난다 — 유령 좌표"
            if a > b:
                yield f"{it['id']}: {frag} 의 시작 행이 끝 행보다 크다"
            touched("G7", 1)
    # EVL 질문의 근거 좌표도 같은 기준으로 본다 — 여기서 유령 좌표를 허용하면
    # '좌표를 지어내 커버리지를 present 로 위조' 하는 실패를 gold 자신이 저지르게 된다.
    by_path = {s["path"]: s for s in SOURCES.values()}
    for q in DOCS["evl/questions.json"]["questions"]:
        for ev in q["requiredEvidence"]:
            path, frag = ev["locator"].split("#")
            if path not in by_path:
                yield f"{q['id']}: 고정되지 않은 근거 파일 {path} (매니페스트 pinnedSources 에 없다)"
                continue
            a, b, n, _ = seg(by_path[path]["sourceId"], ev["locator"])
            touched("G7", 1)
            if a < 1 or b > n:
                yield f"{q['id']}: {ev['locator']} 가 파일 범위(1..{n})를 벗어난다"


# --- G8 PII: 원문 조각이 그 행에 실재한다 -----------------------------------
@rule("G8")
def _g8():
    for it in DOCS["pii.json"]["items"]:
        r = it["ref"]
        name = pathlib.Path(r["locator"].split("#")[0]).name
        ln = int(re.search(r"L(\d+)", r["locator"]).group(1))
        lines = blob_lines(r["sourceId"])
        touched("G8", 1)
        # 모양이 곧 분류인 값은 라벨이 그 분류여야 한다. 라벨을 검사하지 않으면
        # 탐지는 맞고 분류만 틀린 구현이 만점을 받는다.
        cls, txt = it["value"]["class"], it["value"]["text"]
        for want, rx in PII_SHAPES.items():
            if re.fullmatch(rx, txt) and cls != want:
                yield f"{it['id']}: '{txt}' 는 {want} 모양인데 class 가 {cls} 다"
        if re.fullmatch(r"\d{16}", txt) and luhn(txt) and cls != "CARD_NO":
            yield f"{it['id']}: '{txt}' 는 Luhn 을 통과하는 16자리 — class 가 {cls} 다"
        path = type("P", (), {"name": name})
        # 범위를 먼저 본다 — 여기서 색인 예외가 나면 확인기가 죽고, 죽은 확인기의
        # 침묵은 '문제 없음' 과 구분되지 않는다.
        if ln > len(lines):
            yield f"{it['id']}: {path.name}#L{ln} 이 파일 범위(1..{len(lines)})를 벗어난다"
        elif it["value"]["text"] not in lines[ln - 1]:
            yield f"{it['id']}: '{it['value']['text']}' 가 {path.name}#L{ln} 에 없다"


# --- G9 L1 DB: 인용한 행에 그 이름이 실제로 있다 -----------------------------
@rule("G9")
def _g9():
    # 명세에 없는 타입이 생기면 그 타입은 아무 대조도 받지 않는다 — 조용히 늘어나는
    # 무검사 영역을 막는다.
    for _, it in ALL_ITEMS:
        if it["type"] not in VERIFY_TOKENS:
            yield f"{it['id']}: 타입 '{it['type']}' 의 검증 명세가 없다 (VERIFY_TOKENS 미등록)"
    lines = blob_lines("db:legacy-sample")
    for it in DOCS["l1/db.json"]["items"]:
        touched("G9", 1)
        ln = int(re.search(r"L(\d+)", it["ref"]["locator"]).group(1))
        if ln > len(lines):
            yield f"{it['id']}: 인용 행 L{ln} 이 파일 범위(1..{len(lines)})를 벗어난다"
            continue
        # **모든** 항목의 좌표가 실제 내용을 가리켜야 한다. 빈 줄을 가리키는 좌표는
        # 어떤 주장의 근거도 될 수 없다 — 음성 항목이라고 예외를 두면 "왜 그것이
        # 오탐인지" 를 아무 데서도 확인할 수 없고, 좌표가 조용히 밀려도 통과한다.
        if not lines[ln - 1].strip():
            yield f"{it['id']}: 인용 행 L{ln} 이 빈 줄이다 — 근거가 없는 좌표"
            continue
        # 실재하는 것(PRESENT·REPORTED_EXCLUDED)은 이름이 그 줄에 있어야 한다.
        # ABSENT 는 정의상 원본에 없으므로 이름 대조를 요구할 수 없다(위 검사까지만).
        if it["expect"] not in ("PRESENT", "REPORTED_EXCLUDED"):
            continue
        # 코드 트랙과 **같은 명세 테이블**을 쓴다. 여기만 자체 추출을 하면 테이블의
        # DB 항목이 죽은 코드가 되고, 명세를 고쳐도 DB 트랙은 따라오지 않는다.
        spec = VERIFY_TOKENS.get(it["type"])
        for name in (spec(it["value"]) if spec else []):
            if name not in lines[ln - 1]:
                yield f"{it['id']}: '{name}' 가 인용 행 L{ln} 에 없다 — gold 좌표가 원본과 어긋난다"

    # 코드 트랙도 같은 대조를 받는다. DB 만 검사하면 fqn·members 를 지어내도 통과한다.
    for it in DOCS["l1/code.json"]["items"]:
        touched("G9", 1)
        r = it["ref"]
        src = blob_lines(r["sourceId"])
        *_, body = seg(r["sourceId"], r["locator"])
        if not body.strip():
            yield f"{it['id']}: 인용 구간이 비어 있다 — 근거가 없는 좌표"
            continue
        if it["expect"] != "PRESENT":
            continue
        v, ty = it["value"], it["type"]
        if ty == "FILE":
            # 선언은 파일 어딘가에 있다. 좌표 한정으로 보면 좌표를 옮기는 것만으로
            # 대조가 사라진다.
            if not re.search(r"^\s*package\s+" + re.escape(v["package"]) + r"\b",
                             "\n".join(src), re.M):
                yield f"{it['id']}: package 선언 '{v['package']}' 가 파일에 없다"
        for w in (VERIFY_TOKENS[ty](v) if VERIFY_TOKENS.get(ty) else []):
            if w not in body:
                yield (f"{it['id']}: '{w}' 가 인용 구간 {r['locator'].split('#')[-1]} 에 없다 "
                       f"— gold 가 원본에 없는 것을 주장한다")


# --- G10 상호참조가 해소된다 -------------------------------------------------
@rule("G10")
def _g10():
    def check(where, ident):
        # 리포 심볼 FQN·픽스처 좌표는 gold id 가 아니다. gold id 형태만 대조한다.
        if re.match(r"^L[0-3]\.(DB|CODE|DRIFT)\.", ident) and ident not in ITEM_BY_ID:
            yield f"{where}: 존재하지 않는 gold id 참조 '{ident}'"

    for it in DOCS["l2/links.json"]["items"]:
        ends = [v for k in ("left", "right") if isinstance(v := it["value"].get(k), str)]
        ends += it["value"].get("candidates", [])
        touched("G10", 1)
        for v in ends:
            yield from check(it["id"], v)
        # L2 좌표는 **L1 gold 에서 유도**되어야 한다. 손으로 적으면 L1 이 정정돼도
        # 따라가지 않아 조용히 어긋나고, G7 은 범위만 보므로 잡히지 않는다.
        for i, r in enumerate(it["refs"]):
            ep = r.get("endpoint")
            if ep is None:
                if i < len(ends) and ends[i] in ITEM_BY_ID:
                    yield f"{it['id']}: refs[{i}] 에 endpoint 가 없다 (대상 {ends[i]})"
                continue
            if i < len(ends) and ep != ends[i]:
                yield f"{it['id']}: refs[{i}].endpoint '{ep}' 가 value 의 대상 '{ends[i]}' 와 다르다"
            g = ITEM_BY_ID.get(ep)
            if g and g["ref"]["locator"] != r["locator"]:
                yield (f"{it['id']}: refs[{i}] 좌표가 {ep} 의 좌표와 다르다 "
                       f"({r['locator'].split('#')[-1]} ≠ {g['ref']['locator'].split('#')[-1]})")
            # gold id 가 아닌 대상(픽스처 심볼·리포 FQN)은 G9 의 대조를 받지 못한다.
            # 이름이 인용 구간에 실재하는지 여기서 본다 — 없으면 지어낸 심볼이다.
            if g is None:
                sym = ep.split("@")[0].split("(")[0].split(".")[-1]
                *_, body = seg(r["sourceId"], r["locator"])
                if sym and sym not in body:
                    yield f"{it['id']}: refs[{i}] 의 '{sym}' 가 인용 구간에 없다"
        # relation 은 left/right 의 유무와 맞아야 한다. 검사하지 않으면 MOVED 를
        # RENAMED 로 바꿔 적어도 통과하고 drift 판정의 정답이 뒤바뀐다.
        rel_ = it["value"].get("relation")
        has_l = isinstance(it["value"].get("left"), str)
        has_r = isinstance(it["value"].get("right"), str) or bool(it["value"].get("candidates"))
        need = {"DELETED": (True, False), "ADDED": (False, True)}
        if rel_ in need and (has_l, has_r) != need[rel_]:
            yield f"{it['id']}: relation={rel_} 인데 left/right 구성이 맞지 않다"
        if rel_ in ("MOVED", "RENAMED", "REAPPEARED", "OVERRIDES") and not (has_l and has_r):
            yield f"{it['id']}: relation={rel_} 은 양쪽 대상이 모두 있어야 한다"
    # R-L2-5: DB 트랙에서 EXTRACTED 정답은 1건뿐이다. 종전에는 notes 산문에만 있어
    # 둘째가 생겨도 아무도 세지 않았다 — 추론을 명시로 승격한 것이 그대로 통과한다(I1 P2).
    ext = [it["id"] for it in DOCS["l2/links.json"]["items"]
           if it["track"] == "db" and it["expect"] == "PRESENT"
           and it["value"].get("status") == "EXTRACTED"]
    touched("G10", 1)
    if len(ext) != 1:
        yield f"R-L2-5 위반: DB 트랙 EXTRACTED 정답이 {len(ext)}건이다 (1건이어야 한다) {ext}"

    # trap 계층은 '추가만' 검사하면 조용히 줄어도 드러나지 않는다. 전 음성에서
    # 명시적으로 제외한 것만 빠질 수 있게 못박는다 — 곡선의 오른쪽 꼬리를 친절하게
    # 만드는 변조는 diff 한 줄이라 사람이 놓친다.
    cp = DOCS["evl/questions.json"]["calibrationPool"]
    all_neg = {it["id"] for rel in ("l1/db.json", "l1/code.json", "l2/links.json")
               for it in DOCS[rel]["items"] if it["expect"] == "ABSENT"}
    excluded = set(cp["trapMembership"]["excluded"])
    trap = {m for tr in cp["tiers"] if tr["tier"] == "trap" for m in tr["members"]}
    touched("G10", 1)
    for miss in sorted(all_neg - excluded - trap):
        yield f"trap 계층에서 빠진 음성 '{miss}' — 제외하려면 trapMembership.excluded 에 이유와 함께"
    for gone in sorted(excluded - all_neg):
        yield f"trapMembership.excluded 가 음성이 아닌 '{gone}' 를 가리킨다"
    for both in sorted(excluded & trap):
        yield f"'{both}' 가 제외 목록과 trap 계층에 동시에 있다"

    for tier in DOCS["evl/questions.json"]["calibrationPool"]["tiers"]:
        for m in tier["members"]:
            touched("G10", 1)
            if m not in ITEM_BY_ID:
                yield f"calibrationPool/{tier['tier']}: 존재하지 않는 gold id '{m}'"
                continue
            # tier 의 expectedVerdict 와 항목의 실제 정오가 어긋나면 곡선의 한 bin 이
            # 통째로 뒤집힌다. trap 에는 '산출하면 오답' 인 항목만 들어갈 수 있다.
            neg = ITEM_BY_ID[m]["expect"] in ("ABSENT", "NOT_MASKED")
            if neg != (tier["expectedVerdict"] == "INCORRECT"):
                yield (f"calibrationPool/{tier['tier']}(expectedVerdict="
                       f"{tier['expectedVerdict']}): '{m}' 의 expect="
                       f"{ITEM_BY_ID[m]['expect']} 와 어긋난다")


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
        touched("G11", 1)
        qid = q["id"]
        for k, decl in evl["collectionScope"]["declared"].items():
            got = q["coverage"].get(k)
            if decl.startswith("NOT_COLLECTED") and got != "not_collected":
                yield (f"{qid}: 수집 범위가 {k} 를 NOT_COLLECTED 로 선언했는데 "
                       f"coverage.{k}={got} 다 — 수집하지 않은 것을 찾을 수는 없다")
            # 역방향도 막는다. 수집하기로 한 클래스를 질문 쪽에서만 not_collected 로
            # 적으면 그 질문은 보류가 정답이 되어, 아무것도 못 찾는 구현이 공짜 정답을
            # 얻는다 — 가장 쉬운 양성 질문을 보류 질문으로 바꾸는 변조가 실제로 통했다.
            if decl.startswith("COLLECTED") and got == "not_collected":
                yield (f"{qid}: 수집 범위가 {k} 를 COLLECTED 로 선언했는데 "
                       f"coverage.{k}=not_collected 다 — 수집한 것을 안 봤다고 할 수 없다")
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
        # 질문이 선언한 충돌 상태는 conflictGold 의 정본과 같아야 한다. 대조하지 않으면
        # 질문 쪽에서만 RESOLVED 로 적어 보류를 면제받을 수 있다 — 근거 없는 해소다(I1 P4).
        for cid, st in (q.get("expectedConflictStatus") or {}).items():
            real = next((c.get("status") for c in evl["conflictGold"]["positive"]
                         if c["id"] == cid), None)
            if real is None:
                yield f"{qid}: expectedConflictStatus 가 conflictGold 에 없는 '{cid}' 를 가리킨다"
            elif real != st:
                yield f"{qid}: 충돌 '{cid}' 상태가 conflictGold({real})와 다르다 ({st})"
        # 충돌을 주장하면서 반대 증거가 하나도 없으면 그 충돌은 응답만으로 성립하지
        # 않는다(EVL A14 의 gold 판). 종전에는 stance 가 스키마 열거만 받고 아무도
        # 의미를 보지 않아, 반대 증거를 supports 로 바꿔도 통과했다.
        if q["expectedConflicts"] and not any(
                e.get("stance") == "contradicts" for e in q["requiredEvidence"]):
            yield f"{qid}: 충돌을 주장하는데 stance=contradicts 근거가 하나도 없다"
        if not q["expectedConflicts"] and any(
                e.get("stance") == "contradicts" for e in q["requiredEvidence"]):
            yield f"{qid}: 반대 증거가 있는데 대응하는 충돌이 선언되지 않았다 (EVL A14)"
        for cid in q["expectedConflicts"]:
            if cid not in conflict_ids:
                yield f"{qid}: conflictGold 에 없는 충돌 id '{cid}'"
        # 개수 주장은 닫힌 범위 gold 의 실제 항목 수와 대조한다. 한 줄 좌표는
        # "27건" 을 입증하지 못하므로, 주장의 정본을 전수 등재된 gold 로 못박는다.
        for e in q["requiredEvidence"]:
            cc = e.get("countClaim")
            if not cc:
                continue
            got = sum(1 for it in DOCS[cc["goldFile"]]["items"]
                      if it["type"] == cc["goldType"] and it["expect"] == "PRESENT")
            if got != cc["value"]:
                yield (f"{qid}: 개수 주장 {cc['value']} 이 {cc['goldFile']} 의 "
                       f"{cc['goldType']} 정답 {got}건과 다르다")
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
        touched("G12", 1)
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
        touched("G13", 1)
        cases.add(s["case"])
        for f in ("id", "case", "title", "why", "steps"):
            if not s.get(f):
                yield f"{s.get('id', '?')}: 필수 필드 '{f}' 누락"
        # step 은 비규범적 표식이 아니라 실행 순서다 — 중복·누락·역순을 허용하면
        # 'step2 뒤에' 같은 참조가 무엇을 가리키는지 모호해진다(재등장 시나리오가 실제로 참조한다).
        nums = [st.get("step") for st in s["steps"]]
        if nums != list(range(1, len(nums) + 1)):
            yield f"{s['id']}: step 이 배열 순서대로 1..{len(nums)} 가 아니다 (got {nums})"
        # mustHold/mustNot 문장 안에 적힌 gold id 는 그 단계의 **근거 참조**다.
        # 산문이라는 이유로 검사하지 않으면 존재하지 않는 근거를 가진 시나리오가
        # 정답으로 승인되고, 채점자는 대조할 대상이 없어 통과 처리하게 된다.
        for st in s["steps"]:
            for sent in st.get("mustHold", []) + st.get("mustNot", []):
                for tok in re.findall(r"\bL[123]\.[A-Za-z0-9._가-힣]+", sent):
                    tok = tok.rstrip(".")
                    if tok not in ITEM_BY_ID:
                        yield (f"{s['id']} step{st.get('step')}: 문장이 존재하지 않는 gold id "
                               f"'{tok}' 를 참조한다")
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
        touched("G14", 1)
        kinds.add(f["kind"])
        sid = f["sourceId"]
        if sid not in SOURCES:
            yield f"{f['id']}: sourceId '{sid}' 가 매니페스트에 등록돼 있지 않다"
            continue
        # 해시는 **선언끼리** 대조한다. 디스크와의 대조는 G5 가 소유한다 —
        # 같은 파일을 두 규칙이 각자 읽으면 그것이 곧 또 하나의 중복된 진실이다.
        if f["contentHash"] != SOURCES[sid]["contentHash"]:
            yield (f"{f['id']}: contentHash 가 pinnedSources 의 고정값과 다르다 "
                   f"({f['contentHash'][:20]}… ≠ {SOURCES[sid]['contentHash'][:20]}…)")
        if not f["reported"]:
            yield f"{f['id']}: reported 가 비어 있다 — 실패 픽스처인데 보고 기대치가 없다"
        for r in f["reported"]:
            if not r.get("reasonRequired"):
                yield f"{f['id']}: reported 항목에 reasonRequired 가 없다 (사유 없는 보고는 보고가 아니다)"
            # 실패 픽스처의 보고 좌표도 실재해야 한다. 여기만 예외를 두면 "어디서
            # 실패했다고 보고해야 하는가" 의 정답이 존재하지 않는 행을 가리키게 되고,
            # 채점자는 대조할 대상이 없어 그 항목을 통과 처리하게 된다.
            a, b, n, _ = seg(sid, r["locator"])
            if a < 1 or b > n:
                yield (f"{f['id']}: 보고 좌표 {r['locator']} 가 파일 범위(1..{n})를 벗어난다 "
                       f"— 유령 좌표")
            elif a > b:
                yield f"{f['id']}: 보고 좌표 {r['locator']} 의 시작 행이 끝 행보다 크다"
        # R-F-1 은 "extracted 는 그 입력에서 산출되어야 하는 사실의 전부" 라고 적어놓고
        # 아무도 읽지 않았다 — 픽스처에 없는 이름을 지어내도 통과했다.
        body = "\n".join(blob_lines(sid))
        for ex in f["extracted"]:
            name = ex.get("name") or ex.get("fqn", "").split(".")[-1]
            if name and not re.search(r"\b" + re.escape(name) + r"\b", body):
                yield f"{f['id']}: extracted 의 '{name}' 가 픽스처 본문에 없다"
            for col in ex.get("columns", []) + ex.get("primaryKey", []):
                if not re.search(r"\b" + re.escape(col) + r"\b", body):
                    yield f"{f['id']}: extracted 의 컬럼 '{col}' 가 픽스처 본문에 없다"
        # kind 는 보고 종류·추출 유무와 맞아야 한다. 라벨만 바꿔도 통과하면
        # '요구 3종이 다 있다' 는 검사가 라벨 돌려막기로 충족된다.
        kr = {r["kind"] for r in f["reported"]}
        if f["kind"] == "부분 추출" and not f["extracted"]:
            yield f"{f['id']}: kind=부분 추출 인데 extracted 가 비어 있다"
        if f["kind"] != "부분 추출" and f["extracted"]:
            yield f"{f['id']}: kind={f['kind']} 인데 extracted 가 있다 (그것이 부분 추출이다)"
        # 정확 일치를 요구하면 '파싱 실패가 주지만 미지원 구문도 섞인' 정상 픽스처를
        # 만들 수 없다. 대표 종류가 있는지(포함)와 어휘 밖이 없는지(부분집합)로 본다.
        ALLOWED = {"파싱 실패": ({"PARSE_ERROR", "UNSUPPORTED_STATEMENT"}, "PARSE_ERROR"),
                   "미지원 문법": ({"UNSUPPORTED_STATEMENT", "UNSUPPORTED_LANGUAGE"}, None),
                   "부분 추출": ({"PARSE_ERROR", "UNSUPPORTED_STATEMENT"}, None)}
        allowed, must = ALLOWED[f["kind"]]
        if not kr <= allowed:
            yield f"{f['id']}: kind={f['kind']} 인데 보고 종류에 {sorted(kr - allowed)} 가 있다"
        if must and must not in kr:
            yield f"{f['id']}: kind={f['kind']} 인데 {must} 보고가 없다"
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
    # 무엇을 정당화했는지 **말하고** 넘어간다. 조용히 해시만 맞추면 이 명령은
    # "내용이 바뀐 사실" 자체를 지우는 도구가 되고, 리뷰어는 diff 를 보기 전까지
    # 무엇이 legitimize 됐는지 알 수 없다.
    changed = [e["path"] for e in m["goldFiles"] + m["fixtures"]
               if e["sha256"] != sha(HERE / e["path"])]
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
    if changed:
        print(f"내용이 바뀐 파일 {len(changed)}건을 재고정했다:")
        for c in sorted(changed):
            print(f"  - {c}")
    else:
        print("내용이 바뀐 파일 없음 (파생값만 갱신)")
    print(f"  fixtureHash = {m['fixtureHash']}")
    print(f"  goldSetId   = {m['goldSetId']}")
    print("재고정은 검사가 아니다 — validate_gold.py 를 다시 실행하고 리뷰어 승인을 받을 것")
    return 0


def main():
    expected = {f"G{i}" for i in range(1, 15)}
    missing = expected - covered
    if missing:
        errors.append(f"[META] 실행되지 않은 규칙: {sorted(missing)}")
    idle = sorted(r for r in expected - missing if not inspected.get(r))
    if idle:
        errors.append(f"[META] 실행됐지만 아무것도 검사하지 않은 규칙: {idle} "
                      f"— 본문이 비어도 '규칙 N개' 로 집계되던 구멍")
    # 규칙이 무엇을 보는지는 코드가 선언하고 문서가 담는다. 문서에 없는 하위 불변식은
    # '몰래 늘어난 검사' 이고, 코드에 없는데 문서에만 있는 것은 '있다고 적힌 검사' 다.
    declared = {s.split()[0] for subs in SUBCHECKS.values() for s in subs}
    for rid, subs in sorted(SUBCHECKS.items()):
        if rid not in expected:
            errors.append(f"[META] SUBCHECKS 에 없는 규칙 id '{rid}'")
        for s in subs:
            if s.split()[0] not in CONTRACT_DOC:
                errors.append(f"[META] 계약 문서 §5 에 '{s}' 가 없다 "
                              f"— 검사를 늘렸으면 문서에도 적어야 한다")
    for sid in sorted(set(re.findall(r"\bG1?[0-9]\.[0-9]+", CONTRACT_DOC)) - declared):
        errors.append(f"[META] 문서에 '{sid}' 가 있으나 확인기에 그런 하위 불변식이 없다")
    # 선언 ↔ **발화 사례**의 결속. 문서에 적혀 있다는 것은 "검사한다고 주장했다" 까지이고,
    # 그 주장이 참인지는 깨뜨려 봐야 안다(fire.py). 여기서는 사례의 **존재**만 정적으로
    # 확인하고, 실제 발화는 fire.py 가 한다 — 확인기가 매번 61개를 깨뜨려 보면 느려서
    # 아무도 돌리지 않게 되고, 돌지 않는 검사는 없는 검사다.
    try:
        fs = json.loads((HERE / "firing.json").read_text())
        cased = {c["subcheck"] for c in fs["cases"]} | set(fs["waivers"])
        for miss in sorted(declared - cased):
            errors.append(f"[META] '{miss}' 에 발화 사례도 면제도 없다 — "
                          f"검사한다고 적어만 둔 것과 구분되지 않는다")
        for ghost in sorted(cased - declared):
            errors.append(f"[META] firing.json 의 '{ghost}' 가 확인기에 없다")
        for w, why in fs["waivers"].items():
            if not str(why).strip():
                errors.append(f"[META] 면제 '{w}' 에 사유가 없다 — 사유 없는 면제는 구멍이다")
    except Exception as e:
        errors.append(f"[META] firing.json 을 읽을 수 없다: {type(e).__name__}: {e}")
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
    # 입력 축은 승인 상태와 함께 찍는다 — 값만 보이면 미승인 축이 승인된 것처럼 인용된다(#125).
    pa = MANIFEST["probeAxis"]
    print(f"     probe 축(L0 입력) {pa['revision'][:7]} [{pa['status']['state']}] · "
          f"소스 {len(pa['sources'])}건")
    # Run Quality Report(#100) 작성자가 그대로 인용할 값이다.
    print(f"     run.fixtureHash = {MANIFEST['fixtureHash']}")
    print(f"     goldSetId       = {MANIFEST['goldSetId']}")
    return 0


if __name__ == "__main__":
    sys.exit(rehash() if "--rehash" in sys.argv else main())
