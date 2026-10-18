#!/bin/bash
# Installs serve.py as a launchd agent of the current user and builds the
# "Things Dash" app that opens the page.
#
#     ./install.sh            # port 8765
#     ./install.sh 9000       # another port
#
# The agent starts the server at login and restarts it if it stops. Run the
# script again after moving this folder or to change the port; ./uninstall.sh
# removes everything it installs.

set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
PORT="${1:-8765}"

LABEL="com.github.newrlan.things3-dash"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/things3-dash.log"
APP="$HOME/Applications/Things Dash.app"
URL="http://127.0.0.1:$PORT/things-dash.html"
DOMAIN="gui/$(id -u)"

case "$PORT" in
    ''|*[!0-9]*) echo "порт должен быть числом: $PORT" >&2; exit 1 ;;
esac
PY="$(command -v python3)" || { echo "python3 не найден" >&2; exit 1; }
[ -x "$HERE/refresh.sh" ] || { echo "refresh.sh не найден или не исполняемый" >&2; exit 1; }

xml() { sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' <<<"$1"; }

# launchd starts the agent with a bare PATH; refresh.sh needs the same python3
mkdir -p "$(dirname "$PLIST")" "$(dirname "$LOG")"
cat >"$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$(xml "$PY")</string>
        <string>$(xml "$HERE/serve.py")</string>
        <string>$PORT</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$(xml "$HERE")</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>$(xml "$(dirname "$PY")"):/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$(xml "$LOG")</string>
    <key>StandardErrorPath</key>
    <string>$(xml "$LOG")</string>
</dict>
</plist>
EOF
plutil -lint -s "$PLIST"

# a reinstall replaces the running agent; launchd needs a moment to let it go
if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    for _ in $(seq 50); do
        launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1 || break
        sleep 0.1
    done
fi
launchctl bootstrap "$DOMAIN" "$PLIST"

# the app starts the agent if it is not running, waits for the port, opens the page
mkdir -p "$(dirname "$APP")"
rm -rf "$APP"
osacompile -o "$APP" <<EOF
do shell script "launchctl kickstart $DOMAIN/$LABEL >/dev/null 2>&1; for i in \$(seq 50); do curl -s -o /dev/null http://127.0.0.1:$PORT/ && break; sleep 0.1; done; true"
open location "$URL"
EOF

echo "служба:     $LABEL (порт $PORT)"
echo "приложение: $APP"
echo "лог:        $LOG"
echo "страница:   $URL"
