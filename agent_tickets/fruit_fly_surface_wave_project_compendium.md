# Fruit Fly Surface-Wave Project Compendium

Compiled project notes for planning, scientific framing, circuit definition, input design, BCI relevance, optimization, and presentation.

## Compilation Notes

This markdown file compiles and lightly normalizes the uploaded project notes into one document.  
Duplicate source versions were merged where appropriate:
- `Milestone 2 details` overlapped with `Milestone 2 Circuit Boundary.txt`
- `fruit_fly_wave_simulation_milestones` is the full roadmap source document

## Table of Contents

- [Executive Summary and Judge Pitch](#executive-summary-and-judge-pitch)
- [Master Roadmap and Team Split](#master-roadmap-and-team-split)
- [Project Framing and Build Strategy](#project-framing-and-build-strategy)
- [Locked Hypothesis and Milestone 1 Burden of Proof](#locked-hypothesis-and-milestone-1-burden-of-proof)
- [Milestone 2 Circuit Boundary](#milestone-2-circuit-boundary)
- [Input Method in Simulation](#input-method-in-simulation)
- [BCI Relevance and Technical Gap](#bci-relevance-and-technical-gap)
- [Milestone 11–13 Optimization and Runaway-to-Infinity Fix](#milestone-1113-optimization-and-runaway-to-infinity-fix)

## Executive Summary and Judge Pitch

_Source: `Project Milestone Review.txt`_

**90-second pitch**

In less than three days, we took a pretty ambitious neuroscience idea and turned it into a real experimental software system.

The core question behind this project is whether neural computation might depend on more than just point-to-point firing. Our hypothesis is that signals traveling across the physical structure of neurons — what we model as surface-wave dynamics on neuronal morphology — can meaningfully shape how a circuit processes information.

To test that, we did not just build a solver. We built the full experimental scaffold around it. We locked the scientific claim, defined a biologically defensible fruit fly visual subcircuit, created reproducible data registries and subset selection tools, converted neuron morphology into wave-ready geometry and operators, built the baseline simulator for fair comparison, and then integrated the first working surface-wave simulation path on top of that.

What makes this valid is that the system is structured as an actual falsifiable experiment. The same circuit and same stimulus can be run through both a conventional baseline model and our surface-wave model, with shared readouts and milestone-specific readiness checks. So even though we did not finish the full end-to-end scientific proof, we *did* build the framework needed to test the idea rigorously.

So the achievement here is not just code volume — it is that in under three days, this project moved from concept to a reproducible, testable research platform.

Here’s a slightly punchier ending line you could use:

**“We may not have finished the full scientific result yet, but we did finish the hard part of turning a risky idea into a real experiment.”**

## Master Roadmap and Team Split

_Source: `fruit_fly_wave_simulation_milestones`_

### Fruit Fly Surface-Wave Simulation Roadmap

### Detailed milestones with programming-heavy vs math/physics-heavy split
This roadmap assumes the female FAFB FlyWire dataset is the structural source of truth, the visual system is the main simulated domain, and the rest of the brain is mostly used as context rather than fully simulated.

#### The core project idea is:

Build a connectome-constrained fruit fly visual simulation where selected neurons carry surface-wave dynamics across their morphology, driven by a synthetic visual scene generator, and presented through a strong interactive UI / analysis layer.

#### How to read this plan

##### Workload labels
Programming-heavy = data plumbing, APIs, asset pipelines, engine implementation, scene generation, UI, orchestration, reproducibility
Math/physics-heavy = model formulation, numerical operators, stability, wave equations, discretization choices, validation metrics, analysis design
Shared = requires both perspectives at the same time

##### Suggested team split
Jack lead = programming-first milestone
Grant lead = math/physics-first milestone
Shared lead = co-design milestone where both of you should be in the room

##### Important principle
Do not split the project into “Jack builds everything” and “Grant only checks equations.”
The better pattern is:

Jack owns infrastructure, tooling, engine wiring, scene system, UI, and experiment automation
Grant owns the wave model, discretization choices, coupling assumptions, stability reasoning, and validation logic
both of you meet at the interfaces:
subset definition
simulation state definition
operator format
synapse coupling API
output metric schema
UI data contract

#### Top-level tracks

##### Track A — Data / Infrastructure / Engine / UI
Mostly Jack

data registry
subset tooling
geometry fetching and caching
mesh/skeleton asset pipeline
scene generator
simulator software architecture
UI and visual analytics
orchestration and demo packaging

##### Track B — Wave Mathematics / Numerical Methods / Validation
Mostly Grant

define the wave model
choose state variables
define operators and coupling
determine stability constraints
design validation metrics
interpret readouts physically
propose ablations that test the hypothesis

##### Track C — Integration / Scientific Story
Shared

choose the circuit
decide what counts as success
decide what phenomenon the demo proves
interpret baseline vs wave differences
shape the final demo narrative

#### Milestone summary table

### Detailed milestone plan

#### Milestone 1 — Freeze the scientific claim, demo claim, and output contract
Workload split: Shared, leaning math/physics
 Suggested lead: Grant
 Why it matters: This prevents the project from becoming a cool visualization with no testable point, and locks the Milestone 1 scientific and artifact contract before the simulator is overbuilt.

##### Locked hypothesis
Morphology-resolved surface dynamics constitute an additional intraneuronal computational degree of freedom, capable of shaping circuit input-output transformations through distributed spatiotemporal state on neuronal structure.

##### Milestone 1 operational claim
In a connectome-constrained Drosophila visual motion circuit, adding a morphology-resolved surface state should produce small but reproducible, geometry-dependent departures in shared circuit observables relative to fair point/reduced-neuron baselines.
Milestone 1 is about detectability, distinctness, and falsifiability of a small effect.
 It is not yet about broad superiority claims.

##### What the wave model is allowed to add
surface-localized inputs on explicit T4/T5 morphology regions
surface propagation over a morphology graph
local timing structure from geodesic separation, spread, damping, and optional mild anisotropy
a shared downstream readout so comparison to baselines stays fair

##### What it must not add
extra connectome edges
different synapse signs
arbitrary extra weights or a larger tuning budget
a decoder or readout unavailable to the baselines
hand-fitted per-synapse delays granted only to the surface model

##### Baseline definitions
P0: canonical point baseline using passive leaky linear non-spiking single-compartment neurons matched to the same circuit and readout
P1: stronger reduced baseline using an effective-point or reduced-compartment model with explicit synaptic integration current or explicit delay structure

##### Core questions to answer
What exactly is the claim about waves?
 In a connectome-constrained Drosophila visual motion circuit, adding a morphology-resolved surface state should produce small but reproducible, geometry-dependent departures in shared circuit observables relative to fair point/reduced-neuron baselines.
What should the wave model do differently than a baseline point-neuron model?
 It should add distributed, morphology-bound intraneuronal state and nothing else that can trivially explain the result.
What observable will convince you that the surface model matters?
 A geometry-sensitive shared-output effect, preferably on null-direction suppression or response latency, that survives a stronger reduced baseline.
What will the demo show in under a minute?
 The same stimulus driving the same circuit in two models, producing a small but real output difference that shrinks or disappears when geometry is shuffled.

##### Primary observable and companion observables
Core observable: geometry-sensitive shared-output effect
Primary observable: geometry-sensitive null-direction suppression
Main companion observable: response latency
Secondary shared readout: direction selectivity index

##### Evidence ladder
Weak: the surface model shows propagation or spread that the point model cannot show by construction
Moderate: the surface model changes a shared readout such as null-direction suppression, latency, or DSI
Strong: the shared-readout change shrinks or disappears when morphology or synapse topology is shuffled
Very strong: the effect survives the stronger reduced baseline P1

##### One-minute demo story
0–10 s: show a simple moving edge across a small retinotopic patch
10–25 s: split screen with matched point baseline on the left and surface model on the right for the same T4/T5-centered circuit
25–38 s: overlay shared output traces and highlight a small shift in null-direction suppression or latency
38–50 s: toggle intact versus shuffled synapse landing geometry and show the wave-specific difference collapse or materially shrink
50–60 s: freeze on a summary panel captioned “Small, causal, geometry-dependent computational effect.”

##### Must-show plots / UI states
stimulus overview for the simple moving-edge input
split view showing baseline scalar activity versus surface-state activity on morphology
shared output trace overlay for the same circuit and stimulus
null-direction suppression comparison plot
latency shift comparison plot
intact versus shuffled topology ablation comparison plot
P0 versus P1 challenge-baseline comparison plot
final milestone decision panel summarizing the four decision-rule checks

##### Non-goals
whole-brain intelligence claims
broad benchmark superiority
naturalistic cinematic scenes
a wall of metrics
a “look how pretty the waves are” reel
Milestone 2+ simulator build-out beyond what is required to lock the design and output contract

##### Jack owns
writing the project brief into a versioned document
turning success criteria into config fields / experiment metadata
creating the experiment manifest schema
making sure the claim maps onto actual software outputs
defining the required plots, UI states, and result-bundle fields for Milestone 1 checkoff

##### Grant owns
defining the locked wave hypothesis
defining expected signatures:
phase gradients
propagation delays
coherence
geometry-sensitive spread
task-level differences
defining which effects count as nontrivial
defining the Milestone 1 decision rule and falsification logic

##### Done when
there is a one-page written brief in-repo
the locked hypothesis is preserved verbatim
the narrower Milestone 1 operational claim is preserved
P0 and P1 baseline definitions are explicit
the primary observable is centered on geometry-sensitive null-direction suppression
response latency is defined as the main companion observable
the one-minute demo story is defined
the must-show plots and UI states are defined
the decision rule is explicit and traceable to repo outputs

##### Milestone 1 decision rule
Milestone 1 is successful only if all four hold:
nonzero shared-output effect
geometry dependence
survival against a stronger reduced baseline
stability across seeds and modest parameter changes
This version is much tighter than the current section because it keeps the roadmap tone, but now locks the real burden of proof instead of leaving Milestone 1 as a high-level placeholder.

#### Milestone 2 — Lock the circuit boundary
Workload split: Shared, leaning programming
 Suggested lead: Jack

##### Goal
Choose and freeze the smallest scientifically defensible circuit boundary for the first real simulation pass.

##### Locked circuit decision
Milestone 2 is locked to a central-equatorial local motion patch built around one horizontal ON/OFF channel.
The default active graph should use the balanced local-motion subnetwork:
surface-simulated: T4a and T5a
reduced active inputs: Mi1, Tm3, Mi4, Mi9, Tm1, Tm2, Tm4, Tm9
abstracted upstream drive: R1–R6 photoreceptors and lamina L1/L2/L3
readout stop point: T4a/T5a axon terminals in lobula plate layer 1
Only the columns inside the selected stimulus footprint should be included, plus a one-ring halo so each active detector retains its local sampling neighborhood.

##### Locked scope structure
Context graph
 Whole FAFB female brain metadata and connectivity reference, plus all optic-lobe and central-brain structures outside the selected motion subnetwork.
Candidate graph
 The locked active graph, abstracted upstream drive nodes, context-only direct partners, and downstream promotion candidates for later milestones.
Active graph
 A single central-equatorial contiguous patch containing:
T4a and T5a in surface mode
direct ON/OFF feedforward partners in reduced mode
terminal readout at lobula plate layer 1

##### Context-only for Milestone 2
Keep these as context-only, not active simulation:
C3, CT1, TmY15, LT33, Tm23, and same-subtype T4/T5 recurrent tip partners
T4b, T5b, LPi candidates, and tangential-cell readout candidates
the rest of the optic lobe and broader brain

##### Explicit exclusions for Milestone 2
Do not include the following in the active simulation boundary:
R7/R8 color and polarization channels
explicit phototransduction or full lamina dynamics
additional T4/T5 direction layers beyond the chosen horizontal channel
LPi/LPTC inventory or wide-field tangential-cell circuitry
object / looming-specialized visual branches
whole-eye or full-field column tiling
central-brain or behavior-loop active dynamics

##### Locked first vertical slice
The first end-to-end Milestone 2 subnetwork should be:
T4a/T5a + direct ON/OFF reduced inputs + central patch + terminal readout
The first test stimuli should stay simple and local, using bright and dark moving edges or apparent-motion bar pairs along the chosen horizontal axis.

##### Promotion triggers for later milestones
Promote additional circuitry only when it becomes the leading limitation:
promote CT1 if OFF-pathway fit or velocity-tuning residuals dominate
promote L1/L2/L3 point models if the upstream delay abstraction becomes the main criticism
promote LPi / downstream tangential-cell readout only after a clear T4/T5-level effect is established
expand the retinotopic patch only when the target shifts from local motion computation to optic-flow or larger-field behavior
add additional T4/T5 direction layers only after the first horizontal-axis result is secure

##### Jack owns
subset extraction pipeline for the locked boundary
root ID manifests for active, candidate, and context graphs
role labeling for every included neuron
summary reports and previews for the locked subnetwork

##### Grant owns
sign-off on the locked active cell classes
sign-off on what remains reduced, abstracted, context-only, or excluded
scientific review of any proposed promotion beyond the locked boundary

##### Done when
there is a named manifest for the locked boundary
every active neuron has a role label and fidelity class
every relevant non-active neuron is explicitly tagged as context-only or excluded
the Milestone 2 boundary is frozen as the default first simulation pass
both of you can explain why this boundary is sufficient for the first morphology-sensitive test

#### Milestone 3 — Build the data registry and provenance layer
Workload split: Programming-heavy
Suggested lead: Jack

##### Goal
Create one canonical local dataset that every script uses.

##### Registry should contain
root ID
cell type / resolved type
class / subclass
neurotransmitter prediction
neuropils
side
proofread status
snapshot/materialization version
source file
role in project:
context-only
point-simulated
skeleton-simulated
surface-simulated

##### Agent responsibilities:
CSV ingestion and normalization
schema design
table joins
manifest validation
version pinning
reproducibility commands
sanity-checking the biological semantics of fields
helping define what annotations are scientifically relevant
flagging missing metadata needed for later coupling/model design

##### Done when
one command builds the registry
every downstream script reads from the registry
the same experiment can be reproduced from a manifest

#### Milestone 4 — Turn subset selection into a proper tool
Workload split: Programming-heavy
Suggested lead: Jack

##### Goal
Make subset design fast, reproducible, and explorable.

##### Features
selection by cell type
selection by neuropil
selection by visual column
selection by upstream/downstream relations
exclusion rules
neuron-budget caps
named presets like:
motion_minimal
motion_medium
motion_dense

##### Jack owns
CLI / config-driven subset generator
filtering logic
graph summaries
small preview visualizations
exporting manifests and reports

##### Grant owns
defining scientifically meaningful presets
checking that subset boundaries preserve the intended behavior
suggesting ablation-oriented subsets

##### Done when
multiple subsets can be generated automatically
each subset produces a manifest and stats file
you can switch simulator inputs by changing only a config

#### Milestone 5 — Build the geometry ingestion and multiresolution morphology pipeline

##### Goal
Fetch, store, simplify, and standardize neuron geometry for simulation.

##### Asset hierarchy
For each active neuron, generate:

raw mesh
simplified mesh
skeleton
surface graph
patch graph
derived geometric descriptors

##### Agent implements:
mesh download scripts
caching
file formats
simplification pipeline
asset naming/versioning
geometry QA tools
preview viewers or notebooks

##### Agent provides advice on in a mark down file:
advising on what simplification can preserve wave-relevant geometry
identifying which geometric descriptors matter for propagation
defining acceptable error bounds for coarse geometry

##### Done when
active neurons have consistent geometry assets
simplification is automated and reproducible
raw vs simplified vs patchified geometry can be visualized together

#### Milestone 6 — Construct surface discretizations and operators
Workload split: Math/physics-heavy
Suggested lead: Grant
Implementation support: Jack

##### Goal
Turn neuron surfaces into simulation-ready numerical objects.

##### Build
adjacency structures
geodesic neighborhoods
graph or cotangent Laplacian
patch graph
local tangent frames
boundary masks
optional anisotropy tensors
fine-to-coarse transfer operators

##### Jack owns
sparse matrix construction code
asset serialization
performance optimization
operator test harnesses
visualization of operator outputs on meshes

##### Grant owns
choosing the correct discretization family
deciding whether to use graph-based or mesh-based operators
specifying stability-relevant properties
defining what should be conserved or damped
checking whether the operator is faithful enough to the intended physics

##### Done when
a pulse can be initialized on a single neuron
propagation on the surface is numerically stable
coarse and fine operators can be compared
operator quality metrics exist

#### Milestone 7 — Map synapses and define inter-neuron coupling
Workload split: Shared, leaning math/physics
Suggested lead: Shared

##### Goal
Turn connectome edges into transfers between neuron surface states.

##### Need to define
where synaptic input lands on the receiving surface
where output is read on the presynaptic neuron
whether coupling is:
point-to-point
patch-to-patch
distributed patch cloud
how synaptic sign and delay are handled
how multiple synapses aggregate

##### Jack owns
synapse table processing
locating nearest patches / skeleton nodes
building fast lookup structures
serializing coupling maps
coupling inspection tools

##### Grant owns
defining coupling kernels
choosing delay models
deciding how synaptic transfer modifies the surface state
determining whether coupling is instantaneous, filtered, nonlinear, etc.

##### Done when
any edge can be inspected and visualized
the simulator knows where and how input transfers between neurons
coupling rules are configurable and versioned

#### Milestone 8 — Build the visual input stack
This milestone is intentionally split because different parts belong to different people.

##### Milestone 8A — Canonical stimulus library
Workload split: Programming-heavy
Suggested lead: Jack

Build generators for:

flashes
moving bars
drifting gratings
looming stimuli
expansion/contraction flow
rotating flow
translated edge patterns

###### Jack owns
stimulus generation code
parameterized stimulus configs
playback tooling
serialization for experiment reuse

###### Grant owns
making sure the stimulus set is scientifically meaningful
defining which stimuli are best for isolating wave effects

###### Done when
standard stimuli are callable from config
stimuli can be recorded and replayed

##### Milestone 8B — Retinal / ommatidial sampler
Workload split: Shared, leaning math/physics
Suggested lead: Grant
Implementation support: Jack

###### Goal
Map world-space visual stimuli into the fly’s retinotopic input representation.

###### Jack owns
code for image sampling / lattice projection
coordinate system conversions
efficient frame generation
integration with scene playback

###### Grant owns
defining the retinotopic abstraction
deciding how to approximate the fly’s visual sampling lattice
choosing what resolution and geometry are scientifically defensible
determining how stimuli map into early visual units

###### Done when
the same scene can be converted into retinal input frames consistently
you can visualize both the world scene and the sampled fly-view representation

##### Milestone 8C — Scene generator
Workload split: Programming-heavy
Suggested lead: Jack

###### Goal
Create real visual environments instead of only lab stimuli.

###### Scene system should support
2D / 2.5D procedural scenes
moving objects
textured backgrounds
ego-motion
depth layers
scripted events
camera presets

###### Jack owns
rendering / scene code
asset pipelines
scene scripting
replay system
integration with the retinal sampler

###### Grant owns
suggesting the most meaningful physical motion scenarios
identifying scene classes that should expose wave-related differences

###### Done when
a configurable scene can drive the visual input stack end-to-end
scenes can be saved, replayed, and compared

#### Milestone 9 — Build the baseline non-wave simulator
Workload split: Programming-heavy
Suggested lead: Jack

##### Goal
Create a control simulator using simpler neuron dynamics.

##### Why it matters
The wave model is far more convincing if the exact same circuit can be run in:

baseline
surface_wave

##### Jack owns
simulator framework
state update loops
connectivity integration
I/O schema
logging
alignment with the UI and metrics layer

##### Grant owns
defining a fair baseline model
making sure the baseline is not a strawman
helping choose comparable state variables and readouts

##### Done when
the same experiment manifest runs in baseline mode
outputs line up with wave-mode outputs for comparison
the UI can switch between both modes

#### Milestone 10 — Implement the surface-wave dynamics engine
Workload split: Math/physics-heavy
Suggested lead: Grant
Implementation support: Jack

##### Goal
Define and implement the actual wave model.

##### Must define
state variable(s) on the surface
propagation term
damping term
refractory / recovery behavior
synaptic source injection
nonlinearities
optional anisotropy
optional branching effects

##### Candidate model families
damped wave system
diffusion-like neural field
excitable medium
reaction–diffusion system
hybrid field + readout system

##### Jack owns
engine implementation
performance engineering
parameter config plumbing
data structures for stepping the system
GPU / sparse solver integration if needed

##### Grant owns
selecting the model family
deriving or choosing equations
reasoning about stability
defining parameter ranges
specifying what behaviors are physically meaningful vs numerical artifacts

##### Done when
a single-neuron wave test works
multi-neuron propagation works
the engine can run under actual visual input
parameters can be swept systematically

#### Milestone 11 — Add hybrid morphology classes
Workload split: Shared, leaning programming
Suggested lead: Jack

##### Goal
Support multiple fidelity levels in one simulation.

##### Classes
surface neuron — full mesh simulation
skeleton neuron — graph approximation
point neuron — coarse functional placeholder

##### Jack owns
architecture for multi-fidelity neurons
interfaces between fidelity classes
consistent serialization of state
routing between coupling modes

##### Grant owns
defining what each fidelity class is allowed to approximate
setting rules for when a neuron should be promoted/demoted in fidelity
checking whether lower-fidelity surrogates preserve the needed behavior

##### Done when
different fidelity classes coexist in one run
upgrading a neuron does not require rewriting the simulator
mixed-fidelity runs preserve stable semantics

#### Milestone 12 — Define readouts and task layer
Workload split: Shared, leaning math/physics
Suggested lead: Shared

##### Goal
Turn simulation output into interpretable, quantitative results.

##### Readouts to implement
direction selectivity
ON/OFF selectivity
optic-flow estimate
motion vector estimate
latency
synchrony / coherence
phase gradient statistics
wavefront speed / curvature
patch activation entropy

##### Jack owns
readout pipeline implementation
data export formats
reusable analysis functions
hooks into the UI
experiment result packaging

##### Grant owns
defining which metrics actually test the hypothesis
designing how to measure wave-specific structure
interpreting whether differences are meaningful
proposing null tests and metric sanity checks

##### Done when
every run emits a standard result bundle
at least one task metric is automated
baseline vs wave comparisons are quantitative, not just visual

#### Milestone 13 — Build the validation ladder
Workload split: Math/physics-heavy
Suggested lead: Grant

##### Goal
Prove the simulator is not only running, but behaving sensibly.

##### Validation layers

###### 13A — Numerical sanity
timestep stability
energy / amplitude behavior
boundary condition behavior
operator correctness
mesh-resolution sensitivity

###### 13B — Morphology sanity
shape-dependent propagation
bottleneck / branching effects
simplification sensitivity
patchification sensitivity

###### 13C — Circuit sanity
plausible delay structure
sign behavior
aggregation behavior
pathway asymmetry under motion stimuli

###### 13D — Task sanity
stable task outputs
reproducible differences between baseline and wave mode
robustness under perturbation / noise

##### Jack owns
automated test harnesses
regression scripts
notebooks / reports
CI integration if feasible

##### Grant owns
defining the actual validation criteria
deciding which failures are fatal
interpreting whether observed behavior is physically/model-wise plausible

##### Done when
each validation layer has automated tests or notebooks
failures produce actionable diagnostics
model changes can be regression-checked

#### Milestone 14 — Build the UI and analysis dashboard
Workload split: Programming-heavy
Suggested lead: Jack

##### Goal
Create a polished interface that makes the project understandable.

##### UI panes
Scene pane — what the fly sees
Circuit pane — active subset and connectivity context
Morphology pane — neuron meshes/skeletons with activity overlay
Time-series pane — traces and comparisons
Analysis pane — metrics, heatmaps, ablations, phase maps

##### Jack owns
application architecture
rendering and interaction
time scrubber
overlay systems
baseline vs wave comparison mode
export tools for images / video / metrics

##### Grant owns
defining what scientific overlays are most useful
making sure the visualizations reflect the intended quantities
suggesting the plots needed to support the claim

##### Done when
a user can click neurons and inspect them
the UI supports replay and comparison
the project is understandable without reading the code

#### Milestone 15 — Build experiment orchestration and ablations
Workload split: Programming-heavy
Suggested lead: Jack

##### Goal
Run experiments systematically instead of by hand.

##### Experiment dimensions
scene type
motion direction
speed
contrast
noise level
active subset
wave kernel
coupling mode
mesh resolution
timestep / solver settings
fidelity class

##### Required ablations
no waves
waves only on chosen cell classes
no lateral coupling
shuffled synapse locations
shuffled morphology
coarser geometry
altered sign or delay assumptions

##### Jack owns
batch runner
config sweeps
result indexing
output storage conventions
summary tables and auto-generated comparison plots

##### Grant owns
choosing the scientifically meaningful ablations
defining which ablations are most diagnostic
interpreting the results

##### Done when
whole suites run from manifest files
ablations are reproducible
results are easy to compare

#### Milestone 16 — Polish the demo narrative and showcase mode
Workload split: Shared, leaning programming
Suggested lead: Jack

##### Goal
Turn the system into a coherent hackathon demo.

##### Target showcase flow
choose a visual scene
show the fly-view / sampled input
show the active visual subset
show activity propagation
compare baseline and wave mode
highlight one phenomenon unique to the wave model
show a clean summary analysis

##### Jack owns
scripted demo mode
saved presets
replay flow
camera transitions
polished UI state
exportable visuals

##### Grant owns
choosing the most convincing scientific comparisons
defining the narrative around why the wave version matters
making sure the highlighted effect is not a misleading artifact

##### Done when
someone unfamiliar with the code can follow the whole story
the demo feels intentional and smooth
the final effect shown is scientifically defensible

#### Milestone 17 — Extend to whole-brain context views
Workload split: Programming-heavy
Suggested lead: Jack

##### Goal
Show where the active visual circuit sits inside the larger female brain context.

##### Add
whole-brain connectivity context views
downstream / upstream graph overlays
context-only nodes in network views
optional simplified downstream readout modules

##### Jack owns
graph visualization
context queries
scalable UI representations
linking active subset to whole-brain metadata

##### Grant owns
deciding which broader context relationships are scientifically worth showing
identifying meaningful downstream pathways for interpretation

##### Done when
the active visual subset can be viewed in larger brain context
context enriches the story without bloating the simulator

#### Recommended division of labor by phase

##### Phase 1 — Project foundation
Jack

Milestones 2, 3, 4
data registry
subset selection
manifest schema

Grant

Milestone 1
initial scientific claim
candidate observables
wave-model shortlist

Shared checkpoint

finalize the active visual subset
finalize what outputs matter

##### Phase 2 — Geometry and numerics foundation
Jack

Milestone 5
operator implementation support for Milestone 6
asset QA tooling

Grant

Milestone 6
operator design
stability reasoning
mesh/patch representation choice

Shared checkpoint

agree on the state representation and operator API

##### Phase 3 — Circuit coupling and inputs
Jack

implementation-heavy parts of Milestones 7 and 8
synapse lookup tooling
stimulus and scene system
retinal frame pipeline implementation

Grant

coupling kernels
delays
retinal abstraction
input interpretation assumptions

Shared checkpoint

one end-to-end input frame reaches the chosen circuit

##### Phase 4 — Baseline vs wave simulator
Jack

Milestone 9
implementation-heavy parts of Milestone 10
logging and data plumbing

Grant

model formulation for Milestone 10
stability criteria
parameter range selection

Shared checkpoint

same experiment runs in both baseline and wave mode

##### Phase 5 — Evaluation and presentation
Jack

Milestones 14, 15, 16, 17
UI
orchestration
exports
showcase mode

Grant

Milestones 12 and 13
metrics
validation logic
result interpretation

Shared checkpoint

the final demo shows one quantitative and one visual advantage of the wave model

#### Best end-to-end vertical slice
Before expanding the scope, aim for this first complete slice:

one motion-focused visual subset
one canonical visual stimulus family
one scene-generator scenario
one baseline simulator
one wave simulator
one quantitative metric
one polished comparison UI
one “wow” morphology activity visualization

This is the minimum complete system that proves the architecture.

#### Suggested interface contracts between Jack and Grant
To keep collaboration smooth, define these interfaces early.

##### 1. Subset manifest contract
A config format that says:

which neurons are included
what fidelity class each neuron uses
which scene/stimulus is used
which readouts are active

##### 2. Operator contract
A format for:

per-neuron operators
patch graphs
transfer operators
boundary conditions
discretization metadata

##### 3. Wave model contract
Grant defines:

state variables
update equations
parameters
expected constraints

Jack implements:

solver interface
stepping engine
serialization
profiling

##### 4. Result bundle contract
Every run should emit:

metadata
per-neuron / per-patch state summaries
task readouts
validation metrics
comparison-ready outputs

##### 5. UI data contract
The simulator should expose:

scene frames
retinal input
neuron activity overlays
traces
summary metrics
comparison results

#### Strong recommendation
If you ever have to choose where to spend effort, bias toward this split:

##### Jack should bias toward
getting end-to-end pipelines working
making every stage reproducible
making the UI excellent
making the demo feel alive

##### Grant should bias toward
making the wave model worth believing
keeping the operators and coupling scientifically honest
designing the validation ladder
defining the strongest comparisons and ablations

That division plays to both of your strengths and keeps the project from collapsing into either:

a great demo with weak science, or
a deep model with no usable presentation.

#### Final build order recommendation
Milestone 1
Milestone 2
Milestone 3
Milestone 4
Milestone 5
Milestone 6
Milestone 8A / 8B in parallel with 7
Milestone 9
Milestone 10
Milestone 11
Milestone 12
Milestone 13
Milestone 8C if not already complete
Milestone 14
Milestone 15
Milestone 16
Milestone 17

If you want, this can be split next into:

a GitHub issues backlog
a Grant vs Jack task board
or a dependency graph / Kanban structure

## Project Framing and Build Strategy

_Source: `Fruit Fly Brain Mapping.txt`_

The right mental model is **whole-brain context, subset simulation**. That fits the FAFB female release well: FlyWire Codex’s FAFB v783 snapshot is the female adult fly brain with 139,255 neurons and 3,732,460 connections, and Codex already exposes visual-specific resources like a Visual Cell Types Catalog and Visual Columns Map. Codex’s bulk downloads are static proofread snapshots with a 5-synapse threshold for connectivity, while live queries go through CAVE; meshes are not bulk-downloaded from Codex, but per-segment meshes are available programmatically and precomputed skeletons are available for proofread public neurons. ([codex.flywire.ai](https://codex.flywire.ai/fafb?utm_source=chatgpt.com))

I’d also make the default target **the visual motion pathway**, not the whole brain and not olfaction. There is already a strong precedent for this: the 2024 connectome-constrained fly visual model used 64 cell types arranged over a 721-column hexagonal lattice, spanning 45,669 neurons, and was trained on optic-flow estimation from video sequences sampled onto that lattice. The official `flyvis` implementation explicitly supports pretrained models and custom stimuli, which makes it a great reference architecture for your input/task side even if your wave dynamics are completely different. ([nature.com](https://www.nature.com/articles/s41586-024-07939-3))

Here’s the milestone plan I’d follow.

### Milestone 1 — Freeze the scientific claim and demo claim

You need one sentence for the science and one sentence for the demo.

Science claim:
“Wave-like propagation on neuron surfaces changes or enriches the functional behavior of a connectome-constrained fly visual circuit.”

Demo claim:
“A user can place the fly in a synthetic visual scene, watch input flow into a selected visual circuit, and compare classical point-like dynamics versus surface-wave dynamics in real time.”

Done when:
- you have a one-page design brief,
- you define the task outputs you care about,
- you define what would count as evidence that the wave model is doing something nontrivial.

That means choosing your core observables now:
- propagation speed,
- phase gradients,
- coherence across neighboring cells,
- delay structure,
- direction selectivity,
- motion discrimination,
- robustness under noise,
- interpretability in the UI.

### Milestone 2 — Lock the circuit boundary

Do **not** let “female whole brain” trick you into simulating everything. Build three nested scopes:

- **context graph**: whole-brain metadata and connectivity map
- **candidate graph**: all visual-system neurons relevant to your target behavior
- **active graph**: the neurons that actually run in the surface-wave sim

For the first serious version, I’d pick:
- photoreceptors / retinal input abstraction
- lamina
- medulla
- T4/T5 motion pathways
- lobula plate readout
- only the columns needed for the scene’s visible region

Done when:
- you have a YAML/JSON manifest listing included cell types and root IDs,
- every simulated neuron is tagged as “surface-simulated,” “point-simulated,” or “context-only,”
- you can explain why each included class exists.

This is where “map the rest, simulate the subset” becomes concrete.

### Milestone 3 — Build the data registry and provenance layer

Your repo should stop thinking in terms of random CSVs in folders and start thinking in terms of a data registry.

Create a canonical local registry that maps:
- root ID
- cell type / resolved type
- class / subclass
- neurotransmitter prediction
- side / neuropils
- source file
- materialization/snapshot version
- whether it is context-only or active

Done when:
- one command builds a single canonical neuron table,
- every downstream script uses that table instead of ad hoc CSV joins,
- you can reproduce the exact subset from scratch.

This is also where you should create **frozen experiment manifests**, because otherwise you’ll lose track of which subset and parameters produced which result.

### Milestone 4 — Subset selection tooling becomes a real product

Your current subset-selection script is just the beginning. Expand it into an actual subset designer.

It should support:
- selection by cell type
- selection by neuropil
- selection by visual column
- selection by upstream/downstream relation
- selection by known motion-pathway role
- exclusion rules
- max-neuron-budget caps

Use FlyWire Codex annotations and visual-column resources to make this ergonomic rather than manual. ([codex.flywire.ai](https://codex.flywire.ai/faq))

Done when:
- you can generate multiple named subsets like `motion_minimal`, `motion_medium`, `motion_dense`,
- each subset emits a manifest, stats report, and preview image,
- the selection logic is fully scripted.

### Milestone 5 — Geometry ingestion and multiresolution morphology pipeline

This is where the project becomes physically real.

For each active neuron:
- fetch mesh
- fetch skeleton
- store both
- simplify the mesh
- compute derived geometric features
- generate simulation-ready assets

This should become a **multiresolution representation**:
- raw mesh
- simplified mesh
- surface graph
- skeleton graph
- patch graph

That hierarchy matters because FlyWire meshes are extremely detailed; the fafbseg docs show an example neuron with 622,597 faces and explicitly recommend downsampling, while also noting that public proofread neurons have precomputed skeletons available. ([fafbseg-py.readthedocs.io](https://fafbseg-py.readthedocs.io/en/latest/source/tutorials/flywire_neurons.html))

Done when:
- every active neuron has validated geometry assets,
- you can view raw vs simplified vs patchified geometry side by side,
- asset generation is deterministic.

### Milestone 6 — Surface discretization and operator construction

This is the math core for the wave simulator.

For each neuron surface, construct:
- vertex/face adjacency
- geodesic neighborhoods
- cotangent or graph Laplacian
- local tangent frames
- boundary masks
- optional anisotropy tensors
- patch-to-patch interpolation operators

You want the simulator to work on **surface patches**, not raw triangles. That gives you a sane middle layer between full mesh fidelity and tractable dynamics.

Key outputs:
- per-neuron Laplacian
- per-neuron mass matrix or equivalent
- patch graph
- transfer operators between resolutions

Done when:
- you can initialize a pulse on any neuron and watch it propagate stably on the mesh,
- you can quantify numerical stability and energy behavior,
- you can switch between fine and coarse operators.

### Milestone 7 — Synapse localization and inter-neuron coupling model

You need to turn connectome edges into coupling between surface states.

For each connection:
- identify pre/post neurons
- map synapse locations, or approximate them to local surface/skeleton neighborhoods
- assign input/output patches
- define coupling kernels
- define conduction delay / integration rules

Build this as a configurable coupling system with at least three modes:
- point-to-point
- patch-to-patch
- distributed patch cloud

Done when:
- you can inspect any edge and see exactly where it lands on each neuron,
- inter-neuron transfer is visible in the UI,
- switching coupling models does not break the engine.

### Milestone 8 — Visual input stack

This is a full track, not an afterthought.

Split it into three layers:

#### 8A. Canonical stimulus library
Build a stimulus generator for:
- flashes
- bars
- moving edges
- drifting gratings
- looming
- rotating flow
- expanding/contracting optic flow

This gives you controlled experiments.

#### 8B. Retinal / ommatidial sampler
Build a sampling front-end that maps visual space into the fly’s retinotopic input lattice or your chosen abstraction of it.

The reason this is the right abstraction is that existing fly visual models explicitly exploit the visual system’s hexagonal retinotopic organization, and the Nature model samples visual inputs onto a regular hexagonal lattice for optic-flow training. ([nature.com](https://www.nature.com/articles/s41586-024-07939-3))

#### 8C. Scene generator
Then build the real scene system:
- camera with fly-like FOV choices
- moving objects
- textured backgrounds
- ego-motion
- depth layers
- event scripting

Use two scene modes:
- **procedural 2D/2.5D scenes** for fast iteration
- **full rendered scenes** for the polished demo

Done when:
- the exact same circuit can run on simple lab stimuli and on generated scenes,
- you can record and replay stimulus sequences,
- scene parameters are part of experiment manifests.

### Milestone 9 — Baseline neural simulator without waves

Before the wave version becomes the star, build a boring baseline.

This baseline should use:
- point-neuron or compartment-lite dynamics
- same subset
- same connectivity
- same visual inputs
- same readouts
- same UI

Why: every interesting wave result becomes much stronger if you can compare it to a non-wave control under identical inputs.

Done when:
- any experiment can run in `baseline` or `surface_wave` mode,
- outputs are aligned for direct comparison,
- the comparison plots exist by default.

### Milestone 10 — Surface-wave dynamics engine

Now build the actual wave model.

You need to decide what the state on each neuron surface is:
- membrane potential field,
- activation field,
- excitable-medium state,
- multi-field system with recovery variable,
- hybrid field + point readout.

Then define:
- propagation term
- damping
- refractory/recovery
- source injection from synapses
- optional anisotropy
- optional nonlinear thresholding
- optional branching effects near morphological bottlenecks

You should design this so that multiple wave kernels can plug in:
- diffusion-like
- damped wave
- excitable medium
- graph neural field
- reaction–diffusion variant

Done when:
- a single neuron supports stable synthetic wave tests,
- multi-neuron propagation works,
- parameters are saved and sweepable,
- the engine can run under real visual input.

### Milestone 11 — Hybrid morphology strategy

Not every neuron needs the same fidelity.

Use three simulation classes:
- **surface neurons**: fully meshed, wave-simulated
- **skeleton neurons**: graph-propagation approximation
- **point neurons**: functional placeholders

That gives you a realistic path to scaling the active graph without ruining the scientific point.

Done when:
- you can mix all three classes in one run,
- interfaces between them are standardized,
- upgrading a neuron from point to skeleton to surface requires no architecture rewrite.

### Milestone 12 — Readouts and task layer

The system needs explicit outputs, not just pretty waves.

Build readouts for:
- direction selectivity
- ON/OFF selectivity
- optic-flow estimate
- motion vector estimate
- latency
- synchrony/coherence
- phase-map statistics
- wavefront curvature and speed
- patch activation entropy

This is where the project becomes testable rather than aesthetic.

Existing connectome-constrained visual work used optic-flow estimation as the training/evaluation task, so using optic-flow or motion readout as one of your benchmark tasks is very well aligned with prior visual-system modeling. ([nature.com](https://www.nature.com/articles/s41586-024-07939-3))

Done when:
- every run emits a standardized result bundle,
- your UI can compare outputs between baseline and wave mode,
- at least one task metric is quantitative and automated.

### Milestone 13 — Validation ladder

Validation should move from “physics sanity” to “circuit sanity” to “task sanity.”

#### 13A. Numerical sanity
- pulse conservation / decay behavior
- timestep stability
- mesh-resolution sensitivity
- operator correctness
- boundary-condition behavior

#### 13B. Morphology sanity
- does propagation respect neuron shape?
- do branch points and thin segments change behavior in interpretable ways?
- does simplification preserve qualitative dynamics?

#### 13C. Circuit sanity
- are signs/delays/couplings behaving plausibly?
- do known pathway motifs produce expected delays and directional asymmetries?

#### 13D. Task sanity
- do motion stimuli produce structured differences between pathways?
- does the wave model change readouts in a meaningful, reproducible way?

Done when:
- each level has automated tests and notebook demonstrations,
- failures are debuggable,
- validation results are part of CI or at least scripted regression runs.

### Milestone 14 — UI and data presentation layer

Since you called this out explicitly: treat UI as a first-class milestone, not a wrapper.

I’d structure the interface into five panes:

1. **Scene pane**  
   The actual visual world and stimulus timeline.

2. **Circuit pane**  
   Cell types, active subset, connectivity, current experiment scope.

3. **3D morphology pane**  
   Meshes/skeletons with wave activity overlaid.

4. **Time-series pane**  
   Selected neuron/patch traces, readouts, delays, comparisons.

5. **Analysis pane**  
   Heatmaps, phase maps, direction-selectivity plots, ablation comparisons.

This is exactly the kind of integrated structure/function workflow that fruit-fly platforms like FlyBrainLab were built around: 3D exploration, creation of executable circuits, and interactive exploration of circuit logic. ([github.com](https://github.com/FlyBrainLab/FlyBrainLab))

Done when:
- a user can scrub time,
- click a neuron and see its traces,
- compare baseline vs wave mode,
- replay experiments without touching code.

### Milestone 15 — Experiment orchestration and ablation system

You need a runner that launches controlled batches.

Experiment dimensions should include:
- scene type
- motion direction
- speed
- contrast
- noise level
- active subset
- coupling mode
- wave kernel
- mesh resolution
- boundary conditions
- neuron fidelity class

Ablations should include:
- no waves
- waves only on selected cell classes
- no lateral coupling
- shuffled morphology
- shuffled synapse locations
- simplified geometry
- altered neurotransmitter sign rules

Done when:
- you can run whole suites from manifests,
- results are auto-indexed,
- ablations generate comparable outputs.

### Milestone 16 — Demo narrative and polished artifact

The hackathon output should not just be “here is a simulator.” It should be a guided story.

The ideal demo flow is:
- pick a scene,
- show visual input sampling,
- show which neurons are active,
- show wave propagation on surfaces,
- compare to baseline,
- highlight one phenomenon that only becomes visible with the surface model,
- end on a clean analysis view.

Build a scripted showcase mode with:
- prerecorded scene presets
- camera fly-throughs
- annotated highlights
- saved comparisons
- exportable images/video

Done when:
- someone unfamiliar with the code can understand the project from the UI alone,
- the result looks intentional rather than like a pile of debug windows.

### Milestone 17 — Stretch goal: bridge to broader whole-brain context

Once the visual-circuit simulator is alive, expand the role of the rest of the female brain from “unused metadata” to “context layer.”

That means:
- showing downstream paths into broader brain regions,
- letting users inspect where the active visual subset sits in the whole-brain graph,
- adding context-only nodes to network views,
- optionally turning selected downstream populations into simplified readout modules.

This preserves your original ambition without forcing full-brain simulation.

---

### The cleanest build order

If you want the order I’d actually follow, it’s this:

1. freeze scientific/demo claim  
2. lock active visual subset  
3. build canonical neuron registry  
4. finish subset designer  
5. finalize geometry asset pipeline  
6. build surface operators  
7. build baseline non-wave simulator  
8. build canonical stimulus library  
9. build retinal sampler  
10. implement wave engine  
11. map synapses to surface patches  
12. add task/readout layer  
13. build comparison UI  
14. add scene generator  
15. run ablations  
16. polish demo narrative  
17. widen to whole-brain context views

### My strongest recommendation

Make the **first true end-to-end vertical slice** this:

- one motion-focused visual subset
- one canonical stimulus family plus one synthetic scene family
- baseline vs surface-wave comparison
- one polished UI
- one quantitative task metric
- one “wow” visualization of wave propagation across neuron surfaces

That slice is the spine of the whole project. Everything else can scale out from it.

## Locked Hypothesis and Milestone 1 Burden of Proof

_Source: `Computational Neuroscience Project Design.txt`_

### Locked-in hypothesis

> **Morphology-resolved surface dynamics constitute an additional intraneuronal computational degree of freedom, capable of shaping circuit input-output transformations through distributed spatiotemporal state on neuronal structure.**

For **Milestone 1**, the fly experiment should test a narrower operational claim:

> **In a connectome-constrained Drosophila visual motion circuit, adding a morphology-resolved surface state should produce small but reproducible, geometry-dependent departures in shared circuit observables relative to fair point/reduced-neuron baselines.**

That is now the right burden of proof: **detectability, distinctness, and falsifiability of a small effect**.

This is the safer scientific frame because strong fly visual baselines already do a lot with simple neurons. A recent connectome-constrained visual-system model recovered ON/OFF segregation and T4/T5 direction selectivity using passive leaky linear non-spiking neurons with single electrical compartments for most cells, and an earlier T4 model reported that moving all synaptic inputs to the dendrite base left the simulated responses nearly unchanged. More broadly, effective point-neuron models can capture rich dendritic computations when given stronger synaptic integration terms, so the baseline challenge has to be real. ([nature.com](https://www.nature.com/articles/s41586-024-07939-3))

At the same time, the larger research-program idea is scientifically plausible. In other systems, dendrites have been shown to discriminate temporal input sequences, active dendritic integration has been shown to compute direction selectivity, and dendritic spikes can enhance stimulus selectivity. So the idea that intraneuronal spatial-temporal state can matter is not outlandish; the fly experiment just tests a much narrower detectability claim for your specific surface formalism. ([pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/20705816/?utm_source=chatgpt.com))

---

## 1) What should the wave model do differently than a baseline point-neuron model?

### Revised answer

The wave model should differ in **one essential respect only**:

> **It should endow selected neurons with explicit distributed state over morphology, so that synapse landing position, geodesic separation, and local spatiotemporal propagation can influence integration before the signal is collapsed to a downstream readout.**

Everything else should be kept as matched as possible.

T4/T5 is still the right first place to test this because direction selectivity emerges in their dendrites, their inputs are spatially organized along the dendrite with slower leading/trailing inputs and faster central inputs, and asymmetrical T4/T5 dendrites establish preferred direction. T4 also has evidence for passive supralinear interaction between distinct synapse classes on the dendrite, which means a conservative passive or weakly nonlinear surface model is still biologically credible. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC8371135/))

### What the wave model should add

For Milestone 1, the clean version is:

- **Surface-localized inputs.** Synapses land on explicit surface patches or coarse surface regions of the T4/T5 dendrite.
- **Surface propagation.** State evolves over the morphology by local propagation on the surface graph or skeleton-derived patch graph.
- **Local timing structure.** Nearby versus distant inputs interact through propagation delay, spread, damping, and possibly mild anisotropy.
- **Shared output readout.** Downstream circuitry still sees an ordinary scalar or low-dimensional readout, so comparison with the baseline is fair.

### What it should *not* add

It should **not** quietly win by changing unrelated things:

- no extra connectome edges
- no different synapse signs or arbitrary extra weights
- no larger tuning budget
- no decoder that only the wave model gets
- no hand-fitted per-synapse delays in the wave model that the baseline is denied

### Best first implementation

The best first implementation is **conservative**:

- wave layer on **T4/T5 only**
- upstream neurons kept as **point or reduced**
- propagation model **passive or weakly nonlinear**
- parameters limited to a small interpretable set: coupling/spread, damping, optional anisotropy

That is the right choice because the experiment is not trying to show a dramatic fly-wide advantage. It is trying to isolate a small, real effect where the anatomy gives it the best chance to exist.

### Best baselines

Use **two** baselines.

**P0: canonical point baseline**  
Passive leaky linear non-spiking single-compartment neurons, matched to the connectome and readout. That is the strongest “standard” baseline because it already works well in the fly visual system. ([nature.com](https://www.nature.com/articles/s41586-024-07939-3))

**P1: stronger challenge baseline**  
An effective-point or reduced-compartment model with explicit synaptic integration current or explicit delay structure. This is essential because point models can absorb a surprising amount of dendritic computation if you let them. ([pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/31292252/))

### What would falsify this answer

This framing weakens badly if any of the following happens:

- the effect disappears against P1
- intact versus shuffled synapse topology behaves the same
- the surface model only differs on wave-only internal visuals, not shared outputs
- the result requires a baroque parameter regime

So the revised standard is:

> **The wave model should add distributed morphology-bound state, and nothing else that can trivially explain the effect.**

---

## 2) What observable will convince you that the surface model matters?

### Revised answer

Not a wave movie.  
Not a prettier internal state.  
Not a benchmark score alone.

The convincing observable is:

> **a geometry-sensitive shared-output effect**

Meaning: a measurable difference between wave and baseline on a readout both models share, where that difference depends on intact morphology or synapse topology and is challengeable by stronger reduced baselines.

Because T4/T5 direction selectivity is dendritic, their inputs are spatially and temporally ordered on the dendrite, and dendritic asymmetry predicts preferred direction, the most diagnostic shared readouts are **null-direction suppression, response latency, and direction selectivity** under moving-edge stimuli. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC8371135/))

### If I had to choose one primary scalar

I would optimize around:

> **Geometry-sensitive null-direction suppression**, with **response latency** as the main mechanistic companion observable.

That is more aligned with your revised goal than raw “task accuracy.” It asks whether the surface layer changes the transformation itself, not whether it produces a huge gain.

### A good formal metric

Let \(M\) be a shared readout, such as null-direction suppression index or latency.

Define:

\[
\mathrm{GSOE}_M =
\big(M_{\text{surface,intact}} - M_{\text{baseline,intact}}\big)
-
\big(M_{\text{surface,shuffled}} - M_{\text{baseline,shuffled}}\big)
\]

Call this the **geometry-sensitive shared-output effect**.

That scalar bakes in the three things you now care about:

- **detectability**: wave and baseline differ on a shared readout
- **distinctness**: the difference depends on intact geometry/topology
- **falsifiability**: the effect can be driven toward zero by a topology shuffle

### Evidence ladder

**Weak evidence**  
The surface model shows propagation, spread, or phase structure that the point model cannot show by construction.

**Moderate evidence**  
The surface model changes a shared readout such as DSI, null-direction suppression, or latency.

**Strong evidence**  
That shared-readout change shrinks or disappears when morphology or synapse topology is shuffled.

**Very strong evidence**  
The effect survives the stronger reduced baseline P1 as well.

### Best concrete observables for Milestone 1

In order:

1. **Null-direction suppression shift**
2. **Latency shift / latency gradient linked to output change**
3. **DSI shift**
4. **Robustness slope under added noise or contrast loss**
5. **Internal latency/spread maps**

The first three are best because they sit closest to canonical T4/T5 computation. The last one is useful, but not enough on its own.

### What will *not* convince

These do not clear the bar:

- a visually impressive propagation movie with no shared-output consequence
- an effect that disappears once the baseline gets explicit delays
- a difference that survives only because the wave model has extra fitted freedom
- an effect that is present only on one cherry-picked stimulus

So the revised answer is:

> **The surface model matters if it produces a small, reproducible, geometry-dependent change on a shared readout, ideally null-direction suppression or latency, and that change survives a stronger reduced baseline.**

---

## 3) What will the demo show in under a minute?

### Revised answer

The demo should show **existence of effect**, not “advantage.”  
It should feel like a live falsification test.

The right demo claim is:

> **The same circuit, under the same stimulus, produces a small but real output difference when morphology-bound surface dynamics are present, and that difference depends on intact geometry.**

### Best one-minute structure

**0–10 s**  
Show a simple moving edge across a small retinotopic patch. Keep the stimulus trivial and legible.

**10–25 s**  
Split screen:  
left = matched point baseline  
right = surface model on the same T4/T5-centered circuit

The baseline shows scalar membrane activity. The surface model shows distributed state evolving on the dendrite.

**25–38 s**  
Overlay the shared output traces.  
Do not exaggerate. The point should be: “these are similar, but not identical.”  
Highlight a small shift in latency or null-direction suppression.

**38–50 s**  
Toggle the critical ablation: intact topology versus shuffled synapse landing geometry.  
The wave-specific difference should collapse or materially shrink.

**50–60 s**  
Freeze on one summary plot:
- paired null-direction suppression or latency difference
- intact versus shuffled
- surface versus baseline

Caption:
**“Small, causal, geometry-dependent computational effect.”**

### Optional last 10 seconds

If the clean-condition effect is real but visually subtle, then the final seconds can introduce a mild contrast reduction or input noise condition. That is acceptable **only if** the clean-condition effect is already visible. The perturbation is there to clarify a small effect, not to rescue a nonexistent one.

### What the demo should not try to do

It should not try to show:

- whole-brain intelligence
- broad benchmark superiority
- a naturalistic cinematic scene
- a wall of metrics
- a “look how pretty the waves are” reel

That would miss the new burden of proof.

### Why this demo is the right one

T4/T5 is the best first demo substrate because they are the first direction-selective neurons in the fly visual pathway, their computation is explicitly dendritic, anatomy predicts tuning, and strong simple baselines already exist. That makes any surviving small effect much more credible. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC8371135/))

So the demo’s job is not to say “the wave model is amazing.”  
Its job is to say:

> **“The wave layer changes the computation at all, and the change is tied to morphology.”**

---

### The revised Milestone 1 decision rule

Under this framing, I would call Milestone 1 successful if you get all four:

1. **Nonzero shared-output effect** on null-direction suppression, latency, or DSI
2. **Geometry dependence** through topology/morphology perturbation
3. **Survival against a stronger reduced baseline**
4. **Stability across seeds / modest parameter changes**

That is enough. It does not need to be large.

---

### Compressed final version

If I compress the revision into three direct answers:

**What should the wave model do differently than a baseline point-neuron model?**  
It should add **distributed, morphology-bound intraneuronal state** and nothing else that can trivially explain the result.

**What observable will convince you that the surface model matters?**  
A **geometry-sensitive shared-output effect**, preferably on **null-direction suppression or response latency**, that survives a stronger reduced baseline.

**What will the demo show in under a minute?**  
The **same stimulus** driving the **same circuit** in two models, producing a **small but real output difference** that **shrinks or disappears when geometry is shuffled**.

That is the tight version I would now lock in.

## Milestone 2 Circuit Boundary

_Source: `Milestone 2 Circuit Boundary.txt`_

### 1. Executive decision

Lock Milestone 2 to a **central-equatorial local motion patch built around one horizontal ON/OFF channel**, not to a generic lamina-to-behavior slab. The default active graph should **surface-simulate only T4a and T5a**, over just the columns subtending the chosen stimulus aperture plus a one-ring halo, because T4/T5 are the first direction-selective neurons, their subtype geometry is best behaved near the center of the eye, and T4 dendrites sample a local seven-column unit hexagon rather than an arbitrary wide field. Their **direct feedforward partners** should be active only in reduced form: Mi1, Tm3, Mi4 and Mi9 on the ON side, and Tm1, Tm2, Tm4 and Tm9 on the OFF side. Photoreceptors and lamina should stay **abstracted** as retinotopically aligned drive, because the first claim is not about phototransduction or lamina morphology, and the known direct T4/T5 inputs are already sufficient to impose the relevant spatial-temporal drive pattern on the motion detectors. Readout should stop at **T4a/T5a axon terminals** in lobula plate layer 1, not extend yet into LPi or tangential-cell circuitry. LPi neurons, HS/VS/LPTCs, and the rest of the brain should remain context-only, because downstream motion opponency and optic-flow tuning operate at much larger pooling scales and would force a much broader field before you have shown the core intraneuronal effect. This boundary is intentionally much smaller than recent connectome-constrained whole-visual-field models, because Milestone 2 is about falsifying a small geometry-sensitive effect, not maximizing anatomical coverage. The truly minimal T4-only ON circuit is scientifically defensible, but I would **not** lock it as the default, because adding the matched T5 OFF sister channel costs little and sharply reduces the risk that any effect is an ON-pathway artifact. Conversely, adding LPi/LPTC circuitry now would blur whether the first effect comes from intraneuronal morphology or from downstream opponency. So the decision-ready default is: **central patch, T4a/T5a in surface mode, direct ON/OFF columnar inputs in reduced mode, terminal readout only, everything else context or excluded**. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC7069908/))

### 2. Selection principles

- Put morphology-resolved dynamics only where morphology is mechanistically implicated **and** strong simple baselines already pose a real challenge: that means T4/T5, not lamina, not whole-brain feedback. ([nature.com](https://www.nature.com/articles/s41593-017-0046-4))
- Every active non-wave cell must either deliver a **direct, known synaptic drive** onto the surface-simulated neuron or provide the **smallest shared readout** needed for falsifiability. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC8891015/))
- Prefer **local feedforward motion circuitry** over wide-field/global motion circuitry; once a neuron pools over hundreds of T4/T5 cells, it belongs to a later milestone. ([nature.com](https://www.nature.com/articles/s41593-023-01443-z))
- Abstract stages whose explicit simulation mainly adds biological completeness rather than tightening the geometry test; that applies first to **R1–R6 and lamina L1/L2/L3**. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC4243710/))
- Restrict the retinotopic footprint to the **stimulus footprint plus one halo ring**, and keep it near the **center/equator** where subtype preferred directions are least confounded by eye geometry. ([nature.com](https://www.nature.com/articles/s41586-025-09276-5))
- Promote extra classes only when their omission becomes the leading confound in the chosen metric; “biologically real” is not yet enough.

### 3. Cell-class classification

*Here, “active” means numerically simulated at either surface or reduced fidelity.*

#### Required active simulation

- **Selected T4a cells in one central-equatorial contiguous patch (surface-simulated).** Role: first ON direction-selective local motion detectors. Surface-wave relevance: maximal, because direction selectivity emerges in T4/T5 and the hypothesis lives or dies at this computation. Needed for the first falsifiable test: **yes**. What is lost if omitted: the project is no longer testing morphology in the first known motion-detector stage. Can it be abstracted: **no**. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC7069908/))

- **Direct ON feedforward quartet to T4a: Mi1, Tm3, Mi4, Mi9 (reduced active).** Role: the best-established direct drives onto T4, with center/tip/base segregation and distinct dynamics. Surface-wave relevance: these cells impose the structured input pattern that the T4 surface state must integrate. Needed: **yes, in reduced form**. Loss if omitted: you hide critical timing and spatial order in an upstream black box. Can it be abstracted: **yes to point/reduced neurons, no to one lumped input filter**. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC8891015/))

#### Optional active simulation

- **Matched T5a cells (surface-simulated).** Role: first OFF direction-selective detectors in the sister pathway. Surface-wave relevance: same logic as T4, now tested across contrast polarity. Needed for the first falsifiable test: **not strictly**, but recommended in the default lock because it checks whether the effect survives outside the ON pathway. Loss if omitted: no OFF replication. Can it be abstracted: **no if included**. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC7069908/))

- **Direct OFF feedforward quartet to T5a: Tm1, Tm2, Tm4, Tm9 (reduced active).** Role: principal columnar T5 inputs, with Tm9 carrying an especially important offset/delayed contribution. Surface-wave relevance: provides the OFF-pathway analog of the T4 input geometry. Needed: **only once T5 is promoted**. Loss if omitted: OFF-pathway behavior becomes underconstrained and easy to dismiss. Can it be abstracted: **yes to reduced neurons, no to a synthetic current source**. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC6338461/))

- **Downstream horizontal-opponency extension: T4b/T5b, the layer-2→1 LPi subtype, and one HS-family tangential cell.** Role: first biologically faithful downstream motion-opponent readout for the chosen horizontal channel. Surface-wave relevance: indirect, because it tests transmission of a small local effect rather than its origin. Needed: **no** for Milestone 2. Loss if omitted: you cannot yet claim downstream propagation into a global-motion readout. Can it be abstracted: **yes, keep context-only for now**. ([nature.com](https://www.nature.com/articles/s41593-023-01443-z))

#### Context-only

- **R1–R6 photoreceptors and lamina L1/L2/L3.** Role: retinotopic input and ON/OFF channel splitting. Surface-wave relevance: low for Milestone 2. Needed: **as abstracted drive/context, not as active dynamics**. Loss if omitted entirely: you lose input provenance. Can it be abstracted: **yes, safely**. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC4243710/))

- **Minor or underconstrained direct T4/T5 partners: C3, CT1, TmY15, LT33, Tm23, and same-subtype T4/T5 tip recurrence.** Role: surround, gain/velocity tuning, or weaker local modulation. Surface-wave relevance: secondary and, for several of these, functionally underconstrained. Needed: **not yet**. Loss if omitted: possible underfit of velocity tuning or surround effects, especially around CT1/T5. Can they be abstracted: **yes, as context-only annotations or lumped drives**. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC6338461/))

- **Non-chosen T4/T5 directions and extra columns outside the selected patch.** Role: other cardinal directions and later optic-flow coverage. Surface-wave relevance: none for the first single-axis test. Needed: **no**. Loss if omitted: no directional generalization beyond the chosen axis. Can they be abstracted: **yes, as context-only**. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC7069908/))

- **Whole-brain boundary neurons, VPNs/VCNs, and central-brain targets.** Role: multimodal and behavioral context. Surface-wave relevance: none for the first local motion claim. Needed: **metadata only**. Loss if omitted: no behavioral interpretation layer. Can they be abstracted: **yes; they should remain context-only**. ([nature.com](https://www.nature.com/articles/s41586-024-07981-1))

#### Exclude for now

- **R7/R8 color and polarization channel.** Biologically real, but orthogonal to the first elementary-motion test; it adds a second visual modality without strengthening the motion/wave claim. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC2290790/))

- **Object/looming-specialized branches of the visual system.** These are legitimate visual circuits, but they test a different computational question from local motion detection and would dilute the Milestone 2 hypothesis. ([nature.com](https://www.nature.com/articles/s41586-024-07981-1))

- **Full LPi/LPTC inventory and the full optic-flow network.** Useful later, but not before the first local T4/T5 effect is secure. ([nature.com](https://www.nature.com/articles/s41593-023-01443-z))

- **Full optic-lobe or whole-brain active simulation.** The optic lobe already contains tens of thousands of intrinsic neurons, and recent connectome-constrained models span tens of thousands of neurons over hundreds of columns; that scale is the wrong match to Milestone 2’s falsifiability burden. ([nature.com](https://www.nature.com/articles/s41586-024-07981-1))

### 4. Three candidate subnetworks

#### Minimal defensible

- **Scope:** one central-equatorial patch, one preferred direction, ON pathway only.
- **Included cell classes:** T4a surface; Mi1, Tm3, Mi4, Mi9 reduced.
- **Included neuropils:** medulla M10, plus T4a axon terminals in lobula plate layer 1 for readout. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC8891015/))
- **Upstream retinal/photoreceptor stages:** abstracted.
- **Readout:** T4 only.
- **Realistically testable observables:** ON-edge null-direction suppression, response latency, DSI, and geometry-shuffle sensitivity at T4 output. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC7069908/))
- **Cannot test cleanly:** OFF-pathway generality, downstream motion opponency, flow-field selectivity.
- **Main scientific risk:** T4 already admits strong simple explanations; if the effect is tiny, this subnetwork is easiest to dismiss as a pathway-specific curiosity. ([nature.com](https://www.nature.com/articles/s41593-017-0046-4))
- **Main engineering risk:** even this case still demands accurate synapse-to-dendrite localization and a fair stronger baseline.
- **Strong enough for the first demo:** **yes, but narrowly**.
- **Best use:** fastest end-to-end de-risking of the wave implementation.

#### Balanced recommended

- **Scope:** one central-equatorial patch, one preferred direction, matched ON/OFF local motion channels.
- **Included cell classes:** T4a and T5a surface; Mi1, Tm3, Mi4, Mi9, Tm1, Tm2, Tm4, Tm9 reduced.
- **Included neuropils:** medulla M10, lobula Lo1, lobula plate layer 1. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC8891015/))
- **Upstream retinal/photoreceptor stages:** abstracted.
- **Readout:** T4/T5 only, at their axon terminals.
- **Realistically testable observables:** geometry-sensitive null-direction suppression and latency in both ON and OFF pathways; whether the effect replicates across sister motion detectors rather than one cell class only. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC7069908/))
- **Cannot test cleanly:** LPi-mediated motion opponency, LPTC flow-field selectivity, global optic-flow behavior.
- **Main scientific risk:** T5 is less cleanly constrained than T4, and CT1 is the main fragile omission if OFF-pathway dynamics look wrong. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC8725177/))
- **Main engineering risk:** you now need dual-neuropil support and matched ON/OFF handling, but the field size stays small.
- **Strong enough for the first demo:** **yes**.
- **Best use:** Milestone 2 default lock.

#### Expanded but still defensible

- **Scope:** horizontal motion-opponent extension around the same central patch.
- **Included cell classes:** T4a/T5a and T4b/T5b surface; direct ON/OFF quartets reduced; the layer-2→1 LPi subtype; one HS-family tangential cell.
- **Included neuropils:** medulla M10, lobula Lo1, lobula plate layers 1 and 2. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC7069908/))
- **Upstream retinal/photoreceptor stages:** abstracted.
- **Readout:** extends into a lobula plate output cell.
- **Realistically testable observables:** whether a small geometry-sensitive T4/T5 effect survives into downstream motion opponency and improves robustness under noisy stimuli. ([nature.com](https://www.nature.com/articles/s41593-023-01443-z))
- **Cannot test cleanly:** full optic-flow field selectivity, unless the patch grows substantially.
- **Main scientific risk:** downstream pooling and LPi circuitry can dominate the phenotype, making it harder to attribute the first effect to intraneuronal morphology.
- **Main engineering risk:** a biologically fair HS/LPTC readout wants far more visual field, because single LPTCs pool input from up to ~700 T4/T5 cells. ([nature.com](https://www.nature.com/articles/s41593-023-01443-z))
- **Strong enough for the first demo:** **yes, but disproportionate**.
- **Best use:** immediately after the first clean T4/T5-only result, not before.

### 5. Final recommendation

Pick the **Balanced recommended** subnetwork.

It is the smallest boundary I would actually sign off on for Milestone 2. The minimal T4a-only circuit is enough to debug the wave engine, but it leaves you too exposed to the criticism that any geometry-sensitive effect is peculiar to one polarity channel. The balanced choice adds only the matched OFF sister pathway, keeps the active field local, keeps the readout at T4/T5 rather than in wide-field tangential circuitry, and gives you a built-in replication across contrast polarity without importing LPi/LPTC-scale complications. It also respects the strongest baseline challenge: simple single-compartment and connectome-constrained models already do a lot in this system, so the first win has to come from a clean local morphology test, not from extra downstream machinery. Concretely, I would lock the first vertical slice to **T4a/T5a + direct ON/OFF reduced inputs + central patch + terminal readout**, driven by bright and dark moving edges or apparent-motion bar pairs along the chosen horizontal axis, with **geometry-sensitive null-direction suppression** as the primary metric and **response latency** as the mechanistic companion. ([nature.com](https://www.nature.com/articles/s41593-017-0046-4))

### 6. Anti-overbuild section

- **Trap: simulating full photoreceptor and lamina dynamics.** Avoid it. R1–R6 and L1/L2/L3 establish the motion channels, but explicit lamina biophysics will mostly add upstream detail rather than sharpen a T4/T5 morphology claim. Promote them only if reviewers can plausibly say your input abstraction hid the critical delays. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC4243710/))

- **Trap: simulating all four T4/T5 directions immediately.** Avoid it. One preferred axis already gives PD/ND comparisons within the same detector; adding the other three axes mostly increases state size and scene complexity before the first effect exists. Promote vertical or opposite horizontal layers only after the first local geometry effect is secure. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC7069908/))

- **Trap: adding LPi and HS/VS because they feel like a “real output.”** Avoid it for Milestone 2. LPi/LPTC circuitry is where global motion opponency and flow-field selectivity emerge, but that machinery pools over much larger spatial scales and will force field-of-view expansion before you know whether the surface state matters at all. Promote it only after a clear T4/T5-level effect. ([nature.com](https://www.nature.com/articles/s41593-023-01443-z))

- **Trap: surface-simulating upstream interneurons.** Avoid it. The wave hypothesis is strongest at T4/T5; surface-simulating Mi/Tm cells early buys computation, not falsifiability. Keep upstream partners active, but reduced. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC8891015/))

- **Trap: chasing every biologically real direct partner at once.** Avoid it. CT1, C3, TmY15, LT33 and Tm23 are all legitimate biology, but they are exactly the kind of classes that can consume weeks without materially tightening the first claim. Keep them context-only until a specific residual—especially OFF-pathway mismatch or velocity-tuning error—points straight at them. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC6338461/))

- **Trap: using the existence of FAFB or large published models as an argument for large scope.** Avoid it. FAFB is a whole-brain reference and recent visual-system models reach 45,669 neurons over 721 columns; both are excellent context, but neither scale is what Milestone 2 needs. ([codex.flywire.ai](https://codex.flywire.ai/))

### 7. Manifest-ready boundary

**Active graph:**  
`motion_horiz_onoff_patch_v1`

- **Surface detectors:** T4a, T5a in one central-equatorial contiguous patch.
- **Reduced fast/center feedforward inputs:** Mi1, Tm3, Tm1, Tm2, Tm4.
- **Reduced delayed/modulatory feedforward inputs:** Mi4, Mi9, Tm9.
- **Column rule:** include only columns inside the stimulus footprint, plus one surrounding halo ring so every active detector retains its full local sampling neighborhood. ([nature.com](https://www.nature.com/articles/s41586-025-09276-5))
- **Readout sites:** T4a/T5a axon terminals in lobula plate layer 1.
- **Role labels:** `surface_detector`, `direct_fast_feedforward`, `direct_delayed_feedforward`, `terminal_readout`.

**Candidate graph:**

- All active-graph cells above.
- Abstracted upstream drive nodes for R1–R6 and lamina L1/L2/L3.
- Context-only direct partners: C3, CT1, TmY15, LT33, Tm23, same-subtype T4/T5 recurrent tip partners.
- Downstream promotion candidates: T4b, T5b, the layer-2→1 LPi subtype, one HS-family tangential cell.
- All non-active candidate cells explicitly tagged `context_only`. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC4243710/))

**Context graph:**

- Whole FAFB female brain metadata/connectivity reference.
- All optic-lobe neurons outside the candidate graph.
- Boundary neurons, VPNs/VCNs, and central-brain targets for visualization, provenance, and future expansion only. ([codex.flywire.ai](https://codex.flywire.ai/))

**Explicit exclusions:**

- Active simulation of R7/R8 color/polarization channels.
- Explicit phototransduction and full lamina dynamics.
- Vertical motion layers (T4c/T5c, T4d/T5d) for Milestone 2.
- Full LPi/LPTC inventory.
- Object/looming-specialized visual branches.
- Whole-eye/full-field column tiling.
- Any central-brain or behavior-loop active dynamics. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC2290790/))

**Promotion triggers for later milestones:**

- **Promote CT1 local terminals** if OFF-pathway fits or velocity tuning are the dominant residual error. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC8725177/))
- **Promote L1/L2/L3 point models** if the fairness of the upstream delay abstraction becomes the main criticism. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC4243710/))
- **Promote T4b/T5b + LPi2→1 + one HS cell** if you need a downstream motion-opponent readout after the first T4a/T5a effect is secure. ([nature.com](https://www.nature.com/articles/s41593-023-01443-z))
- **Promote vertical T4/T5 layers** if you need direction generalization beyond the first horizontal axis. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC7069908/))
- **Expand the retinotopic patch** only when the scientific target shifts from local motion computation to optic-flow or large-field behavior.

### 8. Failure modes and uncertainty

- **Most fragile omission: CT1, especially for T5 and velocity tuning.** CT1 is not needed for the first null-direction-suppression/latency claim, but it is the first class I would promote if OFF-pathway residuals dominate. The literature supports both its prominence in T5 input and the uncertainty around its exact early role. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC6338461/))

- **Strong baseline danger: T4 may simply be too well explained by simple models for some stimuli.** Multi-compartment vs single-compartment differences can be very small for moving bars, and modern connectome-constrained models already recover key T4/T5 properties with simple neuron dynamics. If your effect survives only against a weak baseline, the boundary is not the win. ([nature.com](https://www.nature.com/articles/s41593-017-0046-4))

- **Distributed redundancy in the direct inputs means “no effect” is hard to interpret.** Mi1/Tm3 are major ON inputs, but Mi4/Mi9 and parallel circuitry make the pathway robust; similarly, T5 input contributions are distributed and Tm9 is unusually important. A null result could mean “wave effects are absent,” but it could also mean “this stimulus and this reduced boundary let the classical circuit absorb the computation.” ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC6845231/))

- **Column-to-column variability is a real risk, especially in the OFF pathway.** Tm9 connectivity is heterogeneous across FAFB columns, so you should build the manifest from actual FAFB neurons and synapse maps, not from a perfectly averaged cartoon. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC10882054/))

- **Field-position choice is fragile.** Away from the center/equator, preferred directions vary systematically because of eye geometry, which makes a first geometry-shuffle test harder to interpret. If your selected patch drifts away from this region, the boundary should be revised before the simulator is blamed. ([nature.com](https://www.nature.com/articles/s41586-025-09276-5))

- **What would force a boundary revision later:** a persistent upstream-delay confound would justify promoting lamina point models; a systematic OFF-pathway failure would justify CT1 promotion; a first clean T4/T5 effect that vanishes downstream would justify the LPi/HS extension; and a claim about optic flow or behavior would justify a larger patch and broader lobula plate circuitry. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC4243710/))

## Input Method in Simulation

_Source: `Input Method in Simulation.txt`_

A simple raster scene with an apple moving on a black background is the cleanest fit to the roadmap: Milestone 8C already wants a scene generator with moving objects, and Milestone 8B explicitly assigns image sampling, lattice projection, coordinate conversion, and frame generation as the retinal-sampler work. Matching the retinal representation to only the columns you actually simulate is also exactly in line with the project boundary logic. 

On **2**, your assumption is **partly right**, but there’s an important distinction. Codex does currently expose **Visual Columns Map** and **Visual Field Map** entries, and its visual-columns resource treats columns as local regions of the visual field. Separately, the 2025 Nature paper built a **one-to-one mapping between medulla columns and ommatidia directions** by matching regular grids from the centre outward. So there really is existing geometry/mapping structure out there now. ([codex.flywire.ai](https://codex.flywire.ai/app/visual_columns_challenge))

But that is **not** the same as “the apple image already gets turned into retinal drive for free.” The paper says the public repo provides **analysis and plotting code**, and the repo README describes it as **R code for the paper**. Your own roadmap also still lists the actual sampler implementation as Milestone 8B work. So I would treat the published eye map as a **reusable geometry prior**, not as a finished real-time image-to-retina pipeline. ([nature.com](https://www.nature.com/articles/s41586-025-09276-5)) 

So my take on your **5-hex idea** is: **good as a toy/debug mode, not good as the final Milestone 8 abstraction**. The locked Milestone 2 boundary is a **central-equatorial patch** with the stimulus footprint plus a **halo ring**, and that recommendation explicitly notes that T4 dendrites sample a **local seven-column unit hexagon**. Also, the recent eye-map work found that the eye’s sampling is irregular, with varying inter-ommatidial angles and shear across the eye. So a hand-picked 5-cell curved patch is a fun bootstrap, but it’s too ad hoc to be the lasting retinal model.  ([nature.com](https://www.nature.com/articles/s41586-025-09276-5))

So for **2**, the thing I would actually lock is this: use a **small central hex patch** aligned to the columns you plan to simulate, and borrow the published eye-map / Codex visual-field information if importing it is painless. If importing it turns into a swamp, fall back to a **flat or gently curved central hex patch**. For debugging, **7 sites** is the real minimum. For the first science pass, I’d probably want something more like **19 or 37 sites**, because you need the selected patch plus its immediate neighborhood.

On **3**, I would not wait around hoping Codex already solves site sampling. Even with the published eye map, you still need a rule for how each site samples the apple image. The map tells you **where a site points**; it does not by itself define the **acceptance-angle / integration kernel**. So I’d lock in **local averaging** for each hex site — basically a small cone/Gaussian-style sampling footprint, not a single pixel pickoff. ([nature.com](https://www.nature.com/articles/s41586-025-09276-5))

On **5**, I would also stop waiting for some existing external thing to make the decision for you. The least-code choice that still matches the locked project boundary is **not** full photoreceptors and **not** full lamina dynamics. The recommended Milestone 2 boundary keeps retinal/photoreceptor stages **abstracted**, then drives the system through reduced ON/OFF intermediates: **Mi1, Tm3, Mi4, Mi9** on the ON side and **Tm1, Tm2, Tm4, Tm9** on the OFF side, with readout at **T4/T5 terminals**. That is the simplest scientifically defensible early-unit mapping you currently have. 

So the version I’d lock right now is:

- **1 locked:** render the apple in a normal 2D scene buffer.
- **2 locked:** use a **local central hex patch**, ideally informed by published eye-map data; fallback is a simple flat/gently curved hex patch.
- **3 locked:** each site uses **local averaging / acceptance-angle sampling**.
- **4 locked:** match only the **active simulated columns**, with a small halo ring.
- **5 locked:** use **abstracted ON/OFF drive** into reduced Mi/Tm inputs, not explicit eye or lamina biophysics.

And the one thing I’d change from your proposal is just this: **don’t make the final retinal abstraction 5 hexes — make the toy mode 5 or 7, but make the real mode at least a small proper hex patch.**

## BCI Relevance and Technical Gap

_Source: `BCI and Surface Waves.txt`_

### Relevance to Brain–Computer Interfaces and Current Technical Gap

This project is relevant to invasive brain–computer interfaces (BCIs) because modern BCI performance depends not only on whether neural activity can be recorded, but on **which structure in that activity is treated as informative**. Current invasive BCIs already make substantial use of multichannel neural signals and increasingly decode them as evolving population activity rather than as isolated, independent electrode channels. Reviews of recent invasive BCI systems describe a landscape that includes intracortical arrays, ECoG, and related modalities specifically valued for their spatial resolution, cortical coverage, and ability to support richer decoding of distributed neural patterns. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC12026362/?utm_source=chatgpt.com))

At the decoding level, the field has already moved beyond purely static per-channel methods. A strong example is recent work on Nonlinear Manifold Alignment with Dynamics (NoMAD), which stabilizes intracortical BCI decoding by aligning recordings to a consistent set of latent **neural dynamics** using recurrent models. That matters here because it shows that invasive BCI research is already comfortable with the idea that useful information lives in the **time-evolving structure of neural population activity**, not just in local firing rates or raw channel amplitudes. ([nature.com](https://www.nature.com/articles/s41467-025-59652-y?utm_source=chatgpt.com))

At the hardware level, current invasive systems are also partly aligned with this project’s motivation. ECoG and high-density cortical interfaces are attractive in part because they preserve spatial organization across many channels and can cover meaningful cortical areas at millimeter or sub-millimeter scales. Longitudinal speech-BCI work further suggests that these spatially distributed signals can remain stable over extended periods, making them viable substrates for chronic decoding. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC12026362/?utm_source=chatgpt.com))

However, there is still a meaningful gap between what current invasive BCIs usually do and what this project is proposing. Although modern decoders increasingly model population dynamics, mainstream invasive BCI systems are **not typically designed around an explicit traveling-wave or surface-propagation framework**. In parallel, the current neuroscience literature argues that traveling waves may constitute a canonical computational motif across scales, and specifically notes that invasive mesoscopic recordings are well positioned to detect propagation across the observed network. That creates an opening: present-day BCIs often exploit spatiotemporal structure in a general sense, but they do not usually treat **propagation direction, phase gradients, wavefront geometry, or cortical-surface spread** as first-class features to be modeled and decoded. ([elifesciences.org](https://elifesciences.org/articles/106753?utm_source=chatgpt.com))

This is where the project contributes something distinctive. Rather than claiming that current BCIs ignore spatial structure altogether, the stronger and more accurate claim is that they mostly use **generic population dynamics**, whereas this project asks whether a more specific class of structure — **wave-like propagation across neural tissue** — carries additional computational and decoding value. If that hypothesis is supported, the implication for invasive BCIs would be that future systems may benefit from decoders that explicitly model neural activity as a spatially propagating field, rather than only as a latent dynamical state with no direct wave interpretation. ([nature.com](https://www.nature.com/articles/s41467-025-59652-y?utm_source=chatgpt.com))

A concise way to state the gap is: **current invasive BCIs already capture and decode structured population activity, but they do not yet generally treat propagating wave-like dynamics across the cortical surface as a primary signal class.** This project is therefore relevant to BCIs not because it introduces invasive recording itself, but because it investigates whether existing and future invasive interfaces are underusing an important form of neural organization. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC12026362/?utm_source=chatgpt.com))

## Milestone 11–13 Optimization and Runaway-to-Infinity Fix

_Source: `Milestone Optimization and Bug Fix.txt`_

The repo’s single-neuron surface solver already does three sane things: it computes a spectral-radius-based stability bound, rejects oversized `integration_timestep_ms`, and its own tests check that the fixture case damps rather than blows up.  

So the two highest-probability failure modes are these:

1. **Your real mesh operator is arriving with the wrong sign convention.**  
   The solver assumes `surface_operator` is a **positive-semidefinite stiffness-like operator**, then applies `-wave_speed_sq_scale * surface_operator_response`. The operator builder in `surface_operators.py` is consistent with that PSD convention. If a real asset reaches the solver as the **negative** Laplacian convention instead, the update becomes anti-diffusive and runs away.  

2. **The coupled execution path can inject energy too aggressively.**  
   In `surface_wave_execution.py`, delayed source patch activity is turned straight into target patch drive via `signed_source_value * target_cloud.weights`, with no target-mass normalization, no global coupling gain, and no soft cap. On a real mesh with feedback, that is the cleanest path to “looks fine at first, then rockets to infinity.” 

So my honest read is:

- **If one isolated real mesh explodes with coupling off:** operator-sign problem.
- **If isolated meshes are stable but the full coupled run explodes:** coupling-overdrive problem.

That is where I’d put money.

For Milestones 11, 12, and 13, your own roadmap already frames them as **hybrid morphology classes**, **readouts/task layer**, and **validation ladder**, and the repo’s readiness pass already points at the downstream workstreams as **mixed_fidelity**, **metrics**, and **validation**. So the fastest path is to build directly on the current solver/execution stack, not start a new architecture.  

### The fix I would make first

#### Patch 1: fail fast on bad operator sign

Put this in solver init, right after loading the operator bundle.

```python
def validate_surface_operator_sign(bundle):
    L = bundle.surface_operator.tocsr().astype(np.float64)

    # 1) symmetry
    asym = (L - L.T).tocsr()
    if asym.nnz and np.max(np.abs(asym.data)) > 1e-8:
        raise ValueError("surface_operator is not symmetric")

    # 2) stiffness-style sign pattern: diag >= 0, offdiag <= 0
    diag = L.diagonal()
    off = (L - sp.diags(diag)).tocsr()

    if np.any(diag < -1e-10):
        raise ValueError("surface_operator has negative diagonal entries")

    if off.nnz and np.max(off.data) > 1e-10:
        raise ValueError(
            "surface_operator has positive off-diagonal entries; "
            "likely wrong sign convention for stiffness operator"
        )

    # 3) Rayleigh test: PSD on mean-free probes
    rng = np.random.default_rng(0)
    for _ in range(4):
        q = rng.standard_normal(L.shape[0])
        q -= q.mean()
        denom = float(q @ q)
        if denom <= 1e-12:
            continue
        rq = float(q @ (L @ q)) / denom
        if rq < -1e-8:
            raise ValueError(
                "surface_operator is not PSD; likely sign-flipped and anti-diffusive"
            )
```

Why this matters: the solver step is already written as if `L` is stiffness-like. If the asset is wrong, nothing downstream will save you.  

#### Patch 2: normalize and bound coupling drive

This is the one I would actually patch **first** in the hackathon branch.

Right now coupling is raw. Make it mass-aware and bounded.

```python
EPS = 1e-12

def soft_clip(x, scale):
    return scale * np.tanh(x / max(scale, EPS))

def normalized_target_drive(component, source_value, patch_mass_diagonal,
                            coupling_gain=0.1, drive_soft_clip=1.0):
    raw = float(source_value * component.signed_weight_total)
    bounded = soft_clip(raw, drive_soft_clip)

    target_patch_mass = float(np.dot(
        patch_mass_diagonal[component.target_cloud.patch_indices],
        component.target_cloud.weights,
    ))

    scaled = coupling_gain * bounded / max(target_patch_mass, EPS)
    return scaled * component.target_cloud.weights
```

And in `_resolve_coupling_patch_drives(...)`:

```python
patch_mass = self._solver_by_root[component.post_root_id] \
    .kernels.operator_bundle.patch_mass_diagonal

source_value = float(np.dot(
    sampled_patch_values,
    component.source_cloud.weights,
))

target_patch_drive = normalized_target_drive(
    component=component,
    source_value=source_value,
    patch_mass_diagonal=patch_mass,
    coupling_gain=self._coupling_gain,
    drive_soft_clip=self._drive_soft_clip,
)

np.add.at(
    coupling_patch_drives[component.post_root_id],
    component.target_cloud.patch_indices,
    target_patch_drive,
)
```

That does three useful things fast:

- removes size dependence from big/small patches,
- stops a single edge from injecting absurd acceleration,
- gives you one knob, `coupling_gain`, to stabilize the whole network quickly.

The current execution code does not do any of that. 

#### Patch 3: add a numerical tripwire

Do not let the sim “politely” go to infinity.

```python
def check_numerics(root_id, snapshot, prev_energy, external_drive_norm,
                   peak_abort=1e3, energy_growth_limit=4.0):
    act = snapshot.state.activation
    vel = snapshot.state.velocity

    if not np.isfinite(act).all() or not np.isfinite(vel).all():
        raise FloatingPointError(f"root {root_id}: non-finite state detected")

    if snapshot.diagnostics.activation_peak_abs > peak_abort:
        raise FloatingPointError(
            f"root {root_id}: activation blew past peak_abort={peak_abort}"
        )

    if external_drive_norm < 1e-9 and prev_energy > 1e-12:
        if snapshot.diagnostics.energy > energy_growth_limit * prev_energy:
            raise FloatingPointError(
                f"root {root_id}: suspicious energy growth without matching drive"
            )
```

This is Milestone 13 work that pays for itself instantly.

### The 5-minute diagnosis that tells you which bug you have

Do these in order:

1. **Run one real mesh root with the same operator bundle, zero coupling, zero external drive after init.**  
   If it still blows up, your operator asset is wrong-sign or malformed.

2. **Run one real mesh root with external drive only, still no coupling.**  
   If stable, solver is fine.

3. **Run the same root set with coupling enabled but `coupling_gain = 0.0`, then `0.05`, then `0.1`.**  
   If the blow-up appears only as gain rises, it is coupling injection, not mesh PDE.

That isolates the fault ridiculously fast.

### How I’d get Milestones 11–13 coded in under 4 hours

Do the smallest shippable version.

#### Milestone 11: mixed fidelity
Do **not** invent a new simulator. Wrap the existing pieces.

- **surface** roots: current `SingleNeuronSurfaceWaveSolver`
- **skeleton** roots: same state shape, but graph operator on coarse patches only
- **point** roots: existing baseline/P1 path

The repo already has the surface solver, coupled execution path, and a baseline comparison workflow, so this is mostly an interface problem, not a physics rewrite.   

#### Milestone 12: readouts
Do streaming readouts only:

- `activation_peak`
- `activation_l2`
- `velocity_l2`
- `energy`
- `latency_ms`
- `mean_patch_activation`

That is enough to compare baseline vs wave and enough to support the existing result-bundle/readiness flow. 

#### Milestone 13: validation
Three validators only:

- **operator validator**: symmetry, sign pattern, PSD probe
- **runtime validator**: finite-state + peak + energy tripwire
- **comparison validator**: same stimulus, same readout schema, same dt

That is the minimum serious validation ladder.

### The pseudocode I’d actually build

```python
## ------------------------------------------------------------
## PRECOMPUTE / BUILD
## ------------------------------------------------------------

def build_runtime(manifest):
    roots = manifest.selected_roots

    fidelity = assign_fidelity_classes(roots)     # surface | skeleton | point

    surface_roots  = [r for r in roots if fidelity[r] == "surface"]
    skeleton_roots = [r for r in roots if fidelity[r] == "skeleton"]
    point_roots    = [r for r in roots if fidelity[r] == "point"]

    # Load operators once
    op = {}
    for r in surface_roots:
        op[r] = load_surface_operator_bundle(r)
        validate_surface_operator_sign(op[r])

    for r in skeleton_roots:
        op[r] = load_skeleton_or_patch_operator_bundle(r)
        validate_reduced_operator(op[r])

    # Build solvers once
    surface_solver = {
        r: make_surface_solver(op[r], manifest.surface_wave_model)
        for r in surface_roots
    }

    skeleton_solver = {
        r: make_reduced_graph_solver(op[r], manifest.reduced_model)
        for r in skeleton_roots
    }

    point_solver = {
        r: make_point_solver(r, manifest.baseline_model)
        for r in point_roots
    }

    # Precompute coupling
    edges = build_flattened_edge_list(manifest, fidelity)

    for e in edges:
        e.delay_steps = quantize_delay(e.delay_ms, manifest.dt_ms)
        e.src_idx, e.src_w = compile_source_cloud(e)
        e.dst_idx, e.dst_w = compile_target_cloud(e)
        e.target_mass = compile_target_effective_mass(e, op, fidelity)
        e.gain = e.user_gain if e.user_gain is not None else manifest.default_coupling_gain

    max_delay = max(e.delay_steps for e in edges) if edges else 0

    # Ring buffers: one per root, patch-level
    patch_readout = preallocate_patch_arrays(roots, op, fidelity)
    delay_ring = preallocate_delay_ring(roots, op, fidelity, max_delay)

    # Streaming metrics
    metrics = init_metric_accumulators(roots)

    # Validation state
    validator = init_validation_state(roots)

    return Runtime(
        roots=roots,
        fidelity=fidelity,
        surface_roots=surface_roots,
        skeleton_roots=skeleton_roots,
        point_roots=point_roots,
        op=op,
        surface_solver=surface_solver,
        skeleton_solver=skeleton_solver,
        point_solver=point_solver,
        edges=edges,
        patch_readout=patch_readout,
        delay_ring=delay_ring,
        metrics=metrics,
        validator=validator,
        cursor=0,
    )

## ------------------------------------------------------------
## HOT LOOP
## ------------------------------------------------------------

def run(runtime, stimulus_schedule, T_shared):
    for t in range(T_shared):

        # 1) zero all drives
        patch_drive = zero_patch_drive_like(runtime.patch_readout)
        point_drive = zero_point_drive_like(runtime.point_roots)

        # 2) external stimulus -> per-root drive
        external = compile_external_drives(runtime, stimulus_schedule[t])

        # 3) delayed recurrent coupling
        for e in runtime.edges:
            src_buffer = runtime.delay_ring[e.pre_root]
            delayed_patch_state = src_buffer[(runtime.cursor - e.delay_steps) % len(src_buffer)]

            source_value = dot(delayed_patch_state[e.src_idx], e.src_w)

            raw = source_value * e.signed_weight_total
            bounded = soft_clip(raw, scale=e.drive_soft_clip)
            scaled = e.gain * bounded / max(e.target_mass, 1e-12)

            scatter_add(
                patch_drive[e.post_root],
                e.dst_idx,
                scaled * e.dst_w,
            )

        # 4) surface roots
        for r in runtime.surface_roots:
            total_patch_drive = external.patch_drive[r] + patch_drive[r]

            prev_energy = runtime.validator.prev_energy[r]

            snap = runtime.surface_solver[r].step(
                patch_drive=total_patch_drive
            )

            runtime.patch_readout[r][:] = runtime.surface_solver[r].current_patch_state().activation

            check_numerics(
                root_id=r,
                snapshot=snap,
                prev_energy=prev_energy,
                external_drive_norm=l2_norm(total_patch_drive),
            )

            runtime.validator.prev_energy[r] = snap.diagnostics.energy

        # 5) skeleton roots
        for r in runtime.skeleton_roots:
            state = runtime.skeleton_solver[r].step(
                drive=external.patch_drive[r] + patch_drive[r]
            )
            runtime.patch_readout[r][:] = state.patch_activation
            check_reduced_numerics(runtime, r, state)

        # 6) point roots
        for r in runtime.point_roots:
            state = runtime.point_solver[r].step(
                drive=external.scalar_drive[r] + point_drive[r]
            )
            runtime.patch_readout[r][:] = point_to_patch_projection(state)
            check_point_numerics(runtime, r, state)

        # 7) streaming metrics
        update_activation_metrics(runtime.metrics, runtime.patch_readout, t)
        update_latency_metrics(runtime.metrics, runtime.patch_readout, t)
        update_energy_metrics(runtime.metrics, runtime.validator, t)
        update_comparison_metrics(runtime.metrics, runtime.patch_readout, t)

        # 8) write current readouts into delay ring
        for r in runtime.roots:
            runtime.delay_ring[r][runtime.cursor % len(runtime.delay_ring[r])] = runtime.patch_readout[r].copy()

        runtime.cursor += 1

    return finalize_result_bundle(runtime)

## ------------------------------------------------------------
## METRICS / VALIDATION
## ------------------------------------------------------------

def finalize_result_bundle(runtime):
    return {
        "mixed_fidelity_summary": summarize_fidelity_mix(runtime),
        "readouts": finalize_metrics(runtime.metrics),
        "validation": finalize_validation(runtime.validator),
        "patch_histories": maybe_emit_compact_traces(runtime),
    }
```

### The coding order I’d use

1. **Add operator-sign validation**
2. **Patch coupling normalization + soft clip**
3. **Add numerical tripwire**
4. **Implement Milestone 11 wrapper layer**
5. **Implement Milestone 12 streaming metrics**
6. **Implement Milestone 13 validators**

That order gets you to “stable and demonstrable” fastest.

The one thing I would **not** do tonight is rebuild the PDE. The repo already has a decent solver core and a tested local fixture path. The likely problem is the handoff between real mesh assets and coupled execution, not the idea of the solver itself.   

Start with the coupling patch. That is the highest-probability win.
