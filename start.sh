#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

command -v python3 >/dev/null || { echo '需要 Python 3.12+'; exit 1; }
python3 -c 'import sys; assert sys.version_info >= (3, 12), "需要 Python 3.12+"'
command -v node >/dev/null || { echo '需要 Node.js 24+'; exit 1; }
node -e 'if (+process.versions.node.split(".")[0] < 24) { console.error("需要 Node.js 24+"); process.exit(1) }'
command -v pnpm >/dev/null || { echo '需要 pnpm：npm install -g pnpm@11.22.0'; exit 1; }

if [[ ! -x .venv/bin/python ]]; then python3 -m venv .venv; fi
echo '准备 API 和网页依赖…'
.venv/bin/python -m pip install --disable-pip-version-check -q -e 'backend[test]'
pnpm install --frozen-lockfile
if [[ "${1:-}" == '--setup-only' ]]; then
  echo '依赖就绪。运行 ./start.sh 启动，./start.sh --public 发布 cpolar。'
  exit 0
fi

launch_mode=legacy
if [[ -f .private/dify/app-keys.json ]]; then launch_mode=dify; fi
if [[ "${1:-}" == '--dify' ]]; then launch_mode=dify; shift; fi
if [[ "${1:-}" == '--legacy' ]]; then launch_mode=legacy; shift; fi
backend_url=http://127.0.0.1:8000
if [[ "$launch_mode" == dify ]]; then backend_url=http://127.0.0.1:8010; fi
if [[ ! -f frontend/.next/BUILD_ID ]] || [[ "$(cat frontend/.next/BUILD_BACKEND_URL 2>/dev/null || true)" != "$backend_url" ]] || find frontend/app frontend/next.config.ts frontend/package.json -type f -newer frontend/.next/BUILD_ID -print -quit | grep -q .; then
  echo '构建网站…'
  API_INTERNAL_URL="$backend_url" pnpm --dir frontend build
  printf '%s\n' "$backend_url" > frontend/.next/BUILD_BACKEND_URL
fi
if [[ "$launch_mode" == dify ]]; then
  bash dify/services.sh install
  echo '工作台：http://127.0.0.1:3000；Dify：http://127.0.0.1:8088'
  if [[ "${1:-}" == '--public' ]]; then exec .venv/bin/python scripts/manage.py public; fi
  exit 0
fi
exec .venv/bin/python scripts/manage.py start "$@"
