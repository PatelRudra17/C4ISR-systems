# Implementation Plan: AI Threat Analysis Dashboard

## Overview

Implement the AI Threat Analysis Dashboard by enriching the demo server with synthetic enriched threat data, creating `frontend/threat-analysis.js` with the `ThreatDashboard` class, extending `frontend/index.html` with the dashboard UI, and wiring up all polling, rendering, and event-handling logic. Implementation language: plain JavaScript (no build system) + Python (FastAPI demo server).

## Tasks

- [x] 1. Enrich demo server with `/api/v1/threats/active` endpoint
  - Add a module-level `_poll_count` counter to `demo_server.py` to drive score mutation
  - Define at least 5 `EnrichedThreat` seed objects with varied `severity` (CRITICAL/HIGH/MEDIUM/LOW) and `ai_confidence` values spanning 0.0–1.0, each with a full `confidence_breakdown` (radar_classification, visual_recognition, behavioral_analysis, signal_intelligence) and a `pattern_id`
  - On each request, mutate each threat's `ai_confidence` by a random delta of ±0.05 clamped to [0.0, 1.0], increment `_poll_count`
  - Add `GET /api/v1/threats/active` returning the mutated `EnrichedThreat[]`
  - Add `GET /api/v1/threats/patterns` returning at least 2 `ThreatPattern` objects (pattern_id, pattern_name, threat_ids, aggregate_confidence, contains_critical, centroid_lat, centroid_lng)
  - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 1.1 Write property test for demo server score mutation bounds (Property 23)
    - **Property 23: Demo mode score mutation stays within bounds**
    - **Validates: Requirements 8.3**
    - Use fast-check to generate random starting scores; simulate N poll cycles; assert each delta ≤ 0.05 and result ∈ [0.0, 1.0]

  - [x] 1.2 Write property test for demo server required fields (Property 24)
    - **Property 24: Demo threats include all required fields**
    - **Validates: Requirements 8.1**
    - Call the demo endpoint; assert every returned threat has non-null `ai_confidence`, `confidence_breakdown`, and `pattern_id`

- [x] 2. Create `frontend/threat-analysis.js` — core class skeleton and pure functions
  - Create `frontend/threat-analysis.js` with the `ThreatDashboard` class
  - Implement constructor accepting `apiBaseURL`; initialize `DashboardState` object (threats, prevThreats, patterns, selectedThreatId, timeWindowMinutes=60, heatmapVisible, feedOk, lastUpdated, isDemoMode, pollCount)
  - Implement `start()` / `stop()` using `setInterval` at 5000 ms
  - Implement `_setFeedStatus(ok)` and `_setDemoMode(isDemoMode)`
  - Implement pure functions: `_getConfidenceColor(score)`, `_getTrendIndicator(prev, next)`, `_computeWeightedScore(breakdown)`, `_computePatternGroups(threats)`, `_computeHeatmapWeights(threats)`
  - Define `SEVERITY_WEIGHTS = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 }`
  - _Requirements: 1.2, 1.3, 1.4, 2.1, 7.4, 6.6, 3.1, 5.2_

  - [x] 2.1 Write property test for confidence color tier mapping (Property 1)
    - **Property 1: Confidence color tier mapping**
    - **Validates: Requirements 1.2, 1.3, 1.4**
    - Generate random scores in [0.0, 1.0]; assert result is always one of `'green'`/`'amber'`/`'red'` and matches the correct threshold

  - [x] 2.2 Write property test for trend indicator direction (Property 21)
    - **Property 21: Trend indicators reflect count direction**
    - **Validates: Requirements 7.4**
    - Generate random (prev, next) count pairs; assert `↑` when next > prev, `↓` when next < prev, `—` when equal

  - [x] 2.3 Write property test for weighted confidence score computation (Property 18)
    - **Property 18: Weighted confidence score computation**
    - **Validates: Requirements 6.6**
    - Generate random breakdown objects with some null scores; assert weighted average formula with renormalization

  - [x] 2.4 Write property test for heatmap cell weight computation (Property 16)
    - **Property 16: Heatmap cell weight computation**
    - **Validates: Requirements 5.2, 5.3**
    - Generate random threat sets per cell; assert weight = sum of SEVERITY_WEIGHTS and empty cell returns 0

- [x] 3. Add dashboard HTML structure to `frontend/index.html`
  - Inside `#module-threats`, replace or augment the existing content with:
    - Module header bar: "THREAT DETECTION" title, "PATTERNS DETECTED" counter (`#patterns-count`), "DEMO MODE" badge (`#demo-badge`, hidden by default), "FEED DEGRADED" banner (`#feed-degraded`, hidden by default), "AI HIGH CONFIDENCE" badge (`#ai-high-confidence-badge`, hidden by default), "LAST UPDATED" timestamp (`#last-updated`)
    - Summary panel (`#threat-summary`): total count, per-severity counts (CRITICAL/HIGH/MEDIUM/LOW) each with trend indicator, average confidence, pattern count
    - Threat list container (`#threat-list`) with scroll, supporting pattern group rows (collapsible) and individual threat rows with confidence bar and percentage
    - Timeline section: time-window selector buttons (15 min, 30 min, 60 min, 4 hr, 24 hr), SVG/div timeline container (`#threat-timeline`), "NO THREAT ACTIVITY" message (`#timeline-empty`)
    - Heatmap toggle button (`#heatmap-toggle`) wired to show/hide the SVG heatmap layer
    - Confidence breakdown panel (`#breakdown-panel`, hidden by default): 4 sub-model rows each with label, sensor source, horizontal bar, percentage or "N/A"
  - Add `<script src="threat-analysis.js" defer></script>` to `<head>`
  - _Requirements: 1.1, 1.5, 2.4, 2.6, 3.2, 3.5, 3.6, 4.1, 4.2, 4.6, 5.5, 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.5, 8.5_

- [x] 4. Implement `_poll()` and threat list rendering
  - Implement `_poll()`: fetch `/api/v1/threats/active` and `/api/v1/threats/patterns`, update state, call all render methods; on failure call `_setFeedStatus(false)`; on success call `_setFeedStatus(true)` and update `#last-updated`
  - Implement `_diffThreats(prev, next)` returning `{ added, removed, updated }`
  - Implement `_renderThreatList(threats, patterns)`: prepend new threat rows with slide-in animation, remove resolved rows, update existing rows' confidence bars with 300 ms CSS transition
  - Implement `_renderPatternGroup(pattern, threats)`: collapsible group row showing pattern name, member count, aggregate confidence; red border when `contains_critical`; expand/collapse toggle reveals member threats
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 1.1, 1.5, 1.6, 3.2, 3.3, 3.5_

  - [x] 4.1 Write property test for new threats prepended / resolved threats removed (Property 4)
    - **Property 4: New threats are prepended; resolved threats are removed**
    - **Validates: Requirements 2.2, 2.3**
    - Generate random prev/next threat ID sets; assert added IDs appear at top of rendered list and removed IDs are absent

  - [x] 4.2 Write property test for every rendered threat entry contains confidence display (Property 2)
    - **Property 2: Every rendered threat entry contains a confidence display**
    - **Validates: Requirements 1.1, 1.5**
    - Generate random EnrichedThreat arrays; assert every resulting DOM element has a percentage text node and a progress bar with `width` style

  - [x] 4.3 Write property test for feed degraded / restored round trip (Property 5)
    - **Property 5: Feed degraded / restored round trip**
    - **Validates: Requirements 2.4, 2.5**
    - Generate random fail/succeed sequences; assert `#feed-degraded` is visible after each failure and hidden after success

  - [x] 4.4 Write property test for last updated timestamp advances (Property 6)
    - **Property 6: Last updated timestamp advances on success**
    - **Validates: Requirements 2.6**
    - Generate random successful polls; assert displayed timestamp is non-decreasing

  - [x] 4.5 Write property test for polling fires at correct interval (Property 3)
    - **Property 3: Polling fires at the correct interval**
    - **Validates: Requirements 2.1**
    - Mock `setInterval` and advance fake timers; assert `_poll()` call count = `floor(T / 5)` ± 1

- [ ] 5. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement pattern group rendering and map connector layer
  - Implement `_renderPatternGroup` fully: render collapsible group in `#threat-list` with pattern name, member count, aggregate confidence, red border when `contains_critical`
  - Add SVG `<g id="pattern-layer">` inside `#tacticalMap`; implement pattern bounding polygon / connector lines linking threats in the same pattern, keyed by `pattern_id`
  - Update `#patterns-count` in the module header on each render
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [ ] 6.1 Write property test for pattern group renders required fields (Property 8)
    - **Property 8: Pattern group renders required fields**
    - **Validates: Requirements 3.2**
    - Generate random ThreatPattern objects; assert rendered group contains pattern name, member count = `threat_ids.length`, and aggregate confidence

  - [ ] 6.2 Write property test for expanding a pattern group reveals member threats (Property 9)
    - **Property 9: Expanding a pattern group reveals member threats**
    - **Validates: Requirements 3.3**
    - Generate random patterns; trigger expand; assert all member threat entries are visible in DOM

  - [ ] 6.3 Write property test for CRITICAL pattern gets red border (Property 10)
    - **Property 10: CRITICAL pattern gets red border**
    - **Validates: Requirements 3.5**
    - Generate patterns with/without `contains_critical`; assert red-border class presence matches flag

  - [ ] 6.4 Write property test for patterns counter equals active pattern count (Property 11)
    - **Property 11: Patterns counter equals active pattern count**
    - **Validates: Requirements 3.6**
    - Generate random pattern lists; assert `#patterns-count` value equals list length

  - [ ] 6.5 Write property test for pattern grouping respects spatial and temporal proximity (Property 7)
    - **Property 7: Pattern grouping respects spatial and temporal proximity**
    - **Validates: Requirements 3.1**
    - Generate random threat pairs with random lat/lng/time; assert same group iff within 5 km AND 15 min

- [ ] 7. Implement SVG heatmap layer
  - Add SVG `<g id="heatmap-layer">` inside `#tacticalMap` (below pattern layer)
  - Implement `_computeHeatmapWeights(threats)`: map threats to grid cells using lat/lng bounds, sum `SEVERITY_WEIGHTS` per cell
  - Implement `_renderHeatmap(threats)`: create/update SVG `<rect>` cells; opacity=0 for empty cells; red fill at opacity 1.0 for weight > 8; interpolate color/opacity for intermediate weights
  - Wire heatmap toggle button (`#heatmap-toggle`) to `state.heatmapVisible`; show/hide `#heatmap-layer`
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ] 7.1 Write property test for high-weight cells render red at full opacity (Property 17)
    - **Property 17: High-weight cells render red at full opacity**
    - **Validates: Requirements 5.4**
    - Generate cells with weight > 8; assert SVG element has red fill at opacity 1.0

- [ ] 8. Implement timeline component
  - Implement `_renderTimeline(threats, windowMinutes)`: filter threats to those with `detected_at` within the last `windowMinutes`; render each as a colored SVG/div marker positioned proportionally on the time axis; color matches `severity` using the same severity-to-color mapping as the threat list
  - Implement hover tooltip on each marker exposing `{ threat_id, threat_type, severity, ai_confidence, detected_at }`
  - Implement incremental append: on new threats arriving, append only new markers without full re-render
  - Wire time-window selector buttons to update `state.timeWindowMinutes` and re-render timeline
  - Show `#timeline-empty` message when no threats fall within the selected window
  - Default window is 60 minutes
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [ ] 8.1 Write property test for timeline filter excludes out-of-window threats (Property 12)
    - **Property 12: Timeline filter excludes out-of-window threats**
    - **Validates: Requirements 4.2**
    - Generate random threats and time windows; assert only in-window threats produce markers

  - [ ] 8.2 Write property test for timeline marker color matches severity (Property 13)
    - **Property 13: Timeline marker color matches severity**
    - **Validates: Requirements 4.3**
    - Generate random threats; assert each marker's color class matches the threat's `severity`

  - [ ] 8.3 Write property test for timeline tooltip contains all required fields (Property 14)
    - **Property 14: Timeline tooltip contains all required fields**
    - **Validates: Requirements 4.4**
    - Generate random threats; assert tooltip data object has non-null `threat_id`, `threat_type`, `severity`, `ai_confidence`, `detected_at`

  - [ ] 8.4 Write property test for new threats append to timeline without full re-render (Property 15)
    - **Property 15: New threats append to timeline without full re-render**
    - **Validates: Requirements 4.5**
    - Generate random new threats within window; assert marker count increases by exactly 1 and existing markers retain positions

- [ ] 9. Implement confidence breakdown panel
  - Implement `_renderBreakdownPanel(threat)`: populate `#breakdown-panel` with 4 rows (Radar Classification, Visual Recognition, Behavioral Analysis, Signal Intelligence); each row shows label, sensor source, horizontal bar with `width` proportional to score, numeric percentage or "N/A" when score is null
  - Wire threat row click event to call `_renderBreakdownPanel(threat)` and show `#breakdown-panel`
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ] 9.1 Write property test for confidence breakdown panel contains all sub-model rows (Property 19)
    - **Property 19: Confidence breakdown panel contains all sub-model rows**
    - **Validates: Requirements 6.2, 6.3, 6.4, 6.5**
    - Generate random EnrichedThreat objects; assert breakdown panel has exactly 4 rows each with label, bar, percentage or "N/A", and sensor source

- [ ] 10. Implement summary panel and AI HIGH CONFIDENCE badge
  - Implement `_renderSummaryPanel(threats, patterns, prevThreats)`: update `#threat-summary` with total count, per-severity counts, average `ai_confidence`, pattern count
  - Compute trend indicators using `_getTrendIndicator` for each severity level; update trend arrow elements
  - Flash CRITICAL count indicator for 2 seconds when CRITICAL count increases vs previous poll
  - Show `#ai-high-confidence-badge` if and only if all threats have `ai_confidence > 0.80` and `threats.length > 0`
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ] 10.1 Write property test for summary panel values match threat list state (Property 20)
    - **Property 20: Summary panel values match threat list state**
    - **Validates: Requirements 7.1**
    - Generate random threat/pattern lists; assert total count, per-severity counts summing to total, average confidence, and pattern count are all correct

  - [ ] 10.2 Write property test for AI HIGH CONFIDENCE badge visibility (Property 22)
    - **Property 22: AI HIGH CONFIDENCE badge visibility**
    - **Validates: Requirements 7.5**
    - Generate random threat lists; assert badge visible iff every threat has `ai_confidence > 0.80` and list is non-empty

- [ ] 11. Wire up initialization and demo mode fallback
  - In `threat-analysis.js`, export / instantiate `ThreatDashboard` and call `start()` when the threats module tab is activated (hook into the existing `showModule('threats')` call in `index.html`)
  - Implement offline fallback: if the first poll fails, load static seed data embedded in `threat-analysis.js` and call `_setDemoMode(true)` to show `#demo-badge` with "DEMO MODE (OFFLINE)"
  - Implement `stop()` call when navigating away from the threats tab to clear the polling interval
  - _Requirements: 2.1, 8.5_

- [ ] 12. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- fast-check is used for property-based tests via CDN (no build system required): `<script src="https://cdn.jsdelivr.net/npm/fast-check/lib/bundle/fast-check.min.js"></script>`
- Each property test file should include the comment: `// Feature: ai-threat-analysis-dashboard, Property N: <property_text>`
- All CSS variables (`--green`, `--amber`, `--red`, `--cyan`) are already defined in `index.html` and available to `threat-analysis.js` DOM elements
- The SVG `#tacticalMap` already exists in `index.html`; heatmap and pattern layers are appended as child `<g>` elements
- The `showModule()` function in `index.html` controls tab visibility and is the correct hook for `start()`/`stop()`
