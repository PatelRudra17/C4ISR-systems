/**
 * AI Threat Analysis Dashboard
 * Feature: ai-threat-analysis-dashboard
 */

const SEVERITY_WEIGHTS = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };

class ThreatDashboard {
    constructor(apiBaseURL) {
        this.apiBaseURL = apiBaseURL;
        this.state = {
            threats: [],
            prevThreats: [],
            patterns: [],
            selectedThreatId: null,
            timeWindowMinutes: 60,
            heatmapVisible: false,
            feedOk: true,
            lastUpdated: null,
            isDemoMode: false,
            pollCount: 0
        };
        this._intervalId = null;
    }

    start() {
        this._poll();
        this._intervalId = setInterval(() => this._poll(), 5000);
    }

    stop() {
        clearInterval(this._intervalId);
        this._intervalId = null;
    }

    _setFeedStatus(ok) {
        this.state.feedOk = ok;
        const el = document.getElementById('feed-degraded');
        if (el) {
            el.style.display = ok ? 'none' : 'flex';
        }
    }

    _setDemoMode(isDemoMode) {
        this.state.isDemoMode = isDemoMode;
        const el = document.getElementById('demo-badge');
        if (el) {
            el.style.display = isDemoMode ? 'flex' : 'none';
        }
    }

    async _poll() {
        try {
            const [threatsRes, patternsRes] = await Promise.all([
                fetch(`${this.apiBaseURL}/api/v1/threats/active`),
                fetch(`${this.apiBaseURL}/api/v1/threats/patterns`)
            ]);
            if (!threatsRes.ok || !patternsRes.ok) throw new Error('Non-OK response');
            const threats = await threatsRes.json();
            const patterns = await patternsRes.json();

            this.state.prevThreats = [...this.state.threats];
            this.state.threats = threats;
            this.state.patterns = patterns;
            this.state.pollCount++;
            this.state.lastUpdated = new Date();

            // Update last-updated display
            const luEl = document.getElementById('last-updated');
            if (luEl) luEl.textContent = 'UPDATED ' + this.state.lastUpdated.toLocaleTimeString();

            this._setFeedStatus(true);
            this._renderThreatList(threats, patterns);
            this._renderSummaryPanel(threats, patterns, this.state.prevThreats);
            this._renderTimeline(threats, this.state.timeWindowMinutes);
            this._renderHeatmap(threats);
        } catch (err) {
            this._setFeedStatus(false);
        }
    }

    _diffThreats(prev, next) {
        const prevMap = new Map(prev.map(t => [t.threat_id, t]));
        const nextMap = new Map(next.map(t => [t.threat_id, t]));
        const added = next.filter(t => !prevMap.has(t.threat_id));
        const removed = prev.filter(t => !nextMap.has(t.threat_id));
        const updated = next.filter(t => prevMap.has(t.threat_id) && prevMap.get(t.threat_id).ai_confidence !== t.ai_confidence);
        return { added, removed, updated };
    }

    _renderThreatList(threats, patterns) {
        const container = document.getElementById('threat-list');
        if (!container) return;

        // Build pattern map for quick lookup
        const patternMap = new Map((patterns || []).map(p => [p.pattern_id, p]));

        // Diff against previous state
        const { added, removed, updated } = this._diffThreats(this.state.prevThreats, threats);

        // Remove resolved threats from DOM
        for (const t of removed) {
            const el = container.querySelector(`[data-threat-id="${t.threat_id}"]`);
            if (el) el.remove();
        }

        // Update confidence bars for changed threats
        for (const t of updated) {
            const el = container.querySelector(`[data-threat-id="${t.threat_id}"]`);
            if (el) {
                const bar = el.querySelector('.confidence-bar');
                const pct = el.querySelector('.confidence-pct');
                if (bar) {
                    const color = this._getConfidenceColor(t.ai_confidence);
                    bar.style.width = `${Math.round(t.ai_confidence * 100)}%`;
                    bar.className = `confidence-bar confidence-${color}`;
                }
                if (pct) pct.textContent = `${Math.round(t.ai_confidence * 100)}%`;
            }
        }

        // Group threats by pattern_id
        const grouped = new Map(); // pattern_id → threats[]
        const ungrouped = [];

        for (const threat of threats) {
            if (threat.pattern_id && patternMap.has(threat.pattern_id)) {
                if (!grouped.has(threat.pattern_id)) grouped.set(threat.pattern_id, []);
                grouped.get(threat.pattern_id).push(threat);
            } else {
                ungrouped.push(threat);
            }
        }

        // Render pattern groups (only if not already in DOM)
        for (const [patternId, groupThreats] of grouped) {
            const pattern = patternMap.get(patternId);
            const existing = container.querySelector(`[data-pattern-id="${patternId}"]`);
            if (!existing) {
                const groupEl = this._renderPatternGroup(pattern, groupThreats);
                container.appendChild(groupEl);
            }
        }

        // Render individual (ungrouped) threats
        // Prepend new threats, append existing ones
        const addedIds = new Set(added.map(t => t.threat_id));

        for (const threat of ungrouped) {
            const existing = container.querySelector(`.threat-row[data-threat-id="${threat.threat_id}"]`);
            if (existing) continue; // already rendered (and updated above if needed)

            const row = this._buildThreatRow(threat);
            if (addedIds.has(threat.threat_id)) {
                row.classList.add('threat-row-new');
                container.prepend(row);
            } else {
                container.appendChild(row);
            }
        }
    }

    _buildThreatRow(threat) {
        const { threat_id, threat_type, severity, ai_confidence, sector } = threat;
        const pct = Math.round(ai_confidence * 100);
        const color = this._getConfidenceColor(ai_confidence);
        const sevLower = (severity || 'low').toLowerCase();

        const row = document.createElement('div');
        row.className = 'threat-row';
        row.dataset.threatId = threat_id;
        row.innerHTML = `
            <span class="severity-badge severity-${sevLower}">${severity}</span>
            <span class="threat-type">${threat_type}</span>
            <span class="threat-id">${threat_id}</span>
            <div class="confidence-bar-container">
                <div class="confidence-bar confidence-${color}" style="width:${pct}%; transition: width 300ms ease;"></div>
            </div>
            <span class="confidence-pct">${pct}%</span>
            <span class="threat-sector">${sector || ''}</span>
        `;
        row.addEventListener('click', () => {
            this._renderBreakdownPanel(threat);
            const panel = document.getElementById('breakdown-panel');
            if (panel) panel.style.display = 'block';
        });
        return row;
    }

    _renderPatternGroup(pattern, threats) {
        const { pattern_id, pattern_name, threat_ids, aggregate_confidence, contains_critical } = pattern;
        const memberCount = (threat_ids || threats || []).length;
        const confPct = Math.round((aggregate_confidence || 0) * 100);

        const group = document.createElement('div');
        group.className = `pattern-group${contains_critical ? ' pattern-critical' : ''}`;
        group.dataset.patternId = pattern_id;

        const header = document.createElement('div');
        header.className = 'pattern-header';
        header.innerHTML = `
            <span class="pattern-name">${pattern_name}</span>
            <span class="pattern-count">${memberCount} THREATS</span>
            <span class="pattern-confidence">${confPct}%</span>
            <span class="pattern-toggle">▶</span>
        `;

        const members = document.createElement('div');
        members.className = 'pattern-members';
        members.style.display = 'none';

        // Render member threat rows
        for (const threat of (threats || [])) {
            members.appendChild(this._buildThreatRow(threat));
        }

        header.addEventListener('click', () => {
            const expanded = members.style.display !== 'none';
            members.style.display = expanded ? 'none' : 'block';
            const toggle = header.querySelector('.pattern-toggle');
            if (toggle) toggle.textContent = expanded ? '▶' : '▼';
        });

        group.appendChild(header);
        group.appendChild(members);
        return group;
    }

    _renderSummaryPanel(threats, patterns, prevThreats) {
        // Stub: will be implemented in Task 10
    }

    _renderTimeline(threats, windowMinutes) {
        // Stub: will be implemented in Task 8
    }

    _renderHeatmap(threats) {
        // Stub: will be implemented in Task 7
    }

    _renderBreakdownPanel(threat) {
        // Stub: will be implemented in Task 9
    }

    _computePatternGroups(threats) {
        // Stub: will be implemented in Task 6
        return [];
    }

    /**
     * Map threats to a 10x10 grid using lat/lng bounds:
     *   lat: 33.5 – 35.0, lng: -119.0 – -117.0
     * Sum SEVERITY_WEIGHTS per cell.
     * Returns a Map keyed by "row,col" with weight values.
     */
    _computeHeatmapWeights(threats) {
        const LAT_MIN = 33.5, LAT_MAX = 35.0;
        const LNG_MIN = -119.0, LNG_MAX = -117.0;
        const ROWS = 10, COLS = 10;

        const weights = new Map();

        for (const threat of threats) {
            const { lat, lng, severity } = threat;
            // Clamp to bounds
            if (lat < LAT_MIN || lat > LAT_MAX || lng < LNG_MIN || lng > LNG_MAX) continue;

            const row = Math.min(ROWS - 1, Math.floor((lat - LAT_MIN) / (LAT_MAX - LAT_MIN) * ROWS));
            const col = Math.min(COLS - 1, Math.floor((lng - LNG_MIN) / (LNG_MAX - LNG_MIN) * COLS));
            const key = `${row},${col}`;
            const w = SEVERITY_WEIGHTS[severity] ?? SEVERITY_WEIGHTS.LOW;
            weights.set(key, (weights.get(key) ?? 0) + w);
        }

        return weights;
    }

    /**
     * Compute weighted average of non-null sub-model scores.
     * Weights: radar_classification=0.35, visual_recognition=0.30,
     *          behavioral_analysis=0.20, signal_intelligence=0.15
     * Renormalize when sub-models are absent/null.
     * Returns null if all scores are null.
     */
    _computeWeightedScore(breakdown) {
        const MODEL_WEIGHTS = {
            radar_classification: 0.35,
            visual_recognition: 0.30,
            behavioral_analysis: 0.20,
            signal_intelligence: 0.15
        };

        let weightedSum = 0;
        let totalWeight = 0;

        for (const [key, weight] of Object.entries(MODEL_WEIGHTS)) {
            const entry = breakdown[key];
            // entry may be an object with a .score field, or a raw number, or null
            let score = null;
            if (entry !== null && entry !== undefined) {
                if (typeof entry === 'object') {
                    score = entry.score;
                } else if (typeof entry === 'number') {
                    score = entry;
                }
            }

            if (score !== null && score !== undefined) {
                weightedSum += score * weight;
                totalWeight += weight;
            }
        }

        if (totalWeight === 0) return null;

        // Renormalize
        return weightedSum / totalWeight;
    }

    /**
     * Return 'green' if score >= 0.85, 'amber' if score >= 0.60, 'red' if score < 0.60.
     */
    _getConfidenceColor(score) {
        if (score >= 0.85) return 'green';
        if (score >= 0.60) return 'amber';
        return 'red';
    }

    /**
     * Return '↑' if next > prev, '↓' if next < prev, '—' if equal.
     */
    _getTrendIndicator(prev, next) {
        if (next > prev) return '↑';
        if (next < prev) return '↓';
        return '—';
    }
}

// Instance created in index.html when threats module activates
window.ThreatDashboard = ThreatDashboard;
