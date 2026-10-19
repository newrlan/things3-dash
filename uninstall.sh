#!/bin/bash
# Removes what install.sh installed: stops the server started by the app and
# deletes the "Things Dash" app. The log and the data of the project stay.

set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$HOME/Applications/Things Dash.app"
# launchd agent of the earlier install.sh
LABEL="com.github.newrlan.things3-dash"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

pkill -f "$HERE/serve.py" 2>/dev/null || true
rm -rf "$APP"
if [ -f "$PLIST" ]; then
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
fi

echo "сервер остановлен, приложение удалено; лог остался: $HOME/Library/Logs/things3-dash.log"
