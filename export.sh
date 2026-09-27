#!/bin/bash
# Exports data from the Things 3 database into two CSV files.
# Read-only: sqlite3 is given -readonly and the URI flag mode=ro.
# Nothing is copied, nothing is written into the Things container.

set -eu

OUT="$(cd "$(dirname "$0")" && pwd)"

# Things keeps one directory per data set; take the most recently modified.
DB=$(ls -td "$HOME/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/ThingsData-"*/"Things Database.thingsdatabase/main.sqlite" | head -1)
echo "database: $DB"

# Print the columns of TMTask, so a schema mismatch is visible at once.
echo -n "TMTask columns: "
sqlite3 -readonly "file:$DB?mode=ro" "PRAGMA table_info(TMTask);" | cut -d'|' -f2 | tr '\n' ' '
echo

# To-dos and projects. Titles of to-dos are NOT exported, only project titles.
sqlite3 -readonly -csv -header "file:$DB?mode=ro" "
SELECT uuid,
       type,            -- expected: 0 = to-do, 1 = project, 2 = heading
       status,          -- expected: 0 = open, 2 = canceled, 3 = completed
       creationDate,    -- raw number, converted later
       stopDate,        -- raw number, set when completed or canceled
       start,           -- current bucket: expected 0 = Inbox, 1 = Anytime, 2 = Someday
       startBucket,     -- raw, semantics checked against the data
       startDate,       -- raw, scheduled start when one is set
       userModificationDate,  -- last edit of the record, any change
       project,         -- uuid of the parent project
       heading,         -- uuid of the parent heading, when the item sits under one
       area,            -- uuid of the area
       -- names of projects (type 1) and headings (type 2); to-do titles stay out
       CASE WHEN type IN (1, 2) THEN title ELSE '' END AS item_title
FROM TMTask
WHERE trashed = 0;
" > "$OUT/tasks.csv"

# Area names, needed to label the report.
sqlite3 -readonly -csv -header "file:$DB?mode=ro" \
    "SELECT uuid, title FROM TMArea;" > "$OUT/areas.csv"

wc -l "$OUT/tasks.csv" "$OUT/areas.csv"
