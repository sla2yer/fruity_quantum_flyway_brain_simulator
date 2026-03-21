# Fruit Fly Surface-Wave Simulation Roadmap

# Detailed milestones with programming-heavy vs math/physics-heavy split

This roadmap assumes the **female FAFB FlyWire dataset** is the structural source of truth, the **visual system** is the main simulated domain, and the rest of the brain is mostly used as **context** rather than fully simulated.

## The core project idea is:

Build a connectome-constrained fruit fly visual simulation where selected neurons carry **surface-wave dynamics** across their morphology, driven by a **synthetic visual scene generator**, and presented through a strong **interactive UI / analysis layer**.

---

## How to read this plan

### Workload labels

- **Programming-heavy** \= data plumbing, APIs, asset pipelines, engine implementation, scene generation, UI, orchestration, reproducibility  
- **Math/physics-heavy** \= model formulation, numerical operators, stability, wave equations, discretization choices, validation metrics, analysis design  
- **Shared** \= requires both perspectives at the same time

### Suggested team split

- **Jack lead** \= programming-first milestone  
- **Grant lead** \= math/physics-first milestone  
- **Shared lead** \= co-design milestone where both of you should be in the room

### Important principle

Do **not** split the project into “Jack builds everything” and “Grant only checks equations.”  
The better pattern is:

- **Jack** owns infrastructure, tooling, engine wiring, scene system, UI, and experiment automation  
- **Grant** owns the wave model, discretization choices, coupling assumptions, stability reasoning, and validation logic  
- both of you meet at the **interfaces**:  
  - subset definition  
  - simulation state definition  
  - operator format  
  - synapse coupling API  
  - output metric schema  
  - UI data contract

---

## Top-level tracks

### Track A — Data / Infrastructure / Engine / UI

**Mostly Jack**

- data registry  
- subset tooling  
- geometry fetching and caching  
- mesh/skeleton asset pipeline  
- scene generator  
- simulator software architecture  
- UI and visual analytics  
- orchestration and demo packaging

### Track B — Wave Mathematics / Numerical Methods / Validation

**Mostly Grant**

- define the wave model  
- choose state variables  
- define operators and coupling  
- determine stability constraints  
- design validation metrics  
- interpret readouts physically  
- propose ablations that test the hypothesis

### Track C — Integration / Scientific Story

**Shared**

- choose the circuit  
- decide what counts as success  
- decide what phenomenon the demo proves  
- interpret baseline vs wave differences  
- shape the final demo narrative

---

## Milestone summary table

| \# | Milestone | Workload split | Suggested lead | Main outcome |
| :---- | :---- | :---- | :---- | :---- |
| 1 | Freeze scientific claim and demo claim | Shared (40% programming / 60% math-physics) | Grant lead, Jack supports | Hypothesis, demo target, success criteria |
| 2 | Lock the circuit boundary | Shared leaning programming (65/35) | Jack lead, Grant supports | Active visual subset and context graph |
| 3 | Build the data registry and provenance layer | Programming-heavy (85/15) | Jack lead | Canonical neuron/connectivity metadata tables |
| 4 | Turn subset selection into a proper tool | Programming-heavy (80/20) | Jack lead | Reproducible named subsets |
| 5 | Build the geometry ingestion pipeline | Programming-heavy (75/25) | Jack lead | Mesh/skeleton assets and simplifications |
| 6 | Construct surface discretizations and operators | Math/physics-heavy (30/70) | Grant lead, Jack implements | Laplacians, patch graphs, transfer operators |
| 7 | Map synapses and define inter-neuron coupling | Shared leaning math-physics (45/55) | Shared lead | Patch-level coupling model |
| 8 | Build the visual input stack | Split by submodule | Split | Stimuli, retinal mapping, scene generator |
| 9 | Build the baseline non-wave simulator | Programming-heavy (70/30) | Jack lead | Control model for comparison |
| 10 | Implement the surface-wave engine | Math/physics-heavy (25/75) | Grant lead, Jack implements | Running wave dynamics on neuron surfaces |
| 11 | Add hybrid morphology classes | Shared leaning programming (60/40) | Jack lead | Surface / skeleton / point neuron mix |
| 12 | Define readouts and task layer | Shared leaning math-physics (45/55) | Shared lead | Quantitative outputs and task metrics |
| 13 | Build the validation ladder | Math/physics-heavy (30/70) | Grant lead | Numerical \+ biological sanity checks |
| 14 | Build the UI and analysis dashboard | Programming-heavy (90/10) | Jack lead | Polished demo and interactive inspection |
| 15 | Build experiment orchestration and ablations | Programming-heavy (80/20) | Jack lead | Batch runs, manifests, comparisons |
| 16 | Polish the demo narrative and showcase mode | Shared leaning programming (75/25) | Jack lead, Grant supports | End-to-end presentation flow |
| 17 | Extend to whole-brain context views | Programming-heavy (75/25) | Jack lead | Context graph around the active visual circuit |

---

# Detailed milestone plan

---

## **Milestone 1 — Freeze the scientific claim, demo claim, and output contract**

**Workload split:** Shared, leaning math/physics  
 **Suggested lead:** Grant  
 **Why it matters:** This prevents the project from becoming a cool visualization with no testable point, and locks the Milestone 1 scientific and artifact contract before the simulator is overbuilt.

### **Locked hypothesis**

**Morphology-resolved surface dynamics constitute an additional intraneuronal computational degree of freedom, capable of shaping circuit input-output transformations through distributed spatiotemporal state on neuronal structure.**

### **Milestone 1 operational claim**

**In a connectome-constrained Drosophila visual motion circuit, adding a morphology-resolved surface state should produce small but reproducible, geometry-dependent departures in shared circuit observables relative to fair point/reduced-neuron baselines.**

Milestone 1 is about **detectability, distinctness, and falsifiability of a small effect**.  
 It is not yet about broad superiority claims.

### **What the wave model is allowed to add**

* surface-localized inputs on explicit T4/T5 morphology regions  
* surface propagation over a morphology graph  
* local timing structure from geodesic separation, spread, damping, and optional mild anisotropy  
* a shared downstream readout so comparison to baselines stays fair

  ### **What it must not add**

* extra connectome edges  
* different synapse signs  
* arbitrary extra weights or a larger tuning budget  
* a decoder or readout unavailable to the baselines  
* hand-fitted per-synapse delays granted only to the surface model

  ### **Baseline definitions**

* **`P0`**: canonical point baseline using passive leaky linear non-spiking single-compartment neurons matched to the same circuit and readout  
* **`P1`**: stronger reduced baseline using an effective-point or reduced-compartment model with explicit synaptic integration current or explicit delay structure

  ### **Core questions to answer**

**What exactly is the claim about waves?**  
 In a connectome-constrained Drosophila visual motion circuit, adding a morphology-resolved surface state should produce small but reproducible, geometry-dependent departures in shared circuit observables relative to fair point/reduced-neuron baselines.

**What should the wave model do differently than a baseline point-neuron model?**  
 It should add distributed, morphology-bound intraneuronal state and nothing else that can trivially explain the result.

**What observable will convince you that the surface model matters?**  
 A geometry-sensitive shared-output effect, preferably on null-direction suppression or response latency, that survives a stronger reduced baseline.

**What will the demo show in under a minute?**  
 The same stimulus driving the same circuit in two models, producing a small but real output difference that shrinks or disappears when geometry is shuffled.

### **Primary observable and companion observables**

* **Core observable:** geometry-sensitive shared-output effect  
* **Primary observable:** geometry-sensitive null-direction suppression  
* **Main companion observable:** response latency  
* **Secondary shared readout:** direction selectivity index

  ### **Evidence ladder**

* **Weak:** the surface model shows propagation or spread that the point model cannot show by construction  
* **Moderate:** the surface model changes a shared readout such as null-direction suppression, latency, or DSI  
* **Strong:** the shared-readout change shrinks or disappears when morphology or synapse topology is shuffled  
* **Very strong:** the effect survives the stronger reduced baseline `P1`

  ### **One-minute demo story**

1. **`0–10 s`**: show a simple moving edge across a small retinotopic patch  
2. **`10–25 s`**: split screen with matched point baseline on the left and surface model on the right for the same T4/T5-centered circuit  
3. **`25–38 s`**: overlay shared output traces and highlight a small shift in null-direction suppression or latency  
4. **`38–50 s`**: toggle intact versus shuffled synapse landing geometry and show the wave-specific difference collapse or materially shrink  
5. **`50–60 s`**: freeze on a summary panel captioned **“Small, causal, geometry-dependent computational effect.”**

   ### **Must-show plots / UI states**

* stimulus overview for the simple moving-edge input  
* split view showing baseline scalar activity versus surface-state activity on morphology  
* shared output trace overlay for the same circuit and stimulus  
* null-direction suppression comparison plot  
* latency shift comparison plot  
* intact versus shuffled topology ablation comparison plot  
* `P0` versus `P1` challenge-baseline comparison plot  
* final milestone decision panel summarizing the four decision-rule checks

  ### **Non-goals**

* whole-brain intelligence claims  
* broad benchmark superiority  
* naturalistic cinematic scenes  
* a wall of metrics  
* a “look how pretty the waves are” reel  
* Milestone 2+ simulator build-out beyond what is required to lock the design and output contract

  ### **Jack owns**

* writing the project brief into a versioned document  
* turning success criteria into config fields / experiment metadata  
* creating the experiment manifest schema  
* making sure the claim maps onto actual software outputs  
* defining the required plots, UI states, and result-bundle fields for Milestone 1 checkoff

  ### **Grant owns**

* defining the locked wave hypothesis  
* defining expected signatures:  
  * phase gradients  
  * propagation delays  
  * coherence  
  * geometry-sensitive spread  
  * task-level differences  
* defining which effects count as nontrivial  
* defining the Milestone 1 decision rule and falsification logic

  ### **Done when**

* there is a one-page written brief in-repo  
* the locked hypothesis is preserved verbatim  
* the narrower Milestone 1 operational claim is preserved  
* `P0` and `P1` baseline definitions are explicit  
* the primary observable is centered on geometry-sensitive null-direction suppression  
* response latency is defined as the main companion observable  
* the one-minute demo story is defined  
* the must-show plots and UI states are defined  
* the decision rule is explicit and traceable to repo outputs

  ### **Milestone 1 decision rule**

Milestone 1 is successful only if all four hold:

1. nonzero shared-output effect  
2. geometry dependence  
3. survival against a stronger reduced baseline  
4. stability across seeds and modest parameter changes

This version is much tighter than the current section because it keeps the roadmap tone, but now locks the real burden of proof instead of leaving Milestone 1 as a high-level placeholder.

- 

---

## **Milestone 2 — Lock the circuit boundary**

**Workload split:** Shared, leaning programming  
 **Suggested lead:** Jack

### **Goal**

Choose and freeze the smallest scientifically defensible circuit boundary for the first real simulation pass.

### **Locked circuit decision**

Milestone 2 is locked to a **central-equatorial local motion patch built around one horizontal ON/OFF channel**.

The default active graph should use the **balanced local-motion subnetwork**:

* **surface-simulated:** T4a and T5a  
* **reduced active inputs:** Mi1, Tm3, Mi4, Mi9, Tm1, Tm2, Tm4, Tm9  
* **abstracted upstream drive:** R1–R6 photoreceptors and lamina L1/L2/L3  
* **readout stop point:** T4a/T5a axon terminals in lobula plate layer 1

Only the columns inside the selected stimulus footprint should be included, plus a **one-ring halo** so each active detector retains its local sampling neighborhood.

### **Locked scope structure**

**Context graph**  
 Whole FAFB female brain metadata and connectivity reference, plus all optic-lobe and central-brain structures outside the selected motion subnetwork.

**Candidate graph**  
 The locked active graph, abstracted upstream drive nodes, context-only direct partners, and downstream promotion candidates for later milestones.

**Active graph**  
 A single central-equatorial contiguous patch containing:

* T4a and T5a in surface mode  
* direct ON/OFF feedforward partners in reduced mode  
* terminal readout at lobula plate layer 1

  ### **Context-only for Milestone 2**

Keep these as context-only, not active simulation:

* C3, CT1, TmY15, LT33, Tm23, and same-subtype T4/T5 recurrent tip partners  
* T4b, T5b, LPi candidates, and tangential-cell readout candidates  
* the rest of the optic lobe and broader brain

  ### **Explicit exclusions for Milestone 2**

Do **not** include the following in the active simulation boundary:

* R7/R8 color and polarization channels  
* explicit phototransduction or full lamina dynamics  
* additional T4/T5 direction layers beyond the chosen horizontal channel  
* LPi/LPTC inventory or wide-field tangential-cell circuitry  
* object / looming-specialized visual branches  
* whole-eye or full-field column tiling  
* central-brain or behavior-loop active dynamics

  ### **Locked first vertical slice**

The first end-to-end Milestone 2 subnetwork should be:

**T4a/T5a \+ direct ON/OFF reduced inputs \+ central patch \+ terminal readout**

The first test stimuli should stay simple and local, using bright and dark moving edges or apparent-motion bar pairs along the chosen horizontal axis.

### **Promotion triggers for later milestones**

Promote additional circuitry only when it becomes the leading limitation:

* promote **CT1** if OFF-pathway fit or velocity-tuning residuals dominate  
* promote **L1/L2/L3 point models** if the upstream delay abstraction becomes the main criticism  
* promote **LPi / downstream tangential-cell readout** only after a clear T4/T5-level effect is established  
* expand the **retinotopic patch** only when the target shifts from local motion computation to optic-flow or larger-field behavior  
* add additional **T4/T5 direction layers** only after the first horizontal-axis result is secure

  ### **Jack owns**

* subset extraction pipeline for the locked boundary  
* root ID manifests for active, candidate, and context graphs  
* role labeling for every included neuron  
* summary reports and previews for the locked subnetwork

  ### **Grant owns**

* sign-off on the locked active cell classes  
* sign-off on what remains reduced, abstracted, context-only, or excluded  
* scientific review of any proposed promotion beyond the locked boundary

  ### **Done when**

* there is a named manifest for the locked boundary  
* every active neuron has a role label and fidelity class  
* every relevant non-active neuron is explicitly tagged as context-only or excluded  
* the Milestone 2 boundary is frozen as the default first simulation pass  
* both of you can explain why this boundary is sufficient for the first morphology-sensitive test  
- 

---

## Milestone 3 — Build the data registry and provenance layer


### Goal

Create one canonical local dataset that every script uses.

### Registry should contain

- root ID  
- cell type / resolved type  
- class / subclass  
- neurotransmitter prediction  
- neuropils  
- side  
- proofread status  
- snapshot/materialization version  
- source file  
- role in project:  
  - context-only  
  - point-simulated  
  - skeleton-simulated  
  - surface-simulated

### Agent responsibilities:

- CSV ingestion and normalization  
- schema design  
- table joins  
- manifest validation  
- version pinning  
- reproducibility commands  
- sanity-checking the biological semantics of fields  
- helping define what annotations are scientifically relevant  
- flagging missing metadata needed for later coupling/model design

### Done when

- one command builds the registry  
- every downstream script reads from the registry  
- the same experiment can be reproduced from a manifest

---

## Milestone 4 — Turn subset selection into a proper tool

**Workload split:** Programming-heavy  
**Suggested lead:** Jack

### Goal

Make subset design fast, reproducible, and explorable.

### Features

- selection by cell type  
- selection by neuropil  
- selection by visual column  
- selection by upstream/downstream relations  
- exclusion rules  
- neuron-budget caps  
- named presets like:  
  - `motion_minimal`  
  - `motion_medium`  
  - `motion_dense`

### agent responabilities

- CLI / config-driven subset generator  
- filtering logic  
- graph summaries  
- small preview visualizations  
- exporting manifests and reports

### Grant owns

- defining scientifically meaningful presets  
- checking that subset boundaries preserve the intended behavior  
- suggesting ablation-oriented subsets

### Done when

- multiple subsets can be generated automatically  
- each subset produces a manifest and stats file  
- you can switch simulator inputs by changing only a config

---

## Milestone 5 — Build the geometry ingestion and multiresolution morphology pipeline

**Workload split:** Programming-heavy with some geometry reasoning  
**Suggested lead:** Jack

### Goal

Fetch, store, simplify, and standardize neuron geometry for simulation.

### Asset hierarchy

For each active neuron, generate:

- raw mesh  
- simplified mesh  
- skeleton  
- surface graph  
- patch graph  
- derived geometric descriptors

### Jack owns

- mesh download scripts  
- caching  
- file formats  
- simplification pipeline  
- asset naming/versioning  
- geometry QA tools  
- preview viewers or notebooks

### Grant owns

- advising on what simplification can preserve wave-relevant geometry  
- identifying which geometric descriptors matter for propagation  
- defining acceptable error bounds for coarse geometry

### Done when

- active neurons have consistent geometry assets  
- simplification is automated and reproducible  
- raw vs simplified vs patchified geometry can be visualized together

---

## Milestone 6 — Construct surface discretizations and operators

**Workload split:** Math/physics-heavy  
**Suggested lead:** Grant  
**Implementation support:** Jack

### Goal

Turn neuron surfaces into simulation-ready numerical objects.

### Build

- adjacency structures  
- geodesic neighborhoods  
- graph or cotangent Laplacian  
- patch graph  
- local tangent frames  
- boundary masks  
- optional anisotropy tensors  
- fine-to-coarse transfer operators

### Jack owns

- sparse matrix construction code  
- asset serialization  
- performance optimization  
- operator test harnesses  
- visualization of operator outputs on meshes

### Grant owns

- choosing the correct discretization family  
- deciding whether to use graph-based or mesh-based operators  
- specifying stability-relevant properties  
- defining what should be conserved or damped  
- checking whether the operator is faithful enough to the intended physics

### Done when

- a pulse can be initialized on a single neuron  
- propagation on the surface is numerically stable  
- coarse and fine operators can be compared  
- operator quality metrics exist

---

## Milestone 7 — Map synapses and define inter-neuron coupling

**Workload split:** Shared, leaning math/physics  
**Suggested lead:** Shared

### Goal

Turn connectome edges into transfers between neuron surface states.

### Need to define

- where synaptic input lands on the receiving surface  
- where output is read on the presynaptic neuron  
- whether coupling is:  
  - point-to-point  
  - patch-to-patch  
  - distributed patch cloud  
- how synaptic sign and delay are handled  
- how multiple synapses aggregate

### Jack owns

- synapse table processing  
- locating nearest patches / skeleton nodes  
- building fast lookup structures  
- serializing coupling maps  
- coupling inspection tools

### Grant owns

- defining coupling kernels  
- choosing delay models  
- deciding how synaptic transfer modifies the surface state  
- determining whether coupling is instantaneous, filtered, nonlinear, etc.

### Done when

- any edge can be inspected and visualized  
- the simulator knows where and how input transfers between neurons  
- coupling rules are configurable and versioned

---

## Milestone 8 — Build the visual input stack

This milestone is intentionally split because different parts belong to different people.

### Milestone 8A — Canonical stimulus library

**Workload split:** Programming-heavy  
**Suggested lead:** Jack

Build generators for:

- flashes  
- moving bars  
- drifting gratings  
- looming stimuli  
- expansion/contraction flow  
- rotating flow  
- translated edge patterns

#### Jack owns

- stimulus generation code  
- parameterized stimulus configs  
- playback tooling  
- serialization for experiment reuse

#### Grant owns

- making sure the stimulus set is scientifically meaningful  
- defining which stimuli are best for isolating wave effects

#### Done when

- standard stimuli are callable from config  
- stimuli can be recorded and replayed

---

### Milestone 8B — Retinal / ommatidial sampler

**Workload split:** Shared, leaning math/physics  
**Suggested lead:** Grant  
**Implementation support:** Jack

#### Goal

Map world-space visual stimuli into the fly’s retinotopic input representation.

#### Jack owns

- code for image sampling / lattice projection  
- coordinate system conversions  
- efficient frame generation  
- integration with scene playback

#### Grant owns

- defining the retinotopic abstraction  
- deciding how to approximate the fly’s visual sampling lattice  
- choosing what resolution and geometry are scientifically defensible  
- determining how stimuli map into early visual units

#### Done when

- the same scene can be converted into retinal input frames consistently  
- you can visualize both the world scene and the sampled fly-view representation

---

### Milestone 8C — Scene generator

**Workload split:** Programming-heavy  
**Suggested lead:** Jack

#### Goal

Create real visual environments instead of only lab stimuli.

#### Scene system should support

- 2D / 2.5D procedural scenes  
- moving objects  
- textured backgrounds  
- ego-motion  
- depth layers  
- scripted events  
- camera presets

#### Jack owns

- rendering / scene code  
- asset pipelines  
- scene scripting  
- replay system  
- integration with the retinal sampler

#### Grant owns

- suggesting the most meaningful physical motion scenarios  
- identifying scene classes that should expose wave-related differences

#### Done when

- a configurable scene can drive the visual input stack end-to-end  
- scenes can be saved, replayed, and compared

---

## Milestone 9 — Build the baseline non-wave simulator

**Workload split:** Programming-heavy  
**Suggested lead:** Jack

### Goal

Create a control simulator using simpler neuron dynamics.

### Why it matters

The wave model is far more convincing if the exact same circuit can be run in:

- `baseline`  
- `surface_wave`

### Jack owns

- simulator framework  
- state update loops  
- connectivity integration  
- I/O schema  
- logging  
- alignment with the UI and metrics layer

### Grant owns

- defining a fair baseline model  
- making sure the baseline is not a strawman  
- helping choose comparable state variables and readouts

### Done when

- the same experiment manifest runs in baseline mode  
- outputs line up with wave-mode outputs for comparison  
- the UI can switch between both modes

---

## Milestone 10 — Implement the surface-wave dynamics engine

**Workload split:** Math/physics-heavy  
**Suggested lead:** Grant  
**Implementation support:** Jack

### Goal

Define and implement the actual wave model.

### Must define

- state variable(s) on the surface  
- propagation term  
- damping term  
- refractory / recovery behavior  
- synaptic source injection  
- nonlinearities  
- optional anisotropy  
- optional branching effects

### Candidate model families

- damped wave system  
- diffusion-like neural field  
- excitable medium  
- reaction–diffusion system  
- hybrid field \+ readout system

### Jack owns

- engine implementation  
- performance engineering  
- parameter config plumbing  
- data structures for stepping the system  
- GPU / sparse solver integration if needed

### Grant owns

- selecting the model family  
- deriving or choosing equations  
- reasoning about stability  
- defining parameter ranges  
- specifying what behaviors are physically meaningful vs numerical artifacts

### Done when

- a single-neuron wave test works  
- multi-neuron propagation works  
- the engine can run under actual visual input  
- parameters can be swept systematically

---

## Milestone 11 — Add hybrid morphology classes

**Workload split:** Shared, leaning programming  
**Suggested lead:** Jack

### Goal

Support multiple fidelity levels in one simulation.

### Classes

- **surface neuron** — full mesh simulation  
- **skeleton neuron** — graph approximation  
- **point neuron** — coarse functional placeholder

### Jack owns

- architecture for multi-fidelity neurons  
- interfaces between fidelity classes  
- consistent serialization of state  
- routing between coupling modes

### Grant owns

- defining what each fidelity class is allowed to approximate  
- setting rules for when a neuron should be promoted/demoted in fidelity  
- checking whether lower-fidelity surrogates preserve the needed behavior

### Done when

- different fidelity classes coexist in one run  
- upgrading a neuron does not require rewriting the simulator  
- mixed-fidelity runs preserve stable semantics

---

## Milestone 12 — Define readouts and task layer

**Workload split:** Shared, leaning math/physics  
**Suggested lead:** Shared

### Goal

Turn simulation output into interpretable, quantitative results.

### Readouts to implement

- direction selectivity  
- ON/OFF selectivity  
- optic-flow estimate  
- motion vector estimate  
- latency  
- synchrony / coherence  
- phase gradient statistics  
- wavefront speed / curvature  
- patch activation entropy

### Jack owns

- readout pipeline implementation  
- data export formats  
- reusable analysis functions  
- hooks into the UI  
- experiment result packaging

### Grant owns

- defining which metrics actually test the hypothesis  
- designing how to measure wave-specific structure  
- interpreting whether differences are meaningful  
- proposing null tests and metric sanity checks

### Done when

- every run emits a standard result bundle  
- at least one task metric is automated  
- baseline vs wave comparisons are quantitative, not just visual

---

## Milestone 13 — Build the validation ladder

**Workload split:** Math/physics-heavy  
**Suggested lead:** Grant

### Goal

Prove the simulator is not only running, but behaving sensibly.

### Validation layers

#### 13A — Numerical sanity

- timestep stability  
- energy / amplitude behavior  
- boundary condition behavior  
- operator correctness  
- mesh-resolution sensitivity

#### 13B — Morphology sanity

- shape-dependent propagation  
- bottleneck / branching effects  
- simplification sensitivity  
- patchification sensitivity

#### 13C — Circuit sanity

- plausible delay structure  
- sign behavior  
- aggregation behavior  
- pathway asymmetry under motion stimuli

#### 13D — Task sanity

- stable task outputs  
- reproducible differences between baseline and wave mode  
- robustness under perturbation / noise

### Jack owns

- automated test harnesses  
- regression scripts  
- notebooks / reports  
- CI integration if feasible

### Grant owns

- defining the actual validation criteria  
- deciding which failures are fatal  
- interpreting whether observed behavior is physically/model-wise plausible

### Done when

- each validation layer has automated tests or notebooks  
- failures produce actionable diagnostics  
- model changes can be regression-checked

---

## Milestone 14 — Build the UI and analysis dashboard

**Workload split:** Programming-heavy  
**Suggested lead:** Jack

### Goal

Create a polished interface that makes the project understandable.

### UI panes

1. **Scene pane** — what the fly sees  
2. **Circuit pane** — active subset and connectivity context  
3. **Morphology pane** — neuron meshes/skeletons with activity overlay  
4. **Time-series pane** — traces and comparisons  
5. **Analysis pane** — metrics, heatmaps, ablations, phase maps

### Jack owns

- application architecture  
- rendering and interaction  
- time scrubber  
- overlay systems  
- baseline vs wave comparison mode  
- export tools for images / video / metrics

### Grant owns

- defining what scientific overlays are most useful  
- making sure the visualizations reflect the intended quantities  
- suggesting the plots needed to support the claim

### Done when

- a user can click neurons and inspect them  
- the UI supports replay and comparison  
- the project is understandable without reading the code

---

## Milestone 15 — Build experiment orchestration and ablations

**Workload split:** Programming-heavy  
**Suggested lead:** Jack

### Goal

Run experiments systematically instead of by hand.

### Experiment dimensions

- scene type  
- motion direction  
- speed  
- contrast  
- noise level  
- active subset  
- wave kernel  
- coupling mode  
- mesh resolution  
- timestep / solver settings  
- fidelity class

### Required ablations

- no waves  
- waves only on chosen cell classes  
- no lateral coupling  
- shuffled synapse locations  
- shuffled morphology  
- coarser geometry  
- altered sign or delay assumptions

### Jack owns

- batch runner  
- config sweeps  
- result indexing  
- output storage conventions  
- summary tables and auto-generated comparison plots

### Grant owns

- choosing the scientifically meaningful ablations  
- defining which ablations are most diagnostic  
- interpreting the results

### Done when

- whole suites run from manifest files  
- ablations are reproducible  
- results are easy to compare

---

## Milestone 16 — Polish the demo narrative and showcase mode

**Workload split:** Shared, leaning programming  
**Suggested lead:** Jack

### Goal

Turn the system into a coherent hackathon demo.

### Target showcase flow

1. choose a visual scene  
2. show the fly-view / sampled input  
3. show the active visual subset  
4. show activity propagation  
5. compare baseline and wave mode  
6. highlight one phenomenon unique to the wave model  
7. show a clean summary analysis

### Jack owns

- scripted demo mode  
- saved presets  
- replay flow  
- camera transitions  
- polished UI state  
- exportable visuals

### Grant owns

- choosing the most convincing scientific comparisons  
- defining the narrative around why the wave version matters  
- making sure the highlighted effect is not a misleading artifact

### Done when

- someone unfamiliar with the code can follow the whole story  
- the demo feels intentional and smooth  
- the final effect shown is scientifically defensible

---

## Milestone 17 — Extend to whole-brain context views

**Workload split:** Programming-heavy  
**Suggested lead:** Jack

### Goal

Show where the active visual circuit sits inside the larger female brain context.

### Add

- whole-brain connectivity context views  
- downstream / upstream graph overlays  
- context-only nodes in network views  
- optional simplified downstream readout modules

### Jack owns

- graph visualization  
- context queries  
- scalable UI representations  
- linking active subset to whole-brain metadata

### Grant owns

- deciding which broader context relationships are scientifically worth showing  
- identifying meaningful downstream pathways for interpretation

### Done when

- the active visual subset can be viewed in larger brain context  
- context enriches the story without bloating the simulator

---

## Recommended division of labor by phase

### Phase 1 — Project foundation

**Jack**

- Milestones 2, 3, 4  
- data registry  
- subset selection  
- manifest schema

**Grant**

- Milestone 1  
- initial scientific claim  
- candidate observables  
- wave-model shortlist

**Shared checkpoint**

- finalize the active visual subset  
- finalize what outputs matter

---

### Phase 2 — Geometry and numerics foundation

**Jack**

- Milestone 5  
- operator implementation support for Milestone 6  
- asset QA tooling

**Grant**

- Milestone 6  
- operator design  
- stability reasoning  
- mesh/patch representation choice

**Shared checkpoint**

- agree on the state representation and operator API

---

### Phase 3 — Circuit coupling and inputs

**Jack**

- implementation-heavy parts of Milestones 7 and 8  
- synapse lookup tooling  
- stimulus and scene system  
- retinal frame pipeline implementation

**Grant**

- coupling kernels  
- delays  
- retinal abstraction  
- input interpretation assumptions

**Shared checkpoint**

- one end-to-end input frame reaches the chosen circuit

---

### Phase 4 — Baseline vs wave simulator

**Jack**

- Milestone 9  
- implementation-heavy parts of Milestone 10  
- logging and data plumbing

**Grant**

- model formulation for Milestone 10  
- stability criteria  
- parameter range selection

**Shared checkpoint**

- same experiment runs in both baseline and wave mode

---

### Phase 5 — Evaluation and presentation

**Jack**

- Milestones 14, 15, 16, 17  
- UI  
- orchestration  
- exports  
- showcase mode

**Grant**

- Milestones 12 and 13  
- metrics  
- validation logic  
- result interpretation

**Shared checkpoint**

- the final demo shows one quantitative and one visual advantage of the wave model

---

## Best end-to-end vertical slice

Before expanding the scope, aim for this first complete slice:

1. one motion-focused visual subset  
2. one canonical visual stimulus family  
3. one scene-generator scenario  
4. one baseline simulator  
5. one wave simulator  
6. one quantitative metric  
7. one polished comparison UI  
8. one “wow” morphology activity visualization

This is the minimum complete system that proves the architecture.

---

## Suggested interface contracts between Jack and Grant

To keep collaboration smooth, define these interfaces early.

### 1\. Subset manifest contract

A config format that says:

- which neurons are included  
- what fidelity class each neuron uses  
- which scene/stimulus is used  
- which readouts are active

### 2\. Operator contract

A format for:

- per-neuron operators  
- patch graphs  
- transfer operators  
- boundary conditions  
- discretization metadata

### 3\. Wave model contract

Grant defines:

- state variables  
- update equations  
- parameters  
- expected constraints

Jack implements:

- solver interface  
- stepping engine  
- serialization  
- profiling

### 4\. Result bundle contract

Every run should emit:

- metadata  
- per-neuron / per-patch state summaries  
- task readouts  
- validation metrics  
- comparison-ready outputs

### 5\. UI data contract

The simulator should expose:

- scene frames  
- retinal input  
- neuron activity overlays  
- traces  
- summary metrics  
- comparison results

---

## Strong recommendation

If you ever have to choose where to spend effort, bias toward this split:

### Jack should bias toward

- getting end-to-end pipelines working  
- making every stage reproducible  
- making the UI excellent  
- making the demo feel alive

### Grant should bias toward

- making the wave model worth believing  
- keeping the operators and coupling scientifically honest  
- designing the validation ladder  
- defining the strongest comparisons and ablations

That division plays to both of your strengths and keeps the project from collapsing into either:

- a great demo with weak science, or  
- a deep model with no usable presentation.

---

## Final build order recommendation

1. Milestone 1  
2. Milestone 2  
3. Milestone 3  
4. Milestone 4  
5. Milestone 5  
6. Milestone 6  
7. Milestone 8A / 8B in parallel with 7  
8. Milestone 9  
9. Milestone 10  
10. Milestone 11  
11. Milestone 12  
12. Milestone 13  
13. Milestone 8C if not already complete  
14. Milestone 14  
15. Milestone 15  
16. Milestone 16  
17. Milestone 17

If you want, this can be split next into:

- a **GitHub issues backlog**  
- a **Grant vs Jack task board**  
- or a **dependency graph / Kanban structure**

