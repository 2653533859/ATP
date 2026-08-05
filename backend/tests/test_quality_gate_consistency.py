"""门禁一致性契约（Q15-01）。

Makefile、`ci.yml` 与 `.pre-commit-config.yaml` 声明的是同一套门禁，但各自
独立写死数值和版本。Q14-01 里 Makefile 的覆盖率门禁停在 52 而 CI 已是 70，
是靠人工比对才发现的；本文件把这类漂移变成测试失败。
"""

from __future__ import annotations

import re

COV_GATE_PATTERN = re.compile(r"--cov-fail-under=(\d+)")
DEV_PIN_PATTERN = re.compile(r"^(?P<name>[A-Za-z0-9_.\-]+)==(?P<version>[A-Za-z0-9_.\-]+)\s*$")
SCRIPT_PATTERN = re.compile(r"scripts/[A-Za-z0-9_.\-]+\.py")

# 这些工具在 pre-commit 里隔离安装，版本必须与 requirements-dev 一致，
# 否则本地钩子和 CI 会给出不同结论。
PINNED_IN_PRE_COMMIT = ("ruff", "mypy", "types-PyYAML", "types-redis")


def _dev_pins(repo_file) -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in repo_file("backend/requirements-dev.txt").splitlines():
        match = DEV_PIN_PATTERN.match(line.strip())
        if match:
            pins[match.group("name")] = match.group("version")
    return pins


def _requirement_lines(repo_file) -> set[str]:
    lines: set[str] = set()
    for name in ("backend/requirements.txt", "backend/requirements-dev.txt"):
        for line in repo_file(name).splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                lines.add(stripped)
    return lines


def _mypy_hook_dependencies(repo_file) -> list[str]:
    """取出 backend-mypy 钩子 additional_dependencies 下的依赖行。"""
    config = repo_file(".pre-commit-config.yaml")
    body = config.split("id: backend-mypy", 1)[1]
    body = body.split("additional_dependencies:", 1)[1]
    deps: list[str] = []
    for raw in body.splitlines()[1:]:
        stripped = raw.strip()
        if not stripped.startswith("- "):
            break
        deps.append(stripped[2:].strip())
    return deps


def _lint_scripts(repo_file) -> set[str]:
    makefile = repo_file("Makefile")
    declaration = re.search(r"^LINT_SCRIPTS = (.+)$", makefile, re.MULTILINE)
    assert declaration, "Makefile 必须用 LINT_SCRIPTS 声明受检脚本清单"
    return set(SCRIPT_PATTERN.findall(declaration.group(1)))


def test_backend_coverage_gate_is_identical_in_makefile_and_ci(repo_file):
    makefile_gates = set(COV_GATE_PATTERN.findall(repo_file("Makefile")))
    ci_gates = set(COV_GATE_PATTERN.findall(repo_file(".github/workflows/ci.yml")))

    assert makefile_gates, "Makefile 必须显式声明 --cov-fail-under"
    assert ci_gates, "ci.yml 必须显式声明 --cov-fail-under"
    assert len(makefile_gates) == 1, f"Makefile 内部覆盖率门禁不一致: {sorted(makefile_gates)}"
    assert len(ci_gates) == 1, f"ci.yml 内部覆盖率门禁不一致: {sorted(ci_gates)}"
    assert makefile_gates == ci_gates, (
        f"Makefile 门禁 {sorted(makefile_gates)} 与 ci.yml 门禁 {sorted(ci_gates)} 漂移；" "抬门禁时必须同时改两处"
    )


def test_ci_doc_quotes_the_live_gate_values(repo_file):
    """`docs/ci-workflows.md` 是排查入口，写着旧数值等于把人引到错的门禁上。

    实测这份文档曾停在 `--cov-fail-under=66` 与前端 4.1%/4.55%/2.7%/4.35%，
    而真实门禁已是 70 与 20.5/17.5/16.5/21.0。
    """
    doc = repo_file("docs/ci-workflows.md")

    ci_gate = COV_GATE_PATTERN.findall(repo_file(".github/workflows/ci.yml"))[0]
    assert f"--cov-fail-under={ci_gate}" in doc, f"文档未同步后端覆盖率门禁 {ci_gate}"

    vitest_config = repo_file("frontend/vitest.config.ts")
    for key in ("statements", "branches", "functions", "lines"):
        match = re.search(rf"{key}:\s*([0-9.]+)", vitest_config)
        assert match, f"frontend/vitest.config.ts 未声明 {key} 门禁"
        value = match.group(1)
        assert f"`{value}%`" in doc, f"文档未同步前端 {key} 门禁 {value}%"


def test_standalone_sweep_is_wired_into_make_and_ci(repo_file):
    """单文件可运行性（Q15-02）必须有自动扫描，否则会静默回归。"""
    sweep = "scripts/pytest-standalone-sweep.py"
    assert "test-backend-standalone:" in repo_file("Makefile")
    assert sweep in repo_file("Makefile")
    assert sweep in repo_file(".github/workflows/ci.yml")


def test_ci_runs_the_backend_suite_on_windows(repo_file):
    """Windows 是文档化的开发平台（Q15-03），CI 必须真的在上面跑一遍后端单测。

    仓库提供 `docs/windows-local-run.md` 与 `scripts/windows-local.ps1`，但在
    Q15-03 之前每个 workflow 都只跑 Linux；第一次在 Windows 上跑全套就撞出一个
    仅该平台失败的用例。
    """
    ci = repo_file(".github/workflows/ci.yml")
    assert "windows-latest" in ci, "ci.yml 缺少 Windows runner"

    windows_job = ci.split("backend-test-windows:", 1)[1].split("\n  frontend-check:", 1)[0]
    assert "runs-on: windows-latest" in windows_job
    assert "pytest backend/tests" in windows_job
    assert "--ignore=backend/tests/integration" in windows_job, "integration 仍只在 Linux 跑"

    doc = repo_file("docs/ci-workflows.md")
    assert "Windows job 的范围" in doc, "Windows job 的范围与刻意排除项必须在文档里写明"


def test_pre_commit_pins_match_requirements_dev(repo_file):
    config = repo_file(".pre-commit-config.yaml")
    pins = _dev_pins(repo_file)

    for name in PINNED_IN_PRE_COMMIT:
        assert name in pins, f"backend/requirements-dev.txt 缺少 {name} 的固定版本"
        expected = f"{name}=={pins[name]}"
        assert expected in config, (
            f".pre-commit-config.yaml 未按 requirements-dev 固定 {expected}；" "本地钩子与 CI 用不同版本会给出不同结论"
        )


def test_mypy_hook_does_not_depend_on_ambient_path_python(repo_file):
    """`language: system` + `entry: python -m mypy` 会用 PATH 上第一个 python。

    `make pre-commit` 会先把 venv 的 bin 目录塞进 PATH 所以看不出问题，但真实
    git commit 触发已安装的钩子时用的是环境 PATH，钩子会崩或用错版本的 mypy。
    """
    config = repo_file(".pre-commit-config.yaml")
    hook_start = config.index("id: backend-mypy")
    hook_body = config[hook_start : hook_start + 900]

    assert "entry: python -m mypy" not in hook_body
    assert "language: system" not in hook_body.split("- id:")[0]
    assert "language: python" in hook_body
    assert "mypy==" in hook_body, "隔离安装必须固定 mypy 版本"


def test_mypy_hook_sees_the_real_type_sources(repo_file):
    """隔离环境里只装 mypy 会让依赖第三方库签名的错误静默消失。

    实测：把 `d116359^` 的 `run_retention.py` 放回去，只装 mypy + 两个 stub 包时
    报 8 个错，装上 sqlalchemy 后与完整 venv 一致报 12 个 —— 少掉的 4 条
    `not_in()` arg-type 正是 2026-07-11 混进 main 并存活 20 天的那批。
    """
    deps = _mypy_hook_dependencies(repo_file)
    assert any(
        dep.startswith("sqlalchemy") for dep in deps
    ), "backend-mypy 钩子必须装 sqlalchemy，否则 SQLAlchemy 相关的 arg-type 错误检不出来"

    known = _requirement_lines(repo_file)
    for dep in deps:
        assert dep in known, f"钩子依赖 {dep!r} 未在 backend/requirements*.txt 中原样固定，版本会漂移"


def test_ci_lint_job_installs_runtime_requirements(repo_file):
    """CI 的 mypy 与钩子、`make mypy` 必须看到同一套类型来源。"""
    ci = repo_file(".github/workflows/ci.yml")
    lint_job = ci.split("backend-lint:", 1)[1].split("\n  migration-check:", 1)[0]

    assert "python -m mypy" in lint_job
    assert (
        "pip install -r backend/requirements.txt" in lint_job
    ), "只装 requirements-dev.txt 时 CI 的 mypy 看不到 SQLAlchemy 签名，会漏报 arg-type 错误"
    assert "pip install -r backend/requirements-dev.txt" in lint_job


def test_ruff_covers_the_same_scripts_everywhere(repo_file):
    """脚本会被 CI 真正执行，但 ruff 的受检范围曾只写在 Makefile 里。

    `scripts/pytest-standalone-sweep.py` 在 CI 里执行；若 ruff 门禁
    （`F821`/`F822`/`F823`，正是未定义名称类错误）不覆盖它，写错一个变量名会是
    lint 绿、钩子绿，跑到该步骤才 NameError 崩。
    """
    expected = _lint_scripts(repo_file)
    assert expected, "LINT_SCRIPTS 不应为空"

    makefile = repo_file("Makefile")
    for target in ("lint:", "format:", "format-check:"):
        body = makefile.split(f"\n{target}", 1)[1].split("\n\n", 1)[0]
        assert "$(LINT_SCRIPTS)" in body, f"Makefile 的 {target} 未使用 LINT_SCRIPTS"

    ci = repo_file(".github/workflows/ci.yml")
    for step in ("python -m ruff check ", "python -m ruff format --check "):
        line = next((entry for entry in ci.splitlines() if step in entry), None)
        assert line, f"ci.yml 缺少 `{step.strip()}` 步骤"
        assert (
            set(SCRIPT_PATTERN.findall(line)) == expected
        ), f"ci.yml 的 `{step.strip()}` 覆盖的脚本与 LINT_SCRIPTS 不一致"

    config = repo_file(".pre-commit-config.yaml")
    for entry in ("entry: ruff check ", "entry: ruff format --check "):
        line = next((item for item in config.splitlines() if entry in item), None)
        assert line, f".pre-commit-config.yaml 缺少 `{entry.strip()}` 钩子"
        assert (
            set(SCRIPT_PATTERN.findall(line)) == expected
        ), f".pre-commit-config.yaml 的 `{entry.strip()}` 覆盖的脚本与 LINT_SCRIPTS 不一致"


def test_setup_installs_dev_tooling_and_the_git_hook(repo_file):
    """`make setup` 之后，验证章节里列的命令必须真的可用。

    此前 setup 只装 backend/requirements.txt，ruff / mypy / pre-commit 都不在
    其中，而 CLAUDE.md 的 Verification 章节却直接让人跑 `make lint` / `make mypy`。
    钩子没装上则本地门禁在 commit 时完全不生效。
    """
    makefile = repo_file("Makefile")
    setup_body = makefile.split("setup:", 1)[1].split("\ndev:", 1)[0]

    assert "requirements-dev.txt" in setup_body
    assert "pre_commit install" in setup_body or "pre-commit install" in setup_body
