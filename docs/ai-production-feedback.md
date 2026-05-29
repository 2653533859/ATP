# AI Production Feedback

> Status: Q9 Phase 2 thin slice.

Q9 starts the AI production feedback loop by extending the existing AI healing stats payload. The goal is to make human adoption and regression outcomes visible before using them to tune prompt examples or automatic thresholds.

## Current Metrics

`GET /api/v1/ai-healing/stats?days=30` now includes:

```json
{
  "production_feedback": {
    "regression_triggered_count": 12,
    "regression_success_count": 9,
    "regression_success_rate": 75.0,
    "latest_feedback_aggregated_at": "2026-05-29T04:17:00+00:00"
  }
}
```

Definitions:

- `regression_triggered_count`: `TestRun` rows in the requested window whose `result_summary.triggered_by_ai_healing_patch` flag is true.
- `regression_success_count`: AI healing regression runs whose status is `passed` or `success`.
- `regression_success_rate`: percentage success rate for AI healing regression runs.
- `latest_feedback_aggregated_at`: latest `HealingFeedbackAggregate.last_aggregated_at` timestamp, used as a freshness signal for scheduled aggregation.

## Prompt Example Weighting

AI healing few-shot examples still require an explicit high-quality mark before they can enter prompts. When multiple matching examples exist, selection now applies a quality weight from `HealingFeedbackAggregate`: higher adoption rate and a stronger feedback sample size rank first, with recency used as a tie-breaker.

## Next Steps

- Add AI case generation funnel persistence: generated drafts, saved drafts, failed generations, warning count, and save rate. Done as an audit-log backed thin slice via `GET /api/v1/ai/cases/funnel-stats`.
- Surface AI production feedback in `AIHealingStatsView`. Done with regression count, success count, success rate, aggregate freshness, and AI case generation funnel cards.
- Add rollback tracking once AI patch rollback has a dedicated action marker.
