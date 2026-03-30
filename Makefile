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
M9_CONFIG ?= config/milestone_9_verification.yaml
M10_CONFIG ?= config/milestone_10_verification.yaml
M11_CONFIG ?= config/milestone_11_verification.yaml
M12_CONFIG ?= config/milestone_12_verification.yaml
M13_CONFIG ?= config/milestone_13_verification.yaml
M14_CONFIG ?= config/milestone_14_verification.yaml
M15_CONFIG ?= config/milestone_15_verification.yaml
M11_READINESS_ARGS ?=
M12_READINESS_ARGS ?=
M13_READINESS_ARGS ?=
M14_READINESS_ARGS ?=
M15_READINESS_ARGS ?=
DASHBOARD_ARGS ?=
DASHBOARD_SESSION_METADATA ?=
DASHBOARD_EXPORT_ARGS ?=
SHOWCASE_ARGS ?=
SHOWCASE_PLAYER_ARGS ?=
SHOWCASE_SESSION_METADATA ?=
SHOWCASE_PLAYER_COMMAND ?= status

.PHONY: help bootstrap verify registry select meshes assets preview coupling-inspect operator-qa simulate suite-run suite-aggregate suite-report compare-analysis dashboard dashboard-open dashboard-export showcase-session showcase-player wave-inspect mixed-fidelity-inspect numerical-validate morphology-validate circuit-validate task-validate validation-ladder-package validation-ladder-smoke milestone6-readiness milestone7-readiness milestone8a-readiness milestone8b-readiness milestone9-readiness milestone10-readiness milestone11-readiness milestone12-readiness milestone13-readiness milestone14-readiness milestone15-readiness validate-manifest test smoke all

COUPLING_INSPECT_ARGS ?=
SIMULATE_ARGS ?=
SUITE_RUN_ARGS ?=
SUITE_AGGREGATE_ARGS ?=
SUITE_REPORT_ARGS ?=
COMPARE_ANALYSIS_ARGS ?=
WAVE_INSPECT_ARGS ?=
MIXED_FIDELITY_INSPECT_ARGS ?=
NUMERICAL_VALIDATE_ARGS ?=
MORPHOLOGY_VALIDATE_ARGS ?=
CIRCUIT_VALIDATE_ARGS ?=
TASK_VALIDATE_ARGS ?=
VALIDATION_LADDER_ARGS ?=
VALIDATION_LADDER_SMOKE_ARGS ?=

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
		'suite-run          Execute or preview a deterministic Milestone 15 experiment suite' \
		'suite-aggregate    Compute deterministic Milestone 15 suite rollups and CSV exports from a packaged suite inventory' \
		'suite-report       Generate deterministic Milestone 15 review tables, plots, and static HTML from a packaged suite inventory' \
		'compare-analysis  Compute experiment-level comparison analysis and package Milestone 12 exports' \
		'dashboard          Build the deterministic Milestone 14 dashboard shell from packaged local artifacts' \
		'dashboard-open     Build and open the deterministic Milestone 14 dashboard shell from local disk' \
		'dashboard-export   Export deterministic dashboard review artifacts from one packaged session' \
		'showcase-session  Package the deterministic Milestone 16 showcase rehearsal surface from packaged local artifacts' \
		'showcase-player   Drive a packaged Milestone 16 showcase session through the scripted player controls' \
		'wave-inspect       Run local surface-wave sweep and offline inspection report(s)' \
		'mixed-fidelity-inspect Run offline surrogate-versus-reference mixed-fidelity inspection' \
		'numerical-validate Run the Milestone 13 numerical-sanity validation suite' \
		'morphology-validate Run the Milestone 13 morphology-sanity validation suite' \
		'circuit-validate   Run the Milestone 13 circuit-sanity validation suite' \
		'task-validate      Run the Milestone 13 task-sanity validation suite' \
		'validation-ladder-package Package existing Milestone 13 layer bundles into one review/regression bundle' \
		'validation-ladder-smoke Run the deterministic packaged Milestone 13 smoke fixture and enforce the committed baseline' \
		'milestone6-readiness Run the Milestone 6 verification pass and publish a readiness report' \
		'milestone7-readiness Run the Milestone 7 integration verification pass and publish a readiness report' \
		'milestone8a-readiness Run the Milestone 8A canonical stimulus integration verification pass and publish a readiness report' \
		'milestone8b-readiness Run the Milestone 8B world-to-retina integration verification pass and publish a readiness report' \
		'milestone9-readiness Run the Milestone 9 baseline simulator integration verification pass and publish a readiness report' \
		'milestone10-readiness Run the Milestone 10 surface-wave integration verification pass and publish a readiness report' \
		'milestone11-readiness Run the Milestone 11 mixed-fidelity integration verification pass and publish a readiness report' \
		'milestone12-readiness Run the Milestone 12 task-layer integration verification pass and publish a readiness report' \
		'milestone13-readiness Run the Milestone 13 validation-ladder integration verification pass and publish a readiness report' \
		'milestone14-readiness Run the Milestone 14 dashboard integration verification pass and publish a readiness report' \
		'milestone15-readiness Run the Milestone 15 experiment-orchestration integration verification pass and publish a readiness report' \
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

suite-run:
	$(PYTHON) scripts/31_run_experiment_suite.py --config $(CONFIG) --schema $(SCHEMA) --design-lock $(DESIGN_LOCK) $(SUITE_RUN_ARGS)

suite-aggregate:
	$(PYTHON) scripts/32_suite_aggregation.py $(SUITE_AGGREGATE_ARGS)

suite-report:
	$(PYTHON) scripts/33_suite_report.py $(SUITE_REPORT_ARGS)

compare-analysis:
	$(PYTHON) scripts/20_experiment_comparison_analysis.py --config $(CONFIG) --manifest $(MANIFEST) --schema $(SCHEMA) --design-lock $(DESIGN_LOCK) $(COMPARE_ANALYSIS_ARGS)

dashboard:
	$(PYTHON) scripts/29_dashboard_shell.py build --config $(CONFIG) --manifest $(MANIFEST) --schema $(SCHEMA) --design-lock $(DESIGN_LOCK) $(DASHBOARD_ARGS)

dashboard-open:
	$(PYTHON) scripts/29_dashboard_shell.py build --config $(CONFIG) --manifest $(MANIFEST) --schema $(SCHEMA) --design-lock $(DESIGN_LOCK) --open $(DASHBOARD_ARGS)

dashboard-export:
	test -n "$(DASHBOARD_SESSION_METADATA)"
	$(PYTHON) scripts/29_dashboard_shell.py export --dashboard-session-metadata $(DASHBOARD_SESSION_METADATA) $(DASHBOARD_EXPORT_ARGS)

showcase-session:
	$(PYTHON) scripts/35_showcase_session.py build --config $(CONFIG) $(SHOWCASE_ARGS)

showcase-player:
	test -n "$(SHOWCASE_SESSION_METADATA)"
	$(PYTHON) scripts/35_showcase_session.py $(SHOWCASE_PLAYER_COMMAND) --showcase-session-metadata $(SHOWCASE_SESSION_METADATA) $(SHOWCASE_PLAYER_ARGS)

wave-inspect:
	$(PYTHON) scripts/15_surface_wave_inspection.py --config $(CONFIG) --manifest $(MANIFEST) --schema $(SCHEMA) --design-lock $(DESIGN_LOCK) $(WAVE_INSPECT_ARGS)

mixed-fidelity-inspect:
	$(PYTHON) scripts/18_mixed_fidelity_inspection.py --config $(CONFIG) --manifest $(MANIFEST) --schema $(SCHEMA) --design-lock $(DESIGN_LOCK) $(MIXED_FIDELITY_INSPECT_ARGS)

numerical-validate:
	$(PYTHON) scripts/23_numerical_validation.py --config $(CONFIG) --manifest $(MANIFEST) --schema $(SCHEMA) --design-lock $(DESIGN_LOCK) $(NUMERICAL_VALIDATE_ARGS)

morphology-validate:
	$(PYTHON) scripts/24_morphology_validation.py --config $(CONFIG) --manifest $(MANIFEST) --schema $(SCHEMA) --design-lock $(DESIGN_LOCK) $(MORPHOLOGY_VALIDATE_ARGS)

circuit-validate:
	$(PYTHON) scripts/25_circuit_validation.py --config $(CONFIG) --manifest $(MANIFEST) --schema $(SCHEMA) --design-lock $(DESIGN_LOCK) $(CIRCUIT_VALIDATE_ARGS)

task-validate:
	$(PYTHON) scripts/26_task_validation.py --config $(CONFIG) --manifest $(MANIFEST) --schema $(SCHEMA) --design-lock $(DESIGN_LOCK) $(TASK_VALIDATE_ARGS)

validation-ladder-package:
	$(PYTHON) scripts/27_validation_ladder.py package $(VALIDATION_LADDER_ARGS)

validation-ladder-smoke:
	$(PYTHON) scripts/27_validation_ladder.py smoke --baseline tests/fixtures/validation_ladder_smoke_baseline.json --enforce-baseline $(VALIDATION_LADDER_SMOKE_ARGS)

milestone6-readiness:
	$(PYTHON) scripts/07_milestone6_readiness.py --config $(M6_CONFIG)

milestone7-readiness:
	$(PYTHON) scripts/09_milestone7_readiness.py --config $(M7_CONFIG) --edges-file $(M7_EDGE_FILE)

milestone8a-readiness:
	$(PYTHON) scripts/11_milestone8a_readiness.py --config $(M8A_CONFIG)

milestone8b-readiness:
	$(PYTHON) scripts/13_milestone8b_readiness.py --config $(M8B_CONFIG)

milestone9-readiness:
	$(PYTHON) scripts/14_milestone9_readiness.py --config $(M9_CONFIG)

milestone10-readiness:
	$(PYTHON) scripts/16_milestone10_readiness.py --config $(M10_CONFIG)

milestone11-readiness:
	$(PYTHON) scripts/19_milestone11_readiness.py --config $(M11_CONFIG) $(M11_READINESS_ARGS)

milestone12-readiness:
	$(PYTHON) scripts/22_milestone12_readiness.py --config $(M12_CONFIG) $(M12_READINESS_ARGS)

milestone13-readiness:
	$(PYTHON) scripts/28_milestone13_readiness.py --config $(M13_CONFIG) $(M13_READINESS_ARGS)

milestone14-readiness:
	$(PYTHON) scripts/30_milestone14_readiness.py --config $(M14_CONFIG) $(M14_READINESS_ARGS)

milestone15-readiness:
	$(PYTHON) scripts/34_milestone15_readiness.py --config $(M15_CONFIG) $(M15_READINESS_ARGS)

validate-manifest:
	$(PYTHON) scripts/04_validate_manifest.py --manifest $(MANIFEST) --schema $(SCHEMA) --design-lock $(DESIGN_LOCK)

test:
	$(PYTHON) -m unittest discover -s tests -v

smoke: test validate-manifest

all: verify registry select meshes assets
