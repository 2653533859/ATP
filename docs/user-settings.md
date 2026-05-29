# User Settings

`user_settings` stores per-user preferences that should follow the user across devices.
It is intentionally key-scoped instead of one global blob, so each feature can migrate
from `localStorage` independently.

## API

- `GET /api/v1/users/me/settings`: list current user's settings.
- `GET /api/v1/users/me/settings/{key}`: read one setting.
- `PUT /api/v1/users/me/settings/{key}`: create or replace one setting.
- `DELETE /api/v1/users/me/settings/{key}`: delete one setting; missing keys are treated as success.

Request body for `PUT`:

```json
{
  "value": {
    "visible": ["passRate", "duration"],
    "order": ["passRate", "duration", "failure"]
  }
}
```

## Suggested Keys

- `language`: UI locale preference.
- `dashboard.layout`: visible chart keys and ordering. This is already used by the Dashboard page, with `localStorage` as a silent fallback.
- `default_project`: user's preferred project id.
- `case.table.columns`: case list column visibility and ordering.

## Constraints

- Key length: up to 128 characters.
- Value: JSON object only, up to 64KB serialized.
- Scope: current authenticated user only; admins do not read or overwrite other users' preferences through this API.
