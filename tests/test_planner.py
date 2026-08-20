from datetime import date
from dataclasses import dataclass

from core.planner import TaskSnapshot, add_months, next_occurrence


# stand-in until Task 3's registry lands
@dataclass(frozen=True)
class RecurringSpec:
    key: str
    mode: str
    interval_months: int
    interval_days: int
    anchor: date
    match_titles: tuple[str, ...]
    templates: tuple


OPEN, DONE, CXL = "To Do", "Completed", "Canceled"


def snap(title, status, due=None, completed=None):
    return TaskSnapshot(title=title, status=status, due=due, completed=completed)


def rel(interval_months=3, interval_days=0, anchor=date(2026, 8, 2)):
    return RecurringSpec(
        key="k",
        mode="relative",
        interval_months=interval_months,
        interval_days=interval_days,
        anchor=anchor,
        match_titles=("T",),
        templates=(),
    )


def fix(interval_months=3, interval_days=0, anchor=date(2026, 9, 20)):
    return RecurringSpec(
        key="k",
        mode="fixed",
        interval_months=interval_months,
        interval_days=interval_days,
        anchor=anchor,
        match_titles=("T",),
        templates=(),
    )


class TestAddMonths:
    def test_plain(self):
        assert add_months(date(2026, 8, 2), 3) == date(2026, 11, 2)

    def test_rollover(self):
        assert add_months(date(2026, 11, 15), 3) == date(2027, 2, 15)

    def test_clamp(self):
        assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)

    def test_two_years(self):
        assert add_months(date(2026, 3, 29), 24) == date(2028, 3, 29)


class TestRelative:
    def test_open_suppresses(self):
        assert (
            next_occurrence(
                rel(),
                [snap("T", OPEN), snap("T", DONE, completed=date(2026, 8, 2))],
                today=date(2026, 8, 20),
            )
            is None
        )

    def test_completed_spawns(self):
        occ = next_occurrence(
            rel(), [snap("T", DONE, completed=date(2026, 8, 2))], today=date(2026, 8, 20)
        )
        assert occ.due == date(2026, 11, 2)

    def test_canceled_also_spawns(self):
        occ = next_occurrence(
            rel(anchor=date(2026, 1, 1)),
            [snap("T", CXL, completed=date(2026, 5, 4))],
            today=date(2026, 8, 20),
        )
        assert occ.due == date(2026, 8, 4)

    def test_latest_completion_wins_incl_anchor(self):
        occ = next_occurrence(
            rel(anchor=date(2026, 8, 2)),
            [snap("T", CXL, completed=date(2026, 5, 4))],
            today=date(2026, 8, 20),
        )
        assert occ.due == date(2026, 11, 2)

    def test_no_history_uses_anchor(self):
        assert next_occurrence(rel(), [], today=date(2026, 8, 20)).due == date(2026, 11, 2)

    def test_day_interval(self):
        occ = next_occurrence(
            rel(interval_months=0, interval_days=21, anchor=date(2026, 8, 10)),
            [],
            today=date(2026, 8, 20),
        )
        assert occ.due == date(2026, 8, 31)


class TestFixed:
    def test_not_yet_due(self):
        assert next_occurrence(fix(), [], today=date(2026, 9, 19)) is None

    def test_due_today_fires(self):
        assert next_occurrence(fix(), [], today=date(2026, 9, 20)).due == date(2026, 9, 20)

    def test_already_materialized_skips(self):
        existing = [snap("T", OPEN, due=date(2026, 9, 20))]
        assert next_occurrence(fix(), existing, today=date(2026, 9, 20)) is None

    def test_completed_occurrence_does_not_block_next_period(self):
        existing = [snap("T", DONE, due=date(2026, 9, 20), completed=date(2026, 9, 21))]
        occ = next_occurrence(fix(), existing, today=date(2026, 12, 20))
        assert occ.due == date(2026, 12, 20)

    def test_missed_periods_create_only_latest(self):
        occ = next_occurrence(fix(), [], today=date(2027, 1, 5))  # missed 9/20 and 12/20
        assert occ.due == date(2026, 12, 20)

    def test_future_dated_open_task_from_native_dedupes(self):
        # Christmas 2026: native already created the batch due 2026-10-15
        spec = fix(interval_months=12, anchor=date(2026, 10, 15))
        existing = [snap("T", OPEN, due=date(2026, 10, 15))]
        assert next_occurrence(spec, existing, today=date(2026, 10, 15)) is None
