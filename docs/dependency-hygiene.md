# Dependency Hygiene (Q13-06)

> Updated: 2026-07-10
> Scope: frontend `npm` dependency install-script approvals and audit posture.

## Install-Script Allowlist

`npm ci` warns about transitive packages with install/postinstall scripts that
have not been explicitly approved. Each was reviewed and recorded in
`frontend/package.json` under `allowScripts`:

| Package | Script | Purpose | Verdict |
|---------|--------|---------|---------|
| `fsevents` | (native binding) | macOS FSEvents native addon used by Vite/Playwright file watching; `os: ["darwin"]` only | Trusted — standard optional native dep, no-op off macOS |
| `core-js` | `postinstall` prints a funding notice, wrapped in `try/catch` | Pulled by `ant-design-vue > @simonwep/pickr` | Trusted — notice only, no filesystem/network side effects |
| `vue-demi` | `postinstall` selects the Vue 2 vs Vue 3 entry | Required by `pinia` to target the installed Vue major | Trusted — must run so Pinia binds to Vue 3 |

CI installs with `npm ci`, which does not execute lifecycle scripts, so these
approvals only affect local `npm install`. The allowlist keeps `npm ci` output
clean and forces any *new* script-bearing dependency to be reviewed before it is
added, rather than being silently accepted.

## Audit Posture

- `npm audit --audit-level=high`: 0 vulnerabilities.
- `npm ci`: 0 `npm warn deprecated` (vue-i18n on v11, glob overridden to v13 —
  see `docs/optimization-roadmap-2026-q12.md` Q12-03).

## Refresh Policy

- Re-run `npm ci` and `npm audit` each quarter; any new deprecation or
  script-approval warning is triaged before merge.
- New install-script dependencies are added to the `allowScripts` map only after
  reading the script and recording its purpose in the table above.
- Version overrides live in `package.json` `overrides` with a one-line rationale
  in the relevant roadmap/baseline doc.

## Verification

```bash
npm --prefix frontend ci    # expect: no allow-scripts, no deprecated warnings
npm --prefix frontend audit --audit-level=high    # expect: 0 vulnerabilities
```
