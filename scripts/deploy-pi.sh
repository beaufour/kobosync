#!/bin/sh
# Deploy kobosync to the Raspberry Pi.
# Usage: ./scripts/deploy-pi.sh [host]
set -e

HOST="${1:-kobohub}"

echo "Deploying to $HOST..."
ssh "$HOST" "
  cd ~/kobosync &&
  git pull &&
  ~/.local/bin/uv cache clean --package kobosync 2>/dev/null || true &&
  ~/.local/bin/uv tool uninstall kobosync 2>/dev/null || true &&
  ~/.local/bin/uv tool install --from . kobosync
"
echo "Done."
