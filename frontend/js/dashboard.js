/**
 * AuditPro — Dashboard
 * Loads audit history, renders stats, handles delete.
 */

const Dashboard = {
  page: 1,
  perPage: 15,
  audits: [],

  async init() {
    Auth.requireAuth();
    await this.loadStats();
    await this.loadHistory();
    this.bindNewAudit();
    this.checkForNewResult();
  },

  /** Load stats row — total audits, avg score, critical issues */
  async loadStats() {
    try {
      const data = await AuditAPI.getHistory(1, 100);
      const audits = data?.audits || [];

      const total = audits.length;
      const avgScore = total
        ? Math.round(audits.reduce((s, a) => s + (a.overall_score || 0), 0) / total)
        : 0;
      const critical = audits.filter(a =>
        a.blackhat_risk_score >= 61 ||
        (a.overall_score !== null && a.overall_score < 40)
      ).length;

      document.getElementById('stat-total').textContent = total;
      document.getElementById('stat-avg').textContent = avgScore || '—';
      document.getElementById('stat-critical').textContent = critical;

      // Colour critical count
      const critEl = document.getElementById('stat-critical');
      if (critical > 0) critEl.style.color = 'var(--critical)';

    } catch (err) {
      console.warn('Stats load failed:', err.message);
    }
  },

  /** Load and render audit history table */
  async loadHistory() {
    const tbody = document.getElementById('audit-tbody');
    const empty = document.getElementById('audit-empty');
    const loading = document.getElementById('audit-loading');

    loading.style.display = 'flex';
    tbody.innerHTML = '';

    try {
      const data = await AuditAPI.getHistory(this.page, this.perPage);
      const audits = data?.audits || [];
      this.audits = audits;

      loading.style.display = 'none';

      if (audits.length === 0) {
        empty.style.display = 'flex';
        return;
      }

      empty.style.display = 'none';
      audits.forEach(audit => {
        tbody.insertAdjacentHTML('beforeend', this.renderRow(audit));
      });

      // Bind row actions
      this.bindRowActions();

    } catch (err) {
      loading.style.display = 'none';
      showToast('Failed to load audit history', 'error');
    }
  },

  renderRow(audit) {
    const overall = audit.overall_score;
    const tech = audit.technical_score;
    const content = audit.content_score;
    const bh = audit.blackhat_risk_score;
    const risk = this.getRiskLevel(bh);

    return `
      <tr data-audit-id="${audit.audit_id}">
        <td>
          <div class="audit-domain">${displayUrl(audit.url)}</div>
          <div class="audit-meta">${audit.primary_keyword || '—'} · ${timeAgo(audit.created_at)}</div>
        </td>
        <td>${this.scorePill(overall)}</td>
        <td>${this.scorePill(tech)}</td>
        <td>${this.scorePill(content)}</td>
        <td><span class="risk-badge ${riskClass(risk)}">${riskLabel(risk)}</span></td>
        <td>
          <div style="display:flex;gap:6px;justify-content:flex-end;">
            <button class="btn btn-secondary btn-sm view-btn" data-id="${audit.audit_id}">View</button>
            <button class="btn btn-ghost btn-sm delete-btn" data-id="${audit.audit_id}" title="Delete" style="color:var(--text-muted);padding:5px 7px;">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 3h8M5 3V2h2v1M4 3v7h4V3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </button>
          </div>
        </td>
      </tr>
    `;
  },

  scorePill(score) {
    if (score === null || score === undefined) return '<span style="color:var(--text-muted);font-size:11px;">—</span>';
    return `<span class="score-pill ${scoreClass(score)}">${score}</span>`;
  },

  getRiskLevel(riskScore) {
    if (!riskScore && riskScore !== 0) return 'unknown';
    if (riskScore <= 15) return 'low';
    if (riskScore <= 35) return 'moderate';
    if (riskScore <= 60) return 'high';
    return 'critical';
  },

  bindRowActions() {
    // View buttons
    document.querySelectorAll('.view-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.dataset.id;
        window.location.href = `./results.html?id=${id}`;
      });
    });

    // Row click (not on action buttons)
    document.querySelectorAll('#audit-tbody tr').forEach(row => {
      row.style.cursor = 'pointer';
      row.addEventListener('click', (e) => {
        if (e.target.closest('button')) return;
        const id = row.dataset.auditId;
        window.location.href = `./results.html?id=${id}`;
      });
    });

    // Delete buttons
    document.querySelectorAll('.delete-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const id = btn.dataset.id;
        if (!confirm('Delete this audit? This cannot be undone.')) return;
        try {
          await AuditAPI.delete(id);
          showToast('Audit deleted', 'success');
          await this.loadHistory();
          await this.loadStats();
        } catch (err) {
          showToast('Failed to delete audit', 'error');
        }
      });
    });
  },

  bindNewAudit() {
    const btn = document.getElementById('new-audit-btn');
    const topBtn = document.getElementById('topbar-new-audit');
    const handler = () => window.location.href = './index.html';
    if (btn) btn.addEventListener('click', handler);
    if (topBtn) topBtn.addEventListener('click', handler);
  },

  /** Check if we just landed from a completed audit */
  checkForNewResult() {
    const newId = sessionStorage.getItem('new_audit_id');
    if (!newId) return;
    sessionStorage.removeItem('new_audit_id');

    const banner = document.getElementById('new-result-banner');
    const link = document.getElementById('new-result-link');
    if (banner && link) {
      link.href = `./results.html?id=${newId}`;
      banner.style.display = 'flex';
      setTimeout(() => {
        banner.style.opacity = '0';
        banner.style.transition = 'opacity 0.5s';
        setTimeout(() => banner.style.display = 'none', 500);
      }, 8000);
    }
  },
};

document.addEventListener('DOMContentLoaded', () => Dashboard.init());
