"""Date wording and grouping. Pure logic: no Flask, no api."""

from datetime import date

import pytest
from dates import describe, group_items, relative_text

TODAY = date(2026, 11, 11)


def item(label_date, date_type="best_before", name="Milk"):
    return {"id": 1, "name": name, "label_date": label_date, "date_type": date_type}


@pytest.mark.parametrize(
    ("label_date", "group"),
    [
        ("2026-11-10", "past"),  # yesterday
        ("2026-11-11", "soon"),  # today counts as soon, not past
        ("2026-11-14", "soon"),  # exactly 3 days away: still in the window
        ("2026-11-15", "later"),  # 4 days away
    ],
)
def test_group_boundaries(label_date, group):
    groups = group_items([item(label_date)], TODAY)
    assert [i["label_date"] for i in groups[group]] == [label_date]


def test_group_keeps_the_api_order():
    items = [item("2026-11-12", name="Juice"), item("2026-11-13", name="Yogurt")]
    groups = group_items(items, TODAY)
    assert [i["name"] for i in groups["soon"]] == ["Juice", "Yogurt"]


def test_best_before_and_expiration_use_different_words():
    best = describe(item("2026-11-13", "best_before"), TODAY)
    expiry = describe(item("2026-11-13", "expiration"), TODAY)
    assert best["date_text"] == "Best before 13 Nov"
    assert expiry["date_text"] == "Expiration date 13 Nov"


def test_year_is_shown_when_not_this_year():
    assert describe(item("2027-01-05"), TODAY)["date_text"] == "Best before 5 Jan 2027"


@pytest.mark.parametrize(
    ("days", "text"),
    [
        (0, "today"),
        (1, "tomorrow"),
        (-1, "yesterday"),
        (2, "in 2 days"),
        (-10, "10 days ago"),
    ],
)
def test_relative_text(days, text):
    assert relative_text(days) == text


def test_wording_never_talks_about_safety():
    for date_type in ("best_before", "expiration"):
        for label_date in ("2026-11-01", "2026-11-12", "2026-12-01"):
            words = describe(item(label_date, date_type), TODAY)
            text = (words["date_text"] + " " + words["when_text"]).lower()
            assert "safe" not in text
            assert "spoil" not in text
