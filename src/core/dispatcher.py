"""Daily dispatcher: evaluate recurring specs, create what's due."""

from dataclasses import replace
from datetime import timedelta

from core.notion import task_properties
from core.planner import next_occurrence
from core.registry import CHRISTMAS_RECIPIENTS, GIFTS, RECURRING, TASKS, TaskTemplate
from core.rules import title_of


def _hydrate_recipients(spec, notion):
    """Build the Christmas templates from live Notion data.

    People's names are personal data and are not stored in this repo - the
    registry holds page ids, so the names come from Notion at run time. Returns
    the spec with templates/match_titles filled in, plus each recipient's full
    name for the Gifts page title.
    """
    templates, full_names = [], {}
    for person_id in CHRISTMAS_RECIPIENTS:
        full = title_of(notion.get_page(person_id)["properties"])
        full_names[person_id] = full
        name = full.split()[0]
        templates.append(
            TaskTemplate(
                title=f"Brainstorm and come up with an idea for {name}'s Christmas Gift",
                tags=("Gifts",),
                priority="High",
            )
        )
        templates.append(
            TaskTemplate(
                title=f"Buy {name}'s Christmas Gift",
                tags=("Gifts",),
                priority="High",
                due_offset_days=30,
                blocked_by_prev=True,
            )
        )
    hydrated = replace(
        spec,
        templates=tuple(templates),
        match_titles=tuple(t.title for t in templates),
    )
    return hydrated, full_names


def dispatch(notion, today):
    log = []
    for spec in RECURRING:
        full_names = {}
        if spec.gift_recipients:
            spec, full_names = _hydrate_recipients(spec, notion)
        existing = notion.snapshots(TASKS, spec.match_titles)
        occ = next_occurrence(spec, existing, today)
        if not occ:
            log.append(f"{spec.key}: nothing to do")
            continue
        prev_id = ""
        for t in spec.templates:
            due = occ.due + timedelta(days=t.due_offset_days)
            if any(s.title == t.title and s.due == due for s in existing):
                # partial-batch recovery: this template was already created by
                # a prior (crashed/partial) run - don't duplicate it. We can't
                # recover its page id from a TaskSnapshot (no id field), so a
                # still-missing blocked_by_prev task loses its Blocked-by link
                # in this edge case; add id-fetching here if that proves needed.
                prev_id = ""
                log.append(f"{spec.key}: '{t.title}' already exists due {due}, skipping")
                continue
            props = task_properties(
                t.title,
                due,
                t.tags,
                t.priority,
                links=t.links,
                notes=t.notes,
                blocked_by=prev_id if t.blocked_by_prev else "",
            )
            prev_id = notion.create_page(TASKS, props)["id"]
            log.append(f"{spec.key}: created '{t.title}' due {due}")
        for person_id in spec.gift_recipients:
            name = full_names[person_id]
            notion.create_page(
                GIFTS,
                {
                    "Description": {
                        "title": [{"text": {"content": f"{name}'s Christmas Gift {occ.due.year}"}}]
                    },
                    "Recipient(s)": {"relation": [{"id": person_id}]},
                    "Status": {"status": {"name": "Not Started"}},
                    "Occasion": {"select": {"name": "Christmas"}},
                    "Gift Date": {"date": {"start": f"{occ.due.year}-12-25"}},
                },
            )
            log.append(f"{spec.key}: created Gifts page for {person_id}")
    return log
