// AEGIS C4ISR - Frontend API Integration
// Connects the tactical UI to the FastAPI backend

class AegisAPI {
    constructor() {
        const origin = window.location.origin;
        this.baseURL = (origin.includes('localhost') || origin === 'null' || origin.startsWith('file'))
            ? 'http://localhost:8000'
            : origin;
        this.token = localStorage.getItem('aegis_token');
        this.refreshToken = localStorage.getItem('aegis_refresh_token');
        this.wsConnections = {};
    }

    // Authentication
    async login(callsign, password, totpCode = null) {
        try {
            const response = await fetch(`${this.baseURL}/api/v1/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ callsign, password, totp_code: totpCode })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Login failed');
            }

            const data = await response.json();

            if (data.mfa_required && data.totp_setup_uri) {
                // First time login - show QR code for TOTP setup
                return { mfaSetup: true, uri: data.totp_setup_uri };
            }

            this.token = data.access_token;
            this.refreshToken = data.refresh_token;
            localStorage.setItem('aegis_token', this.token);
            localStorage.setItem('aegis_refresh_token', this.refreshToken);
            localStorage.setItem('aegis_user', JSON.stringify({
                callsign: data.callsign,
                role: data.role,
                clearance: data.clearance,
                permissions: data.permissions
            }));

            return { success: true, user: data };
        } catch (error) {
            console.error('Login error:', error);
            throw error;
        }
    }

    async logout() {
        try {
            await this.fetch('/api/v1/auth/logout', { method: 'POST' });
        } finally {
            this.token = null;
            this.refreshToken = null;
            localStorage.removeItem('aegis_token');
            localStorage.removeItem('aegis_refresh_token');
            localStorage.removeItem('aegis_user');
            // Close all WebSocket connections
            Object.values(this.wsConnections).forEach(ws => ws.close());
            this.wsConnections = {};
        }
    }

    async getCurrentUser() {
        return await this.fetch('/api/v1/auth/me');
    }

    // Generic fetch with auth
    async fetch(endpoint, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }

        const response = await fetch(`${this.baseURL}${endpoint}`, {
            ...options,
            headers
        });

        if (response.status === 401) {
            // Token expired, try to refresh
            if (this.refreshToken) {
                await this.refreshAccessToken();
                // Retry original request
                headers['Authorization'] = `Bearer ${this.token}`;
                return await fetch(`${this.baseURL}${endpoint}`, { ...options, headers });
            }
        }

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }

        return await response.json();
    }

    async refreshAccessToken() {
        const response = await fetch(`${this.baseURL}/api/v1/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: this.refreshToken })
        });

        if (response.ok) {
            const data = await response.json();
            this.token = data.access_token;
            localStorage.setItem('aegis_token', this.token);
        }
    }

    // Units API
    async getUnits() {
        return await this.fetch('/api/v1/units/');
    }

    async updateUnitPosition(unitId, position) {
        return await this.fetch(`/api/v1/units/${unitId}/position`, {
            method: 'POST',
            body: JSON.stringify(position)
        });
    }

    async getUnitTrack(unitId, hours = 24) {
        return await this.fetch(`/api/v1/units/${unitId}/track?hours=${hours}`);
    }

    // WebSocket for live unit positions
    connectUnitsStream(onUpdate) {
        const wsURL = `${this.baseURL.replace('http', 'ws')}/api/v1/units/stream/live`;
        const ws = new WebSocket(wsURL);

        ws.onopen = () => console.log('Units WebSocket connected');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            onUpdate(data);
        };
        ws.onerror = (error) => console.error('Units WebSocket error:', error);
        ws.onclose = () => console.log('Units WebSocket closed');

        this.wsConnections['units'] = ws;
        return ws;
    }

    // Threats API
    async createThreat(threat) {
        return await this.fetch('/api/v1/threats/', {
            method: 'POST',
            body: JSON.stringify(threat)
        });
    }

    async getThreats(filters = {}) {
        const params = new URLSearchParams(filters).toString();
        return await this.fetch(`/api/v1/threats/?${params}`);
    }

    async getActiveThreats() {
        return await this.fetch('/api/v1/threats/active');
    }

    async resolveThreat(threatId, status, notes = null) {
        return await this.fetch(`/api/v1/threats/${threatId}/resolve`, {
            method: 'PATCH',
            body: JSON.stringify({ status, notes })
        });
    }

    // Drones API
    async getDrones() {
        return await this.fetch('/api/v1/drones/');
    }

    async getDrone(droneId) {
        return await this.fetch(`/api/v1/drones/${droneId}`);
    }

    async sendDroneCommand(droneId, command) {
        return await this.fetch(`/api/v1/drones/${droneId}/command`, {
            method: 'POST',
            body: JSON.stringify(command)
        });
    }

    async createDroneMission(mission) {
        return await this.fetch('/api/v1/drones/mission', {
            method: 'POST',
            body: JSON.stringify(mission)
        });
    }

    // WebSocket for drone telemetry
    connectDroneStream(droneId, onUpdate) {
        const wsURL = `${this.baseURL.replace('http', 'ws')}/api/v1/drones/${droneId}/stream`;
        const ws = new WebSocket(wsURL);

        ws.onopen = () => console.log(`Drone ${droneId} WebSocket connected`);
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            onUpdate(data);
        };
        ws.onerror = (error) => console.error('Drone WebSocket error:', error);
        ws.onclose = () => console.log('Drone WebSocket closed');

        this.wsConnections[`drone_${droneId}`] = ws;
        return ws;
    }

    // Communications API
    async getChannels() {
        return await this.fetch('/api/v1/comms/channels');
    }

    async sendMessage(channelId, plaintext, classification = 'UNCLASSIFIED') {
        return await this.fetch('/api/v1/comms/send', {
            method: 'POST',
            body: JSON.stringify({ channel_id: channelId, plaintext, classification })
        });
    }

    async getMessages(channelId, limit = 50) {
        return await this.fetch(`/api/v1/comms/${channelId}/messages?limit=${limit}`);
    }

    // Analytics API
    async getGPSHistory(unitId, hours = 24) {
        return await this.fetch(`/api/v1/analytics/gps/history?unit_id=${unitId}&hours=${hours}`);
    }

    async getThreatStats() {
        return await this.fetch('/api/v1/analytics/threats/stats');
    }

    async getSystemHealth() {
        return await this.fetch('/api/v1/analytics/system/health');
    }

    async getMissionsSummary() {
        return await this.fetch('/api/v1/analytics/missions/summary');
    }

    // Cyber Security API
    async createCyberEvent(event) {
        return await this.fetch('/api/v1/cyber/event', {
            method: 'POST',
            body: JSON.stringify(event)
        });
    }

    async getCyberEvents(filters = {}) {
        const params = new URLSearchParams(filters).toString();
        return await this.fetch(`/api/v1/cyber/events?${params}`);
    }

    async blockIP(ipAddress, reason, expiresHours = null) {
        return await this.fetch('/api/v1/cyber/block-ip', {
            method: 'POST',
            body: JSON.stringify({ ip_address: ipAddress, reason, expires_hours: expiresHours })
        });
    }

    async getBlockedIPs() {
        return await this.fetch('/api/v1/cyber/blocked-ips');
    }

    async getCyberStats() {
        return await this.fetch('/api/v1/cyber/stats');
    }

    // Sensors API
    async logSensorReading(reading) {
        return await this.fetch('/api/v1/sensors/reading', {
            method: 'POST',
            body: JSON.stringify(reading)
        });
    }

    async logRadarContact(contact) {
        return await this.fetch('/api/v1/sensors/radar/contact', {
            method: 'POST',
            body: JSON.stringify(contact)
        });
    }

    async getSensorHistory(sensorId, hours = 24) {
        return await this.fetch(`/api/v1/sensors/history/${sensorId}?hours=${hours}`);
    }

    // Health check
    async checkHealth() {
        try {
            const response = await fetch(`${this.baseURL}/api/health`);
            return response.ok;
        } catch {
            return false;
        }
    }
}

// Export API instance
const aegisAPI = new AegisAPI();
window.aegisAPI = aegisAPI;

// Authentication UI Handler
class AuthHandler {
    constructor(api) {
        this.api = api;
    }

    showLoginModal() {
        const modal = document.createElement('div');
        modal.id = 'loginModal';
        modal.innerHTML = `
            <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.95); z-index: 10000; display: flex; align-items: center; justify-content: center;">
                <div style="background: #0a0f1a; border: 2px solid #00c8ff; padding: 40px; max-width: 400px; width: 90%;">
                    <h2 style="font-family: Orbitron; color: #00c8ff; margin-bottom: 30px; text-align: center;">AEGIS C4ISR LOGIN</h2>
                    <div id="loginError" style="color: #ff3344; margin-bottom: 15px; display: none;"></div>
                    <input type="text" id="loginCallsign" placeholder="Callsign" style="width: 100%; padding: 12px; margin-bottom: 15px; background: #000; border: 1px solid #1a3a52; color: #e0e6ed; font-family: Rajdhani; font-size: 16px;">
                    <input type="password" id="loginPassword" placeholder="Password" style="width: 100%; padding: 12px; margin-bottom: 15px; background: #000; border: 1px solid #1a3a52; color: #e0e6ed; font-family: Rajdhani; font-size: 16px;">
                    <input type="text" id="loginTotp" placeholder="TOTP Code (if enabled)" style="width: 100%; padding: 12px; margin-bottom: 20px; background: #000; border: 1px solid #1a3a52; color: #e0e6ed; font-family: Rajdhani; font-size: 16px;">
                    <button id="loginBtn" style="width: 100%; padding: 12px; background: #00c8ff; color: #020509; border: none; font-family: Orbitron; font-weight: 700; font-size: 14px; cursor: pointer;">LOGIN</button>
                    <div style="margin-top: 15px; text-align: center; color: #8a9aa8; font-size: 12px;">
                        Default: CDR.ADMIN / AEGIS@Command2026!
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        document.getElementById('loginBtn').onclick = () => this.handleLogin();
        document.getElementById('loginPassword').onkeypress = (e) => {
            if (e.key === 'Enter') this.handleLogin();
        };
        document.getElementById('loginTotp').onkeypress = (e) => {
            if (e.key === 'Enter') this.handleLogin();
        };
    }

    async handleLogin() {
        const callsign = document.getElementById('loginCallsign').value;
        const password = document.getElementById('loginPassword').value;
        const totp = document.getElementById('loginTotp').value || null;
        const errorDiv = document.getElementById('loginError');

        try {
            errorDiv.style.display = 'none';
            const result = await this.api.login(callsign, password, totp);

            if (result.mfaSetup) {
                alert(`MFA Setup Required!\n\nScan this QR code with your authenticator app:\n${result.uri}\n\nThen login again with your TOTP code.`);
                return;
            }

            if (result.success) {
                document.getElementById('loginModal').remove();
                location.reload(); // Reload to initialize with auth
            }
        } catch (error) {
            errorDiv.textContent = error.message;
            errorDiv.style.display = 'block';
        }
    }

    hideLoginModal() {
        const modal = document.getElementById('loginModal');
        if (modal) modal.remove();
    }

    checkAuth() {
        if (!this.api.token) {
            this.showLoginModal();
            return false;
        }
        return true;
    }
}

const authHandler = new AuthHandler(aegisAPI);
window.authHandler = authHandler;

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    // Check if backend is available
    const isHealthy = await aegisAPI.checkHealth();

    if (isHealthy) {
        console.log('✅ Backend API is available');

        // Check authentication
        if (!aegisAPI.token) {
            console.log('⚠️ Not authenticated - showing login');
            authHandler.showLoginModal();
        } else {
            console.log('✅ Authenticated');
            // Initialize real-time connections
            initializeRealTimeUpdates();
        }
    } else {
        console.log('⚠️ Backend API not available - running in demo mode');
        showDemoModeWarning();
    }
});

function showDemoModeWarning() {
    const banner = document.createElement('div');
    banner.innerHTML = `
        <div style="position: fixed; top: 48px; left: 0; right: 0; background: rgba(255,170,0,0.9); color: #000; padding: 10px; text-align: center; z-index: 9999; font-family: Rajdhani; font-weight: 700;">
            ⚠️ DEMO MODE - Backend API not connected. Start Docker to enable full functionality.
        </div>
    `;
    document.body.appendChild(banner);
}

function initializeRealTimeUpdates() {
    // Connect to live unit positions
    aegisAPI.connectUnitsStream((data) => {
        if (data.type === 'update') {
            updateMapUnit(data.data);
        }
    });

    // Update system stats periodically
    setInterval(async () => {
        try {
            const health = await aegisAPI.getSystemHealth();
            updateSystemHealth(health);
        } catch (error) {
            console.error('Error updating system health:', error);
        }
    }, 5000);

    // Load initial data
    loadInitialData();
}

async function loadInitialData() {
    try {
        // Load units
        const units = await aegisAPI.getUnits();
        console.log('Loaded units:', units);

        // Load threats
        const threats = await aegisAPI.getThreats({ limit: 100 });
        console.log('Loaded threats:', threats);

        // Load drones
        const drones = await aegisAPI.getDrones();
        console.log('Loaded drones:', drones);

        // Update UI with real data
        updateUIWithRealData(units, threats, drones);
    } catch (error) {
        console.error('Error loading initial data:', error);
    }
}

function updateMapUnit(unitData) {
    // Update unit position on map
    console.log('Unit position update:', unitData);
    // This would update the SVG map with new coordinates
}

function updateSystemHealth(health) {
    // Update system health display
    if (document.getElementById('cpuValue')) {
        document.getElementById('cpuValue').textContent = health.cpu_percent.toFixed(1) + '%';
        document.getElementById('cpuBar').style.width = health.cpu_percent + '%';
    }
    if (document.getElementById('memValue')) {
        document.getElementById('memValue').textContent = health.memory_percent.toFixed(1) + '%';
        document.getElementById('memBar').style.width = health.memory_percent + '%';
    }
}

function updateUIWithRealData(units, threats, drones) {
    // Update counters
    document.getElementById('unitCount').textContent = units.length;
    document.getElementById('droneCount').textContent = drones.length;
    document.getElementById('threatCount').textContent = threats.filter(t => t.status === 'ACTIVE').length;
}

console.log('AEGIS API Integration loaded ✅');
