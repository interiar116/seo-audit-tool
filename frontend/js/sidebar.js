/**
 * AuditPro — Sidebar Component
 * Handles active nav state, user info population, logout.
 * Import on every page that uses the app shell layout.
 */

const Sidebar = {
  /** Mark the correct nav item as active based on current page */
  setActiveNav() {
    const page = window.location.pathname.split('/').pop() || 'index.html';
    const navMap = {
      'dashboard.html':     'nav-dashboard',
      'audit.html':         'nav-new-audit',
      'audit-loading.html': 'nav-new-audit',
      'results.html':       'nav-dashboard',
      'settings.html':      'nav-settings',
    };
    const activeId = navMap[page];
    if (activeId) {
      const el = document.getElementById(activeId);
      if (el) el.classList.add('active');
    }
  },

  /** Populate user name and avatar */
  populateUser() {
    const user = Auth.getUser();
    if (!user) return;

    const nameEl   = document.getElementById('sidebar-user-name');
    const avatarEl = document.getElementById('sidebar-avatar');
    const badgeEl  = document.getElementById('sidebar-gsc-badge');

    if (nameEl) {
      nameEl.textContent = user.name?.split(' ')[0] || user.email?.split('@')[0] || 'User';
    }

    if (avatarEl) {
      if (user.profile_picture) {
        avatarEl.innerHTML = `<img src="${user.profile_picture}" alt="avatar" style="width:100%;height:100%;object-fit:cover;border-radius:50%;">`;
      } else {
        const initials = (user.name || 'U').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
        avatarEl.textContent = initials;
      }
    }

    if (badgeEl) {
      badgeEl.style.display = user.gsc_connected ? 'inline' : 'none';
    }
  },

  /** Bind logout button */
  bindLogout() {
    const btn = document.getElementById('sidebar-logout-btn');
    if (btn) {
      btn.addEventListener('click', () => Auth.logout());
    }
  },

  /** Init — call once after DOM ready */
  init() {
    this.setActiveNav();
    this.populateUser();
    this.bindLogout();
  },
};

document.addEventListener('DOMContentLoaded', () => Sidebar.init());
