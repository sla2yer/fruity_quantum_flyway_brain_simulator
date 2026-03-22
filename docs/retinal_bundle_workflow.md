## Record a retinal bundle

`scripts/12_retinal_bundle.py` resolves one canonical visual source, applies the
retinal geometry and sampling settings through library APIs, and writes a
reusable `retinal_input_bundle.v1` under the deterministic contract path:

```text
data/processed/retinal/bundles/<source_kind>/<source_family>/<source_name>/<source_hash>/<retinal_spec_hash>/
```

### From a canonical stimulus config

Use a config that already resolves both `stimulus` and `retinal_geometry`:

```bash
python scripts/12_retinal_bundle.py record --config path/to/retinal_stimulus.yaml
```

The config may add optional retinal playback settings under
`retinal_recording`:

```yaml
retinal_recording:
  sampling_kernel:
    acceptance_angle_deg: 0.5
    support_radius_deg: 1.0
    background_fill_value: 0.25
  body_pose:
    translation_world_mm: [0.0, 0.0, 0.0]
    yaw_pitch_roll_deg: [3.0, 0.0, 0.0]
  head_pose:
    translation_body_mm: [0.32, 0.0, 0.1]
    yaw_pitch_roll_deg: [4.0, 0.0, 0.0]
```

The workflow records or reuses the canonical Milestone 8A stimulus bundle
first, then samples that cached source into a retinal bundle. The retinal
metadata records the upstream stimulus bundle ID and metadata path in the
source lineage.

### From a scene entrypoint

Use a local scene YAML that defines `scene`, `retinal_geometry`, and optional
`retinal_recording`:

```bash
python scripts/12_retinal_bundle.py record --scene path/to/scene.yaml
```

The current scene entrypoint supports the local analytic fixture scene:

```yaml
scene:
  scene_family: analytic_panorama
  scene_name: yaw_gradient_panorama
  temporal_sampling:
    time_origin_ms: 0.0
    dt_ms: 20.0
    duration_ms: 60.0
  scene_parameters:
    background_level: 0.45
    azimuth_gain_per_deg: 0.001
    elevation_gain_per_deg: 0.0005
    temporal_modulation_amplitude: 0.1
    temporal_frequency_hz: 2.0
    phase_deg: 15.0
```

The resulting retinal bundle records the upstream scene hash and scene path in
its source lineage so later playback or simulator steps can trace back to the
world-space entrypoint.

## Replay a retinal bundle

Replay directly from a recorded retinal bundle:

```bash
python scripts/12_retinal_bundle.py replay \
  --bundle-metadata data/processed/retinal/bundles/.../retinal_input_bundle.json \
  --time-ms 0 --time-ms 20
```

Or resolve the same canonical output path from the source entrypoint:

```bash
python scripts/12_retinal_bundle.py replay --config path/to/retinal_stimulus.yaml --time-ms 20
python scripts/12_retinal_bundle.py replay --scene path/to/scene.yaml --time-ms 20
```
