#!/usr/bin/env bash
set -euo pipefail
if [[ "$EUID" != 0 ]]; then
  echo '请在本机终端执行：sudo bash dify/install-docker.sh'
  exit 2
fi
export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=30 update
if apt-cache show docker.io docker-compose-v2 >/dev/null 2>&1; then
  apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=30 install -y --no-install-recommends docker.io docker-compose-v2
else
  apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl --connect-timeout 15 --max-time 60 -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://mirrors.aliyun.com/docker-ce/linux/ubuntu %s stable\n' "$(dpkg --print-architecture)" "$VERSION_CODENAME" > /etc/apt/sources.list.d/careerpilot-docker.list
  apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=30 update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
desktop_uid="${PKEXEC_UID:-${SUDO_UID:-}}"
if [[ -n "$desktop_uid" && "$desktop_uid" != 0 ]]; then
  desktop_user="$(getent passwd "$desktop_uid" | cut -d: -f1)"
  if [[ -n "$desktop_user" ]]; then usermod -aG docker "$desktop_user"; fi
fi
docker info --format 'Docker Engine {{.ServerVersion}}'
docker compose version
