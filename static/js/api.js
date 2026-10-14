/**
 * Centralized API client for RailMitra.
 * Uses sessionStorage for per-tab session isolation (supporting multi-passenger demos).
 */

class RailMitraAPI {
  constructor() {
    this.baseUrl = window.location.origin;
  }

  // Token & Session Management
  getSessionToken() {
    return sessionStorage.getItem('rm_session_token');
  }

  setSessionToken(token) {
    sessionStorage.setItem('rm_session_token', token);
  }

  clearSession() {
    sessionStorage.removeItem('rm_session_token');
    sessionStorage.removeItem('rm_passenger_cache');
  }

  getTTEKey() {
    return sessionStorage.getItem('rm_tte_key') || 'tte-demo-key';
  }

  setTTEKey(key) {
    sessionStorage.setItem('rm_tte_key', key);
  }

  // Internal Request Helper
  async request(endpoint, options = {}) {
    const headers = options.headers || {};
    
    // Auto-attach session token if present
    const sessionToken = this.getSessionToken();
    if (sessionToken && !headers['X-Session-Token']) {
      headers['X-Session-Token'] = sessionToken;
    }

    // Auto-attach TTE Key if in TTE context
    if (options.isTTE && !headers['X-TTE-Key']) {
      headers['X-TTE-Key'] = this.getTTEKey();
    }

    if (!headers['Content-Type'] && !(options.body instanceof FormData) && options.method && options.method !== 'GET') {
      headers['Content-Type'] = 'application/json';
    }

    const config = {
      ...options,
      headers
    };

    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, config);
      let data;
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        data = await response.json();
      } else {
        data = await response.text();
      }

      if (!response.ok) {
        const error = new Error(data && data.detail ? data.detail : `HTTP ${response.status}`);
        error.status = response.status;
        error.code = data && data.code ? data.code : 'UNKNOWN_ERROR';
        error.data = data;
        throw error;
      }

      return data;
    } catch (err) {
      console.error(`API Error on [${options.method || 'GET'} ${endpoint}]:`, err);
      throw err;
    }
  }

  // ==========================================
  // Auth & Identity APIs
  // ==========================================
  async validateJourney(pnr, trainNumber, date) {
    return this.request('/api/journey/validate', {
      method: 'POST',
      body: JSON.stringify({ pnr, train_number: trainNumber, date })
    });
  }

  async sendOTP(pnr) {
    return this.request('/api/otp/send', {
      method: 'POST',
      body: JSON.stringify({ pnr })
    });
  }

  async verifyOTP(pnr, code) {
    const res = await this.request('/api/otp/verify', {
      method: 'POST',
      body: JSON.stringify({ pnr, code })
    });
    if (res.session_token) {
      this.setSessionToken(res.session_token);
      sessionStorage.setItem('rm_passenger_cache', JSON.stringify(res.passenger));
    }
    return res;
  }

  async getMe() {
    return this.request('/api/me', { method: 'GET' });
  }

  async logout() {
    try {
      await this.request('/api/logout', { method: 'POST' });
    } finally {
      this.clearSession();
    }
  }

  // ==========================================
  // Matching Engine
  // ==========================================
  async getMatches(need = 'sit_together') {
    return this.request(`/api/match?need=${encodeURIComponent(need)}`, { method: 'GET' });
  }

  // ==========================================
  // Seat Exchange Requests
  // ==========================================
  async createRequest(targetId, need = 'sit_together') {
    return this.request('/api/requests', {
      method: 'POST',
      body: JSON.stringify({ target_id: targetId, need })
    });
  }

  async getMyRequests() {
    return this.request('/api/requests/mine', { method: 'GET' });
  }

  async getIncomingRequests() {
    return this.request('/api/requests/incoming', { method: 'GET' });
  }

  async getRemainingQuota() {
    return this.request('/api/requests/remaining', { method: 'GET' });
  }

  async respondToRequest(requestId, decision) {
    return this.request(`/api/requests/${requestId}/respond`, {
      method: 'POST',
      body: JSON.stringify({ decision })
    });
  }

  async cancelRequest(requestId) {
    return this.request(`/api/requests/${requestId}/cancel`, {
      method: 'POST'
    });
  }

  async getDigitalSlip(requestId) {
    return this.request(`/api/requests/${requestId}/slip`, { method: 'GET' });
  }

  async verifySlipToken(token) {
    return this.request(`/api/verify/${token}`, { method: 'GET' });
  }

  // ==========================================
  // Group Requests
  // ==========================================
  async createGroupRequest(desiredSeating) {
    return this.request('/api/group-requests', {
      method: 'POST',
      body: JSON.stringify({ desired_seating: desiredSeating })
    });
  }

  async getGroupRequest(groupRequestId) {
    return this.request(`/api/group-requests/${groupRequestId}`, { method: 'GET' });
  }

  // ==========================================
  // Notifications
  // ==========================================
  async getNotifications() {
    return this.request('/api/notifications', { method: 'GET' });
  }

  async markNotificationRead(notificationId) {
    return this.request(`/api/notifications/${notificationId}/read`, { method: 'POST' });
  }

  async markAllNotificationsRead() {
    return this.request('/api/notifications/read-all', { method: 'POST' });
  }

  // ==========================================
  // TTE APIs (requires X-TTE-Key)
  // ==========================================
  async getTTERequests() {
    return this.request('/api/tte/requests', {
      method: 'GET',
      isTTE: true
    });
  }

  async reviewTTERequest(requestId, decision, note = '') {
    return this.request(`/api/tte/requests/${requestId}/review`, {
      method: 'POST',
      isTTE: true,
      body: JSON.stringify({ decision, note })
    });
  }

  async getTTEAudit(requestId = null) {
    const query = requestId ? `?request_id=${requestId}` : '';
    return this.request(`/api/tte/audit${query}`, {
      method: 'GET',
      isTTE: true
    });
  }

  async getTTETrainSummary(trainId = 'T-101') {
    return this.request(`/api/tte/train/${trainId}/summary`, {
      method: 'GET',
      isTTE: true
    });
  }

  async getTrainSeating(trainNumber = '12951') {
    return this.request(`/api/train/${trainNumber}/seating`, { method: 'GET' });
  }

  // ==========================================
  // Simulation & Demo
  // ==========================================
  async advanceTrain(trainId = 'T-101', toStation = null) {
    return this.request('/api/demo/advance_train', {
      method: 'POST',
      body: JSON.stringify({ train_id: trainId, to_station: toStation })
    });
  }

  async resetDemo() {
    return this.request('/api/demo/reset', { method: 'POST' });
  }
}

window.api = new RailMitraAPI();
