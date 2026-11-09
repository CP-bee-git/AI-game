#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
action="${1:-status}"
case "$action" in
  install)
    units_dir="$project_dir/.private/dify/systemd"
    mkdir -p "$units_dir"
    cat > "$units_dir/careerpilot-agent-tools.service" <<EOF
[Unit]
Description=CareerPilot Dify Agent Tools
After=network-online.target

[Service]
Type=simple
WorkingDirectory=$project_dir
ExecStart=/bin/bash "$project_dir/dify/run-tools.sh"
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
    cat > "$units_dir/careerpilot-dify-api.service" <<EOF
[Unit]
Description=CareerPilot Dify Business API
After=network-online.target careerpilot-agent-tools.service

[Service]
Type=simple
WorkingDirectory=$project_dir
Environment=AI_BACKEND=dify
ExecStart="$project_dir/.venv/bin/python" -m uvicorn app.main:app --app-dir "$project_dir/backend" --host 127.0.0.1 --port 8010 --workers 1
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
    systemctl --user stop careerpilot-agent-tools careerpilot-dify-api
    systemctl --user daemon-reload
    systemctl --user link "$units_dir/careerpilot-agent-tools.service" "$units_dir/careerpilot-dify-api.service"
    systemctl --user daemon-reload
    systemctl --user enable --now careerpilot-agent-tools careerpilot-dify-api
    ;;
  start)
    if [[ -f "$project_dir/.private/dify/systemd/careerpilot-agent-tools.service" ]]; then
      systemctl --user start careerpilot-agent-tools careerpilot-dify-api
      exit 0
    fi
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
  *) echo '用法：bash dify/services.sh install|start|stop|status'; exit 2 ;;
esac
