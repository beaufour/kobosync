#!/bin/sh
# Pull and reinstall kobosync if there are new commits.
# Skips update if a sync is currently running.
# Intended to be run from cron, e.g.:
#   0 * * * * ~/kobosync/scripts/update.sh >> ~/kobosync-deploy.log 2>&1
set -e

REPO="$HOME/kobosync"

# Don't update while a sync is in progress
if systemctl is-active --quiet kobosync-trigger.service 2>/dev/null; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [update] Sync in progress, skipping update."
    exit 0
fi

cd "$REPO"

PULL_OUTPUT=$(git pull 2>&1)
if echo "$PULL_OUTPUT" | grep -q "Already up to date"; then
    exit 0
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') [update] New code pulled, reinstalling..."
echo "$PULL_OUTPUT"
~/.local/bin/uv tool install --reinstall --from . kobosync
echo "$(date '+%Y-%m-%d %H:%M:%S') [update] Done."
