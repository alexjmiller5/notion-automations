"""Daily dispatcher: evaluate recurring specs, create what's due."""

from datetime import timedelta

from core.notion import task_properties
from core.planner import OPEN_STATUSES, next_occurrence
from core.registry import CERT_TASK_PREFIX, GIFTS, PEOPLE_IDS, RECURRING, TASKS

CERT_LEAD_DAYS = 30
_PERSON_NAMES = {person_id: name for name, person_id in PEOPLE_IDS.items()}


def dispatch(notion, today):
    log = []
    for spec in RECURRING:
        occ = next_occurrence(spec, notion.snapshots(TASKS, spec.match_titles), today)
        if not occ:
            log.append(f"{spec.key}: nothing to do")
            continue
        prev_id = ""
        for t in spec.templates:
            props = task_properties(
                t.title,
                occ.due + timedelta(days=t.due_offset_days),
                t.tags,
                t.priority,
                links=t.links,
                notes=t.notes,
                blocked_by=prev_id if t.blocked_by_prev else "",
            )
            prev_id = notion.create_page(TASKS, props)["id"]
            log.append(
                f"{spec.key}: created '{t.title}' due {occ.due + timedelta(days=t.due_offset_days)}"
            )
        for person_id in spec.gift_recipients:
            name = _PERSON_NAMES.get(person_id, "Unknown")
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


def check_cert(notion, expiry, today):
    if expiry is None:
        return "cert: ASC creds not configured, skipped"
    if (expiry - today).days > CERT_LEAD_DAYS:
        return f"cert: expires {expiry}, outside window"
    existing = notion.query(
        TASKS, filter={"property": "Name", "title": {"contains": CERT_TASK_PREFIX}}
    )
    if any(p["properties"]["Status"]["status"]["name"] in OPEN_STATUSES for p in existing):
        return "cert: open renewal task exists"
    notion.create_page(
        TASKS,
        task_properties(
            f"{CERT_TASK_PREFIX} (expires {expiry.isoformat()})",
            today,
            ("Chore", "Development"),
            "Medium",
        ),
    )
    return "cert: created renewal task"
