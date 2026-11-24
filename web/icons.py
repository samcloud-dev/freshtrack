"""Which small picture to show next to a food item, and how to show its name.

Display only: nothing here changes what is stored in the database.
"""

import re

# Used when no word in the name matches: show where the food is kept.
LOCATION_ICONS = {
    "fridge": "fridge",
    "freezer": "snowflake",
    "cupboard": "cupboard",
}

# The first group with a matching word wins, so the order matters:
# "canned tomatoes" is a can before it is a vegetable.
KEYWORD_ICONS = (
    ("can", ("can", "canned", "tin", "tinned", "beans", "tuna", "soup")),
    (
        "bottle",
        ("milk", "juice", "yogurt", "yoghurt", "kefir", "cream", "smoothie", "drink"),
    ),
    (
        "apple",
        (
            "apple",
            "pear",
            "fruit",
            "berry",
            "berries",
            "grape",
            "orange",
            "banana",
            "plum",
            "peach",
            "mango",
            "lemon",
            "lime",
        ),
    ),
    (
        "leaf",
        (
            "lettuce",
            "spinach",
            "salad",
            "kale",
            "cabbage",
            "herb",
            "carrot",
            "broccoli",
            "pepper",
            "onion",
            "vegetable",
            "veg",
            "cucumber",
            "potato",
            "tomato",
            "tomatoes",
        ),
    ),
    ("bread", ("bread", "bagel", "bun", "loaf", "wrap", "tortilla", "pita")),
    ("cheese", ("cheese", "cheddar", "mozzarella", "feta")),
    ("egg", ("egg",)),
    (
        "meat",
        ("chicken", "beef", "pork", "meat", "sausage", "ham", "bacon", "turkey"),
    ),
    ("fish", ("fish", "salmon", "shrimp", "cod", "sardine")),
)


def _words(name):
    """Lower-case words in a name: 'Canned Tomatoes!' -> ['canned', 'tomatoes']."""
    return re.findall(r"[a-z]+", name.lower())


def _matches(word, keyword):
    # Whole words only, so "can" never matches "candy". A plural "s" is allowed.
    return word == keyword or word == keyword + "s"


def food_icon(name, location):
    """The icon name for an item: by keyword first, then by storage place."""
    for icon, keywords in KEYWORD_ICONS:
        for word in _words(name or ""):
            if any(_matches(word, keyword) for keyword in keywords):
                return icon
    return LOCATION_ICONS.get(location, "basket")


def display_name(name):
    """'juice' -> 'Juice'. Only the first letter changes; the rest is kept as typed."""
    if not name:
        return name
    return name[:1].upper() + name[1:]
