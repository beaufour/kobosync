#!/bin/sh
# Deploy kobosync to the Raspberry Pi.
# Usage: ./scripts/deploy-pi.sh [host]
set -e

HOST="${1:-kobohub}"

echo "Deploying to $HOST..."
ssh "$HOST" "
  cd ~/kobosync &&
  git pull &&
  ~/.local/bin/uv tool install --reinstall --from . kobosync
"
echo "Done."
