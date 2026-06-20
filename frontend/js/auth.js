/**
 * AuditPro — Auth Helper
 * Google OAuth flow, JWT storage, session checks.
 * Import this on every page that needs auth.
 */

const Auth = {
  TOKEN_KEY: 'auth_token',
  USER_KEY:  'user_data',

  /** Get stored JWT token */
  getToken() {
    return localStorage.getItem(this.TOKEN_KEY);
  },

  /** Get stored user object */
  getUser() {
    const raw = localStorage.getItem(this.USER_KEY);
    try { return raw ? JSON.parse(raw) : null; } catch { return null; }
  },

  /** Check if user is logged in */
  isLoggedIn() {
    return !!this.getToken();
  },

  /** Store token and user after login */
  setSession(token, user) {
    localStorage.setItem(this.TOKEN_KEY, token);
    if (user) localStorage.setItem(this.USER_KEY, JSON.stringify(user));
  },

  /** Clear session */
  clearSession() {
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.USER_KEY);
  },

  /**
   * Require auth — redirect to index if not logged in.
   * Call at top of every protected page.
   */
  requireAuth() {
    if (!this.isLoggedIn()) {
      window.location.href = './index.html';
      return false;
    }
    return true;
  },

  /**
   * Redirect logged-in users away from the landing page.
   * Call on index.html.
   */
  redirectIfLoggedIn() {
    if (this.isLoggedIn()) {
      window.location.href = './dashboard.html';
    }
  },

  /**
   * Handle the OAuth callback — extract token from URL.
   * Call on any page that receives the ?token= redirect.
   */
  handleCallback() {
    const params = new URLSearchParams(window.location.search);
    const token  = params.get('token');

    if (token) {
      localStorage.setItem(this.TOKEN_KEY, token);
      // Clean URL without reload
      window.history.replaceState({}, document.title, window.location.pathname);
      return token;
    }
    return null;
  },

  /**
   * Initiate Google OAuth — fetches URL from backend and redirects.
   */
  async loginWithGoogle() {
    try {
      const data = await AuthAPI.getGoogleAuthUrl();
      if (data?.data?.auth_url) {
        window.location.href = data.data.auth_url;
      } else {
        showToast('Failed to get login URL. Please try again.', 'error');
      }
    } catch (err) {
      showToast(err.message || 'Login failed. Please try again.', 'error');
    }
  },

  /**
   * Logout — clears session and redirects to landing page.
   */
  async logout() {
    try {
      await AuthAPI.logout();
    } catch { /* ignore */ }
    this.clearSession();
    window.location.href = './index.html';
  },

  /**
   * Fetch and store fresh user data from server.
   * Returns user object or null.
   */
  async refreshUser() {
    try {
      const data = await AuthAPI.getUser();
      if (data?.data) {
        localStorage.setItem(this.USER_KEY, JSON.stringify(data.data));
        return data.data;
      }
    } catch (err) {
      if (err.status === 401) this.clearSession();
    }
    return null;
  },

  /**
   * Populate sidebar user info (avatar initials, name, GSC badge).
   * Call after DOM ready on any page with the sidebar.
   */
  populateSidebarUser() {
    const user = this.getUser();
    if (!user) return;

    const nameEl   = document.getElementById('sidebar-user-name');
    const avatarEl = document.getElementById('sidebar-avatar');
    const badgeEl  = document.getElementById('sidebar-gsc-badge');

    if (nameEl)   nameEl.textContent = user.name?.split(' ')[0] || user.email?.split('@')[0] || 'User';
    if (avatarEl) {
      if (user.profile_picture) {
        avatarEl.innerHTML = `<img src="${user.profile_picture}" alt="avatar" style="width:100%;height:100%;object-fit:cover;border-radius:50%;">`;
      } else {
        const initials = (user.name || 'U').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
        avatarEl.textContent = initials;
      }
    }
    if (badgeEl)  badgeEl.style.display = user.gsc_connected ? 'inline' : 'none';
  },
};

/**
 * On page load — check for token in URL (OAuth callback),
 * then check if this page requires auth.
 *
 * Usage in HTML:
 *   <script>Auth.handleCallback(); Auth.requireAuth();</script>
 */
document.addEventListener('DOMContentLoaded', () => {
  // Handle OAuth redirect on dashboard
  const token = Auth.handleCallback();
  if (token) {
    Auth.refreshUser().then(() => {
      Auth.populateSidebarUser();
    });
  }
});
