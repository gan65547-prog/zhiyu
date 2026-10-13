SHELL := /bin/bash

IMAGE ?= enterprise-rag-v2
VERSION ?= $(shell python3 -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
REGISTRY ?=
PUSH ?= false
PIP_INDEX_URL ?=
PIP_EXTRA_INDEX_URL ?=

.PHONY: dev-deps build-image test-unit test-integration test-e2e release release-auto

dev-deps:
	python3 -m pip install -r requirements/dev.txt

build-image:
	docker build \
		--build-arg APP_VERSION=$(VERSION) \
		$(if $(PIP_INDEX_URL),--build-arg PIP_INDEX_URL=$(PIP_INDEX_URL),) \
		$(if $(PIP_EXTRA_INDEX_URL),--build-arg PIP_EXTRA_INDEX_URL=$(PIP_EXTRA_INDEX_URL),) \
		-t $(if $(REGISTRY),$(REGISTRY)/,)$(IMAGE):$(VERSION) \
		-t $(if $(REGISTRY),$(REGISTRY)/,)$(IMAGE):latest \
		.

test-unit:
	python3 -m pytest tests/unit -v --tb=short

test-integration:
	python3 -m pytest tests/integration -v --tb=short

test-e2e:
	python3 -m pytest tests/e2e -v --tb=short

release:
	bash scripts/release/release.sh --version $(VERSION) $(if $(REGISTRY),--registry $(REGISTRY),) $(if $(filter true,$(PUSH)),--push,)

release-auto:
	bash scripts/release/release.sh $(if $(REGISTRY),--registry $(REGISTRY),) $(if $(filter true,$(PUSH)),--push,)
