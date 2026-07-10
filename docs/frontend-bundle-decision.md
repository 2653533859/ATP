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

## Trigger Status (2026-07-10) — RESOLVED by Q12-04

The threshold trigger FIRED after the Q12-03 upgrade (ant-design chunk `1502.45 kB` >
`1500 kB`; the i18n runtime was verified isolated in its own chunk, so the growth was
bundler module-graph reassignment). Q12-04 responded with the preferred direction from
this document — automatic on-demand component resolution:

- `unplugin-vue-components` + `AntDesignVueResolver({ importStyle: false })` replaces the
  global `app.use(Antd)` registration (antd v4 cssinjs needs no per-component styles;
  `reset.css` stays global). `dts` generation is disabled for now: enabling typed global
  components exposes ~112 pre-existing `a-*` prop type mismatches that vue-tsc previously
  ignored; typing hardening is a separate roadmap item.
- `main.ts` no longer imports `@/utils/chartTheme` synchronously — the full echarts module
  set it references had made the echarts chunk an entry dependency; registration now runs
  when a chart view first imports `useChartTheme`.

Measured route-level evidence (vite preview, Chrome, gzip transfer for `/login`):

```text
before: 773.9 kB total (ant-design 448.6, echarts 185.6, LoginView itself 1.4)
after removing entry echarts: 583.5 kB (echarts no longer loads on /login)
after on-demand antd:         510.1 kB total (-34% vs baseline)
ant-design chunk: 1502.45 kB / 464.51 gzip -> 1246.41 kB / 387.71 gzip (-17%)
build: no large-chunk warning; threshold stays 1500 kB
```

Functional verification: Vitest `46 passed` (specs mock ant-design-vue directly), vue-tsc
clean, full Playwright E2E `9 passed` including the shared unexpected-pageerror guard —
no missing component registrations.

## Route-Level Split Decision (2026-07-10) — Q13-04

The follow-up trigger's fourth condition ("a route family can be isolated
without duplicating shared Ant Design modules across lazy chunks") was
evaluated with a measured go/no-go experiment.

**Problem confirmed:** with on-demand registration but a `manualChunks(id) =>
'ant-design'` rule, every `ant-design-vue` module was still forced into one
1246 kB chunk. The `/login` route — which uses only form/input/button — pulled
that whole monolith: 374.7 kB gzip of a 510.1 kB first-paint JS transfer (73%).

**Experiment:** drop the `ant-design` manual chunk so Rolldown splits the
tree-shaken components into each lazy route chunk. Measured on `/login` (vite
preview, Chrome, gzip transfer):

```text
before: 510.1 kB, loads the ant-design monolith
after:  335.8 kB (-34%, -174 kB); no monolith — only form/input/collapseMotion/Col etc.
cost:   total dist JS +~35 kB (2771 -> 2806) as antd's shared runtime duplicates
        into a few route chunks; chunk count 45 -> 80; no large-chunk warning
```

**result: adopted (go).** The 174 kB first-paint saving is far above the 15%
route-transfer threshold the roadmap set for acting, and the +35 kB total is
spread across lazy route chunks that only load on navigation. The
`chunkSizeWarningLimit` is tightened 1500 -> 600 kB (echarts ~563 kB is now the
ceiling) so any re-monolithization surfaces immediately.

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
