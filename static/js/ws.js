/**
 * Real-time WebSocket Client with Auto-reconnect and Polling Fallback.
 */

class RailMitraWS {
  constructor() {
    this.socket = null;
    this.listeners = new Map();
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.pingInterval = null;
    this.pollingInterval = null;
    this.isTTE = false;
  }

  init(isTTE = false) {
    this.isTTE = isTTE;
    this.connect();
    // Start fallback poller
    this.startFallbackPolling();
  }

  connect() {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    let url = `${protocol}//${window.location.host}/ws`;

    if (this.isTTE) {
      const tteKey = window.api.getTTEKey();
      url += `?role=tte&tte_key=${encodeURIComponent(tteKey)}`;
    } else {
      const token = window.api.getSessionToken();
      if (!token) return; // Not logged in yet
      url += `?token=${encodeURIComponent(token)}`;
    }

    try {
      this.socket = new WebSocket(url);

      this.socket.onopen = () => {
        console.log('[WS] Connected successfully.');
        this.reconnectAttempts = 0;
        this.startHeartbeat();
        this.emit('connection_status', { connected: true });
      };

      this.socket.onmessage = (event) => {
        try {
          if (event.data === 'pong') return;
          const payload = JSON.parse(event.data);
          if (payload.type) {
            this.emit(payload.type, payload.data || payload);
          }
        } catch (e) {
          console.warn('[WS] Non-JSON message received:', event.data);
        }
      };

      this.socket.onclose = () => {
        this.cleanup();
        this.emit('connection_status', { connected: false });
        this.scheduleReconnect();
      };

      this.socket.onerror = (err) => {
        console.warn('[WS] Socket error:', err);
      };
    } catch (e) {
      console.warn('[WS] Failed to create WebSocket connection:', e);
      this.scheduleReconnect();
    }
  }

  startHeartbeat() {
    clearInterval(this.pingInterval);
    this.pingInterval = setInterval(() => {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.socket.send('ping');
      }
    }, 20000);
  }

  cleanup() {
    clearInterval(this.pingInterval);
    this.socket = null;
  }

  scheduleReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      const timeout = Math.min(1000 * Math.pow(1.5, this.reconnectAttempts), 15000);
      this.reconnectAttempts++;
      setTimeout(() => this.connect(), timeout);
    }
  }

  startFallbackPolling() {
    clearInterval(this.pollingInterval);
    // Poll every 12 seconds in case socket is disconnected
    this.pollingInterval = setInterval(() => {
      if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
        this.emit('poll_sync', {});
      }
    }, 12000);
  }

  on(eventType, callback) {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set());
    }
    this.listeners.get(eventType).add(callback);
    return () => this.off(eventType, callback);
  }

  off(eventType, callback) {
    const list = this.listeners.get(eventType);
    if (list) {
      list.delete(callback);
    }
  }

  emit(eventType, data) {
    const list = this.listeners.get(eventType);
    if (list) {
      list.forEach((cb) => {
        try {
          cb(data);
        } catch (err) {
          console.error(`Error in WS event listener for [${eventType}]:`, err);
        }
      });
    }
    // Also trigger wildcard
    const allList = this.listeners.get('*');
    if (allList) {
      allList.forEach((cb) => cb(eventType, data));
    }
  }
}

window.rmWS = new RailMitraWS();
