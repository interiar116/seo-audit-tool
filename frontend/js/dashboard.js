/**
 * AuditPro — Dashboard
 * Loads audit history, renders stats, handles delete.
 */

const Dashboard = {
  page: 1,
  perPage: 15,
  audits: [],
  currentTab: 'main',

  async init() {
    Auth.requireAuth();
    await this.loadStats();
    await this.loadHistory();
    this.checkForNewResult();
    this.bindTabs();
  },

  bindTabs() {
    document.getElementById('tab-main')?.addEventListener('click', () => {
      this.currentTab = 'main';
      document.getElementById('tab-main').classList.add('active');
      document.getElementById('tab-competitors').classList.remove('active');
      this.loadHistory();
    });
    document.getElementById('tab-competitors')?.addEventListener('click', () => {
      this.currentTab = 'competitors';
      document.getElementById('tab-competitors').classList.add('active');
      document.getElementById('tab-main').classList.remove('active');
      this.loadHistory();
    });
  },

  async loadStats() {
    try {
      const data = await AuditAPI.getHistory(1, 100, false);
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

      const critEl = document.getElementById('stat-critical');
      if (critical > 0) critEl.style.color = 'var(--critical)';

    } catch (err) {
      console.warn('Stats load failed:', err.message);
    }
  },

  async loadHistory() {
    const tbody = document.getElementById('audit-tbody');
    const empty = document.getElementById('audit-empty');
    const emptyComp = document.getElementById('audit-empty-competitors');
    const loading = document.getElementById('audit-loading');
    const tableWrap = document.getElementById('main-table-wrap');
    const compWrap = document.getElementById('competitor-comparison-wrap');
    const isCompetitive = this.currentTab === 'competitors';

    loading.style.display = 'flex';
    empty.style.display = 'none';
    emptyComp.style.display = 'none';
    tbody.innerHTML = '';
    tableWrap.style.display = isCompetitive ? 'none' : '';
    compWrap.style.display = 'none';
    compWrap.innerHTML = '';

    try {
      const data = await AuditAPI.getHistory(this.page, this.perPage, isCompetitive);
      const audits = data?.audits || [];
      this.audits = audits;

      loading.style.display = 'none';

      if (audits.length === 0) {
        if (isCompetitive) {
          emptyComp.style.display = 'flex';
        } else {
          empty.style.display = 'flex';
        }
        return;
      }

      if (isCompetitive) {
        compWrap.style.display = 'block';
        await this.renderCompetitorComparison(audits, compWrap);
      } else {
        tableWrap.style.display = '';
        audits.forEach(audit => {
          tbody.insertAdjacentHTML('beforeend', this.renderRow(audit));
        });
        this.bindRowActions();
      }

    } catch (err) {
      loading.style.display = 'none';
      showToast('Failed to load audit history', 'error');
    }
  },

  async renderCompetitorComparison(summaryAudits, container) {
    const completed = summaryAudits.filter(a => a.status === 'completed').slice(0, 8);
    if (completed.length === 0) {
      container.innerHTML = '<div style="padding:20px 4px;color:#8b949e;font-size:13px;">No completed competitor audits yet.</div>';
      return;
    }

    container.innerHTML = '<div style="padding:20px 4px;color:#8b949e;font-size:13px;display:flex;align-items:center;gap:8px;"><div class="spinner" style="width:14px;height:14px;border-width:2px;"></div>Loading full results…</div>';

    try {
      const results = await Promise.all(
        completed.map(a => AuditAPI.getResults(a.audit_id).catch(() => null))
      );
      const valid = results.filter(Boolean);
      if (valid.length === 0) {
        container.innerHTML = '<div style="padding:20px 4px;color:#8b949e;font-size:13px;">Could not load competitor results.</div>';
        return;
      }
      container.innerHTML = this.buildCompetitorTable(valid, completed);
      this.bindComparisonDropdowns();
    } catch (err) {
      container.innerHTML = '<div style="padding:20px 4px;color:#cf222e;font-size:13px;">Failed to load competitor data.</div>';
    }
  },

  buildCompetitorTable(dataList, summaryList) {
    const colHeaders = dataList.map((d, i) => {
      const url = d.meta?.url || summaryList[i]?.url || '';
      const label = url.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '');
      const auditId = summaryList[i]?.audit_id;
      return `<th style="min-width:155px;max-width:210px;padding:10px 14px;text-align:left;font-weight:400;">
        <div style="font-size:10px;color:#8b949e;margin-bottom:2px;text-transform:uppercase;letter-spacing:.04em;">Competitor ${i + 1}</div>
        <div style="font-size:12px;font-weight:500;color:#e6edf3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:185px;" title="${label}">${label || '—'}</div>
        <div style="margin-top:4px;">
          <a href="./results.html?id=${auditId}" style="font-size:10px;color:var(--accent);text-decoration:none;">View full report →</a>
        </div>
      </th>`;
    }).join('');

    const metricRow = (label, values, lowerBetter = false, suffix = '') => {
      const nums = values.map(v => (typeof v === 'number' && !isNaN(v)) ? v : null);
      const valid = nums.filter(v => v !== null);
      const best  = valid.length ? (lowerBetter ? Math.min(...valid) : Math.max(...valid)) : null;
      const worst = valid.length ? (lowerBetter ? Math.max(...valid) : Math.min(...valid)) : null;
      const cells = nums.map(v => {
        if (v === null) return `<td style="padding:9px 14px;font-size:12px;color:#484f58;">—</td>`;
        const isBest  = best !== null && v === best;
        const isWorst = worst !== null && v === worst && best !== worst;
        const bg    = isBest ? 'rgba(26,127,55,.07)' : isWorst ? 'rgba(207,34,46,.05)' : 'transparent';
        const color = isBest ? '#1a7f37' : isWorst ? '#cf222e' : '#e6edf3';
        return `<td style="padding:9px 14px;font-size:12px;font-weight:500;background:${bg};color:${color};">${v}${suffix}</td>`;
      }).join('');
      return `<tr style="border-top:0.5px solid #21262d;">
        <td style="padding:9px 14px;font-size:12px;color:#8b949e;white-space:nowrap;">${label}</td>${cells}</tr>`;
    };

    const yesNoRow = (label, values) => {
      const cells = values.map(v => {
        const isYes = v === 'Yes';
        return `<td style="padding:9px 14px;font-size:12px;font-weight:500;color:${isYes ? '#1a7f37' : '#cf222e'};">${v ?? '—'}</td>`;
      }).join('');
      return `<tr style="border-top:0.5px solid #21262d;">
        <td style="padding:9px 14px;font-size:12px;color:#8b949e;">${label}</td>${cells}</tr>`;
    };

    const groupHeader = (label, targetId) => `
      <tbody>
        <tr class="cmp-group-header" data-target="${targetId}" style="cursor:pointer;background:#161b22;">
          <td colspan="${dataList.length + 1}" style="padding:8px 14px;font-size:10px;font-weight:500;text-transform:uppercase;letter-spacing:.05em;color:#8b949e;">
            <span class="cmp-chevron" style="display:inline-block;margin-right:6px;transition:transform .2s;font-size:9px;">▶</span>${label}
          </td>
        </tr>
      </tbody>`;

    const overallScores = dataList.map(d => d.scores?.overall ?? null);
    const techScores    = dataList.map(d => d.scores?.technical ?? null);
    const contentScores = dataList.map(d => d.scores?.content ?? null);
    const bhScores      = dataList.map(d => d.scores?.blackhat_risk ?? null);
    const wordCounts    = dataList.map(d => d.meta?.word_count ?? d.summary?.content_word_count ?? null);
    const loadTimes     = dataList.map(d => d.meta?.load_time_ms ? Math.round(d.meta.load_time_ms / 100) / 10 : null);
    const internalLinks = dataList.map(d => d.page_info?.internal_link_count ?? null);
    const externalLinks = dataList.map(d => d.page_info?.external_link_count ?? null);
    const imageCounts   = dataList.map(d => d.page_info?.image_count ?? null);
    const techCritical  = dataList.map(d => d.summary?.technical_critical ?? null);
    const techHigh      = dataList.map(d => d.summary?.technical_high ?? null);
    const techPasses    = dataList.map(d => d.summary?.technical_passes ?? null);
    const kwInTitle     = dataList.map(d => d.content?.keyword_data?.keyword_analysis?.in_title != null ? (d.content.keyword_data.keyword_analysis.in_title ? 'Yes' : 'No') : '—');
    const kwInH1        = dataList.map(d => d.content?.keyword_data?.keyword_analysis?.in_h1 != null ? (d.content.keyword_data.keyword_analysis.in_h1 ? 'Yes' : 'No') : '—');
    const kwInMeta      = dataList.map(d => d.content?.keyword_data?.keyword_analysis?.in_meta_description != null ? (d.content.keyword_data.keyword_analysis.in_meta_description ? 'Yes' : 'No') : '—');
    const kwDensity     = dataList.map(d => { const v = d.content?.keyword_data?.keyword_analysis?.density; return v != null ? parseFloat(v.toFixed(2)) : null; });
    const bhDetected    = dataList.map(d => d.blackhat?.detected_count ?? d.summary?.blackhat_detected_count ?? null);

    const overallRow = `<tr>
      <td style="padding:12px 14px;font-size:13px;font-weight:500;color:#e6edf3;">Overall score</td>
      ${dataList.map((d) => {
        const v = d.scores?.overall ?? null;
        if (v === null) return `<td style="padding:12px 14px;">—</td>`;
        const bestVal = Math.max(...overallScores.filter(s => s !== null));
        const color = v >= 70 ? '#1a7f37' : v >= 40 ? 'var(--accent)' : '#cf222e';
        const bg    = v >= 70 ? 'rgba(26,127,55,.1)' : v >= 40 ? 'rgba(240,136,62,.1)' : 'rgba(207,34,46,.1)';
        return `<td style="padding:12px 14px;">
          <span style="display:inline-flex;align-items:center;gap:6px;">
            <span style="display:inline-flex;align-items:center;justify-content:center;width:46px;height:30px;border-radius:6px;background:${bg};font-size:16px;font-weight:600;color:${color};">${v}</span>
            ${v === bestVal ? '<span style="font-size:10px;color:#1a7f37;font-weight:500;">Best</span>' : ''}
          </span>
        </td>`;
      }).join('')}
    </tr>`;

    return `
      <div style="background:#161b22;border:0.5px solid #30363d;border-radius:12px;overflow:hidden;">
        <div style="padding:12px 16px;border-bottom:0.5px solid #30363d;display:flex;align-items:center;gap:8px;">
          <div style="width:24px;height:24px;border-radius:6px;background:rgba(240,136,62,.1);border:0.5px solid rgba(240,136,62,.3);display:flex;align-items:center;justify-content:center;">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M1 9.5h10M1 6h10M1 2.5h10" stroke="var(--accent)" stroke-width="1.3" stroke-linecap="round"/></svg>
          </div>
          <span style="font-size:13px;font-weight:500;color:#e6edf3;">Competitor comparison</span>
          <span style="font-size:11px;color:#8b949e;margin-left:auto;">${dataList.length} page${dataList.length > 1 ? 's' : ''}</span>
        </div>
        <div style="overflow-x:auto;">
          <table style="width:100%;border-collapse:collapse;min-width:${120 + dataList.length * 175}px;">
            <thead>
              <tr style="border-bottom:0.5px solid #30363d;">
                <th style="padding:10px 14px;text-align:left;font-size:11px;font-weight:500;color:#8b949e;min-width:120px;background:#0d1117;">Metric</th>
                ${colHeaders}
              </tr>
            </thead>
            <tbody>
              ${overallRow}
              ${metricRow('Technical score', techScores)}
              ${metricRow('Content score', contentScores)}
              ${metricRow('Blackhat risk', bhScores, true)}
            </tbody>
            ${groupHeader('Page metrics', 'dcmp-page')}
            <tbody id="dcmp-page" style="display:none;">
              ${metricRow('Word count', wordCounts)}
              ${metricRow('Load time', loadTimes, true, 's')}
              ${metricRow('Internal links', internalLinks)}
              ${metricRow('External links', externalLinks)}
              ${metricRow('Images', imageCounts)}
            </tbody>
            ${groupHeader('Technical issues', 'dcmp-technical')}
            <tbody id="dcmp-technical" style="display:none;">
              ${metricRow('Critical issues', techCritical, true)}
              ${metricRow('High issues', techHigh, true)}
              ${metricRow('Passing checks', techPasses)}
            </tbody>
            ${groupHeader('Keyword signals', 'dcmp-keyword')}
            <tbody id="dcmp-keyword" style="display:none;">
              ${yesNoRow('In title', kwInTitle)}
              ${yesNoRow('In H1', kwInH1)}
              ${yesNoRow('In meta desc', kwInMeta)}
              ${metricRow('Density', kwDensity, false, '%')}
            </tbody>
            ${groupHeader('Blackhat signals', 'dcmp-blackhat')}
            <tbody id="dcmp-blackhat" style="display:none;">
              ${metricRow('Issues detected', bhDetected, true)}
            </tbody>
          </table>
        </div>
      </div>`;
  },

  bindComparisonDropdowns() {
    document.querySelectorAll('.cmp-group-header').forEach(header => {
      header.addEventListener('click', () => {
        const tbody   = document.getElementById(header.dataset.target);
        const chevron = header.querySelector('.cmp-chevron');
        if (!tbody) return;
        const isOpen = tbody.style.display !== 'none';
        tbody.style.display = isOpen ? 'none' : '';
        if (chevron) chevron.style.transform = isOpen ? '' : 'rotate(90deg)';
      });
    });
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
    document.querySelectorAll('.view-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        window.location.href = `./results.html?id=${btn.dataset.id}`;
      });
    });

    document.querySelectorAll('#audit-tbody tr').forEach(row => {
      row.style.cursor = 'pointer';
      row.addEventListener('click', (e) => {
        if (e.target.closest('button')) return;
        window.location.href = `./results.html?id=${row.dataset.auditId}`;
      });
    });

    document.querySelectorAll('.delete-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const id = btn.dataset.id;
        if (!confirm('Delete this audit? This cannot be undone.')) return;
        try {
          await AuditAPI.delete(id);
          showToast('Audit deleted', 'success');
          await this.loadHistory();
          if (this.currentTab === 'main') await this.loadStats();
        } catch (err) {
          showToast('Failed to delete audit', 'error');
        }
      });
    });
  },

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