#!/usr/bin/env python3
"""증거 게이트의 **자동 실행 계약** 확인기 (#124).

I1 은 "재현할 수 없는 측정은 측정이 아니다" 를 무조건 게이트로 두는데, #124 이전에는 그 게이트를
지키는 검사 자체가 사람이 기억해서 돌려야만 실행됐다. 이 확인기는 그 자동 실행이 **선언대로 존재하고,
수동 재현 절차와 갈라지지 않으며, 실패를 삼키지 않는가** 를 검사한다.

  W1  트리거    PR 과 main push 에서 모두 돈다
  W2  범위      #124 이슈 표의 검사가 전부 워크플로 안에 있다
  W3  동일성    bench/l0/README.md 의 `<!-- ci-parity -->` 재현 명령을 CI 가 그대로 쓴다
  W4  실패전파  검사 단계가 실패를 삼키지 않는다 (continue-on-error · `|| true` · `set +e`)
  W5  의존성    Python 3.11+ · JDK · `pip install jsonschema` · `pip install -e codegraph`
  W6  생략금지  gradle 증거 입력 선언이 유효하고, CI 가 gradle 빌드 캐시로 :test 를 건너뛰지 않는다

규칙이 정말 무는지는 규칙별 **결함 주입**으로 확인한다 — 워크플로·gradle·README 원문을 메모리에서
훼손한 뒤 그 규칙이 위반을 내야 한다. 무엇도 물지 않는 확인기는 그린을 만들 뿐 아무것도 막지 않는다.

    python3 docs/superpowers/specs/bench/ci/verify_ci.py
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - 환경 문제는 조용히 통과시키지 않는다
    sys.exit("[fail] PyYAML 이 필요하다: pip install pyyaml")

REPO = Path(__file__).resolve().parents[5]
WORKFLOW = REPO / ".github" / "workflows" / "verify.yml"
README = REPO / "docs" / "superpowers" / "specs" / "bench" / "l0" / "README.md"
GRADLE = REPO / "backend" / "build.gradle.kts"
MANIFEST = Path(__file__).resolve().parent / "manifest.json"

PARITY_MARKER = "<!-- ci-parity -->"

# #124 이슈 표의 검사. 키는 규칙 위반 메시지에 쓰는 이름, 값은 워크플로 run 블록에 있어야 할 조각.
REQUIRED_CHECKS: dict[str, str] = {
    "verify_l0.py (V1~V14)": "bench/l0/verify_l0.py",
    "probe_code.py --check": "bench/l0/probe_code.py --check",
    "build_report.py": "bench/l0/build_report.py",
    "보고서 표류 검사": "git diff --exit-code docs/superpowers/specs/bench/l0/runs",
    "schemas/validate.py": "schemas/validate.py",
    "verify_i1_counts.py": "verify_i1_counts.py",
    "codegraph pytest": "cd codegraph && python3 -m pytest -q",
    "backend ./gradlew test": "cd backend && ./gradlew test",
}


@dataclass
class Ctx:
    """확인 대상 원문. 결함 주입은 이 텍스트를 갈아끼워 같은 규칙을 다시 돌린다."""

    workflow_text: str
    readme_text: str
    gradle_text: str
    repo: Path = REPO

    @property
    def workflow(self) -> dict:
        doc = yaml.safe_load(self.workflow_text)
        return doc if isinstance(doc, dict) else {}

    def triggers(self) -> dict:
        # YAML 1.1 에서 맨 `on:` 은 불리언 True 로 읽힌다 — 두 키를 모두 본다.
        wf = self.workflow
        raw = wf.get("on", wf.get(True))
        return raw if isinstance(raw, dict) else {}

    def steps(self) -> list[dict]:
        out: list[dict] = []
        for job in (self.workflow.get("jobs") or {}).values():
            for step in (job or {}).get("steps") or []:
                if isinstance(step, dict):
                    out.append(step)
        return out

    def run_lines(self) -> list[str]:
        lines: list[str] = []
        for step in self.steps():
            run = step.get("run")
            if isinstance(run, str):
                lines.extend(normalize(ln) for ln in run.splitlines())
        return [ln for ln in lines if ln]

    def run_text(self) -> str:
        return "\n".join(self.run_lines())


def normalize(line: str) -> str:
    """명령 한 줄을 비교 가능한 형태로. 주석·들여쓰기·중복 공백을 지운다."""
    line = re.sub(r"\s+#.*$", "", line.strip())
    if line.startswith("#"):
        return ""
    return re.sub(r"\s+", " ", line)


def parity_commands(readme_text: str) -> list[str]:
    """README 에서 `<!-- ci-parity -->` 가 붙은 bash 펜스의 명령만 뽑는다."""
    cmds: list[str] = []
    lines = readme_text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].strip() == PARITY_MARKER:
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                i += 1
            i += 1  # 여는 펜스
            while i < len(lines) and not lines[i].startswith("```"):
                cmd = normalize(lines[i])
                if cmd:
                    cmds.append(cmd)
                i += 1
        i += 1
    return cmds


# ---------------------------------------------------------------- 규칙 W1~W6


def w1_triggers(c: Ctx) -> list[str]:
    v: list[str] = []
    trig = c.triggers()
    if "pull_request" not in trig:
        v.append("W1: 워크플로가 pull_request 에서 돌지 않는다 — PR 이 붉어질 수 없다")
    push = trig.get("push")
    branches = (push or {}).get("branches") if isinstance(push, dict) else None
    if "main" not in (branches or []):
        v.append("W1: 워크플로가 main push 에서 돌지 않는다 — 머지 후 회귀를 잡지 못한다")
    return v


def w2_scope(c: Ctx) -> list[str]:
    text = c.run_text()
    return [
        f"W2: #124 표의 검사가 CI 에 없다 — {name} ({needle!r})"
        for name, needle in REQUIRED_CHECKS.items()
        if needle not in text
    ]


def w3_parity(c: Ctx) -> list[str]:
    have = set(c.run_lines())
    missing = [cmd for cmd in parity_commands(c.readme_text) if cmd not in have]
    if not parity_commands(c.readme_text):
        return [f"W3: README 에 {PARITY_MARKER} 로 표시된 재현 명령이 하나도 없다"]
    return [f"W3: README 재현 명령이 CI 에 없다 — {cmd!r}" for cmd in missing]


def w4_failure_propagates(c: Ctx) -> list[str]:
    v: list[str] = []
    for step in c.steps():
        if step.get("continue-on-error"):
            v.append(f"W4: continue-on-error 가 실패를 삼킨다 — {step.get('name', step)!r}")
    for line in c.run_lines():
        if re.search(r"\|\|\s*(true|:)\s*$", line):
            v.append(f"W4: `|| true` 가 실패를 삼킨다 — {line!r}")
        if re.match(r"set\s+\+e\b", line):
            v.append(f"W4: `set +e` 가 실패를 삼킨다 — {line!r}")
    return v


def w5_dependencies(c: Ctx) -> list[str]:
    v: list[str] = []
    text = c.run_text()
    pythons = [
        str(s.get("with", {}).get("python-version", ""))
        for s in c.steps()
        if "actions/setup-python" in str(s.get("uses", ""))
    ]
    if not pythons:
        v.append("W5: Python 설치 단계(actions/setup-python)가 없다")
    else:
        for ver in pythons:
            parts = re.findall(r"\d+", ver)
            if len(parts) < 2 or (int(parts[0]), int(parts[1])) < (3, 11):
                v.append(f"W5: Python {ver!r} 은 codegraph 요구(>=3.11) 미만이다")
    if not any("actions/setup-java" in str(s.get("uses", "")) for s in c.steps()):
        v.append("W5: JDK 설치 단계(actions/setup-java)가 없다 — 백엔드 트랙이 돌 수 없다")
    if not re.search(r"pip install[^\n]*\bjsonschema\b", text):
        v.append("W5: `pip install jsonschema` 가 없다 — 스키마 확인기가 임포트에서 죽는다")
    if not re.search(r"pip install[^\n]*-e codegraph", text):
        v.append("W5: `pip install -e codegraph` 가 없다 — 코드 프로브가 수집기를 못 찾는다")
    return v


def w6_no_silent_skip(c: Ctx) -> list[str]:
    v: list[str] = []
    declared = re.findall(r"File\(rootDir\.parentFile,\s*\"([^\"]+)\"\)", c.gradle_text)
    if not declared:
        v.append("W6: build.gradle.kts 에 증거 입력 선언이 하나도 없다 — :test 가 UP-TO-DATE 로 생략된다")
    for rel in declared:
        if not (c.repo / rel).exists():
            v.append(f"W6: gradle 증거 입력 경로가 실재하지 않는다 — {rel!r} (오타는 아무것도 선언하지 않는다)")
    for step in c.steps():
        uses = str(step.get("uses", ""))
        with_ = step.get("with") or {}
        if "setup-gradle" in uses and str(with_.get("cache-disabled", "")).lower() != "true":
            v.append("W6: gradle 빌드 캐시가 켜져 있다 — 이전 실행 결과로 :test 가 UP-TO-DATE 가 된다")
        if "actions/cache" in uses and ".gradle" in str(with_.get("path", "")):
            v.append("W6: ~/.gradle 캐시 복원이 :test 를 UP-TO-DATE 로 만들 수 있다")
    return v


RULES = {
    "W1": w1_triggers,
    "W2": w2_scope,
    "W3": w3_parity,
    "W4": w4_failure_propagates,
    "W5": w5_dependencies,
    "W6": w6_no_silent_skip,
}


def run_rules(c: Ctx) -> list[str]:
    out: list[str] = []
    for rule in RULES.values():
        try:
            out.extend(rule(c))
        except Exception as exc:  # 규칙별 격리 — 하나가 죽어도 나머지 검출을 버리지 않는다
            out.append(f"{rule.__name__}: 규칙 실행 중 예외 {exc!r}")
    return out


# ------------------------------------------------------------- 결함 주입 케이스


def drop_line(text: str, needle: str) -> str:
    return "\n".join(ln for ln in text.splitlines() if needle not in ln)


def _cases(base: Ctx) -> list[tuple[str, str, Ctx]]:
    """(케이스 id, 물어야 할 위반 메시지의 접두사, 훼손된 컨텍스트)

    접두사는 보통 규칙 id(`"W5"`)지만, 한 규칙이 여러 위반을 내는 경우 **그 위반**까지 지정한다
    (`"W5: JDK"`) — 같은 규칙이 다른 이유로 물었는데 통과로 세면 주입이 아무것도 확인하지 못한다.
    """
    wf, rd, gr = base.workflow_text, base.readme_text, base.gradle_text
    from dataclasses import replace

    cases: list[tuple[str, str, Ctx]] = [
        ("W1.no-pull-request", "W1", replace(base, workflow_text=drop_line(wf, "pull_request:"))),
        ("W1.no-main-push", "W1", replace(base, workflow_text=wf.replace("      - main", "      - other", 1))),
    ]
    for needle in REQUIRED_CHECKS.values():
        slug = re.sub(r"[^a-z0-9]+", "-", needle.lower()).strip("-")
        cases.append((f"W2.missing-{slug}", "W2", replace(base, workflow_text=drop_line(wf, needle))))
    cases += [
        (
            "W3.command-drift",
            "W3",
            replace(base, workflow_text=wf.replace("bench/l0/verify_l0.py", "bench/l0/verify_l0.py --quiet")),
        ),
        ("W3.no-marker", "W3", replace(base, readme_text=rd.replace(PARITY_MARKER, ""))),
        (
            "W4.continue-on-error",
            "W4",
            replace(base, workflow_text=wf.replace("      - name: verify_l0", "      - continue-on-error: true\n      - name: verify_l0", 1))
            if "      - name: verify_l0" in wf
            else replace(base, workflow_text=wf + "\n        continue-on-error: true\n"),
        ),
        (
            "W4.swallow-with-or-true",
            "W4",
            replace(base, workflow_text=wf.replace(
                "python3 docs/superpowers/specs/bench/l0/verify_l0.py",
                "python3 docs/superpowers/specs/bench/l0/verify_l0.py || true",
            )),
        ),
        ("W5.no-jsonschema", "W5", replace(base, workflow_text=drop_line(wf, "jsonschema"))),
        ("W5.no-codegraph-install", "W5", replace(base, workflow_text=drop_line(wf, "-e codegraph"))),
        ("W5.python-too-old", "W5", replace(base, workflow_text=wf.replace("python-version:", "python-version: '3.10' #", 1))),
        # 단계 전체를 지운다 — `uses:` 줄만 지우면 남은 `with:` 가 앞 단계에 붙어
        # 엉뚱한 위반(python-version 소실)이 대신 뜨고, 그러면 JDK 규칙이 물었는지 확인하지 못한다.
        (
            "W5.no-jdk",
            "W5: JDK",
            replace(base, workflow_text=re.sub(
                r"      - uses: actions/setup-java@v4\n(?:        .*\n|          .*\n)*", "", wf, count=1
            )),
        ),
        (
            "W6.broken-gradle-input",
            "W6",
            replace(base, gradle_text=gr.replace("bench/l0/runs", "bench/l0/runz", 1)),
        ),
        (
            "W6.gradle-cache",
            "W6",
            replace(base, workflow_text=wf.replace(
                "      - uses: actions/setup-java@v4",
                "      - uses: gradle/actions/setup-gradle@v4\n      - uses: actions/setup-java@v4",
                1,
            )),
        ),
    ]
    return cases


# ------------------------------------------------------------------------ main


def main() -> int:
    for path in (WORKFLOW, README, GRADLE):
        if not path.exists():
            print(f"[fail] 대상 파일이 없다 — {path.relative_to(REPO)}")
            return 1

    base = Ctx(WORKFLOW.read_text(), README.read_text(), GRADLE.read_text())
    mismatches: list[str] = []
    cases = 0

    # 1) 현행 계약이 규칙을 지키는가
    for rid, rule in RULES.items():
        cases += 1
        violations = rule(base)
        status = "OK  " if not violations else "MISS"
        print(f"{status} {rid:<3} 현행 계약")
        for msg in violations:
            print(f"       {msg}")
        mismatches.extend(violations)

    # 2) 규칙이 정말 무는가 — 결함 주입
    for cid, expect, ctx in _cases(base):
        cases += 1
        fired = [m for m in run_rules(ctx) if m.startswith(expect)]
        if fired:
            print(f"OK   {cid:<34} {fired[0]}")
        else:
            print(f"MISS {cid:<34} {expect} 가 물지 않았다 — 결함이 통과한다")
            mismatches.append(f"{cid}: {expect} 미검출")

    manifest = json.loads(MANIFEST.read_text())
    if manifest["caseCount"] != cases:
        mismatches.append(
            f"manifest.caseCount={manifest['caseCount']} 인데 실제 케이스는 {cases} 다 — 정본을 갱신하지 않았다"
        )
    expected_range = f"W1-W{len(RULES)}"
    if manifest["ruleRange"] != expected_range:
        mismatches.append(f"manifest.ruleRange={manifest['ruleRange']!r} 인데 실제는 {expected_range!r} 다")

    print()
    print(f"{cases} cases, {len(mismatches)} mismatches")
    if mismatches:
        for m in mismatches:
            print(f"  - {m}")
        print("[fail] 증거 게이트의 자동 실행 계약이 깨졌다")
        return 1
    print("[ok] 증거 게이트가 CI 에서 자동으로 돌고, 수동 재현 절차와 같은 명령을 쓴다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
