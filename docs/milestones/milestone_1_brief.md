# Milestone 1 Brief

Status: Design locked  
Version: 1.0.0  
Last updated: 2026-03-21  
Owners: Grant (scientific content lead), Jack (repo artifact implementation)  
Source files:
- Workspace input `../response_milestone_1.md` for locked Milestone 1 scientific content
- Workspace input `../fruit_fly_wave_simulation_milestones.md` for ownership and deliverable requirements

## Purpose

Lock the Milestone 1 scientific claim, demo claim, and artifact contract so the repo can support a check-off-able design/specification milestone without overbuilding the simulator.

## Locked hypothesis

> Morphology-resolved surface dynamics constitute an additional intraneuronal computational degree of freedom, capable of shaping circuit input-output transformations through distributed spatiotemporal state on neuronal structure.

## Milestone 1 operational claim

> In a connectome-constrained Drosophila visual motion circuit, adding a morphology-resolved surface state should produce small but reproducible, geometry-dependent departures in shared circuit observables relative to fair point/reduced-neuron baselines.

Milestone 1 is about detectability, distinctness, and falsifiability of a small effect.

## What the wave model is allowed to add

- Surface-localized inputs on explicit T4/T5 morphology regions
- Surface propagation over a morphology graph
- Local timing structure from geodesic separation, spread, damping, and optional mild anisotropy
- A shared downstream readout so comparison to baselines stays fair

## What it must not add

- Extra connectome edges
- Different synapse signs
- Arbitrary extra weights or a larger tuning budget
- A decoder or readout unavailable to the baselines
- Hand-fitted per-synapse delays granted only to the surface model

## Baseline definitions

- `P0`: Canonical point baseline using passive leaky linear non-spiking single-compartment neurons matched to the same circuit and readout
- `P1`: Stronger reduced baseline using an effective-point or reduced-compartment model with explicit synaptic integration current or explicit delay structure

## Primary observable and companion observables

- Core observable: geometry-sensitive shared-output effect
- Primary observable: geometry-sensitive null-direction suppression
- Main companion observable: response latency
- Secondary shared readout: direction selectivity index

## Evidence ladder

- Weak: the surface model shows propagation or spread that the point model cannot show by construction
- Moderate: the surface model changes a shared readout such as null-direction suppression, latency, or DSI
- Strong: the shared-readout change shrinks or disappears when morphology or synapse topology is shuffled
- Very strong: the effect survives the stronger reduced baseline `P1`

## One-minute demo story

1. `0-10 s`: show a simple moving edge across a small retinotopic patch
2. `10-25 s`: split screen with matched point baseline on the left and surface model on the right for the same T4/T5-centered circuit
3. `25-38 s`: overlay shared output traces and highlight a small shift in null-direction suppression or latency
4. `38-50 s`: toggle intact versus shuffled synapse landing geometry and show the wave-specific difference collapse or materially shrink
5. `50-60 s`: freeze on a summary panel captioned "Small, causal, geometry-dependent computational effect."

## Must-show plots / UI states

- Stimulus overview for the simple moving-edge input
- Split view showing baseline scalar activity versus surface-state activity on morphology
- Shared output trace overlay for the same circuit and stimulus
- Null-direction suppression comparison plot
- Latency shift comparison plot
- Intact versus shuffled topology ablation comparison plot
- `P0` versus `P1` challenge-baseline comparison plot
- Final milestone decision panel summarizing the four decision-rule checks

## Non-goals

- Whole-brain intelligence claims
- Broad benchmark superiority
- Naturalistic cinematic scenes
- A wall of metrics
- A "look how pretty the waves are" reel
- Milestone 2+ simulator build-out beyond what is required to lock the design and output contract

## Milestone acceptance checklist

- [x] Versioned written brief exists in-repo
- [x] Locked hypothesis is preserved verbatim
- [x] Narrower Milestone 1 operational claim is preserved
- [x] `P0` and `P1` baseline definitions are explicit
- [x] Primary observable is centered on geometry-sensitive null-direction suppression
- [x] Response latency is defined as the main companion observable
- [x] One-minute demo story is defined
- [x] Must-show plots and UI states are defined
- [x] Decision rule is explicit and traceable to repo outputs

## Milestone 1 decision rule

Milestone 1 is successful only if all four hold:

1. Nonzero shared-output effect
2. Geometry dependence
3. Survival against a stronger reduced baseline
4. Stability across seeds and modest parameter changes

## Revision log

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-03-21 | Converted the Milestone 1 response into a versioned repo brief and aligned it to the roadmap ownership requirements. |
