# Deployment and Disaster-Recovery Readiness Record

> Date: 2026-08-06
> Scope: repository-local deployment configuration and recovery runbook checks
> Status: local prerequisites passed; live cluster and backup-drill evidence remain open

## Local Verification

Run from the repository root:

```bash
make validate-deployment-readiness
```

The check validates the chart values/schema, Compose YAML, Grafana JSON,
backup/restore shell syntax, deployment and disaster-recovery checklist
contracts, and—when installed—`docker-compose config` and `helm lint`.
Use `python3 scripts/validate-deployment-readiness.py --require-helm` on the
release operator workstation so a missing Helm binary is a failure rather than
a skip.

The chart now supports the configuration required by the production checklist:

- `secret.create=false` plus `secret.existingName` binds an ExternalSecrets,
  SOPS, or platform-managed Secret without rendering placeholder credentials.
- `metrics.serviceMonitor.enabled=true` renders a Prometheus Operator
  `ServiceMonitor` for backend `/metrics`.
- `ingress.tls.enabled=true` automatically adds the Nginx HTTPS redirect.
- Beat remains one replica with `Recreate`; the migration Job remains a
  pre-install/pre-upgrade hook; component resource requests and limits remain
  explicit.

## External Evidence Still Required

The following cannot be proven from this checkout and remain unchecked in the
production checklist and DR drill checklist:

- a current PostgreSQL/Redis/MinIO backup and a successful restore;
- a non-primary MinIO object backup and an object restore;
- a staging or production Helm render/apply with ExternalSecret, TLS,
  ServiceMonitor, Grafana, and real resource values;
- a post-restore migration, health check, login/report smoke test, and restored
  object fetch recorded in `docs/backup-restore-drill-record.md`.

No production evidence is marked complete without the corresponding cluster
output, object identifiers, timings, and operator record.
