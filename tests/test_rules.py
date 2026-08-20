from datetime import datetime, timezone

from core import registry as R
from core.rules import NY, evaluate

# 2026-08-20 12:00 UTC == 2026-08-20 08:00 America/New_York (EDT, UTC-4)
NOW = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)


def page(ds, props, page_id="p1", title="Some Page"):
    return {
        "id": page_id,
        "url": f"https://notion.so/{page_id}",
        "parent": {"data_source_id": ds},
        "properties": props,
    }


def status(name):
    return {"status": {"name": name}}


def dateval(iso):
    return {"date": {"start": iso} if iso else None}


# --- Tasks ---


def test_tasks_complete_without_completed_date():
    p = page(
        R.TASKS,
        {
            "Status": status("Completed"),
            "Completed Date": dateval(None),
            "Due Date": dateval("2026-08-01"),
            "Tags": {"multi_select": [{"name": "Chore"}]},
            "Priority": {"select": {"name": "High"}},
            "Tag & Date History": {"rich_text": [{"plain_text": "x"}]},
            "Name": {"title": [{"plain_text": "T"}]},
        },
    )
    v = evaluate(R.TASKS, p, NOW)
    assert [x.rule for x in v] == ["tasks-completed-date-set"]
    assert v[0].fix["Completed Date"]["date"]["start"].startswith("2026-08-20")


def test_tasks_open_with_completed_date_cleared():
    p = page(
        R.TASKS,
        {
            "Status": status("To Do"),
            "Completed Date": dateval("2026-08-01"),
            "Due Date": dateval("2026-08-01"),
            "Tags": {"multi_select": [{"name": "Chore"}]},
            "Priority": {"select": {"name": "High"}},
            "Tag & Date History": {"rich_text": [{"plain_text": "x"}]},
            "Name": {"title": [{"plain_text": "T"}]},
        },
    )
    v = evaluate(R.TASKS, p, NOW)
    assert v[0].rule == "tasks-completed-date-clear" and v[0].fix["Completed Date"]["date"] is None


def test_tasks_defaults_filled_only_if_empty():
    p = page(
        R.TASKS,
        {
            "Status": status("To Do"),
            "Completed Date": dateval(None),
            "Due Date": dateval(None),
            "Tags": {"multi_select": []},
            "Priority": {"select": None},
            "Tag & Date History": {"rich_text": []},
            "Name": {"title": [{"plain_text": "T"}]},
        },
    )
    rules = {x.rule: x for x in evaluate(R.TASKS, p, NOW)}
    assert rules["tasks-default-due"].fix["Due Date"]["date"]["start"] == "2026-08-20"
    assert rules["tasks-default-tags"].fix["Tags"]["multi_select"] == [{"name": "Chore"}]
    assert rules["tasks-default-priority"].fix["Priority"]["select"]["name"] == "High"
    assert "tasks-history" in rules  # empty history -> initial entry


def test_tasks_history_entry_exact_format():
    p = page(
        R.TASKS,
        {
            "Status": status("To Do"),
            "Completed Date": dateval(None),
            "Due Date": dateval("2026-08-20"),
            "Tags": {"multi_select": [{"name": "Chore"}]},
            "Priority": {"select": {"name": "High"}},
            "Tag & Date History": {"rich_text": []},
            "Name": {"title": [{"plain_text": "T"}]},
        },
    )
    rules = {x.rule: x for x in evaluate(R.TASKS, p, NOW)}
    entry = rules["tasks-history"].fix["Tag & Date History"]["rich_text"][0]["text"]["content"]
    assert entry == "[2026-08-20 08:00] --- Tags: [Chore], Due Date: 2026-08-20"


def test_tasks_history_uses_effective_post_default_values():
    # brand-new task: empty Tags, empty Due Date, empty history - the history
    # entry must reflect the defaults tasks-default-tags/tasks-default-due
    # just computed, not the raw (empty) props
    p = page(
        R.TASKS,
        {
            "Status": status("To Do"),
            "Completed Date": dateval(None),
            "Due Date": dateval(None),
            "Tags": {"multi_select": []},
            "Priority": {"select": {"name": "High"}},
            "Tag & Date History": {"rich_text": []},
            "Name": {"title": [{"plain_text": "T"}]},
        },
    )
    rules = {x.rule: x for x in evaluate(R.TASKS, p, NOW)}
    stamp = NOW.astimezone(NY).strftime("%Y-%m-%d %H:%M")
    entry = rules["tasks-history"].fix["Tag & Date History"]["rich_text"][0]["text"]["content"]
    assert entry == f"[{stamp}] --- Tags: [Chore], Due Date: 2026-08-20"


# --- Books ---


def test_books_complete_sets_date_read():
    p = page(
        R.BOOKS,
        {
            "Status": status("Finished"),
            "Date Read": dateval(None),
            "Title": {"title": [{"plain_text": "B"}]},
        },
    )
    v = evaluate(R.BOOKS, p, NOW)
    assert v[0].rule == "books-date-read-set"


def test_books_open_clears_date_read():
    p = page(
        R.BOOKS,
        {
            "Status": status("Not Started"),
            "Date Read": dateval("2026-08-01"),
            "Title": {"title": [{"plain_text": "B"}]},
        },
    )
    v = evaluate(R.BOOKS, p, NOW)
    assert v[0].rule == "books-date-read-clear"


def test_compliant_page_yields_nothing():
    p = page(
        R.BOOKS,
        {
            "Status": status("Finished"),
            "Date Read": dateval("2026-08-01"),
            "Title": {"title": [{"plain_text": "B"}]},
        },
    )
    assert evaluate(R.BOOKS, p, NOW) == []


# --- YouTube ---


def test_youtube_watched_sets_date_watched():
    p = page(
        R.YOUTUBE,
        {
            "Status": status("Watched"),
            "Date Watched": dateval(None),
            "Title": {"title": [{"plain_text": "Y"}]},
        },
    )
    v = evaluate(R.YOUTUBE, p, NOW)
    assert v[0].rule == "youtube-date-watched-set"


def test_youtube_to_watch_clears_date_watched():
    p = page(
        R.YOUTUBE,
        {
            "Status": status("To Watch"),
            "Date Watched": dateval("2026-08-01"),
            "Title": {"title": [{"plain_text": "Y"}]},
        },
    )
    v = evaluate(R.YOUTUBE, p, NOW)
    assert v[0].rule == "youtube-date-watched-clear"


# --- TV ---


def test_tv_finished_sets_date_watched():
    p = page(
        R.TV,
        {
            "Status": status("Finished"),
            "Date Watched": dateval(None),
            "Title": {"title": [{"plain_text": "TV"}]},
        },
    )
    v = evaluate(R.TV, p, NOW)
    assert v[0].rule == "tv-date-watched-set"


def test_tv_not_started_clears_date_watched():
    p = page(
        R.TV,
        {
            "Status": status("Not Started"),
            "Date Watched": dateval("2026-08-01"),
            "Title": {"title": [{"plain_text": "TV"}]},
        },
    )
    v = evaluate(R.TV, p, NOW)
    assert v[0].rule == "tv-date-watched-clear"


# --- Movies ---


def test_movies_only_finished_sets_date_watched():
    p = page(
        R.MOVIES,
        {
            "Status": status("In Progress"),
            "Date Watched": dateval(None),
            "Title": {"title": [{"plain_text": "M"}]},
        },
    )
    assert evaluate(R.MOVIES, p, NOW) == []


def test_movies_finished_sets_date_watched():
    p = page(
        R.MOVIES,
        {
            "Status": status("Finished"),
            "Date Watched": dateval(None),
            "Title": {"title": [{"plain_text": "M"}]},
        },
    )
    v = evaluate(R.MOVIES, p, NOW)
    assert v[0].rule == "movies-date-watched-set"


def test_movies_not_started_clears_date_watched():
    p = page(
        R.MOVIES,
        {
            "Status": status("Not Started"),
            "Date Watched": dateval("2026-08-01"),
            "Title": {"title": [{"plain_text": "M"}]},
        },
    )
    v = evaluate(R.MOVIES, p, NOW)
    assert v[0].rule == "movies-date-watched-clear"


# --- Articles ---


def test_articles_done_sets_read_date():
    p = page(
        R.ARTICLES,
        {
            "Status": status("Done"),
            "Read Date": dateval(None),
            "Name": {"title": [{"plain_text": "A"}]},
        },
    )
    v = evaluate(R.ARTICLES, p, NOW)
    assert v[0].rule == "articles-read-date-set"


def test_articles_not_started_clears_read_date():
    p = page(
        R.ARTICLES,
        {
            "Status": status("Not started"),
            "Read Date": dateval("2026-08-01"),
            "Name": {"title": [{"plain_text": "A"}]},
        },
    )
    v = evaluate(R.ARTICLES, p, NOW)
    assert v[0].rule == "articles-read-date-clear"


# --- Projects ---


def test_projects_complete_sets_completed_date():
    p = page(
        R.PROJECTS,
        {
            "Status": status("Completed"),
            "Completed Date": dateval(None),
            "Title": {"title": [{"plain_text": "P"}]},
        },
    )
    v = evaluate(R.PROJECTS, p, NOW)
    assert v[0].rule == "projects-completed-date-set"


def test_projects_in_progress_clears_completed_date():
    p = page(
        R.PROJECTS,
        {
            "Status": status("In progress"),
            "Completed Date": dateval("2026-08-01"),
            "Title": {"title": [{"plain_text": "P"}]},
        },
    )
    v = evaluate(R.PROJECTS, p, NOW)
    assert v[0].rule == "projects-completed-date-clear"


# --- Synapse ---


def _synapse_page(**overrides):
    props = {
        "Outcome": status("Successful Flow"),
        "Code Execution": status("Success"),
        "Category": {"select": {"name": "bookmarks"}},
        "Remedied?": {"checkbox": False},
        "Date Remedied": dateval(None),
        "Date Reviewed": dateval(None),
        "Raw Input": {"title": [{"plain_text": "S"}]},
    }
    props.update(overrides)
    return page(R.SYNAPSE, props)


def test_synapse_outcome_autoapprove():
    p = _synapse_page(Outcome=status("To Review"))
    # outcome-autoapprove only applies on page.created events; evaluate() takes created flag
    v = evaluate(R.SYNAPSE, p, NOW, created=True)
    assert any(
        x.rule == "synapse-outcome" and x.fix["Outcome"]["status"]["name"] == "Successful Flow"
        for x in v
    )


def test_synapse_remedied_checked_sets_date_remedied():
    p = _synapse_page(**{"Remedied?": {"checkbox": True}, "Date Remedied": dateval(None)})
    v = evaluate(R.SYNAPSE, p, NOW)
    assert any(x.rule == "synapse-date-remedied-set" for x in v)


def test_synapse_remedied_unchecked_clears_date_remedied():
    p = _synapse_page(**{"Remedied?": {"checkbox": False}, "Date Remedied": dateval("2026-08-01")})
    v = evaluate(R.SYNAPSE, p, NOW)
    assert any(x.rule == "synapse-date-remedied-clear" for x in v)


def test_synapse_outcome_reviewed_sets_date_reviewed():
    p = _synapse_page(Outcome=status("Successful Flow"), **{"Date Reviewed": dateval(None)})
    v = evaluate(R.SYNAPSE, p, NOW)
    rules = {x.rule: x for x in v}
    assert (
        rules["synapse-date-reviewed-set"]
        .fix["Date Reviewed"]["date"]["start"]
        .startswith("2026-08-20")
    )


def test_synapse_to_review_clears_date_reviewed():
    p = _synapse_page(Outcome=status("To Review"), **{"Date Reviewed": dateval("2026-08-01")})
    v = evaluate(R.SYNAPSE, p, NOW)
    assert any(x.rule == "synapse-date-reviewed-clear" for x in v)
