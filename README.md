# notion-automations

All of Alex's native Notion automations, codified as code and deployed on
[Modal](https://modal.com): a daily cron dispatcher (recurring tasks,
Developer ID cert-renewal check, compliance reconciler) plus a Notion
webhook receiver (event-triggered rules). No Dockerfile, no Terraform - all
infrastructure lives in `app.py` as code.

## Layout

```
app.py                 Modal shim - image, secrets, endpoints, schedules
src/core/               business logic (plain Python, portable)
src/core/registry.py   the automations catalog (recurring specs + event rules)
src/core/notion.py     Notion API client - the only module that talks to Notion
src/core/asc.py        App Store Connect API client - cert-expiry checks
tests/                  pytest
.env.tpl                secrets manifest (1Password op:// refs, committed)
justfile                dev / test / sync-secrets / deploy
```

See `AGENTS.md` for the architecture rule and stack.

## Bootstrap (one-time, manual)

- `uv run modal token new` - authenticate this machine with Modal
- Alex creates the webhook subscription in the Notion integration dashboard
  and stores the verification token in the project's 1Password vault (the
  one click-ops step that can't be codified)

## Cutover checklist

This app runs live alongside the native Notion automations it replaces.
Turn a native automation off only after its codified replacement is observed
working correctly:

- [ ] Recurring tasks - all switched off together, after the first
      successful cron run
- [ ] Event rules - switched off DB-by-DB as each is verified via the webhook
