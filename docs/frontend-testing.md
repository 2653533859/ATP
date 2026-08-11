# Frontend Testing

> Last updated: 2026-07-10

## Test Stack

- Vitest
- jsdom
- Vue Test Utils
- V8 coverage
- Playwright remains the E2E runner under `frontend/e2e`.

## Commands

```bash
cd frontend
npm run test
npm run test:coverage
npm run type-check
npm run build
```

## Current Unit Coverage Slice

The first Vitest slices cover stable, low-coupling frontend logic:

- `src/stores/auth.spec.ts`: no JWT persistence, cookie-login user bootstrap, and logout on failed `me`.
- `src/api/http.spec.ts`: bearer token injection, 401 logout redirect, backend origin derivation.
- `src/components/common/BatchOperationBar.spec.ts`: selected-count rendering, slot rendering, cancel emission.
- `src/stores/theme.spec.ts`: theme persistence, DOM attribute application, system dark preference, and toggling.
- `src/utils/chartTheme.spec.ts`: ECharts theme registration idempotency and global-theme-driven chart theme names.
- `src/utils/permissions.spec.ts`: role normalization and permission helpers.
- `src/utils/websocket.spec.ts`: cookie-based WebSocket URL, JSON message dispatch, reconnect suppression on manual close.

Current result:

```text
14 files / 47 tests passed
```

Current full-source coverage:

```text
Statements 4.38% | Branches 4.81% | Functions 2.96% | Lines 4.61%
```

The current regression gate is statements `4.1%`, branches `4.55%`, functions `2.7%`, and lines `4.35%`. It remains below the measured baseline and should rise only after another behavioral slice adds measured headroom; the authoritative record is `docs/coverage-baseline-2026-q12.md`.

## CI

The main CI frontend job now runs:

```bash
npm ci
npm run test:coverage
npm run type-check
npm run build
```

CI uploads `frontend/coverage` as `frontend-coverage-report` for line-level inspection.
