.PHONY: dev-api dev-web check smoke

dev-api:
	.venv/bin/uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000

dev-web:
	cd frontend && pnpm dev

smoke:
	PYTHONPATH=backend .venv/bin/python backend/scripts/smoke_flow.py

check:
	.venv/bin/python -m compileall backend/app
	cd frontend && pnpm lint

