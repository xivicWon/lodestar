#!/usr/bin/env python3
"""#115 마스킹 작업의 **종료 조건** — 언제 리뷰-수정 루프를 멈출 수 있는가.

    python3 docs/superpowers/specs/bench/masking/exit_criteria.py

왜 필요한가: AI 리뷰는 매 실행마다 후보 20~30건을 만들고 그중 몇 건을 게시한다. 지적이 0건이 되는
시점은 오지 않으므로, "지적이 없을 때까지" 를 종료 조건으로 삼으면 루프가 끝나지 않는다. 대신
**무엇이 남아 있으면 닫을 수 없는가**를 명시하고 기계가 판정한다.

판정하는 것 (전부 통과해야 종료 가능):

  E1  무조건 게이트 6종 전부 PASS                     — 동작이 계약을 지키는가
  E2  확인기가 깨끗하다 (0 mismatches · manifest 일치) — 그 판정을 믿을 수 있는가
  E3  blocking 미해결 항목 0건                        — 남은 것이 후속으로 미룰 수 있는 종류인가

E3 의 기준은 `open-items.json` 이 정의한다: **제품 코드·규칙 스펙 대상의 MAJOR 는 blocking**,
테스트·증거·문서 강화는 후속 이슈다. 이 구분이 없으면 종료 조건이 성립하지 않는다 — 테스트를
강화할 때마다 강화할 자리가 새로 생기기 때문이다(테스트가 약한 것과 결함이 새는 것은 다르다).

미해결 항목을 여기 등재하지 않고 미루는 것은 추적을 포기하는 것이다. 그래서 이 파일은
"남은 것이 없다" 가 아니라 **"남은 것이 전부 등재돼 있고 그중 blocking 이 없다"** 를 판정한다.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REQUIRED_GATES = [
    "gate-security-masking",
    "gate-engine-parity",
    "gate-engine-parity-branches",
    "gate-db-ingest-masking",
    "gate-code-emit-masking",
    "gate-no-plaintext-in-records",
]


def e1_gates() -> tuple[bool, str]:
    rep = json.loads((HERE / "report.json").read_text(encoding="utf-8"))
    by_id = {g["id"]: g for g in rep["gates"]}
    missing = [g for g in REQUIRED_GATES if g not in by_id]
    if missing:
        return False, f"게이트가 보고서에 없다: {missing}"
    failed = [g for g in REQUIRED_GATES if by_id[g]["status"] != "PASS"]
    if failed:
        return False, f"FAIL 게이트 {len(failed)}건: {failed}"
    return True, f"무조건 게이트 {len(REQUIRED_GATES)}종 전부 PASS"


def e2_verifier() -> tuple[bool, str]:
    """확인기를 **그대로 호출한다**.

    규칙·주입 판정을 여기서 다시 구현하면 같은 산식이 두 곳에 생긴다 — 이 리포가 반복해서 밟은
    결함이다(보고서·게이트·확인기가 서로 다른 식을 쓰던 자리). `verify_masking.main()` 은 규칙
    실행·결함 주입·manifest 대조를 모두 하고 종료 코드로 답한다. 그 답을 그대로 쓴다.
    """
    import contextlib
    import io

    sys.path.insert(0, str(HERE))
    import verify_masking as V  # noqa: E402

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = V.main()
    out = buf.getvalue().strip().splitlines()
    summary = next((l for l in reversed(out) if "mismatches" in l), out[-1] if out else "")
    if rc != 0:
        detail = " · ".join(l.strip("  - ") for l in out if l.startswith("  - ")) or summary
        return False, f"{summary.strip()} — {detail}"
    return True, summary.strip()


def e3_open_items() -> tuple[bool, str]:
    doc = json.loads((HERE / "open-items.json").read_text(encoding="utf-8"))
    items = doc["items"]
    blocking = [i for i in items if i.get("blocking") and not i.get("resolved")]
    open_n = sum(1 for i in items if not i.get("resolved"))
    if blocking:
        lines = "\n".join(f"      - [{i['id']}] {i['area']}/{i['severity']}: {i['summary']}"
                          for i in blocking)
        return False, f"blocking 미해결 {len(blocking)}건 (등재 미해결 {open_n}건)\n{lines}"
    return True, f"blocking 0건 (등재 미해결 {open_n}건 — 전부 후속 이슈로 미룰 수 있는 종류)"


def main() -> int:
    checks = [("E1 무조건 게이트", e1_gates), ("E2 확인기", e2_verifier), ("E3 blocking 항목", e3_open_items)]
    ok_all = True
    for name, fn in checks:
        try:
            ok, detail = fn()
        except Exception as e:  # 확인기 자체가 죽는 것도 종료 불가다
            ok, detail = False, f"검사 실행 실패: {type(e).__name__}: {e}"
        ok_all &= ok
        print(f"  [{'ok' if ok else 'FAIL'}] {name} — {detail}")
    print()
    if ok_all:
        print("[ok] 종료 조건 충족 — 남은 지적은 후속 이슈로 옮기고 이 PR 을 닫을 수 있다")
        return 0
    print("[FAIL] 종료 조건 미충족 — 위 항목을 닫기 전에는 이 PR 을 닫지 않는다")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
