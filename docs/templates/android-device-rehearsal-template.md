# Android Device Rehearsal Evidence

> Date: YYYY-MM-DD
> Operator: <name / team>
> ATP deployment: <environment>
> Topology: direct device TCP / shared host ADB server

## Device

| Field | Value |
| --- | --- |
| Model |  |
| Android version |  |
| Serial | `<masked-to-last-4>` |
| Package under test |  |

## Topology And Environment

| Field | Value |
| --- | --- |
| Worker container |  |
| ADB mode | direct TCP / shared server |
| `ADB_SERVER_SOCKET` |  |
| `ADB_SKIP_SERVER_RESTART` | true/false |
| `ADB_SKIP_CONNECT` | true/false |
| Compose host-gateway mapping present | yes/no |

## Network Doctor

Command:

```bash
<docker compose exec worker env ... scripts/android-network-doctor.sh ...>
```

Full output:

```text
<paste full output; every skipped step must include reason>
```

Result:

- [ ] Every non-skipped step passed.
- [ ] Skipped steps are explained.

## Data Plane

`getprop` sample:

```bash
adb -s <serial> shell getprop
```

Result:

```text
<paste representative parseable output or artifact path>
```

`dumpsys meminfo` sample:

```bash
adb -s <serial> shell dumpsys meminfo <package>
```

Result:

```text
<paste representative parseable output or artifact path>
```

## End-To-End Special Task

| Field | Value |
| --- | --- |
| Special task id |  |
| Run id |  |
| Trigger type | manual / schedule / API |
| Duration |  |
| Final status | completed / failed |

## Result Verification

| Metric type | Sample count | Notes |
| --- | ---: | --- |
| cpu |  |  |
| memory |  |  |
| fps / fluency |  |  |
| stability |  |  |

| Artifact | Name | Size | Download verified |
| --- | --- | ---: | --- |
| CSV report |  |  | yes/no |
| JSON report |  |  | yes/no |
| Screenshot/log |  |  | yes/no |

Incident table:

```text
<readable; may be empty>
```

## Anomalies

| Time | Symptom | Retry / intervention | Outcome |
| --- | --- | --- | --- |
| N/A | None | None | N/A |

## Pass Criteria

- [ ] Doctor reports success for every non-skipped step.
- [ ] End-to-end run reached `completed`.
- [ ] At least one metric sample was collected.
- [ ] CSV and JSON exports both downloaded successfully.
