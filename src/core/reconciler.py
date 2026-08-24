"""Daily compliance sweep: flag violations as remediation tasks; never fix
directly (a human backfills the true event timestamps - the reconciler runs
after the fact and can't know when things actually happened).

State (`since`) is persisted by the caller (app.py, via a modal.Dict) -
this module stays pure of Modal.
"""

from core.notion import task_properties
from core.registry import CALENDAR, TASKS, TRIPS
from core.rules import Violation, evaluate, title_of


def reconcile(notion, dbs, since_iso, now):
    """Returns (log lines, new high-water mark). The mark is None when any
    database could not be swept - the caller must then leave the window open
    and fail the run, so the gap is retried and surfaced rather than skipped.
    One unreachable DB (typically not connected to the integration: Notion
    answers 404, not 403, for anything it can't see) must not cost us the
    sweep of every other DB.
    """
    logs, seen, failed = [], set(), False
    for ds in sorted(dbs):
        try:
            pages = notion.query(
                ds,
                filter={
                    "timestamp": "last_edited_time",
                    "last_edited_time": {"on_or_after": since_iso},
                },
            )
        except Exception as exc:
            failed = True
            logs.append(f"SWEEP FAILED for data source {ds}: {exc}")
            continue
        for page in pages:
            if page["id"] in seen:
                continue
            violations = evaluate(ds, page, now)
            if ds == CALENDAR and not (page["properties"].get("Notes") or {}).get("relation"):
                # webhook-only rule (see handlers.py) re-flagged here since a
                # missed/failed webhook delivery would otherwise go unnoticed
                violations = [
                    *violations,
                    Violation(
                        "calendar-companion-note",
                        page["id"],
                        title_of(page["properties"]),
                        page.get("url", ""),
                        None,
                    ),
                ]
            if ds == TRIPS:
                # same invariant as handlers.py's live sync, re-checked here in
                # case that webhook delivery was missed/failed - never fixed
                # directly (a human decides the intended title), just flagged
                trip_title = title_of(page["properties"])
                desired = f"{trip_title} Notes"
                for rel in (page["properties"].get("Notes") or {}).get("relation", []):
                    note = notion.get_page(rel["id"])
                    if title_of(note["properties"]) != desired:
                        violations = [
                            *violations,
                            Violation(
                                "trips-note-title",
                                page["id"],
                                trip_title,
                                page.get("url", ""),
                                None,
                            ),
                        ]
            if not violations:
                continue
            seen.add(page["id"])
            rules = ", ".join(v.rule for v in violations)
            v0 = violations[0]
            notion.create_page(
                TASKS,
                task_properties(
                    f"Fix Notion data ({rules}) on '{v0.page_title}'",
                    now.date(),
                    ("Chore",),
                    "High",
                    links=v0.page_url,
                ),
            )
            logs.append(f"flagged {v0.page_title}: {rules}")
    return logs, (None if failed else now.isoformat())
