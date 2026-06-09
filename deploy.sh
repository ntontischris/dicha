#!/usr/bin/env bash
# deploy.sh — auto-deploy woo-agent from GitHub (Digital-Challenge/woo-support-ai-agent)
# Runs as user ntontis (docker group, no sudo). Triggered by cron (see crontab).
# Pulls main; if there are new commits, rebuilds the image and recreates the container.
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

REPO_DIR="$HOME/apps/woo-agent-src"
ENV_FILE="$HOME/apps/woo-agent/.env"
CONTAINER="woo-agent"
IMAGE="woo-agent:latest"
PORT="127.0.0.1:8002:8000"
LOG="$HOME/deploy.log"
LOCK="$HOME/.deploy.lock"

log() { echo "$(date '+%F %T') $*" >> "$LOG"; }

# Single-instance guard (cron may overlap with a slow build)
exec 9>"$LOCK"
flock -n 9 || exit 0

cd "$REPO_DIR"
git fetch origin main --quiet

LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse origin/main)"
[[ "$LOCAL" == "$REMOTE" ]] && exit 0   # nothing new

log "deploying $LOCAL -> $REMOTE"
git reset --hard origin/main --quiet

if ! docker build -t "$IMAGE" . >> "$LOG" 2>&1; then
  log "BUILD FAILED — keeping running container"
  exit 1
fi

docker rm -f "$CONTAINER" >> "$LOG" 2>&1 || true
docker run -d --name "$CONTAINER" --restart unless-stopped \
  --env-file "$ENV_FILE" -p "$PORT" "$IMAGE" >> "$LOG" 2>&1

sleep 5
if curl -fsS --max-time 10 http://127.0.0.1:8002/health > /dev/null; then
  log "deploy OK: $(git rev-parse --short HEAD)"
else
  log "HEALTH CHECK FAILED after deploy of $REMOTE"
fi
