#!/usr/bin/env python3
"""하위 불변식 발화 시험 (firing test).

`validate_gold.py` 의 `SUBCHECKS` 는 "이 규칙은 이런 것들을 검사한다" 는 **선언**이다.
선언이 코드와 어긋나도 확인기 자신은 알 수 없다 — 문서에 id 가 있는지만 보기 때문이다.
그래서 선언마다 **그 검사만 깨뜨리는 최소 변형**을 넣고 실제로 그 실패가 나오는지 본다.

    python3 fire.py            # 전체 발화
    python3 fire.py G11        # 특정 규칙만

이 시험이 증명하는 것은 두 가지다.
  (a) 선언한 하위 불변식에 대응하는 **코드가 실재한다** (없으면 발화하지 않는다)
  (b) 그 코드가 **의도한 변형에 반응한다** (id 태그만으로는 증명되지 않는 부분)

변형은 코드가 아니라 `firing.json` 에 **데이터로** 있다. 판정 기준을 코드에 묻으면
사람이 조정할 수 없고, 조정할 수 없는 기준은 리뷰어의 것이 아니라 작성자의 것이 된다.
면제(`waivers`)도 그 파일에 있으며 **사유 없이는 면제되지 않는다**.
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).parent
SPEC = json.loads((HERE / "firing.json").read_text())


def _dig(obj, path):
    """경로를 따라가 (부모, 키) 를 돌려준다.

    `a.b[0].c` 문자열, 또는 키에 `.`·`/` 가 들어가는 경우를 위한 리스트 형태
    `["expectedCounts", "l1/db.json"]` 둘 다 받는다 — 점 표기만 지원하면
    파일명이 키인 자리를 아예 가리킬 수 없다.
    """
    parts = path if isinstance(path, list) else re.findall(r"[^.\[\]]+|\[\d+\]", path)

    def norm(x):
        return int(x[1:-1]) if isinstance(x, str) and x.startswith("[") else x

    cur = obj
    for part in parts[:-1]:
        cur = cur[norm(part)]
    # 마지막 키는 **따라가지 않는다** — 아직 없는 키에 값을 넣는 변형(예: 승인
    # 정보를 새로 채우는 경우)이 KeyError 로 죽으면 그 사례를 아예 쓸 수 없다.
    return cur, norm(parts[-1])


def apply_mut(m):
    op = m["op"]
    if op in ("write", "newfile"):
        (HERE / m["file"]).write_text(m["text"])
        return
    p = HERE / m["file"]
    d = json.loads(p.read_text())
    if op == "set":
        parent, key = _dig(d, m["path"])
        parent[key] = m["value"]
    elif op == "del":
        parent, key = _dig(d, m["path"])
        del parent[key]
    elif op == "append":
        parent, key = _dig(d, m["path"])
        parent[key].append(m["value"])
    else:
        raise ValueError(f"알 수 없는 op: {op}")
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n")


def snapshot():
    tmp = pathlib.Path(tempfile.mkdtemp()) / "gold"
    shutil.copytree(HERE, tmp)
    return tmp


def restore(snap):
    """스냅샷으로 되돌린다 — 시험이 만든 파일까지 지운다.

    되돌리기가 불완전하면 다음 사례가 앞 사례의 잔재 위에서 돌아, 발화 결과가
    사례 순서에 의존하게 된다. 그러면 이 시험 자체가 결정적이지 않다.
    """
    for p in sorted(HERE.rglob("*"), reverse=True):
        rel = p.relative_to(HERE)
        if p.is_file() and not (snap / rel).exists():
            p.unlink()
    for p in snap.rglob("*"):
        if p.is_file():
            dst = HERE / p.relative_to(snap)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)


def run_validator(rehash=False):
    if rehash:
        subprocess.run([sys.executable, "validate_gold.py", "--rehash"],
                       cwd=HERE, capture_output=True)
    r = subprocess.run([sys.executable, "validate_gold.py"], cwd=HERE,
                       capture_output=True, text=True)
    return r.stdout + r.stderr


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    cases = [c for c in SPEC["cases"]
             if not only or c["subcheck"].split(".")[0] == only]
    waivers = SPEC["waivers"]

    # 선언 ↔ 사례의 결속. 사례도 면제도 없는 하위 불변식은 "검사한다고 적어만 둔 것" 이다.
    sys.path.insert(0, str(HERE))
    import importlib.util
    spec = importlib.util.spec_from_file_location("vg", HERE / "validate_gold.py")
    vg = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(vg)
    except SystemExit:
        pass
    declared = {s.split()[0] for subs in vg.SUBCHECKS.values() for s in subs}
    covered = {c["subcheck"] for c in SPEC["cases"]} | set(waivers)
    gaps = sorted(declared - covered)
    ghosts = sorted(covered - declared)

    base = run_validator()
    if not base.strip().startswith("OK"):
        print("중단 — 기준 상태가 이미 실패다. 발화 시험은 그린에서만 의미가 있다.\n")
        print(base)
        return 1

    snap = snapshot()
    results = []
    try:
        for c in cases:
            # 사례 하나가 죽으면 나머지 사례가 아예 돌지 않는다. 확인기에서 겪은
            # 것과 같은 구조이며, 침묵한 시험은 통과한 시험과 구분되지 않는다.
            try:
                for m in c["mutations"]:
                    apply_mut(m)
                out = run_validator(rehash=c.get("needsRehash", False))
                want = c["expect"]["contains"]
                want = [want] if isinstance(want, str) else want
                ok = (f"[{c['expect']['rule']}]" in out
                      and all(w in out for w in want)
                      and "Traceback" not in out)
                note = c["why"]
            except Exception as e:
                ok, note = False, f"{c['why']} (변형 적용 실패: {type(e).__name__}: {e})"
            results.append((c["subcheck"], ok, note))
            restore(snap)
    finally:
        restore(snap)
        run_validator(rehash=True)

    bad = [r for r in results if not r[1]]
    for sc, ok, why in results:
        if not ok:
            print(f"  발화하지 않음  {sc} — {why}")
    for g in gaps:
        print(f"  사례 없음      {g} — 검사한다고 적혀 있으나 발화 사례도 면제도 없다")
    for g in ghosts:
        print(f"  유령 사례      {g} — 확인기에 그런 하위 불변식이 없다")
    for w, reason in sorted(waivers.items()):
        print(f"  면제           {w} — {reason}")

    n = len(results)
    if bad or gaps or ghosts:
        print(f"\nFAIL — 사례 {n}건 중 미발화 {len(bad)} · 사례 없음 {len(gaps)} · "
              f"유령 {len(ghosts)}")
        return 1
    print(f"OK — 하위 불변식 {len(declared)}개 · 발화 사례 {n}건 전부 반응 · "
          f"면제 {len(waivers)}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
