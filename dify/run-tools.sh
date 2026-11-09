#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_dir"
set -a
source .private/dify/tools.env
set +a
if [[ -z "${AGENT_TOOLS_HOST:-}" ]] && command -v docker >/dev/null; then
  AGENT_TOOLS_HOST="$(docker network inspect bridge --format '{{(index .IPAM.Config 0).Gateway}}' 2>/dev/null || true)"
  if [[ -z "$AGENT_TOOLS_HOST" ]] && id -nG "$(id -un)" | tr ' ' '\n' | grep -qx docker; then
    AGENT_TOOLS_HOST="$(sg docker -c "docker network inspect bridge --format '{{(index .IPAM.Config 0).Gateway}}'" 2>/dev/null || true)"
  fi
fi
exec .venv/bin/uvicorn app.agent_api:app --app-dir backend --host "${AGENT_TOOLS_HOST:-127.0.0.1}" --port 8091 --workers 1
