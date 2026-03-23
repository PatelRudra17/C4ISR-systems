# Requirements Document

## Introduction

The AI Threat Analysis Dashboard enhances the existing AEGIS C4ISR Threat Detection module with real-time AI-driven threat scoring, pattern detection, confidence visualization, and historical timeline analysis. The feature replaces the basic threat listing with a comprehensive analytical dashboard that surfaces AI model outputs, groups related threats into patterns, and provides operators with actionable situational awareness through live-updating visual indicators.

## Glossary

- **Dashboard**: The enhanced Threat Detection module view within the AEGIS C4ISR frontend
- **Threat**: A detected hostile contact with associated metadata (type, severity, location, sensor source)
- **AI_Engine**: The backend service responsible for computing threat confidence scores and pattern classifications
- **Confidence_Score**: A numeric value between 0.0 and 1.0 representing the AI model's certainty that a detected contact is a genuine threat
- **Threat_Pattern**: A named grouping of two or more spatially or temporally related threats identified by the AI_Engine as part of a coordinated activity
- **Severity_Level**: A discrete classification of threat danger: CRITICAL, HIGH, MEDIUM, or LOW
- **Heatmap**: A grid-based visual overlay on the tactical map where cell color intensity encodes the density or severity of threats in that geographic area
- **Timeline**: A chronological visualization of threat events within a configurable time window
- **Confidence_Breakdown**: A per-model decomposition of the overall Confidence_Score showing individual sub-model contributions
- **Polling_Interval**: The frequency at which the Dashboard queries the backend for updated threat data
- **Demo_Server**: The local FastAPI demo server running on port 8000 that provides mock threat data
- **Operator**: An authenticated AEGIS user viewing the Dashboard

## Requirements

### Requirement 1: Live Threat Confidence Score Display

**User Story:** As an Operator, I want to see a live AI confidence score for each threat, so that I can quickly assess how certain the system is about each detected contact.

#### Acceptance Criteria

1. THE Dashboard SHALL display a Confidence_Score for every threat entry in the threat list.
2. WHEN a threat's Confidence_Score is greater than or equal to 0.85, THE Dashboard SHALL render the confidence indicator in green.
3. WHEN a threat's Confidence_Score is between 0.60 and 0.84 inclusive, THE Dashboard SHALL render the confidence indicator in amber.
4. WHEN a threat's Confidence_Score is less than 0.60, THE Dashboard SHALL render the confidence indicator in red.
5. THE Dashboard SHALL display the Confidence_Score as both a numeric percentage (e.g., "94%") and a filled progress bar.
6. WHEN a threat's Confidence_Score changes between polling cycles, THE Dashboard SHALL animate the progress bar transition over 300 milliseconds.

---

### Requirement 2: Real-Time Threat Feed Updates

**User Story:** As an Operator, I want the threat list to update automatically as new threats are detected, so that I always have current situational awareness without manual refresh.

#### Acceptance Criteria

1. THE Dashboard SHALL poll the `/api/v1/threats/active` endpoint at a Polling_Interval of 5 seconds.
2. WHEN a new threat is received that was not present in the previous poll, THE Dashboard SHALL prepend the threat to the threat list with a slide-in animation.
3. WHEN a threat's status changes to a resolved state between polls, THE Dashboard SHALL remove the threat entry from the active list within one Polling_Interval.
4. IF the polling request fails, THEN THE Dashboard SHALL display a connection status indicator showing "FEED DEGRADED" and retain the last known threat data.
5. WHEN the polling connection is restored after a failure, THE Dashboard SHALL clear the "FEED DEGRADED" indicator and resume normal updates.
6. THE Dashboard SHALL display a "LAST UPDATED" timestamp that reflects the time of the most recent successful poll.

---

### Requirement 3: AI Pattern Detection Visualization

**User Story:** As an Operator, I want to see related threats grouped into named patterns, so that I can identify coordinated hostile activity rather than treating each threat in isolation.

#### Acceptance Criteria

1. THE AI_Engine SHALL group threats into Threat_Patterns based on spatial proximity (within 5 km) and temporal proximity (within 15 minutes).
2. THE Dashboard SHALL display each Threat_Pattern as a collapsible group in the threat list, showing the pattern name, member count, and aggregate Confidence_Score.
3. WHEN an Operator expands a Threat_Pattern group, THE Dashboard SHALL reveal the individual threat entries belonging to that pattern.
4. THE Dashboard SHALL render a visual connector or bounding polygon on the tactical map linking all threats within the same Threat_Pattern.
5. WHEN a Threat_Pattern contains a threat with Severity_Level CRITICAL, THE Dashboard SHALL highlight the entire pattern group with a red border.
6. THE Dashboard SHALL display a "PATTERNS DETECTED" counter in the module header showing the total number of active Threat_Patterns.

---

### Requirement 4: Threat Timeline Visualization

**User Story:** As an Operator, I want to view a chronological timeline of threat events, so that I can understand how the threat situation has evolved over time.

#### Acceptance Criteria

1. THE Dashboard SHALL render a horizontal timeline showing threat events for a configurable time window defaulting to the last 60 minutes.
2. WHEN an Operator selects a time window option (15 min, 30 min, 60 min, 4 hr, 24 hr), THE Dashboard SHALL re-render the timeline to display only threats detected within that window.
3. THE Dashboard SHALL represent each threat on the timeline as a colored marker where the color corresponds to the threat's Severity_Level.
4. WHEN an Operator hovers over a timeline marker, THE Dashboard SHALL display a tooltip containing the threat ID, type, Severity_Level, Confidence_Score, and detection timestamp.
5. THE Dashboard SHALL update the timeline in real time as new threats arrive, appending new markers without requiring a full re-render.
6. WHEN no threats exist within the selected time window, THE Dashboard SHALL display the message "NO THREAT ACTIVITY IN SELECTED WINDOW".

---

### Requirement 5: Severity Heatmap

**User Story:** As an Operator, I want a geographic heatmap of threat severity, so that I can identify high-risk zones at a glance without reading individual threat entries.

#### Acceptance Criteria

1. THE Dashboard SHALL render a Heatmap overlay on the tactical map that divides the operational theater into a grid of cells.
2. THE Dashboard SHALL compute each cell's color intensity based on the sum of Severity_Level weights of threats within that cell, where CRITICAL=4, HIGH=3, MEDIUM=2, LOW=1.
3. WHEN a cell contains no threats, THE Dashboard SHALL render it with zero opacity (transparent).
4. WHEN a cell's aggregate severity weight exceeds 8, THE Dashboard SHALL render it in red at full opacity.
5. THE Dashboard SHALL provide a toggle control allowing the Operator to show or hide the Heatmap overlay independently of other map layers.
6. THE Dashboard SHALL update the Heatmap within one Polling_Interval of new threat data being received.

---

### Requirement 6: AI Confidence Breakdown Per Threat

**User Story:** As an Operator, I want to see a per-model confidence breakdown for each threat, so that I can understand which sensors and AI sub-models contributed to the overall score.

#### Acceptance Criteria

1. WHEN an Operator selects a threat entry, THE Dashboard SHALL display a Confidence_Breakdown panel showing individual sub-model scores.
2. THE Confidence_Breakdown SHALL include scores for at minimum the following sub-models: Radar Classification, Visual Recognition, Behavioral Analysis, and Signal Intelligence.
3. THE Dashboard SHALL render each sub-model score as a labeled horizontal bar with a numeric percentage.
4. THE Dashboard SHALL display the sensor source (e.g., "RADAR-A") associated with each sub-model score.
5. WHEN a sub-model score is unavailable (e.g., sensor offline), THE Dashboard SHALL display "N/A" for that sub-model rather than omitting the row.
6. THE AI_Engine SHALL compute the overall Confidence_Score as the weighted average of available sub-model scores, where Radar Classification weight=0.35, Visual Recognition weight=0.30, Behavioral Analysis weight=0.20, Signal Intelligence weight=0.15.

---

### Requirement 7: Threat Scoring Summary Dashboard

**User Story:** As an Operator, I want a high-level scoring summary panel, so that I can assess the overall threat environment at a glance before drilling into individual threats.

#### Acceptance Criteria

1. THE Dashboard SHALL display a summary panel containing: total active threat count, count by Severity_Level, average Confidence_Score across all active threats, and count of active Threat_Patterns.
2. THE Dashboard SHALL update the summary panel within one Polling_Interval of receiving new threat data.
3. WHEN the count of CRITICAL threats increases compared to the previous poll, THE Dashboard SHALL flash the CRITICAL count indicator for 2 seconds.
4. THE Dashboard SHALL display a trend indicator (up arrow, down arrow, or dash) next to each Severity_Level count showing the change direction since the previous poll.
5. WHEN all active threats have a Confidence_Score above 0.80, THE Dashboard SHALL display an "AI HIGH CONFIDENCE" status badge in the summary panel.

---

### Requirement 8: Demo Mode Data Support

**User Story:** As a developer, I want the Dashboard to function with realistic mock data when the full backend is unavailable, so that the feature can be demonstrated and tested without a live AI pipeline.

#### Acceptance Criteria

1. WHEN the Demo_Server is the active backend, THE Dashboard SHALL generate synthetic threat data including Confidence_Scores, Confidence_Breakdowns, and Threat_Patterns.
2. THE Demo_Server SHALL return at least 5 threats with varied Severity_Levels and Confidence_Scores spanning the full 0.0–1.0 range.
3. WHEN operating in demo mode, THE Dashboard SHALL simulate real-time updates by mutating Confidence_Scores by a random delta of ±0.05 on each Polling_Interval.
4. THE Demo_Server SHALL return at least 2 Threat_Patterns grouping the demo threats.
5. WHEN operating in demo mode, THE Dashboard SHALL display a "DEMO MODE" badge in the module header so the Operator is aware data is synthetic.
