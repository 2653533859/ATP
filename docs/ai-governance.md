# AI Model and Prompt Governance

ATP uses project-level `ai_llm_config_id` to decide which model configuration a
project uses. The configuration is managed in System -> AI Model Config and is
stored in `ai_llm_configs`.

## Project-Level Model Selection

- `projects.ai_llm_config_id` binds a project to one AI provider/model.
- Disabled configs are rejected before generation or diagnosis.
- API keys remain encrypted and are never returned by list/detail APIs.

## Model Discovery and Capability Flags

The System -> AI Model Config form provides **Fetch models**. It uses the
configured endpoint and API key to read the provider's model catalog, then
filters obvious embedding, reranking, moderation, speech, and text-to-speech
models before showing the remaining choices. OpenAI-compatible providers use
`/v1/models`; Ollama prefers its native `/api/tags` endpoint.

The returned list is a provider catalog, not a full chat health check. Keep the
model name editable so a provider-specific alias can still be entered manually.

The same form provides **Test connection**. It sends a fixed, bounded text
request and returns only the provider, selected model, latency, and a generic
success message; provider output, API keys, and raw error bodies are not
returned. Existing configurations reuse their encrypted key, while a new
Ollama configuration may omit the key. The request uses a 15-second timeout and
four-token limit, preserves only explicitly allowed provider parameters such as
`thinking`/`reasoning_effort`, and records a safe audit summary on success.

The form also offers thinking-mode shortcuts for `thinking=true`,
`enable_thinking=true`, and `reasoning_effort=low|medium|high`. The default is
off. The shortcut only edits the same `default_params` JSON field and does not
override manually entered parameters until the user selects a mode. Capability
labels are hints from model discovery or model-name matching, not proof that a
provider accepts a parameter; always verify with **Test connection** and the
provider documentation.

For a direct Ollama server, use its native `http://host:11434` endpoint and
leave API Key empty. For Open WebUI, select the OpenAI-compatible provider,
use `http://host:3000/v1`, and provide an Open WebUI API token from Settings ->
Account; the host login password is not an API token. The client accepts either
a Base URL with or without the `/v1` suffix and avoids duplicating the prefix.
All AI generation, diagnosis, and healing paths preserve this keyless Ollama
behavior; an empty key remains invalid for non-Ollama providers.

`supports_vision` should be enabled only when the selected model accepts image
input and the workflow actually sends images or screenshots. For AI healing,
the global `AI_HEALING_VISION_ENABLED` flag must also be enabled; the separate
vision daily limit remains in force.

Thinking/reasoning is not a universal switch. Leave it disabled by default and
only add the provider-documented parameter in `default_params`, for example:

```json
{
  "reasoning_effort": "medium"
}
```

Depending on the provider, the documented key may instead be `thinking` or
`enable_thinking`. If the selected model does not support the key, remove it;
multimodal support and reasoning support are independent capabilities.

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

## AI Case Generation Context

The AI case generation drawer can optionally include one project test dataset
and multiple project Mock rules:

- Dataset context includes the schema and up to five sample rows. The selected
  dataset is automatically bound to saved drafts, and the prompt asks the model
  to use matching `{{field}}` placeholders. When a version exists, the newest
  version selected for generation is saved on the case as `dataset_version` and
  is used by the Worker for deterministic parameterized execution.
- Mock context includes method, path, status code, response headers/body,
  match conditions and up to three recorded samples. The model can use these
  to create request steps and response assertions; at most 20 Mock rules can be
  selected in one generation request.
- Context is project-scoped and selected explicitly by the user. Passwords,
  tokens, cookies, authorization values and other secret-looking fields are
  replaced with `[已脱敏]` before the LLM request.
- Context is advisory: drafts remain editable and must be reviewed before
  saving or executing. AI does not create or modify Mock rules automatically.
- Saved AI cases keep `_ai_source` in their config with the selected dataset ID,
  dataset version, and Mock rule IDs. This is provenance metadata only; AI does
  not mutate the source dataset or Mock rules.

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
