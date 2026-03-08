# Dashboard Stats Design

**Date:** 2026-03-08
**Scope:** Fix dashboard overview range consistency and stale-state rendering on stats request failures.

## Goal

Make the dashboard avoid contradictory data when users change the global day-range selector or when one of the statistics requests fails.

## Current Problems

- The dashboard passes `days` to trend and failure-top APIs, but drops it for overview data.
- The overview cards can therefore show run totals and pass rate from a different time scope than the charts.
- Each stats loader swallows request failures and leaves the previous successful state rendered on screen.

## Chosen Design

- Keep `total_cases` as all-time project scope data.
- Apply the selected `days` range to overview `total_runs` and `pass_rate` by extending `/statistics/overview` to accept a `days` query param.
- Keep `recent_runs_7d` explicitly fixed to the last 7 days so the fourth card remains a distinct operational signal instead of duplicating `total_runs`.
- On any stats request failure, reset only the affected dashboard section to an empty/default state so stale data is not shown for the newly selected filters.

## Non-Goals

- No dashboard UI redesign.
- No request-cancellation or race-resolution changes in this patch.
- No new frontend testing framework.

## Testing Strategy

- Add a focused backend regression test proving `/statistics/overview` uses the selected `days` value for overview run metrics while still keeping the 7-day card fixed.
- Validate the frontend change with targeted type-check/build-oriented verification because the repo does not currently include a frontend unit-test harness.
