/**
 * AuditSentinel — Admin Panel
 * Platform-wide stats, user management, audit browser, algorithm updates.
 * Access restricted to ADMIN_EMAIL.
 */

const ADMIN_EMAIL = 'innovativeideas116@gmail.com';

const Admin = {
  currentTab: 'users',
  allUsers: [],
  auditPage: 1,
  auditStatus: '',
  auditSearch: '',

  async init() {
    Auth.requireAuth();

    const user = Auth.getUser();
    if (!user || user.email !== ADMIN_EMAIL) {
      window.location.href = './dashboard.html';
      return;
    }

    this.bindTabs();
    this.bindControls();

    await this.loadStats();
    await this.loadUsers();
  },

  // ── Tabs ──────────────────────────────────────────────────────────────────

  bindTabs() {
    const tabs = [
      { id: 'tab-users',   panel: 'panel-users',   name: 'users' },
      { id: 'tab-audits',  panel: 'panel-audits',  name: 'audits' },
      { id: 'tab-updates', panel: 'panel-updates',  name: 'updates' },
    ];

    tabs.forEach(tab => {
      document.getElementById(tab.id)?.addEventListener('click', () => {
        this.currentTab = tab.name;
        tabs.forEach(t => {
          document.getElementById(t.id)?.classList.toggle('active', t.name === tab.name);
          const panel = document.getElementById(t.panel);
          if (panel) panel.style.display = t.name === tab.name ? '' : 'none';
        });
        this.loadTab(tab.name);
      });
    });
  },

  async loadTab(name) {
    if (name === 'users')   await this.loadUsers();
    if (name === 'audits')  await this.loadAudits(1, '', '');
    if (name === 'updates') await this.loadUpdates();
  },

  // ── Controls ──────────────────────────────────────────────────────────────

  bindControls() {
    document.getElementById('refresh-stats-btn')?.addEventListener('click', () => this.loadStats());

    document.getElementById('user-search')?.addEventListener('input', e => {
      this.filterUsers(e.target.value);
    });

    document.getElementById('audit-search-btn')?.addEventListener('click', () => {
      this.auditSearch = document.getElementById('audit-search')?.value || '';
      this.auditStatus = document.getElementById('audit-status-filter')?.value || '';
      this.loadAudits(1, this.auditStatus, this.auditSearch);
    });

    document.getElementById('audit-search')?.addEventListener('keydown', e => {
      if (e.key === 'Enter') document.getElementById('audit-search-btn')?.click();
    });

    document.getElementById('add-update-toggle')?.addEventListener('click', () => {
      const panel = document.getElementById('update-form-panel');
      if (panel) panel.style.display = panel.style.display === 'none' ? '' : 'none';
    });

    document.getElementById('add-update-cancel')?.addEventListener('click', () => {
      document.getElementById('update-form-panel').style.display = 'none';
      document.getElementById('update-form')?.reset();
    });

    document.getElementById('update-form')?.addEventListener('submit', e => this.handleAddUpdate(e));
  },

  // ── Stats ─────────────────────────────────────────────────────────────────

  async loadStats() {
    try {
      const data = await AdminAPI.getStats();
      document.getElementById('stat-users').textContent   = data.users ?? '—';
      document.getElementById('stat-audits').textContent  = data.audits ?? '—';
      document.getElementById('stat-avg').textContent     = data.avg_score ?? '—';
      document.getElementById('stat-gsc').textContent     = data.gsc_connected ?? '—';
      const runEl = document.getElementById('stat-running');
      runEl.textContent = data.running ?? '0';
      if (data.running > 0) runEl.style.color = 'var(--accent)';
    } catch (err) {
      console.warn('Stats failed:', err.message);
    }
  },

  // ── Users ─────────────────────────────────────────────────────────────────

  async loadUsers() {
    this._showLoading();
    try {
      const data = await AdminAPI.getUsers();
      this.allUsers = data.users || [];
      this._showPanel('panel-users');
      this.renderUsers(this.allUsers);
    } catch (err) {
      this._showPanel('panel-users');
      showToast('Failed to load users', 'error');
    }
  },

  renderUsers(users) {
    const tbody = document.getElementById('users-tbody');
    if (!users.length) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:28px;">No users found</td></tr>';
      return;
    }

    tbody.innerHTML = users.map(u => {
      const initials = (u.name || u.email || 'U').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
      const gscHtml = u.gsc_connected
        ? '<span class="gsc-badge" style="display:inline-block;">GSC</span>'
        : '<span style="color:var(--text-muted);font-size:11px;">—</span>';
      return `
        <tr>
          <td>
            <div style="display:flex;align-items:center;gap:9px;">
              <div class="user-avatar-sm">${initials}</div>
              <div>
                <div style="font-size:12.5px;font-weight:500;color:var(--text-primary);">${u.name || '—'}</div>
                <div style="font-size:11px;color:var(--text-muted);">${u.email}</div>
              </div>
            </div>
          </td>
          <td style="font-size:12px;">${formatDate(u.created_at)}</td>
          <td style="font-size:12px;">${u.last_login ? timeAgo(u.last_login) : '<span style="color:var(--text-muted);">—</span>'}</td>
          <td>${gscHtml}</td>
          <td style="font-size:12px;font-weight:500;">${u.audit_count}</td>
          <td style="text-align:right;">
            <button class="btn btn-secondary btn-sm view-user-audits-btn"
              data-user-id="${u.id}">View Audits</button>
          </td>
        </tr>
        <tr class="user-audits-row" id="user-audits-row-${u.id}" style="display:none;">
          <td colspan="6">
            <div class="user-audits-inner" id="user-audits-inner-${u.id}"></div>
          </td>
        </tr>`;
    }).join('');

    tbody.querySelectorAll('.view-user-audits-btn').forEach(btn => {
      btn.addEventListener('click', () =>
        this.toggleUserAudits(parseInt(btn.dataset.userId), btn)
      );
    });
  },

  async toggleUserAudits(userId, btn) {
    const row = document.getElementById(`user-audits-row-${userId}`);
    const inner = document.getElementById(`user-audits-inner-${userId}`);
    if (!row) return;

    if (row.style.display !== 'none') {
      row.style.display = 'none';
      btn.textContent = 'View Audits';
      return;
    }

    row.style.display = '';
    btn.textContent = 'Hide Audits';
    inner.innerHTML = '<div style="display:flex;gap:7px;align-items:center;color:var(--text-muted);font-size:12px;"><div class="spinner spinner-sm"></div>Loading…</div>';

    try {
      const data = await AdminAPI.getUserAudits(userId);
      const audits = data.audits || [];
      if (!audits.length) {
        inner.innerHTML = '<p style="font-size:12px;color:var(--text-muted);margin:0;">No audits yet.</p>';
        return;
      }
      inner.innerHTML = `
        <div style="font-size:10.5px;font-weight:500;color:var(--text-muted);text-transform:uppercase;letter-spacing:.04em;margin-bottom:10px;">Last ${audits.length} audits</div>
        <div class="table-wrap">
          <table class="data-table" style="min-width:500px;">
            <thead><tr>
              <th style="width:36%">URL</th>
              <th>Overall</th><th>Tech</th><th>Content</th><th>Blackhat</th>
              <th>Date</th>
              <th style="text-align:right">View</th>
            </tr></thead>
            <tbody>
              ${audits.map(a => `<tr>
                <td style="font-size:11.5px;">${displayUrl(a.url)}</td>
                <td>${a.overall_score != null ? `<span class="score-pill ${scoreClass(a.overall_score)}">${a.overall_score}</span>` : '—'}</td>
                <td style="font-size:12px;">${a.technical_score ?? '—'}</td>
                <td style="font-size:12px;">${a.content_score ?? '—'}</td>
                <td style="font-size:12px;">${a.blackhat_risk_score ?? '—'}</td>
                <td style="font-size:11px;color:var(--text-muted);">${timeAgo(a.created_at)}</td>
                <td style="text-align:right;">
                  <a href="./results.html?id=${a.audit_id}" style="font-size:11px;color:var(--accent);text-decoration:none;">View →</a>
                </td>
              </tr>`).join('')}
            </tbody>
          </table>
        </div>`;
    } catch (err) {
      inner.innerHTML = '<p style="font-size:12px;color:var(--critical);margin:0;">Failed to load audits.</p>';
    }
  },

  filterUsers(search) {
    const q = search.toLowerCase().trim();
    const filtered = q
      ? this.allUsers.filter(u =>
          (u.name || '').toLowerCase().includes(q) ||
          (u.email || '').toLowerCase().includes(q)
        )
      : this.allUsers;
    this.renderUsers(filtered);
  },

  // ── All Audits ────────────────────────────────────────────────────────────

  async loadAudits(page = 1, status = '', search = '') {
    this.auditPage = page;
    this.auditStatus = status;
    this.auditSearch = search;
    this._showLoading();

    try {
      const data = await AdminAPI.getAudits(page, 25, status, search);
      this._showPanel('panel-audits');
      this.renderAudits(data.audits || [], data.total || 0, data.per_page || 25);
    } catch (err) {
      this._showPanel('panel-audits');
      showToast('Failed to load audits', 'error');
    }
  },

  renderAudits(audits, total, perPage) {
    const tbody = document.getElementById('audits-tbody');

    if (!audits.length) {
      tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:var(--text-muted);padding:28px;">No audits found</td></tr>';
    } else {
      tbody.innerHTML = audits.map(a => {
        const statusDot = a.status === 'completed' ? 'dot-green'
                        : a.status === 'failed'    ? 'dot-red'
                        :                            'dot-orange';
        const rl = this.getRiskLevel(a.blackhat_risk_score);
        return `<tr>
          <td>
            <div style="font-size:12px;font-weight:500;color:var(--text-primary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:200px;"
              title="${a.url}">${displayUrl(a.url)}</div>
            ${a.is_competitive ? '<span style="font-size:9px;padding:1px 5px;border-radius:3px;background:rgba(240,136,62,.1);color:var(--accent);">COMP</span>' : ''}
          </td>
          <td style="font-size:11px;color:var(--text-muted);max-width:140px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${a.user_email}">${a.user_email}</td>
          <td>${a.overall_score != null ? `<span class="score-pill ${scoreClass(a.overall_score)}">${a.overall_score}</span>` : '<span style="color:var(--text-muted)">—</span>'}</td>
          <td style="font-size:12px;">${a.technical_score ?? '—'}</td>
          <td style="font-size:12px;">${a.content_score ?? '—'}</td>
          <td><span class="risk-badge ${riskClass(rl)}">${riskLabel(rl)}</span></td>
          <td>
            <span style="display:flex;align-items:center;gap:5px;font-size:11px;white-space:nowrap;">
              <span class="dot ${statusDot}"></span>${a.status}
            </span>
          </td>
          <td style="font-size:11px;color:var(--text-muted);white-space:nowrap;">${timeAgo(a.created_at)}</td>
          <td style="text-align:right;">
            <a href="./results.html?id=${a.audit_id}" style="font-size:11px;color:var(--accent);text-decoration:none;white-space:nowrap;">View →</a>
          </td>
        </tr>`;
      }).join('');
    }

    const totalPages = Math.ceil(total / perPage) || 1;
    document.getElementById('audits-pagination').innerHTML = `
      <span class="page-info">${total} total &middot; Page ${this.auditPage} of ${totalPages}</span>
      <button class="page-btn" onclick="Admin.loadAudits(${this.auditPage - 1},'${this.auditStatus}','${this.auditSearch}')"
        ${this.auditPage <= 1 ? 'disabled' : ''}>← Prev</button>
      <button class="page-btn" onclick="Admin.loadAudits(${this.auditPage + 1},'${this.auditStatus}','${this.auditSearch}')"
        ${this.auditPage >= totalPages ? 'disabled' : ''}>Next →</button>`;
  },

  getRiskLevel(score) {
    if (score == null) return 'unknown';
    if (score <= 15) return 'low';
    if (score <= 35) return 'moderate';
    if (score <= 60) return 'high';
    return 'critical';
  },

  // ── Algorithm Updates ─────────────────────────────────────────────────────

  async loadUpdates() {
    this._showLoading();
    try {
      const data = await AdminAPI.getAlgorithmUpdates();
      this._showPanel('panel-updates');
      this.renderUpdates(data.updates || []);
    } catch (err) {
      this._showPanel('panel-updates');
      showToast('Failed to load algorithm updates', 'error');
    }
  },

  renderUpdates(updates) {
    const tbody = document.getElementById('updates-tbody');
    if (!updates.length) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:28px;">No algorithm updates yet</td></tr>';
      return;
    }

    const typeClass = {
      'core':             'update-type-core',
      'spam':             'update-type-spam',
      'helpful-content':  'update-type-helpful-content',
      'product-reviews':  'update-type-product-reviews',
    };

    tbody.innerHTML = updates.map(u => {
      const cls  = typeClass[u.update_type] || 'update-type-other';
      const type = u.update_type
        ? u.update_type.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
        : '—';
      const sourceHtml = u.source_url
        ? `<a href="${u.source_url}" target="_blank" rel="noopener" style="font-size:11px;color:var(--accent);text-decoration:none;">Source ↗</a>`
        : '';

      return `<tr>
        <td style="font-size:12.5px;font-weight:500;color:var(--text-primary);">${u.update_name}</td>
        <td style="font-size:12px;white-space:nowrap;">${formatDate(u.update_date)}</td>
        <td><span class="update-type-badge ${cls}">${type}</span></td>
        <td>${u.severity ? `<span class="severity-${u.severity}">${u.severity.charAt(0).toUpperCase() + u.severity.slice(1)}</span>` : '<span style="color:var(--text-muted)">—</span>'}</td>
        <td style="font-size:11.5px;color:var(--text-secondary);">${u.description || '<span style="color:var(--text-muted)">—</span>'}</td>
        <td style="text-align:right;">
          <div style="display:flex;align-items:center;gap:10px;justify-content:flex-end;">
            ${sourceHtml}
            <button class="btn btn-ghost btn-sm delete-update-btn" data-id="${u.id}"
              style="color:var(--critical);padding:4px 8px;" title="Delete update">
              <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
                <path d="M2 3h8M5 3V2h2v1M4 3v7h4V3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
          </div>
        </td>
      </tr>`;
    }).join('');

    tbody.querySelectorAll('.delete-update-btn').forEach(btn => {
      btn.addEventListener('click', () => this.deleteUpdate(parseInt(btn.dataset.id)));
    });
  },

  async handleAddUpdate(e) {
    e.preventDefault();
    const form = e.target;
    const fd = new FormData(form);
    const data = {
      update_name: fd.get('update_name'),
      update_date: fd.get('update_date'),
      update_type: fd.get('update_type') || null,
      severity:    fd.get('severity')    || null,
      description: fd.get('description') || null,
      source_url:  fd.get('source_url')  || null,
    };

    const btn = form.querySelector('[type="submit"]');
    btn.disabled = true;
    btn.textContent = 'Saving…';

    try {
      await AdminAPI.createAlgorithmUpdate(data);
      showToast('Algorithm update added', 'success');
      form.reset();
      document.getElementById('update-form-panel').style.display = 'none';
      await this.loadUpdates();
    } catch (err) {
      showToast(err.message || 'Failed to add update', 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Save Update';
    }
  },

  async deleteUpdate(id) {
    if (!confirm('Delete this algorithm update? This cannot be undone.')) return;
    try {
      await AdminAPI.deleteAlgorithmUpdate(id);
      showToast('Update deleted', 'success');
      await this.loadUpdates();
    } catch (err) {
      showToast('Failed to delete update', 'error');
    }
  },

  // ── Helpers ───────────────────────────────────────────────────────────────

  _showLoading() {
    document.getElementById('admin-loading').style.display = 'flex';
    ['panel-users', 'panel-audits', 'panel-updates'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });
  },

  _showPanel(panelId) {
    document.getElementById('admin-loading').style.display = 'none';
    document.getElementById(panelId).style.display = '';
  },
};

document.addEventListener('DOMContentLoaded', () => Admin.init());
