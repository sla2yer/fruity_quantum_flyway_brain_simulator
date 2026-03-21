VENV_PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PYTHON ?= $(VENV_PYTHON)
CONFIG ?= config/local.yaml
MANIFEST ?= manifests/examples/milestone_1_demo.yaml
SCHEMA ?= schemas/milestone_1_experiment_manifest.schema.json
DESIGN_LOCK ?= config/milestone_1_design_lock.yaml
M6_CONFIG ?= config/milestone_6_verification.yaml

.PHONY: help bootstrap verify registry select meshes assets preview operator-qa milestone6-readiness validate-manifest test smoke all

help:
	@printf '%s\n' \
		'bootstrap          Create/update .venv and install the repo in editable mode' \
		'test               Run local unit tests' \
		'smoke              Run tests plus manifest validation' \
		'verify             Check FlyWire/CAVE access (needs token/config)' \
		'registry           Build canonical metadata/connectivity registries' \
		'select             Build the selected root-id subset' \
		'meshes             Fetch raw meshes and optional skeletons' \
		'assets             Build processed mesh/graph assets' \
		'preview            Build static offline geometry preview report(s)' \
		'operator-qa        Build static offline operator QA report(s)' \
		'milestone6-readiness Run the Milestone 6 verification pass and publish a readiness report' \
		'validate-manifest  Validate the example manifest against schema/design lock' \
		'all                Run verify -> registry -> select -> meshes -> assets'

bootstrap:
	test -x .venv/bin/python || python3 -m venv .venv
	./.venv/bin/python -m pip install --upgrade pip
	./.venv/bin/python -m pip install -e .

verify:
	$(PYTHON) scripts/00_verify_access.py --config $(CONFIG)

registry:
	$(PYTHON) scripts/build_registry.py --config $(CONFIG)

select:
	$(PYTHON) scripts/01_select_subset.py --config $(CONFIG)

meshes:
	$(PYTHON) scripts/02_fetch_meshes.py --config $(CONFIG)

assets:
	$(PYTHON) scripts/03_build_wave_assets.py --config $(CONFIG)

preview:
	$(PYTHON) scripts/05_preview_geometry.py --config $(CONFIG)

operator-qa:
	$(PYTHON) scripts/06_operator_qa.py --config $(CONFIG)

milestone6-readiness:
	$(PYTHON) scripts/07_milestone6_readiness.py --config $(M6_CONFIG)

validate-manifest:
	$(PYTHON) scripts/04_validate_manifest.py --manifest $(MANIFEST) --schema $(SCHEMA) --design-lock $(DESIGN_LOCK)

test:
	$(PYTHON) -m unittest discover -s tests -v

smoke: test validate-manifest

all: verify registry select meshes assets
