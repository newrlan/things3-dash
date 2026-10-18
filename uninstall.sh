#!/bin/bash
# Removes what install.sh installed: stops the launchd agent, deletes its plist
# and the "Things Dash" app. The log and the data of the project stay.

set -eu
LABEL="com.github.newrlan.things3-dash"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
APP="$HOME/Applications/Things Dash.app"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$PLIST"
rm -rf "$APP"

echo "служба и приложение удалены; лог остался: $HOME/Library/Logs/things3-dash.log"
