.PHONY: setup start public stop smoke check e2e

setup:
	./start.sh --setup-only

start:
	./start.sh

public:
	./start.sh --public

stop:
	python3 scripts/manage.py stop

smoke:
	PYTHONPATH=backend .venv/bin/python backend/scripts/smoke_flow.py
	.venv/bin/python backend/scripts/check_careers.py
	.venv/bin/python backend/scripts/check_reports.py

check:
	.venv/bin/python -m compileall -q backend/app backend/scripts scripts
	cd frontend && pnpm exec next typegen && pnpm lint && pnpm build
	git diff --check

e2e:
	cd frontend && pnpm test:e2e
