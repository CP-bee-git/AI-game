#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
action="${1:-status}"
case "$action" in
  start)
    if ! systemctl --user is-active --quiet careerpilot-agent-tools; then
      systemd-run --user --unit=careerpilot-agent-tools --property="WorkingDirectory=$project_dir" \
        --property=Restart=on-failure /bin/bash "$project_dir/dify/run-tools.sh"
    fi
    if ! systemctl --user is-active --quiet careerpilot-dify-api; then
      systemd-run --user --unit=careerpilot-dify-api --property="WorkingDirectory=$project_dir" \
        --property=Restart=on-failure --setenv=AI_BACKEND=dify \
        "$project_dir/.venv/bin/python" -m uvicorn app.main:app --app-dir "$project_dir/backend" --host 127.0.0.1 --port 8010 --workers 1
    fi
    ;;
  stop)
    systemctl --user stop careerpilot-agent-tools careerpilot-dify-api
    ;;
  status)
    systemctl --user status careerpilot-agent-tools careerpilot-dify-api --no-pager
    ;;
  *) echo '用法：bash dify/services.sh start|stop|status'; exit 2 ;;
esac
