"""Icon choice and name display. Pure logic: no Flask, no api."""

import pytest
from icons import display_name, food_icon


@pytest.mark.parametrize(
    ("name", "location", "icon"),
    [
        ("Milk", "fridge", "bottle"),
        ("orange juice", "fridge", "bottle"),
        ("Canned tomatoes", "freezer", "can"),  # can wins over tomato
        ("Fruits", "fridge", "apple"),  # plural "s" still matches
        ("Apples", "cupboard", "apple"),
        ("Baby spinach", "fridge", "leaf"),
        ("Sourdough bread", "cupboard", "bread"),
        ("Eggs", "fridge", "egg"),
        ("Cheddar", "fridge", "cheese"),
        ("Chicken thighs", "freezer", "meat"),
        ("Salmon", "freezer", "fish"),
    ],
)
def test_keyword_picks_the_icon(name, location, icon):
    assert food_icon(name, location) == icon


@pytest.mark.parametrize(
    ("location", "icon"),
    [("fridge", "fridge"), ("freezer", "snowflake"), ("cupboard", "cupboard")],
)
def test_no_keyword_falls_back_to_the_storage_place(location, icon):
    assert food_icon("Frozen peas", location) == icon


def test_whole_words_only():
    # "candy" contains "can" but is not a can; it falls back to the cupboard.
    assert food_icon("Candy", "cupboard") == "cupboard"


def test_unknown_place_and_empty_name_get_the_basket():
    assert food_icon("", "garage") == "basket"
    assert food_icon(None, None) == "basket"


@pytest.mark.parametrize(
    ("stored", "shown"),
    [
        ("juice", "Juice"),
        ("Milk", "Milk"),
        ("greek yogurt", "Greek yogurt"),  # only the first letter changes
        ("iPhone charger", "IPhone charger"),
        ("", ""),
    ],
)
def test_display_name_capitalises_only_the_first_letter(stored, shown):
    assert display_name(stored) == shown
