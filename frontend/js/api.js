/**
 * AuditPro — API Helper
 * Centralised fetch wrapper for all Flask backend calls.
 * Handles JWT attachment, error parsing, and token expiry.
 */

const API_BASE = 'https://seo-audit-backend-hgjz.onrender.com';

/**
 * Core fetch wrapper — attaches JWT, handles errors uniformly.
 */
async function apiFetch(path, options = {}) {
  const token = localStorage.getItem('auth_token');

  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  const config = {
    ...options,
    headers,
  };

  try {
    const res = await fetch(`${API_BASE}${path}`, config);

    // Token expired — clear and redirect to login
    if (res.status === 401) {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user_data');
      window.location.href = '/index.html';
      return;
    }

    const data = await res.json();

    if (!res.ok) {
      const err = new ApiError(
        data?.error?.message || (typeof data?.error === 'string' ? data.error : null) || data?.message || 'Request failed',
        res.status,
        data?.code || data?.error?.code || 'UNKNOWN_ERROR'
      );
      err.next_available_at = data?.next_available_at || null;
      throw err;
    }

    return data;

  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Network error — check your connection', 0, 'NETWORK_ERROR');
  }
}

class ApiError extends Error {
  constructor(message, status, code) {
    super(message);
    this.status = status;
    this.code   = code;
  }
}

/* ══════════════════════════════════════════════════════════════
   AUTH
   ══════════════════════════════════════════════════════════════ */

const AuthAPI = {
  /** Get Google OAuth URL */
  getGoogleAuthUrl() {
    return apiFetch('/api/auth/google');
  },

  /** Get current user from JWT */
  getUser() {
    return apiFetch('/api/auth/user');
  },

  /** Logout — clears server session */
  logout() {
    return apiFetch('/api/auth/logout', { method: 'POST' });
  },

  /** Health check */
  health() {
    return apiFetch('/api/health');
  },
};

/* ══════════════════════════════════════════════════════════════
   AUDIT
   ══════════════════════════════════════════════════════════════ */

const AuditAPI = {
  /**
   * Start a new audit.
   * @param {string} url - Target URL
   * @param {string} targetKeyword - Primary keyword
   * @param {object} options - { secondaryKeyword, brandName, runCloakingCheck }
   */
  start(url, targetKeyword, options = {}) {
    return apiFetch('/api/audit/start', {
      method: 'POST',
      body: JSON.stringify({
        url,
        target_keyword: targetKeyword,
        secondary_keyword: options.secondaryKeyword || null,
        brand_name: options.brandName || null,
        run_cloaking_check: options.runCloakingCheck || false,
      }),
    });
  },

  /**
   * Poll audit status.
   * @param {number} auditId
   */
  getStatus(auditId) {
    return apiFetch(`/api/audit/status/${auditId}`);
  },

  /**
   * Get full audit results.
   * @param {number} auditId
   */
  getResults(auditId) {
    return apiFetch(`/api/audit/results/${auditId}`);
  },

  /**
   * Get paginated audit history.
   * @param {number} page
   * @param {number} perPage
   */
  getHistory(page = 1, perPage = 20) {
    return apiFetch(`/api/audit/history?page=${page}&per_page=${perPage}`);
  },

  /**
   * Delete an audit.
   * @param {number} auditId
   */
  delete(auditId) {
    return apiFetch(`/api/audit/${auditId}`, { method: 'DELETE' });
  },
  /** Check if user can run an audit today */
  checkLimit() {
    return apiFetch('/api/audit/limit');
  },
};

/* ══════════════════════════════════════════════════════════════
   HELPERS
   ══════════════════════════════════════════════════════════════ */

/**
 * Poll audit status until completed or failed.
 * Calls onProgress(statusData) on each poll.
 * Resolves with final status data.
 */
async function pollAuditStatus(auditId, onProgress, intervalMs = 3000, maxAttempts = 60) {
  let attempts = 0;

  return new Promise((resolve, reject) => {
    const timer = setInterval(async () => {
      attempts++;
      try {
        const data = await AuditAPI.getStatus(auditId);

        if (onProgress) onProgress(data);

        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(timer);
          resolve(data);
        }

        if (attempts >= maxAttempts) {
          clearInterval(timer);
          reject(new Error('Audit timed out — please try again'));
        }

      } catch (err) {
        clearInterval(timer);
        reject(err);
      }
    }, intervalMs);
  });
}

/**
 * Score to CSS class helper.
 */
function scoreClass(score) {
  if (score >= 70) return 'score-good';
  if (score >= 40) return 'score-medium';
  return 'score-bad';
}

/**
 * Score bar fill class helper.
 */
function fillClass(score) {
  if (score >= 70) return 'fill-good';
  if (score >= 40) return 'fill-medium';
  return 'fill-bad';
}

/**
 * Risk score to badge class.
 */
function riskClass(riskLevel) {
  const map = { low: 'risk-low', moderate: 'risk-moderate', high: 'risk-high', critical: 'risk-critical' };
  return map[riskLevel] || 'risk-moderate';
}

/**
 * Risk level to display label.
 */
function riskLabel(riskLevel) {
  const map = { low: 'LOW', moderate: 'MOD', high: 'HIGH', critical: 'CRIT' };
  return map[riskLevel] || riskLevel?.toUpperCase();
}

/**
 * Format date string to readable format.
 */
function formatDate(isoString) {
  if (!isoString) return '—';
  const d = new Date(isoString);
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

/**
 * Format relative time (e.g. "2 hours ago").
 */
function timeAgo(isoString) {
  if (!isoString) return '';
  const diff = Date.now() - new Date(isoString).getTime();
  const mins  = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days  = Math.floor(diff / 86400000);
  if (mins < 1)   return 'just now';
  if (mins < 60)  return `${mins}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7)   return `${days}d ago`;
  return formatDate(isoString);
}

/**
 * Truncate URL for display.
 */
function displayUrl(url) {
  return url.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '');
}

/**
 * Show a toast notification.
 */
function showToast(message, type = 'info', duration = 3500) {
  const existing = document.getElementById('ap-toast');
  if (existing) existing.remove();

  const colors = {
    success: 'background:#dafbe1;color:#1a7f37;border-color:rgba(26,127,55,.3)',
    error:   'background:#fff0ee;color:#cf222e;border-color:rgba(207,34,46,.3)',
    info:    'background:#fff;color:#1f2328;border-color:#e1e4e8',
    warning: 'background:#fff8e6;color:#9a6700;border-color:rgba(154,103,0,.3)',
  };

  const toast = document.createElement('div');
  toast.id = 'ap-toast';
  toast.style.cssText = `
    position:fixed;bottom:20px;right:20px;z-index:9999;
    padding:10px 16px;border-radius:8px;font-size:13px;
    border:0.5px solid;font-family:-apple-system,sans-serif;
    box-shadow:0 4px 12px rgba(0,0,0,.08);
    transition:opacity .3s;
    ${colors[type] || colors.info}
  `;
  toast.textContent = message;
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}
