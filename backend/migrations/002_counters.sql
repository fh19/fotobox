-- Persistent counters. The print count used to live in the printer backend as a
-- plain attribute, so every backend start reset it (it always showed the full
-- cartridge). Counters belong in the database on /data, which survives both a
-- reboot and the read-only root overlay.
CREATE TABLE counters (
    name  TEXT    PRIMARY KEY,
    value INTEGER NOT NULL DEFAULT 0
);

-- Successful prints since the last manual reset, across events.
INSERT INTO counters (name, value) VALUES ('prints_total', 0);
