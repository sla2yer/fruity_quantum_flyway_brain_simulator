CONFIG ?= config/local.yaml

verify:
	python scripts/00_verify_access.py --config $(CONFIG)

select:
	python scripts/01_select_subset.py --config $(CONFIG)

meshes:
	python scripts/02_fetch_meshes.py --config $(CONFIG)

assets:
	python scripts/03_build_wave_assets.py --config $(CONFIG)

all: verify select meshes assets
