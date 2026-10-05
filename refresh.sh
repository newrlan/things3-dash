#!/bin/bash
# Re-reads the Things database and rebuilds the HTML page: build_week.py reads
# the database read-only, updates history.sqlite and writes week.html from
# week.template.html.
#
# The page is self-contained: no external requests, data embedded, works offline.

set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"

python3 "$HERE/build_week.py"

echo
echo "готово: $(date '+%H:%M:%S')"
