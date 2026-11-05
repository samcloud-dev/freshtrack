-- FreshTrack database schema: one table of food items.
-- Safe to run more than once: nothing is created twice and no data is removed.

CREATE TABLE IF NOT EXISTS items (
    id          integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        text        NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 100),
    quantity    text        NOT NULL CHECK (length(btrim(quantity)) BETWEEN 1 AND 50),
    location    text        NOT NULL CHECK (location IN ('fridge', 'freezer', 'cupboard')),
    label_date  date        NOT NULL,
    date_type   text        NOT NULL CHECK (date_type IN ('best_before', 'expiration')),
    status      text        NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'used', 'discarded')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    closed_at   timestamptz,
    -- An active item has no closed time; a used or discarded item always has one.
    CHECK ((status = 'active') = (closed_at IS NULL))
);

-- The active list is always read "soonest date first", so index exactly that.
CREATE INDEX IF NOT EXISTS items_active_by_label_date
    ON items (label_date, id)
    WHERE status = 'active';
