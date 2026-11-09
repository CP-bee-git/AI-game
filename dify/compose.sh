#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
if [[ ! -f "$project_dir/.runtime/dify/docker/docker-compose.yaml" ]]; then
  echo '先运行：python3 scripts/prepare_dify.py prepare'
  exit 2
fi
compose_command=(docker compose --project-directory "$project_dir/.runtime/dify/docker" \
  -f "$project_dir/.runtime/dify/docker/docker-compose.yaml" \
  -f "$project_dir/.private/dify/compose.override.yml" "$@")
if ! docker info >/dev/null 2>&1 && id -nG "$(id -un)" | tr ' ' '\n' | grep -qx docker; then
  printf -v grouped_command '%q ' "${compose_command[@]}"
  exec sg docker -c "$grouped_command"
fi
exec "${compose_command[@]}"
