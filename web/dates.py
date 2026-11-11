"""Date wording and grouping for the pages.

FreshTrack describes dates only. It never says whether food is safe to eat.
"""

from datetime import date

# Same window as the morning email: due within 3 days, or already past.
SOON_DAYS = 3

DATE_TYPE_WORDS = {
    "best_before": "Best before",
    "expiration": "Expiration date",
}


def format_day(day, today):
    """'13 Nov', or '13 Nov 2027' when the year is not this year."""
    text = f"{day.day} {day:%b}"
    if day.year != today.year:
        text += f" {day.year}"
    return text


def relative_text(days_left):
    """How far the label date is from today, in plain words."""
    if days_left == 0:
        return "today"
    if days_left == 1:
        return "tomorrow"
    if days_left == -1:
        return "yesterday"
    if days_left > 1:
        return f"in {days_left} days"
    return f"{-days_left} days ago"


def describe(item, today):
    """Add the words the page shows, for example 'Best before 13 Nov · in 2 days'."""
    label_date = date.fromisoformat(item["label_date"])
    days_left = (label_date - today).days
    words = DATE_TYPE_WORDS.get(item["date_type"], "Label date")
    return {
        **item,
        "days_left": days_left,
        "date_text": f"{words} {format_day(label_date, today)}",
        "when_text": relative_text(days_left),
    }


def group_items(items, today, soon_days=SOON_DAYS):
    """Split items into past, soon (today up to soon_days) and later. Order is kept."""
    groups = {"past": [], "soon": [], "later": []}
    for item in items:
        described = describe(item, today)
        if described["days_left"] < 0:
            groups["past"].append(described)
        elif described["days_left"] <= soon_days:
            groups["soon"].append(described)
        else:
            groups["later"].append(described)
    return groups
