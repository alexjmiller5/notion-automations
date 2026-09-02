from datetime import date

import pytest

from core.dispatcher import _hydrate_recipients, dispatch
from core.planner import TaskSnapshot
from core.registry import TASKS, RecurringSpec, TaskTemplate, cc_keepalive_title

RECIPIENTS = ("r1", "r2", "r3", "r4", "r5")
CARDS = ("Card A", "Card B")

# Recipient names live in Notion, not the repo, so the fake serves them the
# way the People DB does.
FAKE_PEOPLE = {
    pid: {"properties": {"Name": {"title": [{"plain_text": f"Person{i} Surname"}]}}}
    for i, pid in enumerate(RECIPIENTS)
}

PLANTS = RecurringSpec(
    key="water-plants",
    mode="relative",
    interval_months=3,
    anchor=date(2026, 8, 2),
    match_titles=("Water the office plants",),
    templates=(TaskTemplate(title="Water the office plants", tags=("Chore",), priority="High"),),
)
CHRISTMAS = RecurringSpec(
    key="christmas",
    mode="fixed",
    interval_months=12,
    anchor=date(2026, 10, 15),
    match_titles=(),
    templates=(),
    gift_recipients=RECIPIENTS,
)
SPECS = (PLANTS, CHRISTMAS)


class FakeNotion:
    def __init__(self, snaps=None, inactive_accounts=()):
        self._snaps = snaps or {}
        self._inactive = inactive_accounts
        self.card_options = CARDS
        self.created = []

    def get_data_source(self, ds):
        return {
            "properties": {
                "Credit Card / Account": {
                    "select": {"options": [{"name": n} for n in self.card_options]}
                }
            }
        }

    def snapshots(self, ds, titles):
        return self._snaps.get(titles, [])

    def get_page(self, page_id):
        return FAKE_PEOPLE[page_id]

    def any_match(self, ds, filter):
        account = filter["and"][0]["select"]["equals"]
        return account not in self._inactive

    def create_page(self, ds, properties, icon=None):
        self.created.append((ds, properties))
        return {"id": f"page-{len(self.created)}", "url": "u"}


def test_dispatch_creates_due_relative_task():
    fake = FakeNotion()  # no history -> every relative spec fires from anchor
    dispatch(fake, date(2026, 8, 20), SPECS, CARDS)
    titles = [p["Name"]["title"][0]["text"]["content"] for _, p in fake.created]
    assert "Water the office plants" in titles


def test_dispatch_open_task_suppresses():
    fake = FakeNotion()
    specs = [_hydrate_recipients(s, fake)[0] if s.gift_recipients else s for s in SPECS]
    fake._snaps = {
        s.match_titles: [TaskSnapshot(t, "To Do", None, None) for t in s.match_titles]
        for s in specs
    }
    dispatch(fake, date(2026, 8, 20), SPECS, CARDS)
    assert fake.created == []


def test_christmas_creates_gifts_and_blocked_chain():
    fake = FakeNotion()
    dispatch(fake, date(2026, 10, 15), SPECS, CARDS)
    gifts = [(ds, p) for ds, p in fake.created if "Recipient(s)" in p]
    buys = [p for _, p in fake.created if "Blocked by" in p]
    assert len(gifts) == 5 and len(buys) == 5
    assert gifts[0][1]["Gift Date"]["date"]["start"] == "2026-12-25"  # computed year


def test_christmas_partial_batch_skips_existing_template_but_finishes_the_rest():
    # simulates a prior run that crashed after creating just the first
    # person's Brainstorm task: only that one template + due already exists,
    # everything else (9 tasks + 5 gifts) is still missing and must be
    # created on retry, without duplicating the one that's already there
    spec, _ = _hydrate_recipients(CHRISTMAS, FakeNotion())
    existing_template = spec.templates[0]
    existing_due = spec.anchor  # due_offset_days=0 for the first (Brainstorm) template
    snaps = {
        spec.match_titles: [TaskSnapshot(existing_template.title, "To Do", existing_due, None)]
    }
    fake = FakeNotion(snaps=snaps)
    dispatch(fake, spec.anchor, (CHRISTMAS,), CARDS)
    christmas_titles = [
        p["Name"]["title"][0]["text"]["content"]
        for _, p in fake.created
        if "Name" in p and p["Name"]["title"][0]["text"]["content"] in spec.match_titles
    ]
    assert christmas_titles.count(existing_template.title) == 0  # not duplicated
    assert len(christmas_titles) == len(spec.templates) - 1  # every other task created
    gifts = [(ds, p) for ds, p in fake.created if "Recipient(s)" in p]
    assert len(gifts) == 5  # gifts still created in full


def test_hydration_builds_the_brainstorm_then_buy_pairs():
    spec, full_names = _hydrate_recipients(CHRISTMAS, FakeNotion())
    assert len(spec.templates) == 10 and len(full_names) == 5
    buys = [t for t in spec.templates if t.blocked_by_prev]
    assert len(buys) == 5 and all(t.due_offset_days == 30 for t in buys)
    # first names only in task titles, full names for the Gifts page titles
    assert (
        spec.templates[0].title
        == "Brainstorm and come up with an idea for Person0's Christmas Gift"
    )
    assert full_names[RECIPIENTS[0]] == "Person0 Surname"
    assert spec.match_titles == tuple(t.title for t in spec.templates)


def test_keepalive_creates_task_for_inactive_card_only():
    fake = FakeNotion(inactive_accounts=("Card B",))
    dispatch(fake, date(2026, 8, 25), SPECS, CARDS)
    keepalive = [
        (ds, p)
        for ds, p in fake.created
        if "no transactions in the past year" in p["Name"]["title"][0]["text"]["content"]
    ]
    assert len(keepalive) == 1
    ds, p = keepalive[0]
    assert ds == TASKS
    assert p["Name"]["title"][0]["text"]["content"] == cc_keepalive_title("Card B")
    assert p["Due Date"]["date"]["start"] == "2026-08-25"
    assert p["Tags"]["multi_select"] == [{"name": "Finances"}]


def test_keepalive_open_task_suppresses():
    title = cc_keepalive_title("Card B")
    fake = FakeNotion(
        snaps={(title,): [TaskSnapshot(title, "To Do", date(2026, 8, 1), None)]},
        inactive_accounts=("Card B",),
    )
    dispatch(fake, date(2026, 8, 25), SPECS, CARDS)
    titles = [p["Name"]["title"][0]["text"]["content"] for _, p in fake.created]
    assert title not in titles


def test_keepalive_fails_hard_on_unknown_card_option():
    # a Transactions-DB overhaul that renames a card option must fail the run
    # (Modal emails on schedule failure), never silently create bogus tasks
    fake = FakeNotion()
    fake.card_options = ("Card A",)  # Card B missing
    with pytest.raises(RuntimeError, match="Card B"):
        dispatch(fake, date(2026, 8, 25), SPECS, CARDS)
