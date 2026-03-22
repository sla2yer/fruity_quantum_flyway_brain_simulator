VENV_PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PYTHON ?= $(VENV_PYTHON)
CONFIG ?= config/local.yaml
MANIFEST ?= manifests/examples/milestone_1_demo.yaml
SCHEMA ?= schemas/milestone_1_experiment_manifest.schema.json
DESIGN_LOCK ?= config/milestone_1_design_lock.yaml
M6_CONFIG ?= config/milestone_6_verification.yaml
M7_CONFIG ?= config/milestone_7_verification.yaml
M7_EDGE_FILE ?= config/milestone_7_verification_edges.txt
M8A_CONFIG ?= config/milestone_8a_verification.yaml
M8B_CONFIG ?= config/milestone_8b_verification.yaml

.PHONY: help bootstrap verify registry select meshes assets preview coupling-inspect operator-qa simulate milestone6-readiness milestone7-readiness milestone8a-readiness milestone8b-readiness validate-manifest test smoke all

COUPLING_INSPECT_ARGS ?=
SIMULATE_ARGS ?=

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
		'coupling-inspect   Build static offline coupling inspection report(s)' \
		'operator-qa        Build static offline operator QA report(s)' \
		'simulate           Execute manifest-driven simulator runs and write result bundles' \
		'milestone6-readiness Run the Milestone 6 verification pass and publish a readiness report' \
		'milestone7-readiness Run the Milestone 7 integration verification pass and publish a readiness report' \
		'milestone8a-readiness Run the Milestone 8A canonical stimulus integration verification pass and publish a readiness report' \
		'milestone8b-readiness Run the Milestone 8B world-to-retina integration verification pass and publish a readiness report' \
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

coupling-inspect:
	$(PYTHON) scripts/08_coupling_inspection.py --config $(CONFIG) $(COUPLING_INSPECT_ARGS)

operator-qa:
	$(PYTHON) scripts/06_operator_qa.py --config $(CONFIG)

simulate:
	$(PYTHON) scripts/run_simulation.py --config $(CONFIG) --manifest $(MANIFEST) --schema $(SCHEMA) --design-lock $(DESIGN_LOCK) $(SIMULATE_ARGS)

milestone6-readiness:
	$(PYTHON) scripts/07_milestone6_readiness.py --config $(M6_CONFIG)

milestone7-readiness:
	$(PYTHON) scripts/09_milestone7_readiness.py --config $(M7_CONFIG) --edges-file $(M7_EDGE_FILE)

milestone8a-readiness:
	$(PYTHON) scripts/11_milestone8a_readiness.py --config $(M8A_CONFIG)

milestone8b-readiness:
	$(PYTHON) scripts/13_milestone8b_readiness.py --config $(M8B_CONFIG)

validate-manifest:
	$(PYTHON) scripts/04_validate_manifest.py --manifest $(MANIFEST) --schema $(SCHEMA) --design-lock $(DESIGN_LOCK)

test:
	$(PYTHON) -m unittest discover -s tests -v

smoke: test validate-manifest

all: verify registry select meshes assets
