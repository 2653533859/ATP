# Frontend Testing

> Last updated: 2026-07-08

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

- `src/stores/auth.spec.ts`: token bootstrap, login persistence, logout on failed `me`.
- `src/api/http.spec.ts`: bearer token injection, 401 logout redirect, backend origin derivation.
- `src/components/common/BatchOperationBar.spec.ts`: selected-count rendering, slot rendering, cancel emission.
- `src/stores/theme.spec.ts`: theme persistence, DOM attribute application, system dark preference, and toggling.
- `src/utils/chartTheme.spec.ts`: ECharts theme registration idempotency and global-theme-driven chart theme names.
- `src/utils/permissions.spec.ts`: role normalization and permission helpers.
- `src/utils/websocket.spec.ts`: tokenized WebSocket URL, JSON message dispatch, reconnect suppression on manual close.

Current result:

```text
18 passed
```

Current full-source coverage visibility:

```text
1.8%
```

No frontend coverage threshold is enforced yet. The next slices should expand reusable component and route-level logic coverage before setting a minimum threshold.

## CI

The main CI frontend job now runs:

```bash
npm ci
npm run test
npm run type-check
npm run build
```
