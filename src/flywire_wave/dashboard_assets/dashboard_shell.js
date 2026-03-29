(function () {
  "use strict";

  const bootstrapNode = document.getElementById("dashboard-app-bootstrap");
  if (!bootstrapNode) {
    return;
  }

  const bootstrap = JSON.parse(bootstrapNode.textContent || "{}");
  const stateRoot = document.querySelector("[data-dashboard-root]");
  if (!stateRoot) {
    return;
  }

  const store = createDashboardStore(bootstrap);
  bindControls(store);
  store.subscribe(function render() {
    renderDashboard(store, bootstrap);
  });
  renderDashboard(store, bootstrap);

  function createDashboardStore(model) {
    let state = clone(model.global_interaction_state);
    state.hovered_neuron_id = null;
    state.hover_source_pane_id = null;

    const listeners = new Set();
    const replayModel = model.replay_model || {};
    const timebase = replayModel.timebase || model.time_series_context.timebase || {};
    const bounds = replayModel.time_cursor_bounds || {};
    const maxSampleIndex = Math.max(
      0,
      Number(
        bounds.max_sample_index !== undefined
          ? bounds.max_sample_index
          : Number(timebase.sample_count || 1) - 1
      )
    );
    const dtMs = Number(timebase.dt_ms || 0);
    const playbackIntervalMs = Math.max(
      180,
      Number(replayModel.playback_interval_ms || Math.round(Math.max(dtMs, 1) * 18))
    );
    let playbackTimer = null;

    function emit() {
      listeners.forEach(function notify(listener) {
        listener(clone(state));
      });
    }

    function syncPlayback() {
      const shouldPlay = state.time_cursor.playback_state === "playing";
      if (!shouldPlay && playbackTimer !== null) {
        window.clearInterval(playbackTimer);
        playbackTimer = null;
        return;
      }
      if (shouldPlay && playbackTimer === null) {
        playbackTimer = window.setInterval(function tick() {
          const nextIndex = Number(state.time_cursor.sample_index) + 1;
          if (nextIndex > maxSampleIndex) {
            setPlaybackState("paused");
            return;
          }
          setTimeCursorSampleIndex(nextIndex);
        }, playbackIntervalMs);
      }
    }

    function setState(mutator) {
      const draft = clone(state);
      mutator(draft);
      state = normalizeState(model, draft);
      syncPlayback();
      emit();
    }

    function availableOverlays(nextState) {
      return getOverlayOptions(model, nextState).filter(function onlyAvailable(item) {
        return item.availability === "available";
      });
    }

    function ensureActiveOverlay(nextState) {
      const activeOverlayId = String(nextState.active_overlay_id);
      const available = availableOverlays(nextState);
      const activeAvailable = available.some(function isActive(item) {
        return item.overlay_id === activeOverlayId;
      });
      if (activeAvailable) {
        return nextState;
      }
      if (available.length > 0) {
        nextState.active_overlay_id = String(available[0].overlay_id);
      }
      return nextState;
    }

    function setActiveArmId(armId) {
      setState(function update(draft) {
        draft.selected_arm_pair.active_arm_id = String(armId);
      });
    }

    function setSelectedNeuronId(rootId) {
      setState(function update(draft) {
        draft.selected_neuron_id = Number(rootId);
      });
    }

    function setSelectedReadoutId(readoutId) {
      setState(function update(draft) {
        draft.selected_readout_id = String(readoutId);
      });
    }

    function setActiveOverlayId(overlayId) {
      setState(function update(draft) {
        draft.active_overlay_id = String(overlayId);
        ensureActiveOverlay(draft);
      });
    }

    function setComparisonMode(comparisonModeId) {
      setState(function update(draft) {
        draft.comparison_mode = String(comparisonModeId);
        ensureActiveOverlay(draft);
      });
    }

    function setPlaybackState(playbackState) {
      setState(function update(draft) {
        draft.time_cursor.playback_state = String(playbackState);
      });
    }

    function togglePlayback() {
      setPlaybackState(
        state.time_cursor.playback_state === "playing" ? "paused" : "playing"
      );
    }

    function setTimeCursorSampleIndex(index) {
      setState(function update(draft) {
        const clamped = Math.max(0, Math.min(maxSampleIndex, Number(index)));
        draft.time_cursor.sample_index = clamped;
        draft.time_cursor.time_ms = Number(timebase.time_origin_ms || 0) + clamped * dtMs;
      });
    }

    function stepCursor(direction) {
      setTimeCursorSampleIndex(Number(state.time_cursor.sample_index) + Number(direction));
    }

    function rewindCursor() {
      setState(function update(draft) {
        draft.time_cursor.playback_state = "paused";
        draft.time_cursor.sample_index = 0;
        draft.time_cursor.time_ms = Number(timebase.time_origin_ms || 0);
      });
    }

    function setHoveredNeuronId(rootId, sourcePaneId) {
      setState(function update(draft) {
        if (rootId === null || rootId === undefined || rootId === "") {
          draft.hovered_neuron_id = null;
          draft.hover_source_pane_id = null;
          return;
        }
        draft.hovered_neuron_id = Number(rootId);
        draft.hover_source_pane_id = String(sourcePaneId || "");
      });
    }

    function clearHoveredNeuronId() {
      setHoveredNeuronId(null, null);
    }

    return {
      subscribe: function subscribe(listener) {
        listeners.add(listener);
        return function unsubscribe() {
          listeners.delete(listener);
        };
      },
      getState: function getState() {
        return clone(state);
      },
      actions: {
        clearHoveredNeuronId: clearHoveredNeuronId,
        rewindCursor: rewindCursor,
        setActiveArmId: setActiveArmId,
        setActiveOverlayId: setActiveOverlayId,
        setComparisonMode: setComparisonMode,
        setHoveredNeuronId: setHoveredNeuronId,
        setPlaybackState: setPlaybackState,
        setSelectedNeuronId: setSelectedNeuronId,
        setSelectedReadoutId: setSelectedReadoutId,
        setTimeCursorSampleIndex: setTimeCursorSampleIndex,
        stepCursor: stepCursor,
        togglePlayback: togglePlayback,
      },
    };
  }

  function normalizeState(model, candidate) {
    const next = clone(candidate);
    const selectedBundlePair = model.selected_bundle_pair || {};
    const allowedArmIds = [
      String((selectedBundlePair.baseline || {}).arm_id || ""),
      String((selectedBundlePair.wave || {}).arm_id || ""),
    ].filter(Boolean);
    if (!allowedArmIds.includes(String(next.selected_arm_pair.active_arm_id))) {
      next.selected_arm_pair.active_arm_id = allowedArmIds[0] || "";
    }

    const rootCatalog = Array.isArray(model.morphology_context.root_catalog)
      ? model.morphology_context.root_catalog
      : [];
    const selectedRootIds = rootCatalog.map(function collect(item) {
      return Number(item.root_id);
    });
    if (!selectedRootIds.includes(Number(next.selected_neuron_id))) {
      next.selected_neuron_id = selectedRootIds[0] || 0;
    }

    const circuitNodes = getCircuitNodes(model);
    const hoverableRootIds = circuitNodes.map(function collect(item) {
      return Number(item.root_id);
    });
    if (next.hovered_neuron_id !== null && next.hovered_neuron_id !== undefined) {
      if (!hoverableRootIds.includes(Number(next.hovered_neuron_id))) {
        next.hovered_neuron_id = null;
        next.hover_source_pane_id = null;
      } else {
        next.hovered_neuron_id = Number(next.hovered_neuron_id);
        next.hover_source_pane_id = next.hover_source_pane_id
          ? String(next.hover_source_pane_id)
          : "circuit";
      }
    } else {
      next.hovered_neuron_id = null;
      next.hover_source_pane_id = null;
    }

    const readouts = Array.isArray(model.time_series_context.comparable_readout_catalog)
      ? model.time_series_context.comparable_readout_catalog
      : [];
    const readoutIds = readouts.map(function collect(item) {
      return String(item.readout_id);
    });
    if (!readoutIds.includes(String(next.selected_readout_id))) {
      next.selected_readout_id = readoutIds[0] || "";
    }

    const comparisonModes = Array.isArray(model.comparison_mode_catalog)
      ? model.comparison_mode_catalog
      : [];
    const comparisonModeIds = comparisonModes.map(function collect(item) {
      return String(item.comparison_mode_id);
    });
    if (!comparisonModeIds.includes(String(next.comparison_mode))) {
      next.comparison_mode = comparisonModeIds[0] || "";
    }
    const availableComparisonModes = getComparisonModeOptions(model)
      .filter(function onlyAvailable(item) {
        return item.availability === "available";
      })
      .map(function map(item) {
        return String(item.comparison_mode_id);
      });
    if (
      availableComparisonModes.length > 0 &&
      availableComparisonModes.indexOf(String(next.comparison_mode)) === -1
    ) {
      next.comparison_mode = availableComparisonModes[0];
    }

    const replayModel = model.replay_model || {};
    const timebase = replayModel.timebase || model.time_series_context.timebase || {};
    const sampleCount = Math.max(1, Number(timebase.sample_count || 1));
    const clampedIndex = Math.max(
      0,
      Math.min(sampleCount - 1, Number(next.time_cursor.sample_index || 0))
    );
    next.time_cursor.sample_index = clampedIndex;
    const canonicalTime = Array.isArray(replayModel.canonical_time_ms)
      ? replayModel.canonical_time_ms
      : [];
    next.time_cursor.time_ms =
      canonicalTime.length > clampedIndex
        ? Number(canonicalTime[clampedIndex] || 0)
        : Number(timebase.time_origin_ms || 0) + clampedIndex * Number(timebase.dt_ms || 0);
    if (["paused", "playing"].indexOf(String(next.time_cursor.playback_state)) === -1) {
      next.time_cursor.playback_state = "paused";
    }

    return next;
  }

  function bindControls(store) {
    bindChange("dashboard-comparison-mode", function (value) {
      store.actions.setComparisonMode(value);
    });
    bindChange("dashboard-overlay-mode", function (value) {
      store.actions.setActiveOverlayId(value);
    });
    bindChange("dashboard-neuron", function (value) {
      store.actions.setSelectedNeuronId(value);
    });
    bindChange("dashboard-readout", function (value) {
      store.actions.setSelectedReadoutId(value);
    });
    bindInput("dashboard-time-cursor", function (value) {
      store.actions.setTimeCursorSampleIndex(value);
    });

    document.querySelectorAll("[data-arm-id]").forEach(function attach(node) {
      node.addEventListener("click", function onClick() {
        store.actions.setActiveArmId(node.getAttribute("data-arm-id"));
      });
    });

    document.querySelectorAll("[data-playback-action]").forEach(function attach(node) {
      node.addEventListener("click", function onClick() {
        const action = node.getAttribute("data-playback-action");
        if (action === "rewind") {
          store.actions.rewindCursor();
          return;
        }
        if (action === "step_back") {
          store.actions.setPlaybackState("paused");
          store.actions.stepCursor(-1);
          return;
        }
        if (action === "step_forward") {
          store.actions.setPlaybackState("paused");
          store.actions.stepCursor(1);
          return;
        }
        store.actions.togglePlayback();
      });
    });
  }

  function renderDashboard(store, model) {
    const state = store.getState();
    renderToolbar(state, model);
    renderScenePane(state, model);
    renderCircuitPane(state, model, store);
    renderMorphologyPane(state, model, store);
    renderTimeSeriesPane(state, model);
    renderAnalysisPane(state, model);
  }

  function renderToolbar(state, model) {
    document.querySelectorAll("[data-arm-id]").forEach(function toggle(node) {
      node.classList.toggle(
        "is-active",
        node.getAttribute("data-arm-id") === String(state.selected_arm_pair.active_arm_id)
      );
    });

    syncComparisonModeSelect(state, model);
    syncSelectValue("dashboard-neuron", String(state.selected_neuron_id));
    syncSelectValue("dashboard-readout", String(state.selected_readout_id));
    syncOverlaySelect(state, model);
    syncTimeControls(state);
    syncPlaybackButtons(state);
  }

  function renderScenePane(state, model) {
    const body = getPaneBody("scene");
    if (!body) {
      return;
    }
    const scene = model.scene_context || {};
    const pair = model.selected_bundle_pair || {};
    const frame = sceneFrameForState(scene, state);
    const renderLayer = activeSceneLayer(scene);
    const renderStatus = String(scene.render_status || "unavailable");

    body.innerHTML = [
      paneBand(
        "Synchronized input view",
        "",
        '<div class="scene-band-grid">' +
          '<div class="scene-stage">' +
          sceneCanvasMarkup(frame, renderStatus, scene) +
          "</div>" +
          '<div class="scene-sidebar">' +
          pillRow([
            statePill("Active arm", String(state.selected_arm_pair.active_arm_id)),
            statePill("Overlay", overlayName(model, state.active_overlay_id)),
            statePill(
              "Cursor",
              formatTimeCursor(state.time_cursor.time_ms, state.time_cursor.sample_index)
            ),
          ]) +
          paragraph(
            renderStatus === "available"
              ? "The frame comes from the packaged dashboard session payload, derived from the canonical stimulus or retinal contract for this session."
              : "No replayable scene layer is available for this session. The pane keeps the contract-backed metadata visible instead of fabricating context."
          ) +
          layerChipList(scene.render_layers || []) +
          summaryList([
            ["Source", String(scene.source_kind || "unknown")],
            ["Name", String(scene.stimulus_name || scene.representation_family || "n/a")],
            ["Conditions", String((scene.selected_condition_ids || []).join(", ") || "n/a")],
            ["Replay source", String(((scene.frame_discovery || {}).replay_source) || "n/a")],
            ["Frame count", String(((scene.frame_discovery || {}).frame_count) || 0)],
            ["Baseline arm", String((pair.baseline || {}).arm_id || "n/a")],
            ["Wave arm", String((pair.wave || {}).arm_id || "n/a")],
          ]) +
          "</div>" +
          "</div>"
      ),
      paneBand(
        "Frame metrics",
        "",
        frame
          ? summaryList([
              ["Frame index", String(frame.frame_index)],
              ["Frame time", Number(frame.time_ms).toFixed(1) + " ms"],
              ["Render size", String(frame.width) + " x " + String(frame.height)],
              ["Mean luminance", Number(frame.mean_luminance).toFixed(3)],
              ["Range", Number(frame.min_luminance).toFixed(3) + " to " + Number(frame.max_luminance).toFixed(3)],
            ])
          : summaryList([
              ["Render status", String(renderStatus)],
              [
                "Reason",
                String(((scene.frame_discovery || {}).unavailable_reason) || "scene layer unavailable"),
              ],
            ])
      ),
    ].join("");

    if (frame) {
      const canvas = body.querySelector("[data-scene-canvas='true']");
      paintSceneFrame(canvas, frame);
    }
  }

  function renderCircuitPane(state, model, store) {
    const body = getPaneBody("circuit");
    if (!body) {
      return;
    }
    const circuit = model.circuit_context || {};
    const selectedRoots = Array.isArray(circuit.root_catalog) ? circuit.root_catalog : [];
    const connectivity = circuit.connectivity_context || {};
    const graphNodes = Array.isArray(connectivity.node_catalog) ? connectivity.node_catalog : [];
    const focusNode = focusedCircuitNode(model, state);
    const layerCards = circuitLayerCards(connectivity.context_layers || {});

    body.innerHTML = [
      paneBand(
        "Connectivity context",
        "",
        '<div class="circuit-band-grid">' +
          '<div class="circuit-graph-shell">' +
          circuitGraphMarkup(graphNodes, connectivity.edge_catalog || [], state) +
          "</div>" +
          '<div class="circuit-side-column">' +
          pillRow([
            statePill("Selected neuron", String(state.selected_neuron_id)),
            statePill("Hover", hoveredNeuronLabel(model, state)),
            statePill(
              "Edges",
              String(((connectivity.network_summary || {}).edge_count) || 0)
            ),
            statePill(
              "Cursor",
              formatTimeCursor(state.time_cursor.time_ms, state.time_cursor.sample_index)
            ),
          ]) +
          layerCards +
          summaryList([
            [
              "Selected roots",
              String(((connectivity.network_summary || {}).selected_root_count) || selectedRoots.length),
            ],
            [
              "Context roots",
              String(((connectivity.network_summary || {}).context_root_count) || 0),
            ],
            [
              "Total synapses",
              String(((connectivity.network_summary || {}).total_synapse_count) || 0),
            ],
            ["Overlay", overlayName(model, state.active_overlay_id)],
          ]) +
          "</div>" +
          "</div>"
      ),
      paneBand(
        "Subset roster",
        "",
        '<div class="circuit-band-grid">' +
          '<div class="root-list-grid">' +
          selectedRoots.map(function render(root) {
            return selectedRootCardMarkup(root, state);
          }).join("") +
          "</div>" +
          circuitFocusCardMarkup(focusNode, connectivity, circuit) +
          "</div>"
      ),
    ].join("");

    attachCircuitInteractions(body, store);
  }

  function renderMorphologyPane(state, model, store) {
    const body = getPaneBody("morphology");
    if (!body) {
      return;
    }
    const morphology = model.morphology_context || {};
    const rootCatalog = Array.isArray(morphology.root_catalog) ? morphology.root_catalog : [];
    const selectedRoot =
      rootCatalog.find(function find(root) {
        return Number(root.root_id) === Number(state.selected_neuron_id);
      }) || rootCatalog[0] || {};
    const hoveredNode = focusedCircuitNode(model, state);
    const overlayState = resolveMorphologyOverlayState(morphology, state, selectedRoot);
    const geometry = selectedRoot.render_geometry || {};
    body.innerHTML = [
      paneBand(
        "Geometry Focus",
        "",
        '<div class="morphology-band-grid">' +
          '<div class="morphology-stage-shell">' +
          morphologyStageMarkup(selectedRoot, overlayState) +
          "</div>" +
          '<div class="morphology-side-column">' +
          pillRow([
            statePill("Neuron", String(state.selected_neuron_id)),
            statePill("Hover", hoveredNeuronLabel(model, state)),
            statePill("Readout", String(state.selected_readout_id)),
          ]) +
          overlayScopeBanner(overlayState) +
          summaryList([
            ["Cell type", String(selectedRoot.cell_type || "unknown")],
            ["Project role", String(selectedRoot.project_role || "unknown")],
            ["Morphology class", String(selectedRoot.morphology_class || "unknown")],
            [
              "Runtime representation",
              String((selectedRoot.preferred_representation || geometry.representation_id || "unknown")).replace(/_/g, " "),
            ],
            [
              "Available geometry",
              String((selectedRoot.available_representations || []).join(", ") || "n/a"),
            ],
            [
              "Wave diagnostics",
              String((((selectedRoot.overlay_samples || {}).wave_patch_activity || {}).availability) || "unknown"),
            ],
          ]) +
          paragraph(String(((selectedRoot.inspection || {}).truth_note) || (geometry.truth_note || "No morphology truth note is available."))) +
          overlayStatusCard(overlayState) +
          "</div>" +
          "</div>"
      ),
      paneBand(
        "Selected Subset",
        "",
        '<div class="morphology-root-grid">' +
          rootCatalog.map(function render(root) {
            return morphologyRootCardMarkup(root, state);
          }).join("") +
          "</div>"
      ),
      paneBand(
        "Linked Inspection",
        "",
        paragraph(
          overlayNarrative(model, state.active_overlay_id, state.comparison_mode)
        ) +
          summaryList([
            ["Camera focus", formatCameraFocus(selectedRoot.camera_focus || geometry.camera_focus || {})],
            ["Hover source", String(state.hover_source_pane_id || "none")],
            [
              "Hover metadata",
              hoveredNode
                ? [
                    String(hoveredNode.root_id),
                    String(hoveredNode.cell_type || hoveredNode.subset_membership || "context"),
                  ].join(" | ")
                : "none",
            ],
            [
              "Phase maps",
              String((((selectedRoot.phase_map_reference || {}).availability) || "unavailable")),
            ],
          ])
      ),
    ].join("");
    attachMorphologyInteractions(body, store);
  }

  function renderTimeSeriesPane(state, model) {
    const body = getPaneBody("time_series");
    if (!body) {
      return;
    }
    let viewModel;
    try {
      viewModel = resolveTimeSeriesViewModel(model, state);
    } catch (error) {
      const message = error && error.message ? error.message : String(error);
      body.innerHTML = paneBand(
        "Comparison unavailable",
        "",
        comparisonFailureMarkup(message)
      );
      return;
    }
    const comparisonOptions = getComparisonModeOptions(model);
    const unavailableComparisons = comparisonOptions.filter(function filter(item) {
      return item.availability !== "available";
    });
    const selectedRoot = viewModel.selected_root || {};
    const shared = viewModel.shared_comparison || {};
    const waveDiagnostic = viewModel.wave_diagnostic || {};
    body.innerHTML = [
      paneBand(
        "Replay cursor",
        "",
        pillRow([
          statePill("Playback", String(state.time_cursor.playback_state)),
          statePill(
            "Cursor",
            formatTimeCursor(state.time_cursor.time_ms, state.time_cursor.sample_index)
          ),
          statePill("Hover", hoveredNeuronLabel(model, state)),
          statePill("Neuron", String(selectedRoot.root_id || state.selected_neuron_id)),
        ]) +
          paragraph(
            "The replay cursor and neuron focus are linked dashboard state. Scene, circuit, morphology, readout, and analysis panes all read the same selection and time cursor."
          ) +
          (unavailableComparisons.length > 0
            ? comparisonFailureMarkup(
                unavailableComparisons
                  .map(function map(item) {
                    return String(item.display_name) + ": " + String(item.reason || "unavailable");
                  })
                  .join(" | ")
              )
            : "")
      ),
      paneBand(
        "Shared comparison traces",
        "",
        scopeBannerMarkup(
          "shared_comparison",
          "Fairness-critical shared readout surface on the canonical replay timebase."
        ) +
          timeSeriesChartMarkup(
            shared.chart_series || [],
            viewModel.cursor.sample_index,
            "shared_comparison"
          ) +
        summaryList([
          ["Readout", String(shared.display_name || shared.readout_id || "n/a")],
          ["Units", String(shared.units || "n/a")],
          ["Baseline", Number(shared.baseline_value || 0).toFixed(3)],
          ["Wave", Number(shared.wave_value || 0).toFixed(3)],
          ["Delta", Number(shared.delta_value || 0).toFixed(3)],
          ["Selection", String(selectedRoot.root_id || "n/a") + " | " + String(selectedRoot.morphology_class || "unknown")],
        ]) +
          paragraph(String(shared.fairness_note || ""))
      ),
      paneBand(
        "Wave-only diagnostic",
        "",
        scopeBannerMarkup(
          "wave_only_diagnostic",
          "Wave-only diagnostics stay visible, but they are intentionally separated from the shared comparison trace."
        ) +
          (waveDiagnostic.availability === "available"
            ? timeSeriesChartMarkup(
                [
                  {
                    series_id: "wave_diagnostic",
                    display_name: "Wave diagnostic",
                    values: waveDiagnostic.values || [],
                    scope_label: "wave_only_diagnostic",
                  },
                ],
                viewModel.cursor.sample_index,
                "wave_only_diagnostic"
              )
            : comparisonFailureMarkup(
                String(waveDiagnostic.reason || "No wave-only diagnostic is packaged for the selected neuron.")
              )) +
          summaryList([
            ["Root", String(selectedRoot.root_id || "n/a")],
            ["Diagnostic", String(waveDiagnostic.display_name || "n/a")],
            ["Availability", String(waveDiagnostic.availability || "unknown")],
            ["Cursor value", waveDiagnostic.availability === "available" ? Number(waveDiagnostic.cursor_value || 0).toFixed(3) : "n/a"],
            ["Elements", String(waveDiagnostic.element_count || 0)],
            ["Semantics", String(waveDiagnostic.projection_semantics || "n/a")],
          ])
      ),
    ].join("");
  }

  function renderAnalysisPane(state, model) {
    const body = getPaneBody("analysis");
    if (!body) {
      return;
    }
    const analysis = model.analysis_context || {};
    const shared = analysis.shared_comparison || {};
    const wave = analysis.wave_only_diagnostics || {};
    const validation = analysis.validation_evidence || {};
    const overlayOptions = analysisOverlayOptions(model, state);
    let timeSeriesView = null;
    let timeSeriesError = null;
    try {
      timeSeriesView = resolveTimeSeriesViewModel(model, state);
    } catch (error) {
      timeSeriesError = error && error.message ? error.message : String(error);
    }
    const overlayState = resolveAnalysisOverlayState(
      analysis,
      state,
      timeSeriesView,
      timeSeriesError,
      overlayOptions
    );
    const exportTargets = (Array.isArray(model.export_target_catalog)
      ? model.export_target_catalog
      : []
    ).filter(function onlyAnalysis(item) {
      const panes = Array.isArray(item.supported_pane_ids) ? item.supported_pane_ids : [];
      return panes.indexOf("analysis") !== -1;
    });
    body.innerHTML = [
      paneBand(
        "Overlay Focus",
        "",
        pillRow([
          statePill("Comparison", comparisonModeName(model, state.comparison_mode)),
          statePill("Overlay", overlayName(model, state.active_overlay_id)),
          statePill("Cursor", formatTimeCursor(state.time_cursor.time_ms, state.time_cursor.sample_index)),
          statePill("Neuron", String(state.selected_neuron_id)),
          statePill("Readout", String(state.selected_readout_id)),
        ]) +
          overlayScopeBanner(overlayState) +
          analysisOverlaySummaryMarkup(overlayState)
      ),
      paneBand(
        "Shared Comparison",
        "",
        scopeBannerMarkup(
          "shared_comparison",
          "Packaged Milestone 12 shared-comparison cards stay separated from wave-only and reviewer-facing evidence."
        ) +
          analysisSectionMarkup(
            "Task summary cards",
            Array.isArray(shared.task_summary_cards) ? shared.task_summary_cards : [],
            analysisTaskCardMarkup
          ) +
          analysisSectionMarkup(
            "Comparison cards",
            Array.isArray(shared.comparison_cards) ? shared.comparison_cards : [],
            analysisComparisonCardMarkup
          ) +
          analysisSectionMarkup(
            "Ablation summaries",
            Array.isArray(shared.ablation_summaries) ? shared.ablation_summaries : [],
            analysisAblationCardMarkup
          ) +
          matrixDeckMarkup(Array.isArray(shared.matrix_views) ? shared.matrix_views : [])
      ),
      paneBand(
        "Wave-Only Diagnostics",
        "",
        scopeBannerMarkup(
          "wave_only_diagnostic",
          "Wave diagnostics remain visible, but they stay explicitly outside the fairness-critical shared comparison surface."
        ) +
          analysisSectionMarkup(
            "Diagnostic cards",
            Array.isArray(wave.diagnostic_cards) ? wave.diagnostic_cards : [],
            analysisDiagnosticCardMarkup
          ) +
          analysisSectionMarkup(
            "Phase-map references",
            Array.isArray(wave.phase_map_references) ? wave.phase_map_references : [],
            function render(item) {
              return analysisPhaseMapCardMarkup(item, state.selected_neuron_id);
            }
          ) +
          matrixDeckMarkup(Array.isArray(wave.matrix_views) ? wave.matrix_views : [])
      ),
      paneBand(
        "Validation Evidence",
        "",
        scopeBannerMarkup(
          "validation_evidence",
          "Reviewer-oriented Milestone 13 evidence stays visually distinct from shared-comparison metrics and wave diagnostics."
        ) +
          validationStatusMarkup(validation) +
          analysisSectionMarkup(
            "Validator summaries",
            Array.isArray(validation.validator_summaries) ? validation.validator_summaries : [],
            validationSummaryCardMarkup
          ) +
          analysisSectionMarkup(
            "Open findings",
            Array.isArray(validation.open_findings) ? validation.open_findings : [],
            validationFindingCardMarkup
          )
      ),
      paneBand(
        "Overlay Catalog And Exports",
        "",
        analysisOverlayCatalogMarkup(overlayOptions) +
          analysisSectionMarkup(
            "Deterministic exports",
            exportTargets,
            exportTargetCardMarkup
          ) +
          linkRow(model.links)
      ),
    ].join("");
  }

  function analysisOverlayOptions(model, state) {
    const analysis = model.analysis_context || {};
    const entries =
      (((analysis.analysis_overlay_catalog || {}).entries) && Array.isArray((analysis.analysis_overlay_catalog || {}).entries))
        ? (analysis.analysis_overlay_catalog || {}).entries
        : [];
    const summaryCounts = analysis.summary_counts || {};
    const statusCard = ((analysis.validation_evidence || {}).status_card) || {};
    return entries.map(function map(item) {
      let availability = "available";
      let reason = null;
      const supportedModes = Array.isArray(item.supported_comparison_modes)
        ? item.supported_comparison_modes
        : [];
      if (supportedModes.indexOf(String(state.comparison_mode)) === -1) {
        availability = "unavailable";
        reason = "not supported by " + comparisonModeName(model, state.comparison_mode);
      } else if (String(item.overlay_id) === "shared_readout_activity") {
        if (
          Number(summaryCounts.task_summary_card_count || 0) < 1 &&
          Number(summaryCounts.shared_comparison_card_count || 0) < 1
        ) {
          availability = "unavailable";
          reason = "shared comparison summaries are absent from the packaged analysis payload";
        }
      } else if (String(item.overlay_id) === "paired_readout_delta") {
        if (Number(summaryCounts.matrix_view_count || 0) < 1) {
          availability = "unavailable";
          reason = "matrix-like comparison views are absent from the packaged analysis payload";
        }
      } else if (String(item.overlay_id) === "wave_patch_activity") {
        if (Number(analysis.wave_diagnostic_card_count || 0) < 1) {
          availability = "unavailable";
          reason = "requested wave-only diagnostics are absent from the packaged analysis payload";
        }
      } else if (String(item.overlay_id) === "phase_map_reference") {
        if (Number(analysis.phase_map_reference_count || 0) < 1) {
          availability = "unavailable";
          reason = "requested phase-map references are absent from the packaged analysis payload";
        }
      } else if (String(item.overlay_id) === "validation_status_badges") {
        if (!String(statusCard.overall_status || "").trim()) {
          availability = "unavailable";
          reason = "validation summary is missing overall_status";
        }
      } else if (String(item.overlay_id) === "reviewer_findings") {
        if (!((analysis.validation_evidence || {}).review_handoff)) {
          availability = "unavailable";
          reason = "validation review handoff is empty";
        }
      }
      return {
        overlay_id: String(item.overlay_id),
        display_name: String(item.display_name),
        overlay_category: String(item.overlay_category),
        description: String(item.description || ""),
        availability: availability,
        reason: reason,
      };
    });
  }

  function resolveAnalysisOverlayState(analysis, state, timeSeriesView, timeSeriesError, overlayOptions) {
    const overlayId = String(state.active_overlay_id);
    const entry =
      (Array.isArray(overlayOptions) ? overlayOptions : []).find(function find(item) {
        return String(item.overlay_id) === overlayId;
      }) || null;
    if (!entry) {
      return {
        overlay_id: overlayId,
        availability: "inapplicable",
        reason: "This overlay is owned by another pane.",
        scope_label: "other_pane_only",
      };
    }
    if (String(entry.availability) !== "available") {
      return {
        overlay_id: overlayId,
        availability: String(entry.availability),
        reason: entry.reason,
        scope_label: String(entry.overlay_category),
      };
    }
    if (
      overlayId === "shared_readout_activity" ||
      overlayId === "paired_readout_delta"
    ) {
      if (!timeSeriesView) {
        return {
          overlay_id: overlayId,
          availability: "unavailable",
          reason: String(timeSeriesError || "shared comparison replay state is unavailable"),
          scope_label: String(entry.overlay_category),
        };
      }
      return Object.assign(
        {
          overlay_id: overlayId,
          availability: "available",
          reason: null,
          scope_label: String(entry.overlay_category),
        },
        clone(timeSeriesView.shared_comparison || {}),
        {
          cursor: clone(timeSeriesView.cursor || {}),
        }
      );
    }
    if (overlayId === "wave_patch_activity") {
      const diagnostics = Array.isArray(((analysis.wave_only_diagnostics || {}).diagnostic_cards))
        ? ((analysis.wave_only_diagnostics || {}).diagnostic_cards)
        : [];
      return {
        overlay_id: overlayId,
        availability: "available",
        reason: null,
        scope_label: String(entry.overlay_category),
        diagnostic_card_count: diagnostics.length,
        metric_ids: diagnostics
          .map(function map(item) {
            return String(item.metric_id || "");
          })
          .filter(Boolean),
      };
    }
    if (overlayId === "phase_map_reference") {
      const refs = Array.isArray(((analysis.wave_only_diagnostics || {}).phase_map_references))
        ? ((analysis.wave_only_diagnostics || {}).phase_map_references)
        : [];
      const matches = refs.filter(function filter(item) {
        const rootIds = Array.isArray(item.root_ids) ? item.root_ids : [];
        return rootIds.length === 0 || rootIds.indexOf(Number(state.selected_neuron_id)) !== -1;
      });
      return {
        overlay_id: overlayId,
        availability: "available",
        reason: null,
        scope_label: String(entry.overlay_category),
        matching_phase_map_count: matches.length,
        phase_map_reference_count: refs.length,
      };
    }
    if (overlayId === "validation_status_badges") {
      return {
        overlay_id: overlayId,
        availability: "available",
        reason: null,
        scope_label: String(entry.overlay_category),
        status_card: clone(((analysis.validation_evidence || {}).status_card) || {}),
        layer_summaries: clone(((analysis.validation_evidence || {}).layer_summaries) || []),
      };
    }
    return {
      overlay_id: overlayId,
      availability: "available",
      reason: null,
      scope_label: String(entry.overlay_category),
      review_handoff: clone(((analysis.validation_evidence || {}).review_handoff) || {}),
      open_findings: clone(((analysis.validation_evidence || {}).open_findings) || []),
      validator_summaries: clone(((analysis.validation_evidence || {}).validator_summaries) || []),
    };
  }

  function analysisOverlaySummaryMarkup(overlayState) {
    if (String(overlayState.availability) !== "available") {
      return comparisonFailureMarkup(
        String(overlayState.reason || "The selected overlay is unavailable for this analysis view.")
      );
    }
    if (
      String(overlayState.overlay_id) === "shared_readout_activity" ||
      String(overlayState.overlay_id) === "paired_readout_delta"
    ) {
      return (
        summaryList([
          ["Readout", String(overlayState.display_name || overlayState.readout_id || "n/a")],
          ["Baseline", Number(overlayState.baseline_value || 0).toFixed(3)],
          ["Wave", Number(overlayState.wave_value || 0).toFixed(3)],
          ["Delta", Number(overlayState.delta_value || 0).toFixed(3)],
        ]) + paragraph(String(overlayState.fairness_note || ""))
      );
    }
    if (String(overlayState.overlay_id) === "wave_patch_activity") {
      return summaryList([
        ["Diagnostic cards", String(overlayState.diagnostic_card_count || 0)],
        ["Metric ids", String((overlayState.metric_ids || []).join(", ") || "n/a")],
        ["Overlay", "Wave-only diagnostic"],
      ]);
    }
    if (String(overlayState.overlay_id) === "phase_map_reference") {
      return summaryList([
        ["Matching phase maps", String(overlayState.matching_phase_map_count || 0)],
        ["Total packaged refs", String(overlayState.phase_map_reference_count || 0)],
        ["Selected neuron", String(overlayState.matching_phase_map_count > 0 ? "highlighted" : "no direct ref")],
      ]);
    }
    if (String(overlayState.overlay_id) === "validation_status_badges") {
      const statusCard = overlayState.status_card || {};
      const layers = Array.isArray(overlayState.layer_summaries) ? overlayState.layer_summaries : [];
      return summaryList([
        ["Overall status", String(statusCard.overall_status || "unknown")],
        ["Review status", String(statusCard.review_status || "unknown")],
        ["Open findings", String(statusCard.open_finding_count || 0)],
        ["Layers", String(layers.length)],
      ]);
    }
    return summaryList([
      ["Review status", String(((overlayState.review_handoff || {}).review_status) || "unknown")],
      ["Open findings", String((overlayState.open_findings || []).length)],
      ["Validators", String((overlayState.validator_summaries || []).length)],
      ["Owner", String(((overlayState.review_handoff || {}).review_owner) || "n/a")],
    ]);
  }

  function analysisSectionMarkup(title, items, formatter) {
    const records = Array.isArray(items) ? items : [];
    if (records.length === 0) {
      return (
        '<section class="analysis-section">' +
        "<h4>" +
        escapeHtml(String(title)) +
        "</h4>" +
        comparisonFailureMarkup("No packaged items are available for this section.") +
        "</section>"
      );
    }
    return (
      '<section class="analysis-section">' +
      "<h4>" +
      escapeHtml(String(title)) +
      "</h4>" +
      '<div class="analysis-card-grid">' +
      records.slice(0, 6).map(function render(item) {
        return formatter(item);
      }).join("") +
      "</div>" +
      "</section>"
    );
  }

  function analysisTaskCardMarkup(item) {
    return analysisMetaCard("Task", [
      ["Metric", String(item.requested_metric_id || "n/a")],
      ["Group", String(item.group_id || "n/a")],
      ["Value", formatNumericValue(item.value, item.units)],
      ["Direction", String(item.effect_direction || "n/a")],
    ]);
  }

  function analysisComparisonCardMarkup(item) {
    const summary = item.summary || {};
    return analysisMetaCard("Comparison", [
      ["Output", String(item.display_name || item.output_id || "n/a")],
      ["Kind", String(item.output_kind || "n/a")],
      ["Fairness", String(item.fairness_mode || item.scope_label || "n/a")],
      ["Matrix", String(summary.matrix_id || "n/a")],
    ]);
  }

  function analysisAblationCardMarkup(item) {
    return analysisMetaCard("Ablation", [
      ["Group", String(item.group_id || "n/a")],
      ["Task cards", String(item.task_card_count || 0)],
      ["Comparison cards", String(item.comparison_card_count || 0)],
      ["Mean score", item.mean_task_score === null || item.mean_task_score === undefined ? "n/a" : Number(item.mean_task_score).toFixed(3)],
    ]);
  }

  function analysisDiagnosticCardMarkup(item) {
    return analysisMetaCard("Wave diagnostic", [
      ["Arm", String(item.arm_id || "n/a")],
      ["Metric", String(item.metric_id || "n/a")],
      ["Mean", formatNumericValue(item.mean_value, item.units)],
      ["Seeds", String(item.seed_count || 0)],
    ]);
  }

  function analysisPhaseMapCardMarkup(item, selectedNeuronId) {
    const rootIds = Array.isArray(item.root_ids) ? item.root_ids : [];
    const matches = rootIds.length === 0 || rootIds.indexOf(Number(selectedNeuronId)) !== -1;
    return analysisMetaCard("Phase map", [
      ["Artifact", basename(item.path || item.artifact_path || item.report_path)],
      ["Roots", String(rootIds.join(", ") || "all")],
      ["Selected neuron", matches ? "matched" : "not targeted"],
      ["Format", String(item.format || item.artifact_format || "n/a")],
    ]);
  }

  function validationStatusMarkup(validation) {
    const statusCard = (validation.status_card || {});
    const review = validation.review_handoff || {};
    return (
      '<div class="analysis-status-grid">' +
      analysisMetaCard("Validation status", [
        ["Overall", String(statusCard.overall_status || "unknown")],
        ["Review", String(statusCard.review_status || "unknown")],
        ["Open findings", String(statusCard.open_finding_count || 0)],
        ["Layers", String(statusCard.layer_count || 0)],
      ]) +
      analysisMetaCard("Reviewer handoff", [
        ["Owner", String(review.review_owner || "n/a")],
        ["Decision", String(review.scientific_plausibility_decision || "pending")],
        ["Follow-on", String(review.follow_on_action || "n/a")],
        ["Overall", String(review.overall_status || "unknown")],
      ]) +
      "</div>"
    );
  }

  function validationSummaryCardMarkup(item) {
    const statusCounts = item.status_counts || {};
    const statuses = Object.keys(statusCounts)
      .map(function map(key) {
        return String(key) + ":" + String(statusCounts[key]);
      })
      .join(", ");
    return analysisMetaCard("Validator", [
      ["Validator", String(item.validator_id || "n/a")],
      ["Layer", String(item.layer_id || "n/a")],
      ["Review", String(item.review_status || "n/a")],
      ["Statuses", statuses || "none"],
    ]);
  }

  function validationFindingCardMarkup(item) {
    return analysisMetaCard("Finding", [
      ["Id", String(item.finding_id || "n/a")],
      ["Validator", String(item.validator_id || "n/a")],
      ["Status", String(item.status || "unknown")],
      ["Case", String(item.case_id || "n/a")],
    ]);
  }

  function exportTargetCardMarkup(item) {
    return analysisMetaCard("Export target", [
      ["Target", String(item.display_name || item.export_target_id || "n/a")],
      ["Id", String(item.export_target_id || "n/a")],
      ["Kind", String(item.target_kind || "n/a")],
      ["Cursor bound", Boolean(item.requires_time_cursor) ? "yes" : "no"],
    ]);
  }

  function matrixDeckMarkup(matrices) {
    const records = Array.isArray(matrices) ? matrices : [];
    if (records.length === 0) {
      return "";
    }
    return (
      '<section class="analysis-section">' +
      "<h4>Matrix views</h4>" +
      '<div class="analysis-matrix-grid">' +
      records.slice(0, 2).map(function render(item) {
        return matrixPreviewMarkup(item);
      }).join("") +
      "</div>" +
      "</section>"
    );
  }

  function matrixPreviewMarkup(matrix) {
    const rows = ((matrix.row_axis || {}).ids || []).slice(0, 4);
    const cols = ((matrix.column_axis || {}).ids || []).slice(0, 4);
    const values = Array.isArray(matrix.values) ? matrix.values : [];
    const range = Array.isArray(matrix.value_range) ? matrix.value_range : [0, 1];
    return (
      '<article class="matrix-preview">' +
      "<h5>" +
      escapeHtml(String(matrix.matrix_id || "matrix")) +
      "</h5>" +
      '<p class="band-copy">' +
      escapeHtml(String(matrix.value_semantics || matrix.scope_label || "")) +
      "</p>" +
      '<div class="matrix-scroll"><table class="matrix-table"><thead><tr><th></th>' +
      cols.map(function map(col) {
        return "<th>" + escapeHtml(String(col)) + "</th>";
      }).join("") +
      "</tr></thead><tbody>" +
      rows.map(function renderRow(rowId, rowIndex) {
        return (
          "<tr><th>" +
          escapeHtml(String(rowId)) +
          "</th>" +
          cols.map(function renderCol(_, colIndex) {
            const row = Array.isArray(values[rowIndex]) ? values[rowIndex] : [];
            return matrixCellMarkup(row[colIndex], range, matrix.scope_label);
          }).join("") +
          "</tr>"
        );
      }).join("") +
      "</tbody></table></div>" +
      "</article>"
    );
  }

  function matrixCellMarkup(value, range, scopeLabel) {
    const numeric = typeof value === "number" ? value : null;
    const style = numeric === null ? "background:rgba(18,69,89,0.05);" : matrixCellStyle(numeric, range, scopeLabel);
    const label = numeric === null ? "n/a" : Number(numeric).toFixed(3);
    return '<td class="matrix-cell" style="' + escapeHtml(style) + '">' + escapeHtml(label) + "</td>";
  }

  function matrixCellStyle(value, range, scopeLabel) {
    const minValue = Number((Array.isArray(range) ? range[0] : 0) || 0);
    const maxValue = Number((Array.isArray(range) ? range[1] : 1) || 1);
    const span = Math.max(1e-9, maxValue - minValue);
    const t = Math.max(0, Math.min(1, (Number(value) - minValue) / span));
    if (String(scopeLabel) === "wave_only_diagnostics") {
      return "background:rgba(194,119,44," + (0.12 + 0.48 * t).toFixed(3) + ");";
    }
    return "background:rgba(10,92,99," + (0.10 + 0.46 * t).toFixed(3) + ");";
  }

  function analysisOverlayCatalogMarkup(items) {
    return (
      '<section class="analysis-section">' +
      "<h4>Scientific overlay catalog</h4>" +
      '<div class="analysis-catalog-grid">' +
      (Array.isArray(items) ? items : []).map(function render(item) {
        return (
          '<article class="analysis-overlay-card">' +
          "<strong>" +
          escapeHtml(String(item.display_name || item.overlay_id)) +
          "</strong>" +
          '<span class="analysis-overlay-meta">' +
          escapeHtml(String(item.overlay_category || "n/a").replace(/_/g, " ")) +
          " | " +
          escapeHtml(String(item.availability || "unknown")) +
          "</span>" +
          '<p class="band-copy">' +
          escapeHtml(String(item.reason || item.description || "")) +
          "</p>" +
          "</article>"
        );
      }).join("") +
      "</div>" +
      "</section>"
    );
  }

  function analysisMetaCard(title, rows) {
    return (
      '<article class="meta-card analysis-meta-card">' +
      "<h4>" +
      escapeHtml(String(title)) +
      "</h4>" +
      summaryList(rows) +
      "</article>"
    );
  }

  function formatNumericValue(value, units) {
    if (typeof value !== "number") {
      return String(value === undefined || value === null ? "n/a" : value);
    }
    return Number(value).toFixed(3) + (units ? " " + String(units) : "");
  }

  function syncComparisonModeSelect(state, model) {
    const select = document.getElementById("dashboard-comparison-mode");
    if (!select) {
      return;
    }
    const options = getComparisonModeOptions(model);
    select.innerHTML = options
      .map(function render(option) {
        const disabled = option.availability === "available" ? "" : " disabled";
        const selected = option.comparison_mode_id === String(state.comparison_mode) ? " selected" : "";
        const suffix = option.availability === "available" ? "" : " (Unavailable)";
        return (
          '<option value="' +
          escapeHtml(String(option.comparison_mode_id)) +
          '"' +
          disabled +
          selected +
          ">" +
          escapeHtml(String(option.display_name) + suffix) +
          "</option>"
        );
      })
      .join("");
    select.value = String(state.comparison_mode);
  }

  function syncOverlaySelect(state, model) {
    const select = document.getElementById("dashboard-overlay-mode");
    if (!select) {
      return;
    }
    const currentOptions = getOverlayOptions(model, state);
    select.innerHTML = currentOptions
      .map(function render(option) {
        const disabled = option.availability === "available" ? "" : " disabled";
        const selected = option.overlay_id === String(state.active_overlay_id) ? " selected" : "";
        const suffix = option.availability === "available" ? "" : " (Unavailable)";
        return (
          '<option value="' +
          escapeHtml(String(option.overlay_id)) +
          '"' +
          disabled +
          selected +
          ">" +
          escapeHtml(String(option.display_name) + suffix) +
          "</option>"
        );
      })
      .join("");
    select.value = String(state.active_overlay_id);
  }

  function syncTimeControls(state) {
    const slider = document.getElementById("dashboard-time-cursor");
    if (slider) {
      slider.value = String(state.time_cursor.sample_index);
    }
    const readout = document.querySelector("[data-time-readout='true']");
    if (readout) {
      readout.textContent =
        "sample " +
        String(state.time_cursor.sample_index) +
        " | " +
        Number(state.time_cursor.time_ms).toFixed(1) +
        " ms | " +
        String(state.time_cursor.playback_state);
    }
  }

  function syncPlaybackButtons(state) {
    document.querySelectorAll("[data-playback-action='toggle']").forEach(function sync(node) {
      node.textContent = state.time_cursor.playback_state === "playing" ? "Pause" : "Play";
      node.classList.toggle("is-active", state.time_cursor.playback_state === "playing");
    });
  }

  function attachCircuitInteractions(body, store) {
    body.querySelectorAll("[data-root-select]").forEach(function attach(node) {
      node.addEventListener("click", function onClick() {
        store.actions.setSelectedNeuronId(node.getAttribute("data-root-select"));
      });
    });
    body.querySelectorAll("[data-root-hover]").forEach(function attach(node) {
      node.addEventListener("mouseenter", function onEnter() {
        store.actions.setHoveredNeuronId(node.getAttribute("data-root-hover"), "circuit");
      });
      node.addEventListener("mouseleave", function onLeave() {
        store.actions.clearHoveredNeuronId();
      });
    });
  }

  function attachMorphologyInteractions(body, store) {
    body.querySelectorAll("[data-morphology-root-select]").forEach(function attach(node) {
      node.addEventListener("click", function onClick() {
        store.actions.setSelectedNeuronId(node.getAttribute("data-morphology-root-select"));
      });
    });
    body.querySelectorAll("[data-morphology-root-hover]").forEach(function attach(node) {
      node.addEventListener("mouseenter", function onEnter() {
        store.actions.setHoveredNeuronId(node.getAttribute("data-morphology-root-hover"), "morphology");
      });
      node.addEventListener("mouseleave", function onLeave() {
        store.actions.clearHoveredNeuronId();
      });
    });
  }

  function resolveMorphologyOverlayState(morphology, state, selectedRoot) {
    const overlayId = String(state.active_overlay_id);
    if ([
      "selected_subset_highlight",
      "shared_readout_activity",
      "wave_patch_activity",
    ].indexOf(overlayId) === -1) {
      return {
        overlay_id: overlayId,
        availability: "inapplicable",
        reason: "This overlay is owned by another pane.",
        scope_label: "other_pane_only",
      };
    }
    if (overlayId === "selected_subset_highlight") {
      return {
        overlay_id: overlayId,
        availability: "available",
        reason: null,
        scope_label: "context",
      };
    }
    if (overlayId === "shared_readout_activity") {
      const support = ((morphology.overlay_support || {}).shared_readout_activity) || {};
      const readoutCatalog = Array.isArray(support.readout_catalog) ? support.readout_catalog : [];
      const readout = readoutCatalog.find(function find(item) {
        return String(item.readout_id) === String(state.selected_readout_id);
      });
      if (!readout) {
        return {
          overlay_id: overlayId,
          availability: "unavailable",
          reason: "The selected readout is not packaged for morphology overlays.",
          scope_label: String(support.scope_label || "shared_comparison"),
        };
      }
      const sample = clampSampleIndex(state.time_cursor.sample_index, readout.time_ms.length);
      const baselineValue = Number(readout.baseline_values[sample] || 0);
      const waveValue = Number(readout.wave_values[sample] || 0);
      const deltaValue = Number(readout.delta_values[sample] || 0);
      let comparisonValue = baselineValue;
      if (String(state.comparison_mode) === "paired_delta") {
        comparisonValue = deltaValue;
      } else if (String(state.selected_arm_pair.active_arm_id).indexOf("surface_wave") !== -1) {
        comparisonValue = waveValue;
      }
      return {
        overlay_id: overlayId,
        availability: "available",
        reason: null,
        scope_label: String(support.scope_label || "shared_comparison"),
        sample_index: sample,
        time_ms: Number(readout.time_ms[sample] || 0),
        baseline_value: baselineValue,
        wave_value: waveValue,
        delta_value: deltaValue,
        comparison_value: comparisonValue,
        normalized_scalar: normalizeOverlayScalar(
          comparisonValue,
          Number(readout.abs_value_scale || 1)
        ),
      };
    }
    const waveOverlay = (((selectedRoot.overlay_samples || {}).wave_patch_activity) || {});
    if (String(waveOverlay.availability) !== "available") {
      return {
        overlay_id: overlayId,
        availability: String(waveOverlay.availability || "unavailable"),
        reason: String(waveOverlay.reason || "Wave diagnostics are unavailable for this root."),
        scope_label: String(waveOverlay.scope_label || "wave_only_diagnostic"),
      };
    }
    const elementSeries = Array.isArray(waveOverlay.element_series) ? waveOverlay.element_series : [];
    const sample = clampSampleIndex(state.time_cursor.sample_index, waveOverlay.time_ms.length || 0);
    const absScale = Number(((waveOverlay.summary || {}).max_abs_value) || 1);
    return {
      overlay_id: overlayId,
      availability: "available",
      reason: null,
      scope_label: String(waveOverlay.scope_label || "wave_only_diagnostic"),
      sample_index: sample,
      time_ms: Number((waveOverlay.time_ms || [])[sample] || 0),
      projection_semantics: String(waveOverlay.projection_semantics || "wave_projection"),
      element_values: elementSeries.map(function map(item) {
        const value = Number((item.values || [])[sample] || 0);
        return {
          element_id: String(item.element_id),
          value: value,
          normalized_scalar: normalizeOverlayScalar(value, absScale),
        };
      }),
    };
  }

  function morphologyStageMarkup(selectedRoot, overlayState) {
    if (!selectedRoot || !selectedRoot.render_geometry) {
      return '<div class="scene-empty"><strong>No morphology geometry is available.</strong></div>';
    }
    const geometry = selectedRoot.render_geometry || {};
    const stageNote =
      String(geometry.title || "Morphology") +
      " | " +
      String((selectedRoot.preferred_representation || geometry.representation_id || "unknown")).replace(/_/g, " ");
    return [
      '<div class="morphology-stage-header">',
      "<strong>" + escapeHtml(stageNote) + "</strong>",
      "<span>" + escapeHtml(String(overlayState.availability || "unknown")) + "</span>",
      "</div>",
      morphologySvgMarkup(geometry, overlayState),
      '<p class="band-copy morphology-caption">' +
        escapeHtml(String(geometry.truth_note || "No render-truth note is packaged.")) +
      "</p>",
    ].join("");
  }

  function morphologySvgMarkup(geometry, overlayState) {
    const viewBox = Array.isArray(geometry.view_box) ? geometry.view_box : [-1, -1, 2, 2];
    const overlayElementMap = {};
    if (Array.isArray(overlayState.element_values)) {
      overlayState.element_values.forEach(function each(item) {
        overlayElementMap[String(item.element_id)] = item;
      });
    }
    const sharedTone = overlayTone(
      Number(overlayState.normalized_scalar || 0.5),
      String(overlayState.scope_label || "shared_comparison"),
      String(overlayState.overlay_id || "")
    );
    const basePolygons = (Array.isArray(geometry.mesh_polygons) ? geometry.mesh_polygons : [])
      .map(function render(item) {
        const points = shapePointString(item.points || []);
        const fill =
          overlayState.availability === "available" &&
          String(overlayState.overlay_id) === "shared_readout_activity"
            ? sharedTone.fill
            : "rgba(18, 69, 89, 0.08)";
        const stroke =
          overlayState.availability === "available" &&
          String(overlayState.overlay_id) === "shared_readout_activity"
            ? sharedTone.stroke
            : "rgba(18, 69, 89, 0.24)";
        if (String(item.kind) === "polyline") {
          return (
            '<polyline class="morphology-polyline" points="' +
            escapeHtml(points) +
            '" style="stroke:' +
            escapeHtml(stroke) +
            ';fill:none;"></polyline>'
          );
        }
        return (
          '<polygon class="morphology-polygon" points="' +
          escapeHtml(points) +
          '" style="fill:' +
          escapeHtml(fill) +
          ';stroke:' +
          escapeHtml(stroke) +
          ';"></polygon>'
        );
      })
      .join("");
    const baseSegments = (Array.isArray(geometry.segments) ? geometry.segments : [])
      .map(function render(item) {
        return (
          '<line class="morphology-segment" x1="' +
          Number(((item.points || [])[0] || [0, 0])[0]).toFixed(3) +
          '" y1="' +
          Number(((item.points || [])[0] || [0, 0])[1]).toFixed(3) +
          '" x2="' +
          Number(((item.points || [])[1] || [0, 0])[0]).toFixed(3) +
          '" y2="' +
          Number(((item.points || [])[1] || [0, 0])[1]).toFixed(3) +
          '"></line>'
        );
      })
      .join("");
    const basePoint = geometry.point
      ? (
          '<circle class="morphology-point" cx="' +
          Number((geometry.point.center || [0, 0])[0]).toFixed(3) +
          '" cy="' +
          Number((geometry.point.center || [0, 0])[1]).toFixed(3) +
          '" r="' +
          Number(geometry.point.radius || 0.32).toFixed(3) +
          '"></circle>'
        )
      : "";
    const overlayShapes = overlayState.availability === "available"
      ? (Array.isArray(geometry.overlay_elements) ? geometry.overlay_elements : [])
          .map(function render(item) {
            const overlayValue =
              String(overlayState.overlay_id) === "wave_patch_activity"
                ? overlayElementMap[String(item.element_id)]
                : {
                    normalized_scalar: Number(overlayState.normalized_scalar || 0.5),
                  };
            const tone = overlayTone(
              Number((overlayValue || {}).normalized_scalar || 0.5),
              String(overlayState.scope_label || "shared_comparison"),
              String(overlayState.overlay_id || "")
            );
            if (String(item.kind) === "polygon") {
              return (
                '<polygon class="morphology-overlay" points="' +
                escapeHtml(shapePointString(item.points || [])) +
                '" style="fill:' +
                escapeHtml(tone.fill) +
                ';stroke:' +
                escapeHtml(tone.stroke) +
                ';"></polygon>'
              );
            }
            if (String(item.kind) === "segment") {
              return (
                '<line class="morphology-overlay-line" x1="' +
                Number(((item.points || [])[0] || [0, 0])[0]).toFixed(3) +
                '" y1="' +
                Number(((item.points || [])[0] || [0, 0])[1]).toFixed(3) +
                '" x2="' +
                Number(((item.points || [])[1] || [0, 0])[0]).toFixed(3) +
                '" y2="' +
                Number(((item.points || [])[1] || [0, 0])[1]).toFixed(3) +
                '" style="stroke:' +
                escapeHtml(tone.stroke) +
                ';"></line>'
              );
            }
            return (
              '<circle class="morphology-overlay-point" cx="' +
              Number((item.center || [0, 0])[0]).toFixed(3) +
              '" cy="' +
              Number((item.center || [0, 0])[1]).toFixed(3) +
              '" r="0.11" style="fill:' +
              escapeHtml(tone.fill) +
              ';stroke:' +
              escapeHtml(tone.stroke) +
              ';"></circle>'
            );
          })
          .join("")
      : "";
    const overlayUnavailable =
      overlayState.availability === "available"
        ? ""
        : (
            '<div class="morphology-overlay-empty">' +
            "<strong>" + escapeHtml(String(overlayState.availability || "unavailable")) + "</strong>" +
            "<p>" + escapeHtml(String(overlayState.reason || "No overlay detail is available.")) + "</p>" +
            "</div>"
          );
    return [
      '<div class="morphology-stage-frame">',
      '<svg class="morphology-svg" viewBox="' +
        escapeHtml(viewBox.join(" ")) +
        '">',
      basePolygons,
      baseSegments,
      basePoint,
      overlayShapes,
      "</svg>",
      overlayUnavailable,
      "</div>",
    ].join("");
  }

  function morphologyRootCardMarkup(root, state) {
    const isSelected = Number(root.root_id) === Number(state.selected_neuron_id);
    const isHovered = state.hovered_neuron_id !== null && Number(root.root_id) === Number(state.hovered_neuron_id);
    const waveOverlay = (((root.overlay_samples || {}).wave_patch_activity) || {});
    return [
      '<button type="button" class="morphology-root-card' +
        (isSelected ? " is-selected" : "") +
        (isHovered ? " is-hovered" : "") +
        '" data-morphology-root-select="' +
        escapeHtml(String(root.root_id)) +
        '" data-morphology-root-hover="' +
        escapeHtml(String(root.root_id)) +
        '">',
      "<strong>" + escapeHtml(String(root.root_id)) + "</strong>",
      "<span>" +
        escapeHtml(
          [
            String(root.cell_type || "unknown"),
            String(root.morphology_class || "unknown"),
          ].join(" | ")
        ) +
        "</span>",
      "<span>" +
        escapeHtml(
          [
            String(root.preferred_representation || "n/a").replace(/_/g, " "),
            String(waveOverlay.availability || "no wave overlay"),
          ].join(" | ")
        ) +
        "</span>",
      "</button>",
    ].join("");
  }

  function overlayScopeBanner(overlayState) {
    const tone =
      String(overlayState.scope_label) === "shared_comparison"
        ? " fairness-chip"
        : String(overlayState.scope_label) === "wave_only_diagnostic"
          ? " diagnostic-chip"
          : String(overlayState.scope_label) === "validation_evidence"
            ? " validation-chip"
          : " context-chip";
    return (
      '<div class="scope-banner">' +
      '<span class="scope-chip' + tone + '">' +
      escapeHtml(String(overlayState.scope_label || "context").replace(/_/g, " ")) +
      "</span>" +
      '<span class="scope-copy">' +
      escapeHtml(scopeCopyForOverlay(overlayState)) +
      "</span>" +
      "</div>"
    );
  }

  function overlayStatusCard(overlayState) {
    const rows = [];
    if (String(overlayState.overlay_id) === "shared_readout_activity" && overlayState.availability === "available") {
      rows.push(["Baseline", Number(overlayState.baseline_value || 0).toFixed(3)]);
      rows.push(["Wave", Number(overlayState.wave_value || 0).toFixed(3)]);
      rows.push(["Delta", Number(overlayState.delta_value || 0).toFixed(3)]);
      rows.push(["Sample", Number(overlayState.time_ms || 0).toFixed(1) + " ms"]);
    } else if (String(overlayState.overlay_id) === "wave_patch_activity" && overlayState.availability === "available") {
      rows.push(["Sample", Number(overlayState.time_ms || 0).toFixed(1) + " ms"]);
      rows.push(["Semantics", String(overlayState.projection_semantics || "wave_projection")]);
      rows.push(["Elements", String((overlayState.element_values || []).length)]);
    } else {
      rows.push(["Status", String(overlayState.availability || "unknown")]);
      rows.push(["Reason", String(overlayState.reason || "none")]);
    }
    return '<div class="meta-card">' + "<h4>Overlay State</h4>" + summaryList(rows) + "</div>";
  }

  function scopeCopyForOverlay(overlayState) {
    if (String(overlayState.scope_label) === "shared_comparison") {
      return "Fairness-critical shared readout overlay.";
    }
    if (String(overlayState.scope_label) === "wave_only_diagnostic") {
      return "Wave-only morphology diagnostic.";
    }
    if (String(overlayState.scope_label) === "validation_evidence") {
      return "Reviewer-oriented validation evidence.";
    }
    if (String(overlayState.availability) === "inapplicable") {
      return "Owned by another pane.";
    }
    return "Context overlay.";
  }

  function formatCameraFocus(cameraFocus) {
    if (!cameraFocus || !Array.isArray(cameraFocus.view_box)) {
      return "n/a";
    }
    return cameraFocus.view_box.map(function map(value) {
      return Number(value).toFixed(2);
    }).join(", ");
  }

  function shapePointString(points) {
    return (Array.isArray(points) ? points : []).map(function map(point) {
      return Number((point || [0, 0])[0]).toFixed(3) + "," + Number((point || [0, 0])[1]).toFixed(3);
    }).join(" ");
  }

  function normalizeOverlayScalar(value, absScale) {
    const scale = Math.max(Number(absScale || 0), 1e-9);
    return Math.max(0, Math.min(1, 0.5 + (0.5 * Number(value || 0)) / scale));
  }

  function overlayTone(normalizedScalar, scopeLabel, overlayId) {
    const t = Math.max(0, Math.min(1, Number(normalizedScalar || 0.5)));
    if (String(scopeLabel) === "wave_only_diagnostic") {
      return {
        fill: "rgba(194, 119, 44, " + (0.24 + 0.58 * t).toFixed(3) + ")",
        stroke: "rgba(143, 78, 24, " + (0.45 + 0.45 * t).toFixed(3) + ")",
      };
    }
    if (String(overlayId) === "shared_readout_activity") {
      return {
        fill: "rgba(10, 92, 99, " + (0.18 + 0.52 * t).toFixed(3) + ")",
        stroke: "rgba(18, 69, 89, " + (0.38 + 0.45 * t).toFixed(3) + ")",
      };
    }
    return {
      fill: "rgba(18, 69, 89, 0.18)",
      stroke: "rgba(18, 69, 89, 0.34)",
    };
  }

  function clampSampleIndex(index, sampleCount) {
    const maxIndex = Math.max(0, Number(sampleCount || 1) - 1);
    return Math.max(0, Math.min(maxIndex, Number(index || 0)));
  }

  function getOverlayOptions(model, state) {
    const baseStatuses = (model.overlay_catalog || {}).base_availability_by_id || {};
    return ((model.overlay_catalog || {}).overlay_definitions || []).map(function map(item) {
      const baseStatus = baseStatuses[item.overlay_id] || {
        availability: "available",
        reason: null,
      };
      let availability = String(baseStatus.availability);
      let reason = baseStatus.reason;
      const supportedModes = Array.isArray(item.supported_comparison_modes)
        ? item.supported_comparison_modes
        : [];
      if (supportedModes.indexOf(String(state.comparison_mode)) === -1) {
        availability = "unavailable";
        reason = "not supported by " + comparisonModeName(model, state.comparison_mode);
      }
      return {
        overlay_id: String(item.overlay_id),
        display_name: String(item.display_name),
        overlay_category: String(item.overlay_category),
        availability: availability,
        reason: reason,
      };
    });
  }

  function getComparisonModeOptions(model) {
    const statuses = {};
    (Array.isArray((model.replay_model || {}).comparison_mode_statuses)
      ? (model.replay_model || {}).comparison_mode_statuses
      : []
    ).forEach(function each(item) {
      statuses[String(item.comparison_mode_id)] = item;
    });
    return (Array.isArray(model.comparison_mode_catalog) ? model.comparison_mode_catalog : []).map(function map(item) {
      const status = statuses[String(item.comparison_mode_id)] || {
        availability: "available",
        reason: null,
      };
      return {
        comparison_mode_id: String(item.comparison_mode_id),
        display_name: String(item.display_name),
        description: String(item.description || ""),
        availability: String(status.availability || "available"),
        reason: status.reason,
      };
    });
  }

  function resolveTimeSeriesViewModel(model, state) {
    const context = model.time_series_context || {};
    const replayModel = model.replay_model || {};
    const comparisonStatus = getComparisonModeOptions(model).find(function find(item) {
      return String(item.comparison_mode_id) === String(state.comparison_mode);
    });
    if (!comparisonStatus) {
      throw new Error("Selected comparison mode is not declared in the replay model.");
    }
    if (comparisonStatus.availability !== "available") {
      throw new Error(String(comparisonStatus.reason || "comparison mode unavailable"));
    }
    const sharedTraceCatalog = Array.isArray(context.shared_trace_catalog)
      ? context.shared_trace_catalog
      : [];
    const trace = sharedTraceCatalog.find(function find(item) {
      return String(item.readout_id) === String(state.selected_readout_id);
    });
    if (!trace) {
      throw new Error("Selected shared readout trace is not packaged for this dashboard session.");
    }
    const selectionCatalog = Array.isArray(context.selection_catalog)
      ? context.selection_catalog
      : [];
    const selectedRoot = selectionCatalog.find(function find(item) {
      return Number(item.root_id) === Number(state.selected_neuron_id);
    });
    if (!selectedRoot) {
      throw new Error("Selected neuron is not packaged in the dashboard time-series context.");
    }
    const sampleCount = Array.isArray(replayModel.canonical_time_ms)
      ? replayModel.canonical_time_ms.length
      : (Array.isArray(trace.time_ms) ? trace.time_ms.length : 1);
    const sample = clampSampleIndex(state.time_cursor.sample_index, sampleCount);
    const baselineValue = Number((trace.baseline_values || [])[sample] || 0);
    const waveValue = Number((trace.wave_values || [])[sample] || 0);
    const deltaValue = Number((trace.delta_values || [])[sample] || 0);
    const sharedComparison = sharedComparisonView(trace, state, replayModel);
    const waveDiagnostic = waveDiagnosticView(selectedRoot, sample);
    return {
      cursor: {
        sample_index: sample,
        time_ms: Array.isArray(replayModel.canonical_time_ms)
          ? Number((replayModel.canonical_time_ms || [])[sample] || 0)
          : Number(state.time_cursor.time_ms || 0),
      },
      comparison_status: comparisonStatus,
      selected_root: selectedRoot,
      shared_comparison: {
        readout_id: String(trace.readout_id),
        display_name: String(trace.display_name || trace.readout_id),
        units: String(trace.units || "n/a"),
        baseline_value: baselineValue,
        wave_value: waveValue,
        delta_value: deltaValue,
        chart_series: sharedComparison.chart_series,
        fairness_note: sharedComparison.fairness_note,
      },
      wave_diagnostic: waveDiagnostic,
    };
  }

  function sharedComparisonView(trace, state, replayModel) {
    const baselineSeries = Array.isArray(trace.baseline_values) ? trace.baseline_values : [];
    const waveSeries = Array.isArray(trace.wave_values) ? trace.wave_values : [];
    const deltaSeries = Array.isArray(trace.delta_values) ? trace.delta_values : [];
    if (String(state.comparison_mode) === "paired_delta") {
      return {
        fairness_note:
          "Shared delta view remains on the canonical paired timebase and does not absorb wave-only diagnostics.",
        chart_series: [
          {
            series_id: "delta",
            display_name: "Wave - Baseline",
            values: deltaSeries,
            scope_label: "shared_comparison",
          },
        ],
      };
    }
    if (String(state.comparison_mode) === "single_arm") {
      const pair = (replayModel || {}).selected_pair_status || {};
      const useWave = String(state.selected_arm_pair.active_arm_id) === String(pair.wave_arm_id || "");
      return {
        fairness_note:
          "Single-arm replay still uses the shared readout surface, but only one arm is foregrounded at a time.",
        chart_series: [
          {
            series_id: useWave ? "wave" : "baseline",
            display_name: useWave ? "Wave" : "Baseline",
            values: useWave ? waveSeries : baselineSeries,
            scope_label: "shared_comparison",
          },
        ],
      };
    }
    return {
      fairness_note:
        "Baseline-versus-wave replay is fairness-critical and stays on the shared readout catalog plus canonical shared timebase.",
      chart_series: [
        {
          series_id: "baseline",
          display_name: "Baseline",
          values: baselineSeries,
          scope_label: "shared_comparison",
        },
        {
          series_id: "wave",
          display_name: "Wave",
          values: waveSeries,
          scope_label: "shared_comparison",
        },
      ],
    };
  }

  function waveDiagnosticView(selectedRoot, sampleIndex) {
    const diagnostic = ((selectedRoot || {}).wave_diagnostic) || {};
    if (String(diagnostic.availability) !== "available") {
      return diagnostic;
    }
    const timeMs = Array.isArray(diagnostic.time_ms) ? diagnostic.time_ms : [];
    const values = Array.isArray(diagnostic.values) ? diagnostic.values : [];
    const resolvedSample = clampSampleIndex(sampleIndex, values.length || timeMs.length || 1);
    return Object.assign({}, diagnostic, {
      sample_index: resolvedSample,
      cursor_time_ms: Number(timeMs[resolvedSample] || 0),
      cursor_value: Number(values[resolvedSample] || 0),
    });
  }

  function sceneFrameForState(scene, state) {
    const frames = Array.isArray(scene.replay_frames) ? scene.replay_frames : [];
    if (frames.length === 0) {
      return null;
    }
    const targetTimeMs = Number(state.time_cursor.time_ms || 0);
    let selected = frames[0];
    for (let index = 0; index < frames.length; index += 1) {
      if (Number(frames[index].time_ms) > targetTimeMs) {
        break;
      }
      selected = frames[index];
    }
    return selected;
  }

  function activeSceneLayer(scene) {
    const layers = Array.isArray(scene.render_layers) ? scene.render_layers : [];
    return (
      layers.find(function find(item) {
        return String(item.layer_id) === String(scene.active_layer_id);
      }) ||
      layers[0] ||
      null
    );
  }

  function hoveredNeuronLabel(model, state) {
    const hovered = focusedCircuitNode(model, state);
    if (!hovered) {
      return "none";
    }
    return (
      String(hovered.root_id) +
      (hovered.cell_type ? " | " + String(hovered.cell_type) : "")
    );
  }

  function focusedCircuitNode(model, state) {
    const nodes = getCircuitNodes(model);
    if (state.hovered_neuron_id !== null && state.hovered_neuron_id !== undefined) {
      const hovered = nodes.find(function find(item) {
        return Number(item.root_id) === Number(state.hovered_neuron_id);
      });
      if (hovered) {
        return hovered;
      }
    }
    return (
      nodes.find(function find(item) {
        return Number(item.root_id) === Number(state.selected_neuron_id);
      }) ||
      nodes[0] ||
      null
    );
  }

  function getCircuitNodes(model) {
    return Array.isArray((((model.circuit_context || {}).connectivity_context || {}).node_catalog))
      ? (((model.circuit_context || {}).connectivity_context || {}).node_catalog)
      : [];
  }

  function sceneCanvasMarkup(frame, renderStatus, scene) {
    if (!frame) {
      return (
        '<div class="scene-empty">' +
        "<strong>Scene layer unavailable.</strong>" +
        "<p>" +
        escapeHtml(String(((scene.frame_discovery || {}).unavailable_reason) || renderStatus)) +
        "</p>" +
        "</div>"
      );
    }
    return [
      '<div class="scene-canvas-frame">',
      '<canvas class="scene-canvas" data-scene-canvas="true" width="' +
        escapeHtml(String(frame.width)) +
        '" height="' +
        escapeHtml(String(frame.height)) +
        '"></canvas>',
      '<div class="scene-caption">',
      "<span>" + escapeHtml("frame " + String(frame.frame_index)) + "</span>",
      "<span>" + escapeHtml(Number(frame.time_ms).toFixed(1) + " ms") + "</span>",
      "</div>",
      "</div>",
    ].join("");
  }

  function layerChipList(layers) {
    return chipList(
      (Array.isArray(layers) ? layers : []).map(function map(item) {
        return {
          label:
            String(item.display_name || item.layer_id) +
            " | " +
            String(item.availability || "unknown") +
            (item.replay_source ? " | " + String(item.replay_source) : ""),
          tone: item.availability === "available" ? "good" : "warn",
        };
      })
    );
  }

  function selectedRootCardMarkup(root, state) {
    const isSelected = Number(root.root_id) === Number(state.selected_neuron_id);
    const isHovered = state.hovered_neuron_id !== null && Number(root.root_id) === Number(state.hovered_neuron_id);
    return [
      '<button type="button" class="root-button' +
        (isSelected ? " is-selected" : "") +
        (isHovered ? " is-hovered" : "") +
        '" data-root-select="' +
        escapeHtml(String(root.root_id)) +
        '" data-root-hover="' +
        escapeHtml(String(root.root_id)) +
        '">',
      '<span class="root-main">',
      "<strong>" + escapeHtml(String(root.root_id)) + "</strong>",
      "<span>" +
        escapeHtml(
          [
            String(root.cell_type || "unknown"),
            String(root.morphology_class || "unknown"),
          ].join(" | ")
        ) +
        "</span>",
      "</span>",
      '<span class="root-meta">' +
        escapeHtml(
          [
            String((root.connectivity_summary || {}).incoming_synapse_count || 0) + " in",
            String((root.connectivity_summary || {}).outgoing_synapse_count || 0) + " out",
          ].join(" / ")
        ) +
        "</span>",
      "</button>",
    ].join("");
  }

  function circuitFocusCardMarkup(focusNode, connectivity, circuit) {
    if (!focusNode) {
      return '<div class="meta-card"><p class="band-copy">No circuit node is available.</p></div>';
    }
    const layerContext = connectivity.context_layers || {};
    return [
      '<div class="meta-card">',
      "<h4>Focus metadata</h4>",
      summaryList([
        ["Root", String(focusNode.root_id)],
        ["Cell type", String(focusNode.cell_type || "unknown")],
        ["Project role", String(focusNode.project_role || focusNode.subset_membership || "unknown")],
        ["Morphology", String(focusNode.morphology_class || "unknown")],
        ["Neighbors", String((focusNode.neighbor_root_ids || []).join(", ") || "none")],
        ["Context neighbors", String((focusNode.context_root_ids || []).join(", ") || "none")],
        ["Incoming synapses", String(focusNode.incoming_synapse_count || 0)],
        ["Outgoing synapses", String(focusNode.outgoing_synapse_count || 0)],
        [
          "Edge bundles",
          String(((layerContext.edge_coupling_bundles || {}).availability) || "unknown"),
        ],
        ["Local registry", basename(circuit.local_synapse_registry_path)],
      ]),
      "</div>",
    ].join("");
  }

  function circuitLayerCards(contextLayers) {
    const items = Object.keys(contextLayers || {})
      .sort()
      .map(function map(layerId) {
        const layer = contextLayers[layerId] || {};
        return (
          '<article class="mini-card">' +
          "<strong>" + escapeHtml(layerId.replace(/_/g, " ")) + "</strong>" +
          "<span>" + escapeHtml(String(layer.availability || "unknown")) + "</span>" +
          "</article>"
        );
      });
    return '<div class="mini-card-grid">' + items.join("") + "</div>";
  }

  function circuitGraphMarkup(nodes, edges, state) {
    if (!Array.isArray(nodes) || nodes.length === 0) {
      return '<div class="scene-empty"><strong>No connectivity context.</strong></div>';
    }
    const width = 360;
    const height = 260;
    const positions = computeGraphLayout(nodes, width, height);
    const maxCount = Math.max(
      1,
      ...((Array.isArray(edges) ? edges : []).map(function map(item) {
        return Number(item.synapse_count || 0);
      }))
    );
    const edgeMarkup = (Array.isArray(edges) ? edges : [])
      .map(function render(edge) {
        const pre = positions[edge.pre_root_id];
        const post = positions[edge.post_root_id];
        if (!pre || !post) {
          return "";
        }
        const edgeClass =
          "graph-edge" +
          (edge.source_selected && edge.target_selected ? " is-selected-edge" : " is-context-edge");
        const strokeWidth = 1.4 + (3.2 * Number(edge.synapse_count || 0)) / maxCount;
        return [
          '<g class="graph-edge-group">',
          '<line class="' +
            edgeClass +
            '" x1="' +
            pre.x.toFixed(2) +
            '" y1="' +
            pre.y.toFixed(2) +
            '" x2="' +
            post.x.toFixed(2) +
            '" y2="' +
            post.y.toFixed(2) +
            '" style="stroke-width:' +
            strokeWidth.toFixed(2) +
            'px"></line>',
          '<text class="graph-edge-label" x="' +
            ((pre.x + post.x) / 2).toFixed(2) +
            '" y="' +
            ((pre.y + post.y) / 2).toFixed(2) +
            '">' +
            escapeHtml(String(edge.synapse_count)) +
            "</text>",
          "</g>",
        ].join("");
      })
      .join("");
    const nodeMarkup = nodes
      .map(function render(node) {
        const position = positions[node.root_id];
        const isSelected = Number(node.root_id) === Number(state.selected_neuron_id);
        const isHovered = state.hovered_neuron_id !== null && Number(node.root_id) === Number(state.hovered_neuron_id);
        const nodeClass =
          "graph-node" +
          (node.selection_enabled ? " is-selectable" : " is-context") +
          (isSelected ? " is-selected" : "") +
          (isHovered ? " is-hovered" : "");
        const labelClass =
          "graph-label" + (node.selection_enabled ? "" : " is-context-label");
        return [
          '<g class="graph-node-group" data-root-hover="' +
            escapeHtml(String(node.root_id)) +
            '"' +
            (node.selection_enabled
              ? ' data-root-select="' + escapeHtml(String(node.root_id)) + '"'
              : "") +
            '>',
          '<circle class="' +
            nodeClass +
            '" cx="' +
            position.x.toFixed(2) +
            '" cy="' +
            position.y.toFixed(2) +
            '" r="' +
            String(position.radius) +
            '"></circle>',
          '<text class="' +
            labelClass +
            '" x="' +
            position.x.toFixed(2) +
            '" y="' +
            (position.y + position.radius + 16).toFixed(2) +
            '">' +
            escapeHtml(String(node.root_id)) +
            "</text>",
          "</g>",
        ].join("");
      })
      .join("");
    return [
      '<svg class="circuit-graph" viewBox="0 0 ' + String(width) + " " + String(height) + '">',
      edgeMarkup,
      nodeMarkup,
      "</svg>",
    ].join("");
  }

  function computeGraphLayout(nodes, width, height) {
    const selected = nodes.filter(function filter(node) {
      return String(node.subset_membership) === "selected_subset";
    });
    const context = nodes.filter(function filter(node) {
      return String(node.subset_membership) !== "selected_subset";
    });
    const centerX = width / 2;
    const centerY = height / 2;
    const positions = {};

    positionRing(selected, centerX, centerY, selected.length <= 1 ? 0 : 68, 18);
    positionRing(context, centerX, centerY, context.length <= 1 ? 104 : 110, 14);
    return positions;

    function positionRing(group, x, y, radius, nodeRadius) {
      if (!group.length) {
        return;
      }
      if (group.length === 1) {
        positions[group[0].root_id] = {
          x: x,
          y: y + (radius === 0 ? 0 : radius),
          radius: nodeRadius,
        };
        return;
      }
      group.forEach(function each(node, index) {
        const angle = (-Math.PI / 2) + (2 * Math.PI * index) / group.length;
        positions[node.root_id] = {
          x: x + Math.cos(angle) * radius,
          y: y + Math.sin(angle) * radius,
          radius: nodeRadius,
        };
      });
    }
  }

  function paintSceneFrame(canvas, frame) {
    if (!canvas || !frame) {
      return;
    }
    const width = Number(frame.width || 0);
    const height = Number(frame.height || 0);
    if (width <= 0 || height <= 0) {
      return;
    }
    const pixels = decodeBase64ToBytes(frame.pixels_b64);
    const context = canvas.getContext("2d");
    if (!context) {
      return;
    }
    canvas.width = width;
    canvas.height = height;
    const image = context.createImageData(width, height);
    for (let index = 0; index < pixels.length; index += 1) {
      const value = pixels[index];
      const base = index * 4;
      image.data[base] = value;
      image.data[base + 1] = value;
      image.data[base + 2] = value;
      image.data[base + 3] = 255;
    }
    context.putImageData(image, 0, 0);
  }

  function decodeBase64ToBytes(value) {
    const binary = window.atob(String(value || ""));
    const bytes = new Uint8ClampedArray(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return bytes;
  }

  function overlayName(model, overlayId) {
    const item = ((model.overlay_catalog || {}).overlay_definitions || []).find(function find(entry) {
      return String(entry.overlay_id) === String(overlayId);
    });
    return item ? String(item.display_name) : String(overlayId);
  }

  function comparisonModeName(model, comparisonModeId) {
    const item = (model.comparison_mode_catalog || []).find(function find(entry) {
      return String(entry.comparison_mode_id) === String(comparisonModeId);
    });
    return item ? String(item.display_name) : String(comparisonModeId);
  }

  function overlayNarrative(model, overlayId, comparisonModeId) {
    return (
      overlayName(model, overlayId) +
      " remains linked to " +
      comparisonModeName(model, comparisonModeId) +
      " mode, so morphology work later can swap richer visuals in without changing the shell-owned state contract."
    );
  }

  function getPaneBody(paneId) {
    return document.querySelector('[data-pane-body="' + paneId + '"]');
  }

  function syncSelectValue(selectId, value) {
    const select = document.getElementById(selectId);
    if (select) {
      select.value = String(value);
    }
  }

  function paneBand(title, kicker, content) {
    return [
      '<section class="pane-band">',
      '  <div class="band-title">',
      "    <div>",
      "      <p class=\"section-kicker\">" + escapeHtml(kicker || "linked view") + "</p>",
      "      <h3>" + escapeHtml(title) + "</h3>",
      "    </div>",
      "  </div>",
      content,
      "</section>",
    ].join("");
  }

  function statePill(label, value) {
    return '<span class="state-pill"><strong>' + escapeHtml(label) + ":</strong> " + escapeHtml(value) + "</span>";
  }

  function pillRow(items) {
    return '<div class="pill-row">' + items.join("") + "</div>";
  }

  function chipList(items) {
    return (
      '<div class="chip-list">' +
      items
        .map(function render(item) {
          const toneClass = item.tone === "warn" ? " is-warn" : " is-good";
          return '<span class="chip' + toneClass + '">' + escapeHtml(String(item.label)) + "</span>";
        })
        .join("") +
      "</div>"
    );
  }

  function scopeBannerMarkup(scopeLabel, text) {
    const tone =
      String(scopeLabel) === "shared_comparison"
        ? " fairness-chip"
        : String(scopeLabel) === "wave_only_diagnostic"
          ? " diagnostic-chip"
          : String(scopeLabel) === "validation_evidence"
            ? " validation-chip"
          : " context-chip";
    return (
      '<div class="scope-banner">' +
      '<span class="scope-chip' + tone + '">' +
      escapeHtml(String(scopeLabel).replace(/_/g, " ")) +
      "</span>" +
      '<span class="scope-copy">' +
      escapeHtml(String(text)) +
      "</span>" +
      "</div>"
    );
  }

  function comparisonFailureMarkup(message) {
    return (
      '<div class="comparison-failure">' +
      "<strong>Comparison unavailable</strong>" +
      "<p>" + escapeHtml(String(message)) + "</p>" +
      "</div>"
    );
  }

  function timeSeriesChartMarkup(series, sampleIndex, scopeLabel) {
    const normalizedSeries = Array.isArray(series) ? series : [];
    if (!normalizedSeries.length) {
      return comparisonFailureMarkup("No trace series are packaged for this selection.");
    }
    const pointCount = Math.max(
      1,
      ...normalizedSeries.map(function map(item) {
        return Array.isArray(item.values) ? item.values.length : 0;
      })
    );
    const width = 520;
    const height = 220;
    const paddingX = 28;
    const paddingY = 18;
    const allValues = normalizedSeries.reduce(function flatten(acc, item) {
      return acc.concat((Array.isArray(item.values) ? item.values : []).map(function map(value) {
        return Number(value || 0);
      }));
    }, []);
    const minValue = allValues.length ? Math.min.apply(null, allValues) : 0;
    const maxValue = allValues.length ? Math.max.apply(null, allValues) : 0;
    const domainPad = Math.max((maxValue - minValue) * 0.1, 0.1);
    const yMin = minValue - domainPad;
    const yMax = maxValue + domainPad;
    const resolvedSample = clampSampleIndex(sampleIndex, pointCount);
    const cursorX = pointCount === 1
      ? width / 2
      : paddingX + ((width - paddingX * 2) * resolvedSample) / (pointCount - 1);
    const gridLines = [0, 0.25, 0.5, 0.75, 1]
      .map(function map(tick) {
        const y = paddingY + (height - paddingY * 2) * tick;
        return (
          '<line class="trace-grid-line" x1="' +
          paddingX +
          '" y1="' +
          y.toFixed(2) +
          '" x2="' +
          (width - paddingX) +
          '" y2="' +
          y.toFixed(2) +
          '"></line>'
        );
      })
      .join("");
    const pathMarkup = normalizedSeries
      .map(function render(item) {
        const values = Array.isArray(item.values) ? item.values : [];
        const points = values
          .map(function map(value, index) {
            const x = pointCount === 1
              ? width / 2
              : paddingX + ((width - paddingX * 2) * index) / (pointCount - 1);
            const normalizedY = yMax === yMin ? 0.5 : (Number(value || 0) - yMin) / (yMax - yMin);
            const y = height - paddingY - normalizedY * (height - paddingY * 2);
            return x.toFixed(2) + "," + y.toFixed(2);
          })
          .join(" ");
        const markerValue = Number(values[resolvedSample] || 0);
        const markerYNorm = yMax === yMin ? 0.5 : (markerValue - yMin) / (yMax - yMin);
        const markerY = height - paddingY - markerYNorm * (height - paddingY * 2);
        const color = traceSeriesColor(item.series_id, scopeLabel);
        return [
          '<polyline class="trace-line" points="' +
            escapeHtml(points) +
            '" style="stroke:' +
            escapeHtml(color) +
            ';"></polyline>',
          '<circle class="trace-marker" cx="' +
            cursorX.toFixed(2) +
            '" cy="' +
            markerY.toFixed(2) +
            '" r="4" style="fill:' +
            escapeHtml(color) +
            ';"></circle>',
        ].join("");
      })
      .join("");
    const legend = normalizedSeries
      .map(function render(item) {
        const color = traceSeriesColor(item.series_id, scopeLabel);
        return (
          '<span class="trace-legend-item">' +
          '<span class="trace-legend-swatch" style="background:' + escapeHtml(color) + ';"></span>' +
          escapeHtml(String(item.display_name || item.series_id)) +
          "</span>"
        );
      })
      .join("");
    return [
      '<div class="trace-stage">',
      '<svg class="trace-svg" viewBox="0 0 ' + width + " " + height + '">',
      gridLines,
      '<line class="trace-cursor" x1="' +
        cursorX.toFixed(2) +
        '" y1="' +
        paddingY +
        '" x2="' +
        cursorX.toFixed(2) +
        '" y2="' +
        (height - paddingY) +
        '"></line>',
      pathMarkup,
      "</svg>",
      '<div class="trace-legend">' + legend + "</div>",
      "</div>",
    ].join("");
  }

  function traceSeriesColor(seriesId, scopeLabel) {
    if (String(scopeLabel) === "wave_only_diagnostic" || String(seriesId) === "wave_diagnostic") {
      return "#b56a2b";
    }
    if (String(seriesId) === "baseline") {
      return "#4a5a66";
    }
    if (String(seriesId) === "delta") {
      return "#7f4f24";
    }
    return "#0a5c63";
  }

  function paragraph(text) {
    return '<p class="band-copy">' + escapeHtml(String(text)) + "</p>";
  }

  function summaryList(rows) {
    return (
      '<dl class="summary-list">' +
      rows
        .map(function render(row) {
          return (
            "<dt>" +
            escapeHtml(String(row[0])) +
            "</dt><dd>" +
            escapeHtml(String(row[1])) +
            "</dd>"
          );
        })
        .join("") +
      "</dl>"
    );
  }

  function linkRow(links) {
    const items = [];
    if (links.analysis_offline_report) {
      items.push(anchor(links.analysis_offline_report, "Analysis report"));
    }
    if (links.validation_offline_report) {
      items.push(anchor(links.validation_offline_report, "Validation report"));
    }
    items.push(anchor(links.dashboard_session_metadata, "Session metadata"));
    items.push(anchor(links.dashboard_session_payload, "Session payload"));
    items.push(anchor(links.dashboard_session_state, "Session state"));
    return '<div class="link-row">' + items.join("") + "</div>";
  }

  function anchor(href, label) {
    return '<a href="' + escapeHtml(String(href)) + '">' + escapeHtml(String(label)) + "</a>";
  }

  function formatTimeCursor(timeMs, sampleIndex) {
    return Number(timeMs).toFixed(1) + " ms @ " + String(sampleIndex);
  }

  function basename(value) {
    if (!value) {
      return "n/a";
    }
    const normalized = String(value).replace(/\\/g, "/");
    return normalized.split("/").pop() || normalized;
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function bindChange(id, handler) {
    const node = document.getElementById(id);
    if (!node) {
      return;
    }
    node.addEventListener("change", function onChange(event) {
      handler(event.target.value);
    });
  }

  function bindInput(id, handler) {
    const node = document.getElementById(id);
    if (!node) {
      return;
    }
    node.addEventListener("input", function onInput(event) {
      handler(event.target.value);
    });
  }
})();
