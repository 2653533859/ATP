# Frontend Bundle Decision

> Updated: 2026-07-10
> Scope: Q11-41 Ant Design/icon chunk relationship and ECharts bundle size.

## Decision

1. Keep `ant-design-vue` and `@ant-design/icons-vue` as separate manual chunks.
2. Keep the current `1500 kB` warning threshold; do not raise it to hide growth.
3. Replace full ECharts namespace imports in mobile-special reports with `echarts/core` and explicit chart/component/renderer registration.
4. Accept the current Ant Design chunk temporarily because ATP uses a broad component surface and the build is warning-free; revisit global `app.use(Antd)` when the chunk exceeds the threshold or field performance evidence shows a loading problem.

## Evidence

Baseline build before Q11-41:

```text
echarts: 1126.62 kB, 374.44 kB gzip
ant-design-icons: 41.97 kB, 9.32 kB gzip
ant-design: 1498.98 kB, 464.47 kB gzip
```

The historical `ant-design-icons -> ant-design -> ant-design-icons` circular chunk warning was recorded under the previous Vite toolchain. Vite `8.1.3` no longer emits it with the current split.

An explicit merge experiment placed icons and Ant Design in one chunk:

```text
ant-design merged: 1541.24 kB, 474.26 kB gzip
result: rejected; exceeded the 1500 kB threshold and emitted a large-chunk warning
```

Selected build after modular ECharts imports:

```text
echarts: 563.41 kB, 191.53 kB gzip
ant-design-icons: 41.97 kB, 9.32 kB gzip
ant-design: 1498.98 kB, 464.47 kB gzip
result: build passed with no circular or large-chunk warning
```

The ECharts change reduces the minified chunk by about 50% and gzip transfer size by about 49% while retaining Bar/Line charts, grid, legend, tooltip, canvas rendering, and registered ATP chart themes.

## Import Contract

- `frontend/src/utils/chartTheme.ts` is the single registration point: it calls `use([...])` from `echarts/core` with the app-wide union of renderers, charts, and components (canvas, line/bar/pie, grid, legend, title, tooltip), alongside the ATP theme registration.
- Views import `useChartTheme` (they already do for theming), which guarantees registration; views must not call `use([...])` themselves.
- Do not add `import * as echarts from 'echarts'` or runtime imports from the full ECharts entrypoint.
- Both rules are enforced by `backend/tests/frontend/test_frontend_bundle_decision.py`.

## Ant Design Follow-Up Trigger

The current Ant Design chunk is close to the configured limit. Start a dedicated component auto-import/tree-shaking change when any of these occurs:

- The chunk exceeds `1500 kB` after minification.
- A build emits the circular or large-chunk warning again.
- Production/staging performance shows the Ant Design chunk materially affects first route load, LCP, or cache invalidation.
- A route family can be isolated without duplicating shared Ant Design modules across lazy chunks.

The preferred future direction is automatic on-demand component resolution or a tested explicit registration layer. Do not manually split internal Ant Design modules by path; that is more likely to create unstable cross-chunk cycles.

## Verification

```bash
npm --prefix frontend run test
npm --prefix frontend run type-check
npm --prefix frontend run build
npm --prefix frontend run e2e
```

Review the emitted `echarts`, `ant-design-icons`, and `ant-design` sizes and retain the build output in release evidence when the dependency or chunk configuration changes.
