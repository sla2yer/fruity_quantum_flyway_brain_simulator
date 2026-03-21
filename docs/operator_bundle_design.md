# Milestone 6 Operator Bundle Contract And Discretization Choice

This note freezes the first operator-facing contract for Milestone 6 so later
simulator work can target explicit archive roles and explicit numerical
assumptions instead of reverse-engineering Milestone 5 geometry bundles.

## Contract summary

The processed manifest now carries `_operator_contract_version:
operator_bundle.v1` plus a per-root `operator_bundle` block. That block owns:

- the fine operator archive
- the coarse operator archive
- the transfer-operator archive
- the operator metadata sidecar
- the realized discretization family and fallback status
- normalization / mass treatment
- boundary-condition mode
- geodesic-neighborhood settings
- transfer-operator availability

Compatibility during migration is deliberate:

- `fine_operator` now points to the dedicated
  `config.paths.processed_graph_dir/<root_id>_fine_operator.npz` archive
- `coarse_operator` now points to the dedicated
  `config.paths.processed_graph_dir/<root_id>_coarse_operator.npz` archive
- `patch_graph_path` is still written as the structural Milestone 5 topology
  summary used for preview / QA and for reconstructing the patch partition
- the legacy `<root_id>_meta.json` sidecar is still written so Milestone 5
  consumers do not break while downstream code migrates to the new contract

## Candidate families

### Graph-based surface operators

Definition:

- surface adjacency from the simplified mesh connectivity
- combinatorial or normalized graph Laplacian
- patch transfers built from patch membership only

Advantages:

- robust on imperfect meshes
- cheap to build and easy to regression test
- no dependence on cotangent-weight edge cases

Costs:

- ignores triangle geometry and surface area unless extra weighting is added
- geodesic distance is only approximated by hop count
- boundary semantics are implicit and easy to misinterpret
- convergence to a surface PDE is weaker than for a metric-aware mesh operator

### Mesh-based operators

Definition:

- triangle-mesh Laplace-Beltrami discretization on the simplified surface
- cotangent stiffness matrix
- explicit mass matrix
- coarse operators derived from fine operators and transfer maps

Advantages:

- metric-aware and standard for diffusion / wave equations on surfaces
- makes conservation and stability statements precise in a mesh inner product
- clean boundary interpretation when seams or open surfaces exist
- gives a principled path to Galerkin coarse operators

Costs:

- requires handling degenerate triangles, non-manifold cases, and negative
  cotangent edge contributions carefully
- more implementation work than a graph Laplacian

## Decision

The default fine-surface discretization for Milestone 6 is:

- `triangle_mesh_cotangent_fem`
- lumped mass matrix
- mass-normalized state inner product
- zero-flux boundary handling on the simplified closed surface

This is the default the later wave engine should treat as scientifically
authoritative.

The default coarse construction is:

- fine-to-coarse restriction by lumped-mass patch averaging
- coarse-to-fine prolongation by piecewise-constant patch injection
- coarse operator by Galerkin projection from the fine operator

This keeps the fine and coarse systems comparable in one inner product instead
of treating the patch graph as an unrelated second discretization.

More explicitly, the Milestone 6 bundle now serializes:

- physical-field prolongation `P` that is constant on each patch
- physical-field restriction `R = M_c^{-1} P^T M_f`
- coarse patch mass `M_c = P^T M_f P`
- coarse patch stiffness `K_c = P^T K_f P`
- normalized transfers `P_hat = M_f^{1/2} P M_c^{-1/2}` and
  `R_hat = P_hat^T`
- normalized coarse operator `A_c = M_c^{-1/2} K_c M_c^{-1/2}`

That means coarse dynamics are derived from the same variational object as the
fine surface operator instead of from an unrelated patch-edge heuristic.

## Allowed fallback

Fallback is allowed when the default operator cannot be serialized safely or has
not been built yet. The allowed fallback family is:

- `surface_graph_uniform_laplacian`
- counting-measure / uniform-vertex averaging on transfers
- geodesic neighborhoods represented by surface-graph hop counts

Use the fallback only when at least one of these is true:

1. the simplified mesh has degeneracies or topology issues that make cotangent
   assembly unreliable
2. a build is intentionally limited to the Milestone 5 geometry bundle plus
   structural transfer data
3. a regression fixture needs a deterministic structural operator without the
   full metric machinery

Whenever fallback is used, the manifest must say so explicitly through the
per-root `operator_bundle.discretization_family`, `mass_treatment`,
`normalization`, and `realization_mode` fields.

## Conserved and damped quantities

The later wave engine inherits these expectations:

- the constant field remains in the nullspace of the Laplacian
- zero-flux boundaries do not inject or remove net mass
- pure diffusion should dissipate energy and preserve total mass
- undamped wave propagation should not gain energy from the spatial operator
- any damping operator must be positive semidefinite and separate from the
  conservative spatial operator
- fine/coarse restriction and prolongation should preserve constants; no
  transfer step should create a net source term by itself

## Stability-relevant assumptions

Later milestones should preserve these assumptions instead of silently changing
them:

- stiffness operators are symmetric
- mass operators are positive diagonal after lumping
- the effective generalized operator is positive semidefinite
- boundary treatment stays zero-flux unless an experiment explicitly opts into
  absorbing or clamped boundaries
- time-step limits should be derived from the largest relevant eigenvalue of
  `M^{-1}L` rather than an ad hoc graph-degree rule
- coarse operators and transfer maps should be interpreted in the same inner
  product as the fine operator

## What the current bundle guarantees

`operator_bundle.v1` now serializes:

- a dedicated fine operator archive with cotangent stiffness, lumped mass,
  symmetric mass-normalized operator form, and explicit supporting geometry
- a dedicated coarse operator archive with patch mass, Galerkin stiffness, the
  normalized coarse operator, and patch-local supporting arrays
- an explicit transfer-operator archive with physical-field restriction /
  prolongation, normalized-state transfer operators, and quality metrics
- an operator metadata sidecar that records the realized discretization,
  weighting scheme, frame convention, boundary mode, geodesic settings, coarse
  assembly rule, and coarse-versus-fine comparison metrics

The serialized quality metrics are intentionally simple and inspectable:

- constant-field transfer residuals
- total-mass / total-area preservation residuals
- normalized transfer adjoint / identity residuals
- Galerkin residual `||A_c - R_hat A_f P_hat||`
- coarse-subspace application residual and Rayleigh-quotient drift
- fine-state and fine-application projection residuals for a deterministic
  fixture probe
