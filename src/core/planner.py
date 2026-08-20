"""Pure recurrence engine. No Notion, no I/O — dates in, decisions out."""

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

OPEN_STATUSES = frozenset({"To Do", "In Progress"})


@dataclass(frozen=True)
class TaskSnapshot:
    title: str
    status: str
    due: date | None
    completed: date | None


@dataclass(frozen=True)
class Occurrence:
    due: date


def add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    year, month = d.year + m // 12, m % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _step(d: date, spec) -> date:
    return add_months(d, spec.interval_months) + timedelta(days=spec.interval_days)


def next_occurrence(spec, existing, today):
    if spec.mode == "relative":
        if any(t.status in OPEN_STATUSES for t in existing):
            return None
        completions = [t.completed for t in existing if t.completed]
        last = max(completions + [spec.anchor]) if completions else spec.anchor
        return Occurrence(due=_step(last, spec))
    # fixed: series anchor + n*interval; materialize the latest series date <= today
    # unless a task for that date already exists (any status).
    d = spec.anchor
    latest_due = None
    while d <= today:
        latest_due = d
        d = _step(d, spec)
    if latest_due is None:
        return None
    if any(t.due == latest_due for t in existing):
        return None
    return Occurrence(due=latest_due)
