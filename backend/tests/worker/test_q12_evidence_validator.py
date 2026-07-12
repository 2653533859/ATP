from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_validator(repo_root: Path):
    script = repo_root / "scripts" / "validate-q12-evidence.py"
    spec = importlib.util.spec_from_file_location("validate_q12_evidence", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_scaffold(repo_root: Path):
    script = repo_root / "scripts" / "scaffold-q12-evidence.py"
    spec = importlib.util.spec_from_file_location("scaffold_q12_evidence", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_valid_docs(tmp_path: Path):
    slo = tmp_path / "slo-history-2026-07-01-2026-07-14.md"
    android = tmp_path / "android-device-rehearsal-2026-07-14.md"
    acceptance = tmp_path / "q12-acceptance-summary.md"

    slo.write_text(
        """# SLO History Evidence

> Window: 2026-07-01 to 2026-07-14
> Record type: day-14 stable calibration
> Source deployment: staging-prod
> Prometheus: prom-main
> Grafana dashboard: `atp-overview`

## Preconditions

- [x] Prometheus continuously scraped `atp-backend` for the full window.
- [x] Worker metrics were scraped on `WORKER_METRICS_PORT` for the full window.
- [x] Grafana `atp-overview` loaded against the same Prometheus source.
- [x] Traffic profile is documented as real usage or synthetic profile.

## Scrape Health

| Date | Backend scrape healthy | Worker scrape healthy | Gaps / notes |
| --- | --- | --- | --- |
| 2026-07-01 | healthy | healthy | none |

## API Availability

Target from `docs/slo-guide.md`: 99.5%

| Date | Daily worst 1h | Daily mean 1h | Request volume | 5xx shape / notes |
| --- | ---: | ---: | ---: | --- |
| 2026-07-01 | 99.9% | 99.99% | 12000 | none |

Decision:

```text
met; keep target; alert or release-gate decision: defer paging until next review.
```

## API P95 Latency

Target from `docs/slo-guide.md`: 800 ms

| Date | 5m panel worst | 1h comparison worst | Daily mean | Endpoint mix notes |
| --- | ---: | ---: | ---: | --- |
| 2026-07-01 | 420 ms | 390 ms | 180 ms | normal |

Decision:

```text
met; keep target; alert or release-gate decision: defer paging until next review.
```

## Run Success Rate

Target from `docs/slo-guide.md`: 95%

| Date | Daily worst 1h | Daily mean 1h | Run volume | Status mix / notes |
| --- | ---: | ---: | ---: | --- |
| 2026-07-01 | 97% | 98% | 84 | normal |

Decision:

```text
met; keep target; alert or release-gate decision: defer paging until next review.
```

## Breaches

| Date/time | SLO | Observed value | Cause | Attribution | Action / follow-up |
| --- | --- | ---: | --- | --- | --- |
| N/A | N/A | N/A | No breaches | N/A | N/A |

## Attached Artifacts

| Artifact | Path | Source |
| --- | --- | --- |
| Grafana CSV | `docs/fixtures/slo-2026-07-01.csv` | dashboard export |

## Final Calibration Decision

- Alert enablement: deferred
- Release-blocking gate: deferred
- Rationale:

```text
Day-14 decision: keep targets and review on 2026-07-28.
```
""",
        encoding="utf-8",
    )

    android.write_text(
        """# Android Device Rehearsal Evidence

> Date: 2026-07-14
> Operator: QA
> ATP deployment: staging-prod
> Topology: shared host ADB server

## Device

| Field | Value |
| --- | --- |
| Model | Pixel 8 |
| Android version | 15 |
| Serial | `***1234` |
| Package under test | com.acme.app |

## Topology And Environment

| Field | Value |
| --- | --- |
| Worker container | atp-worker-1 |
| ADB mode | shared server |
| `ADB_SERVER_SOCKET` | tcp:host.docker.internal:5037 |
| `ADB_SKIP_SERVER_RESTART` | true |
| `ADB_SKIP_CONNECT` | true |
| Compose host-gateway mapping present | yes |

## Network Doctor

```bash
docker compose exec worker env ADB_SKIP_SERVER_RESTART=true ADB_SKIP_CONNECT=true scripts/android-network-doctor.sh
```

```text
all non-skipped steps passed; shared server reconnect skipped by design
```

- [x] Every non-skipped step passed.
- [x] Skipped steps are explained.

## Data Plane

```bash
adb -s ***1234 shell getprop
adb -s ***1234 shell dumpsys meminfo com.acme.app
```

```text
[ro.product.model]: [Pixel 8]
TOTAL PSS: 123456
```

## End-To-End Special Task

| Field | Value |
| --- | --- |
| Special task id | 71 |
| Run id | 7001 |
| Trigger type | manual |
| Duration | 4m12s |
| Final status | completed |

## Result Verification

| Metric type | Sample count | Notes |
| --- | ---: | --- |
| cpu | 42 | ok |
| memory | 42 | ok |

| Artifact | Name | Size | Download verified |
| --- | --- | ---: | --- |
| CSV report | run-7001.csv | 10 KB | yes |
| JSON report | run-7001.json | 12 KB | yes |

## Anomalies

| Time | Symptom | Retry / intervention | Outcome |
| --- | --- | --- | --- |
| N/A | None | None | N/A |

## Pass Criteria

- [x] Doctor reports success for every non-skipped step.
- [x] End-to-end run reached `completed`.
- [x] At least one metric sample was collected.
- [x] CSV and JSON exports both downloaded successfully.
""",
        encoding="utf-8",
    )

    acceptance.write_text(
        """# Q12 Acceptance Summary

> Date: 2026-07-14
> Status: accepted

## Scope

Q12 acceptance closes the external evidence carried through Q13/Q14.

## Evidence Links

| Evidence | Required path | Status |
| --- | --- | --- |
| SLO history | `docs/slo-history-2026-07-01-2026-07-14.md` | complete |
| Android rehearsal | `docs/android-device-rehearsal-2026-07-14.md` | complete |

## SLO Decision

| SLO | Target | Observed result | Decision |
| --- | --- | --- | --- |
| API availability | 99.5% | met | keep |
| API P95 latency | 800 ms | met | keep |
| Run success rate | 95% | met | keep |

Alert enablement:

```text
deferred until second stable window.
```

Release-blocking gate:

```text
deferred until second stable window.
```

## Android Rehearsal Decision

| Requirement | Result |
| --- | --- |
| Network doctor passed | yes |
| `getprop` data plane parseable | yes |
| `dumpsys meminfo` data plane parseable | yes |
| Special task run completed | yes |
| Metric samples collected | yes |
| CSV and JSON exports verified | yes |

## Follow-Ups

| Priority | Follow-up | Owner | Due |
| --- | --- | --- | --- |
| P2 | Re-run on second device model | QA | 2026-07-28 |

## Acceptance Statement

```text
Q12 external evidence is accepted with the documented follow-up.
```
""",
        encoding="utf-8",
    )
    return slo, android, acceptance


def test_validator_accepts_complete_external_evidence(repo_root, tmp_path):
    validator = _load_validator(repo_root)
    slo, android, acceptance = _write_valid_docs(tmp_path)

    assert validator.validate_all(slo, android, acceptance) == []
    assert validator.main(["--slo", str(slo), "--android", str(android), "--acceptance", str(acceptance)]) == 0


def test_validator_rejects_unfilled_templates(repo_root, tmp_path):
    validator = _load_validator(repo_root)
    slo, android, acceptance = _write_valid_docs(tmp_path)
    slo.write_text((repo_root / "docs/templates/slo-history-template.md").read_text(encoding="utf-8"), encoding="utf-8")

    errors = validator.validate_all(slo, android, acceptance)

    assert any("unfilled placeholder" in error for error in errors)
    assert any("unchecked checklist" in error for error in errors)


def test_validator_requires_acceptance_links(repo_root, tmp_path):
    validator = _load_validator(repo_root)
    slo, android, acceptance = _write_valid_docs(tmp_path)
    acceptance.write_text(
        acceptance.read_text(encoding="utf-8").replace("docs/slo-history-2026-07-01-2026-07-14.md", "docs/missing.md"),
        encoding="utf-8",
    )

    errors = validator.validate_all(slo, android, acceptance)

    assert any("docs/slo-history-2026-07-01-2026-07-14.md" in error for error in errors)


def test_scaffold_initializes_linked_evidence_drafts(repo_root, tmp_path):
    scaffold = _load_scaffold(repo_root)
    docs = tmp_path / "docs"
    templates = docs / "templates"
    templates.mkdir(parents=True)
    for template in (
        "slo-history-template.md",
        "android-device-rehearsal-template.md",
        "q12-acceptance-summary-template.md",
    ):
        (templates / template).write_text(
            (repo_root / "docs" / "templates" / template).read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    slo, android, acceptance = scaffold.scaffold_evidence(
        tmp_path,
        "2026-07-01",
        "2026-07-14",
        "2026-07-14",
    )

    assert slo == docs / "slo-history-2026-07-01-2026-07-14.md"
    assert android == docs / "android-device-rehearsal-2026-07-14.md"
    assert acceptance == docs / "q12-acceptance-summary.md"
    assert "> Window: 2026-07-01 to 2026-07-14" in slo.read_text(encoding="utf-8")
    assert "> Date: 2026-07-14" in android.read_text(encoding="utf-8")
    acceptance_content = acceptance.read_text(encoding="utf-8")
    assert "docs/slo-history-2026-07-01-2026-07-14.md" in acceptance_content
    assert "docs/android-device-rehearsal-2026-07-14.md" in acceptance_content


def test_scaffold_rejects_bad_dates_and_existing_files(repo_root, tmp_path):
    scaffold = _load_scaffold(repo_root)
    docs = tmp_path / "docs"
    templates = docs / "templates"
    templates.mkdir(parents=True)
    for template in (
        "slo-history-template.md",
        "android-device-rehearsal-template.md",
        "q12-acceptance-summary-template.md",
    ):
        (templates / template).write_text(
            (repo_root / "docs" / "templates" / template).read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    assert (
        scaffold.main(
            ["--repo-root", str(tmp_path), "--start", "bad", "--end", "2026-07-14", "--android-date", "2026-07-14"]
        )
        == 1
    )

    scaffold.scaffold_evidence(tmp_path, "2026-07-01", "2026-07-14", "2026-07-14")

    try:
        scaffold.scaffold_evidence(tmp_path, "2026-07-01", "2026-07-14", "2026-07-14")
    except FileExistsError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("expected scaffold to reject existing evidence drafts")

    slo, _, _ = scaffold.scaffold_evidence(
        tmp_path,
        "2026-07-01",
        "2026-07-14",
        "2026-07-14",
        force=True,
    )
    assert "> Window: 2026-07-01 to 2026-07-14" in slo.read_text(encoding="utf-8")
