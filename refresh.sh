#!/bin/bash
# Re-reads the Things database and rebuilds the HTML page.
#   1. export.sh      - read-only export into tasks.csv / areas.csv
#   2. build_week.py  - week.html from week.template.html
#
# The page is self-contained: no external requests, data embedded, works offline.

set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "== экспорт из базы =="
"$HERE/export.sh"

echo
echo "== сборка страницы =="
python3 "$HERE/build_week.py"

echo
echo "готово: $(date '+%H:%M:%S')"
