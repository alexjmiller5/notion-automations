# notion-automations

All of Alex's native Notion automations, codified as code and deployed on
[Modal](https://modal.com): a daily cron dispatcher (recurring tasks,
compliance reconciler) plus a Notion webhook receiver (event-triggered
rules). No Dockerfile, no Terraform - all infrastructure lives in `app.py`
as code.

## Layout

```
app.py                 Modal shim - image, secrets, endpoints, schedule
src/core/               business logic (plain Python, portable)
src/core/registry.py   Notion ids + spec model/loaders (spec DATA lives in life-data)
src/core/notion.py     Notion API client
src/core/hub.py        life-data hub client - pulls the spec tables at run time
scripts/run_local.py   dry-run the dispatch logic with no Modal at all
tests/                  pytest
.env.tpl                secrets manifest (1Password op:// refs, committed)
justfile                dev / test / run / sync-secrets / deploy
```

See `AGENTS.md` for the architecture rule and stack.

## Bootstrap (one-time, manual)

1. `op-project-bootstrap .env.tpl --repo alexjmiller5/notion-automations` -
   creates the `Notion Automations` vault, the `Notion Automations ENV` item
   (one field per `.env.tpl` line - `NOTION_API_TOKEN` prompted,
   `NOTION_WEBHOOK_SECRET` left `CHANGEME` until the webhook step below fills
   it in), AND the `Modal Notion Automations` deploy-token item (bootstrap
   scans `.github/workflows/*.yml` for `op://` refs and mints its fields via
   `scripts/provision.py`, which copies the canonical workspace token from
   the AI Agent vault - no prompt, nothing touches disk), plus the read-only
   `notion-automations-ci` service account and the repo's
   `OP_SERVICE_ACCOUNT_TOKEN` GitHub secret.
   (Local `just dev` / `just run` need no `~/.modal.toml` either - the
   machine-wide `modal` wrapper injects the same 1P-held token.)
2. Create the webhook subscription (Notion has no API for this - integration
   settings only):
   - Deploy first (push to `main`) so `notion_webhook`'s URL exists.
   - **Re-subscribing later** (new endpoint URL, new integration): clear
     `NOTION_WEBHOOK_SECRET` first and redeploy. Notion posts the handshake
     token unsigned, so the endpoint only accepts a handshake while no
     secret is set - otherwise anyone could spray fake tokens into the logs
     and have one adopted as the signing secret. A 401 on the handshake
     means the old secret is still configured.
   - `notion.so/profile/integrations` -> the integration -> **Webhooks**
     tab -> paste the deployed endpoint URL -> subscribe to
     `page.created` and `page.properties_updated`.
   - Notion POSTs a one-time verification payload to the endpoint; it's
     logged (`just logs`) and also shown directly in the integration UI -
     copy the token either place.
   - `op item edit "Notion Automations ENV" --vault "Notion Automations" "NOTION_WEBHOOK_SECRET=<token>"`
   - `just sync-secrets` to push it to the deployed Modal secret, then
     make a small test edit on any watched DB and confirm `just logs`
     shows the event handled (not a 401).

## Local runs

- `just run-local` - dry run: same dispatch logic with zero Modal involvement,
  `DRY_RUN=true` forced so nothing writes to Notion (`scripts/run_local.py`).
- `just run` - **not a dry run** - triggers `daily()` once against real Modal
  infra (ephemeral container, not the deployed schedule) and performs real
  writes to Notion.

## Cutover checklist

This app runs live alongside the native Notion automations it replaces.
Full inventory (43 automations, one row each) is the Notion page
[Notion Tasks DB Automations - Full Inventory (2026-08-19)](https://www.notion.so/3c203953-a8af-818b-998f-f5a152078c8a) -
this checklist just groups them by DB as the shutdown order. Turn an
automation off only after its codified replacement has been observed
working correctly (a cron run for schedule-triggered ones, a live webhook
delivery for event-triggered ones):

**Tasks DB - schedule-triggered** (the life-data `recurring_specs` table, all fire from
the one `daily()` cron - switch off together after the first clean run):
- [ ] Recertify Touchless ID
- [ ] Redeem Credit Card Rewards
- [ ] Wipe Down Screens
- [ ] Christmas Gifts
- [ ] Update 1Password Backup
- [ ] Biyearly Dentist Appointments
- [ ] Yearly Doctor Appointments
- [ ] Yearly Investment Review
- [ ] Reselect U.S. Bank CC Cashback Categories
- [ ] Use Unused LSA money
- [ ] Update Hotkeys Database (already inactive - delete, don't just disable)
- [ ] Gov Ball
- [ ] Review Synapse Logs
- [ ] Snoozing Instagram Suggestions
- [ ] Career Socials/Resume Checkup
- [ ] Get Flu and Covid Vaccines
- [ ] 1Password Backup
- [ ] Change Toothbursh Head
- [ ] Organizing Contacts

**Tasks DB - event-triggered** (webhook, verify each fires correctly on a
real edit before disabling):
- [ ] Set Default Task Properties
- [ ] Track Tag & Date History (delete - feature retired 2026-08-20, property already removed from the DB)
- [ ] Add Completed Date
- [ ] Remove Completed Date

**Trips**:
- [ ] Alex Miller's automation

**Calendar**:
- [ ] Create Calendar Item Notes

**Projects**:
- [ ] Set Completed Date

**Synapse Executions**:
- [ ] Auto Approve Bookmark Executions
- [ ] Set Date Remedied
- [ ] Clear Date Remedied
- [ ] Set Date Reviewed
- [ ] Clear Date Reviewed

**Books**:
- [ ] Add Date Read
- [ ] Clear Date Read

**YouTube Videos**:
- [ ] Add Date Watched
- [ ] Remove Date Watched

**TV Shows**:
- [ ] Add Date Watched
- [ ] Remove Date Watched

**Movies**:
- [ ] Add Date Watched
- [ ] Remove Date Watched

**Articles**:
- [ ] Add Read Date
- [ ] Remove Read Date

**Podcast Episodes**:
- [ ] Add Date Listened To
- [ ] Remove Date Listened To
