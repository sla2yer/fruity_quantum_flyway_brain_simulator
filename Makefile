PYTHON ?= python3
CONFIG ?= config/local.yaml
MANIFEST ?= manifests/examples/milestone_1_demo.yaml
SCHEMA ?= schemas/milestone_1_experiment_manifest.schema.json
DESIGN_LOCK ?= config/milestone_1_design_lock.yaml

verify:
	$(PYTHON) scripts/00_verify_access.py --config $(CONFIG)

select:
	$(PYTHON) scripts/01_select_subset.py --config $(CONFIG)

meshes:
	$(PYTHON) scripts/02_fetch_meshes.py --config $(CONFIG)

assets:
	$(PYTHON) scripts/03_build_wave_assets.py --config $(CONFIG)

validate-manifest:
	$(PYTHON) scripts/04_validate_manifest.py --manifest $(MANIFEST) --schema $(SCHEMA) --design-lock $(DESIGN_LOCK)

all: verify select meshes assets
