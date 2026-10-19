#!/bin/bash
# Builds the "Things Dash" app: a click starts serve.py in the background, if it
# is not running yet, and opens the page in the browser.
#
#     ./install.sh            # port 8765
#     ./install.sh 9000       # another port
#
# The server is started by the app, not by launchd: macOS then asks for access
# to the Things database on behalf of "Things Dash", which a launchd agent
# never gets. Run the script again after moving this folder or to change the
# port; ./uninstall.sh stops the server and removes the app.

set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
PORT="${1:-8765}"

APP="$HOME/Applications/Things Dash.app"
LOG="$HOME/Library/Logs/things3-dash.log"
URL="http://127.0.0.1:$PORT/things-dash.html"
# launchd agent of the earlier install.sh
LABEL="com.github.newrlan.things3-dash"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

case "$PORT" in
    ''|*[!0-9]*) echo "порт должен быть числом: $PORT" >&2; exit 1 ;;
esac
PY="$(command -v python3)" || { echo "python3 не найден" >&2; exit 1; }
[ -x "$HERE/refresh.sh" ] || { echo "refresh.sh не найден или не исполняемый" >&2; exit 1; }
case "$HERE$PY$HOME" in
    *[\"\\\']*) echo "путь с кавычкой или обратной косой чертой не поддерживается" >&2; exit 1 ;;
esac

if [ -f "$PLIST" ]; then
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    echo "удалена служба launchd от прошлой установки"
fi

# the button that refreshes the page lives on the page: build it once from here
if [ ! -f "$HERE/things-dash.html" ]; then
    echo "нет things-dash.html, собираю"
    "$HERE/refresh.sh"
fi

# the app runs with a bare PATH, refresh.sh needs the same python3;
# the app stays open while the server it started runs, and stops it on quit
mkdir -p "$(dirname "$APP")" "$(dirname "$LOG")"
rm -rf "$APP"
osacompile -s -o "$APP" <<EOF
global serverPid

on run
	set serverPid to ""
	set probeCmd to "curl -s -o /dev/null http://127.0.0.1:$PORT/"
	set waitCmd to "for i in \$(seq 50); do " & probeCmd & " && break; sleep 0.1; done; true"
	try
		do shell script probeCmd
	on error
		set serverPid to do shell script "cd '$HERE' && PATH='$(dirname "$PY")':/usr/bin:/bin:/usr/sbin:/sbin nohup '$PY' '$HERE/serve.py' $PORT >>'$LOG' 2>&1 </dev/null & echo \$!"
		do shell script waitCmd
	end try
	open location "$URL"
end run

on reopen
	open location "$URL"
end reopen

on quit
	if serverPid is not "" then do shell script "kill " & serverPid & " 2>/dev/null; true"
	continue quit
end quit
EOF

echo "приложение: $APP"
echo "страница:   $URL"
echo "лог:        $LOG"
