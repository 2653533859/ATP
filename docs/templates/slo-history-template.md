# SLO History Evidence

> Window: YYYY-MM-DD to YYYY-MM-DD
> Record type: day-7 initial calibration / day-14 stable calibration
> Source deployment: <production-or-production-like-env>
> Prometheus: <instance / URL / scrape identity>
> Grafana dashboard: `atp-overview`

## Preconditions

- [ ] Prometheus continuously scraped `atp-backend` for the full window.
- [ ] Worker metrics were scraped on `WORKER_METRICS_PORT` for the full window.
- [ ] Grafana `atp-overview` loaded against the same Prometheus source.
- [ ] Traffic profile is documented as real usage or synthetic profile.

Traffic profile:

```text
<describe request volume, endpoint mix, scheduled runs, synthetic load profile, and known gaps>
```

## Scrape Health

| Date | Backend scrape healthy | Worker scrape healthy | Gaps / notes |
| --- | --- | --- | --- |
| YYYY-MM-DD | yes/no | yes/no |  |

## API Availability

Target from `docs/slo-guide.md`: <target>

| Date | Daily worst 1h | Daily mean 1h | Request volume | 5xx shape / notes |
| --- | ---: | ---: | ---: | --- |
| YYYY-MM-DD |  |  |  |  |

Decision:

```text
<met / missed; keep / tighten / loosen target; alert or release-gate decision>
```

## API P95 Latency

Target from `docs/slo-guide.md`: <target>

| Date | 5m panel worst | 1h comparison worst | Daily mean | Endpoint mix notes |
| --- | ---: | ---: | ---: | --- |
| YYYY-MM-DD |  |  |  |  |

Decision:

```text
<met / missed; keep / tighten / loosen target; alert or release-gate decision>
```

## Run Success Rate

Target from `docs/slo-guide.md`: <target>

| Date | Daily worst 1h | Daily mean 1h | Run volume | Status mix / notes |
| --- | ---: | ---: | ---: | --- |
| YYYY-MM-DD |  |  |  |  |

Decision:

```text
<met / missed; keep / tighten / loosen target; alert or release-gate decision>
```

## Breaches

| Date/time | SLO | Observed value | Cause | Attribution | Action / follow-up |
| --- | --- | ---: | --- | --- | --- |
| N/A | N/A | N/A | No breaches | N/A | N/A |

## Attached Artifacts

| Artifact | Path | Source |
| --- | --- | --- |
| Grafana snapshot / CSV | `docs/fixtures/<file>` | <panel/export> |

## Final Calibration Decision

- Alert enablement: <enabled / deferred>
- Release-blocking gate: <enabled / deferred>
- Rationale:

```text
<explicit day-7 or day-14 decision and next review date>
```
