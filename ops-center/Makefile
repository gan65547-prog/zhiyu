.PHONY: dev test smoke smoke-dry lint staging-validate console-install console-build console-dev

VENV_PY=.venv/bin/python
VENV_PIP=.venv/bin/pip
VENV_UVICORN=.venv/bin/uvicorn
VENV_PYTEST=.venv/bin/pytest

dev:
	$(VENV_UVICORN) app.main:app --host 0.0.0.0 --port 8081 --reload

test:
	$(VENV_PYTEST) -q

smoke:
	./scripts/smoke.sh

smoke-dry:
	BASE_URL=http://127.0.0.1:8081 OP_ID=ops-smoke-001 OPERATOR=ops-smoke ./scripts/smoke.sh --dry-run

staging-validate:
	./scripts/staging_validate.sh

lint:
	$(VENV_PY) -m py_compile app/main.py app/routers/health.py app/routers/tenants.py app/routers/operations.py app/services/business_gateway.py

# 独立 Vue 控制台（Vite），构建产物输出到 static/console，由 FastAPI 挂载在 /console/
console-install:
	cd console && npm install

console-build: console-install
	cd console && npm run build

console-dev:
	cd console && npm run dev
