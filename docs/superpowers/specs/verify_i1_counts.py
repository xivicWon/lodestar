#!/usr/bin/env python3
"""#116 I1 §1.1 — 계약이 적은 DB 픽스처 수치가 실측·gold·RQR 예시와 같은지 확인한다 (C1~C5).

계약 문서에 숫자를 적는 것은 baseline 을 고정하는 것이다. 그 숫자가 고정 revision 원문에서 나오지
않았으면 그 위에 쌓인 모든 측정이 틀린 분모를 쓴다 — `CREATE TABLE` 28(#116) 이 정확히 그 사고였다.
주석 한 줄을 센 `grep -ci` 결과가 계약이 되고, gold(#99)·L0 실측(#88)이 27 을 확증할 때까지 살아남았다.

    python3 docs/superpowers/specs/verify_i1_counts.py
    # 5 checks, 0 mismatches

각 검사는 **한 축씩** 본다: C1 원문 실측 ↔ 계약, C2 계약 내부 서술 정합, C3 gold(#99), C4 RQR 예시(#100),
C5 개정 이력(I1 §7.3 — 이전 값 없이 덮어쓰면 개정이 아니다).

계약: 2026-07-29-m0-i1-baseline-contract.md
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
CONTRACT = HERE / "2026-07-29-m0-i1-baseline-contract.md"
GOLD_DB = HERE / "gold/l1/db.json"
RQR_EXAMPLES = HERE / "schemas/rqr-examples"

REVISION = "3c27259"
FIXTURE = "backend/src/main/resources/com/ontostudio/rdb/legacy-sample.sql"

# 주석 안의 같은 문자열은 세지 않는다 — gold R-DB-1 과 같은 규칙이다.
TABLE_STMT = re.compile(r"^\s*CREATE\s+TABLE\s+\S+\s*\(", re.IGNORECASE | re.MULTILINE)
VIEW_STMT = re.compile(r"^\s*CREATE\s+VIEW\s+", re.IGNORECASE | re.MULTILINE)
FK_STMT = re.compile(r"FOREIGN\s+KEY", re.IGNORECASE)

CONTRACT_ROW = re.compile(
    r"`CREATE TABLE` (\d+), `CREATE VIEW` (\d+), 명시 `FOREIGN KEY` (\d+)")
CONTRACT_PROSE = re.compile(r"(\d+)\s*테이블 중 명시 FK")


def fixture_text() -> str:
    raw = subprocess.run(["git", "show", f"{REVISION}:{FIXTURE}"], cwd=REPO,
                         capture_output=True, text=True, check=True).stdout
    return "\n".join(line.split("--", 1)[0] for line in raw.splitlines())


def measured() -> dict:
    text = fixture_text()
    return {"TABLE": len(TABLE_STMT.findall(text)),
            "VIEW": len(VIEW_STMT.findall(text)),
            "FOREIGN_KEY": len(FK_STMT.findall(text))}


def contract_text() -> str:
    return CONTRACT.read_text(encoding="utf-8")


def c1_contract_matches_fixture(errs: list) -> None:
    """§1.1 표의 수치는 고정 revision 원문의 **문장** 수와 같다."""
    m = CONTRACT_ROW.search(contract_text())
    if not m:
        errs.append("C1: §1.1 DB 행의 수치 표기를 찾지 못했다")
        return
    got = {"TABLE": int(m[1]), "VIEW": int(m[2]), "FOREIGN_KEY": int(m[3])}
    want = measured()
    if got != want:
        errs.append(f"C1: §1.1 수치 {got} != 원문 실측 @{REVISION} {want}")


def c2_prose_matches_row(errs: list) -> None:
    """같은 절의 서술문("N테이블 중 …")도 같은 수를 써야 한다 — 표만 고치면 반쪽 개정이다."""
    text = contract_text()
    row, prose = CONTRACT_ROW.search(text), CONTRACT_PROSE.search(text)
    if not row or not prose:
        errs.append("C2: §1.1 표 또는 서술문을 찾지 못했다")
        return
    if int(prose[1]) != int(row[1]):
        errs.append(f"C2: 서술문 {prose[1]}테이블 != 표 {row[1]}")


def c3_gold_matches_contract(errs: list) -> None:
    """gold(#99) counts 와 어긋나면 채점 분모와 계약이 다른 것을 말한다."""
    m = CONTRACT_ROW.search(contract_text())
    if not m:
        errs.append("C3: §1.1 수치 표기를 찾지 못했다 (C1 참조)")
        return
    counts = json.loads(GOLD_DB.read_text(encoding="utf-8"))["counts"]
    for key, val in (("TABLE", int(m[1])), ("VIEW", int(m[2])), ("FOREIGN_KEY", int(m[3]))):
        if counts[key] != val:
            errs.append(f"C3: gold counts.{key}={counts[key]} != 계약 {val}")


def c4_rqr_examples_match_contract(errs: list) -> None:
    """L1 db RQR 예시의 counts.input 은 테이블+뷰다 — 예시가 틀린 분모를 실어 나르면 안 된다."""
    m = CONTRACT_ROW.search(contract_text())
    if not m:
        errs.append("C4: §1.1 수치 표기를 찾지 못했다 (C1 참조)")
        return
    tables, views = int(m[1]), int(m[2])
    manifest = json.loads((RQR_EXAMPLES / "manifest.json").read_text(encoding="utf-8"))
    # R2(input = output+failed+excluded) 음성 픽스처는 분모를 **일부러** 틀린다 — 이 검사의 대상이 아니다.
    deliberate = {c["file"] for c in manifest["cases"] if c.get("rule") == "R2"}
    for path in sorted(RQR_EXAMPLES.glob("*.json")):
        if path.name == "manifest.json" or path.name in deliberate:
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        run, counts = doc.get("run", {}), doc.get("counts", {})
        if run.get("layer") != "L1" or run.get("track") != "db":
            continue
        if counts.get("input") == 0:  # 대상 없는 실행 픽스처는 이 검사의 대상이 아니다
            continue
        if counts.get("input") != tables + views:
            errs.append(f"C4: {path.name} counts.input={counts.get('input')} "
                        f"!= 테이블+뷰 {tables + views}")
        if path.name.startswith("valid.") and counts.get("output") != tables:
            errs.append(f"C4: {path.name} counts.output={counts.get('output')} != 테이블 {tables}")
        if re.search(rf"\b{tables + views + 1}\b", json.dumps(doc, ensure_ascii=False)):
            errs.append(f"C4: {path.name} 에 옛 분모 {tables + views + 1} 문자열이 남아 있다")


def c5_revision_history_keeps_old_value(errs: list) -> None:
    """I1 §7.3 — 수치 변경은 이전 값과 함께 남긴다. 덮어쓰기는 개정이 아니다."""
    text = contract_text()
    if "개정 이력" not in text:
        errs.append("C5: 개정 이력 절이 없다 (I1 §7.3)")
        return
    head = text.split("## 0.", 1)[0]
    if not re.search(r"28\s*→\s*27|28 → 27", head):
        errs.append("C5: 개정 이력에 이전 값(28 → 27)이 남아 있지 않다")


def c6_history_line_coordinates_resolve(errs: list) -> None:
    """개정 이력이 적은 새 행 번호(L→L)가 실제로 그 내용을 가리켜야 한다.

    상단에 개정 이력을 붙이면(§7.3) 이후 모든 행이 밀린다. 밀린 좌표를 적어 두는 것은 gold 의
    문서 축(docsRevision)을 올릴 때 쓰는 안내인데, 그 좌표가 틀리면 유령 좌표를 하나 더 만든다.
    """
    lines = contract_text().splitlines()
    expect = [(r"DB 행 L\d+ → L(\d+)", CONTRACT_ROW),                      # §1.1 DB 행
              (r"FK 서술 L\d+ → L(\d+)", CONTRACT_PROSE),                   # §1.1 서술문
              (r"파싱 실패\" 행 L\d+ → L(\d+)",
               re.compile(r"^\| L1 무보고 파싱 실패"))]                       # §4.1 게이트 행
    text = contract_text()
    for pattern, target in expect:
        m = re.search(pattern, text)
        if not m:
            errs.append(f"C6: 개정 이력의 행 번호 표기를 찾지 못했다 ({pattern})")
            continue
        no = int(m[1])
        if not (1 <= no <= len(lines)) or not target.search(lines[no - 1]):
            errs.append(f"C6: 개정 이력이 가리킨 L{no} 이 {target.pattern!r} 를 담고 있지 않다")


CHECKS = [c1_contract_matches_fixture, c2_prose_matches_row, c3_gold_matches_contract,
          c4_rqr_examples_match_contract, c5_revision_history_keeps_old_value,
          c6_history_line_coordinates_resolve]


def main() -> int:
    errs: list = []
    for check in CHECKS:
        try:
            check(errs)
        except Exception as exc:  # 한 검사의 예외가 나머지를 가리지 않게 한다
            errs.append(f"{check.__name__}: 예외 {exc!r}")
    print(f"{len(CHECKS)} checks, {len(errs)} mismatches")
    for e in errs:
        print("FAIL " + e)
    if errs:
        return 1
    print("[ok] I1 §1.1 DB 수치가 원문 실측·gold·RQR 예시와 일치한다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
