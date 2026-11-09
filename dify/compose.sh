#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
if [[ ! -f "$project_dir/.runtime/dify/docker/docker-compose.yaml" ]]; then
  echo '先运行：python3 scripts/prepare_dify.py prepare'
  exit 2
fi
exec docker compose --project-directory "$project_dir/.runtime/dify/docker" \
  -f "$project_dir/.runtime/dify/docker/docker-compose.yaml" \
  -f "$project_dir/.private/dify/compose.override.yml" "$@"
