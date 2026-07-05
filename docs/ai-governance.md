# AI Model and Prompt Governance

ATP uses project-level `ai_llm_config_id` to decide which model configuration a
project uses. The configuration is managed in System -> AI Model Config and is
stored in `ai_llm_configs`.

## Project-Level Model Selection

- `projects.ai_llm_config_id` binds a project to one AI provider/model.
- Disabled configs are rejected before generation or diagnosis.
- API keys remain encrypted and are never returned by list/detail APIs.

## `default_params` Governance Keys

`default_params` is the editable JSON surface for both provider parameters and
ATP governance controls.

Provider parameters passed to LLM APIs:

```json
{
  "temperature": 0.2,
  "max_tokens": 1200,
  "top_p": 0.9
}
```

ATP governance keys:

```json
{
  "prompt_templates": {
    "ai_case_generation": "You are a senior API test designer...",
    "failure_diagnosis": "You are a concise test failure diagnosis assistant..."
  },
  "daily_limits": {
    "ai_case_generation": 50,
    "failure_diagnosis": 100
  },
  "fallback_enabled": true
}
```

Rules:

- `prompt_templates.<capability>` overrides the system prompt for that
  capability. Supported capabilities currently include `ai_case_generation` and
  `failure_diagnosis`.
- `system_prompt` may be used as a coarse global override when no capability
  template is provided.
- `daily_limits.<capability>` limits actual LLM calls per config per UTC day.
  `0` or a missing value means unlimited.
- `fallback_enabled=false` disables friendly rule fallback text for capabilities
  that support deterministic fallback. Keep it enabled in production unless the
  caller explicitly wants to surface model failures.
- Reserved ATP governance keys are filtered out and are not sent to provider
  chat completion payloads.

## Error Degradation

- AI case generation has no reliable deterministic replacement for LLM output;
  quota or provider errors are surfaced to the caller.
- Failure diagnosis keeps a rule-based fallback summary and structured repair
  suggestions. If the model call fails and `fallback_enabled=true`, users still
  receive actionable diagnostic text.
- Existing AI healing keeps global safety gates such as
  `AI_HEALING_DAILY_LIMIT`, `AI_HEALING_VISION_DAILY_LIMIT`, cache TTL, and
  high-quality examples.

## Change Checklist

- Update `docs/ai-governance.md` when adding a new capability key.
- Keep `app.services.ai_governance.llm_extra_params` allowlist narrow.
- Never place secrets inside `default_params`; API keys belong in
  `api_key_encrypted`.
- Add a static or unit test when wiring a new AI call through governance helpers.
