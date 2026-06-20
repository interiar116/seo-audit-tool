/**
 * AuditPro — Results Page
 * Fetches audit results and renders all sections with expand/collapse.
 */

const Results = {

  auditId: null,
  data: null,

  async init() {
    Auth.requireAuth();

    const params = new URLSearchParams(window.location.search);
    this.auditId = params.get('id');

    if (!this.auditId) {
      window.location.href = './dashboard.html';
      return;
    }

    this.showLoading(true);

    try {
      const data = await AuditAPI.getResults(this.auditId);
      this.data = data;
      this.render(data);

      // Load comparison table if ?compare= is present
      const compareParam = params.get('compare');
      if (compareParam) {
        const ids = compareParam.split(',').map(s => s.trim()).filter(Boolean);
        if (ids.length > 0) {
          document.getElementById('comparison-section').style.display = 'block';
          this.loadComparison(ids, data);
        }
      }
    } catch (err) {
      this.showError(err.message);
    } finally {
      this.showLoading(false);
    }

    // Re-run button
    document.getElementById('rerun-btn')?.addEventListener('click', () => this.rerun());
  },

  showLoading(show) {
    const el = document.getElementById('results-loading');
    const content = document.getElementById('results-content');
    if (el) el.style.display = show ? 'flex' : 'none';
    if (content) content.style.display = show ? 'none' : 'block';
  },

  showError(msg) {
    const el = document.getElementById('results-error');
    const msgEl = document.getElementById('results-error-msg');
    if (el) el.style.display = 'block';
    if (msgEl) msgEl.textContent = msg || 'Failed to load results.';
    this.showLoading(false);
  },

  render(data) {
    this.renderScoreHero(data);
    this.renderTechnical(data.technical);
    this.renderContent(data.content);
    this.renderBlackhat(data.blackhat);
    this.renderSidebar(data);
    this.bindAccordions();
  },

  // ── Score hero ──────────────────────────────────────────────────────────────

  renderScoreHero(data) {
    const scores  = data.scores || {};
    const meta    = data.meta || {};
    const pageInfo = data.page_info || {};
    const summary = data.summary || {};

    // Big score box
    const overall = scores.overall ?? 0;
    const boxEl   = document.getElementById('big-score-box');
    const numEl   = document.getElementById('big-score-num');
    if (boxEl && numEl) {
      numEl.textContent = overall;
      const bg = overall >= 70 ? 'rgba(26,127,55,.1)' : overall >= 40 ? 'rgba(240,136,62,.1)' : 'rgba(207,34,46,.1)';
      const border = overall >= 70 ? 'rgba(26,127,55,.3)' : overall >= 40 ? 'rgba(240,136,62,.3)' : 'rgba(207,34,46,.3)';
      const color  = overall >= 70 ? '#1a7f37' : overall >= 40 ? 'var(--accent)' : '#cf222e';
      boxEl.style.background = bg;
      boxEl.style.border = `1.5px solid ${border}`;
      numEl.style.color = color;
    }

    // Meta
    const url = meta.url || '';
    document.getElementById('hero-url') && (document.getElementById('hero-url').textContent = displayUrl(url));
    document.getElementById('hero-kw')  && (document.getElementById('hero-kw').textContent  = `Keyword: ${data.content?.keyword_data?.target_keyword || '—'}`);
    document.getElementById('hero-time') && (document.getElementById('hero-time').textContent =
      `Audited ${timeAgo(meta.audited_at)} · ${meta.load_time_ms ? (meta.load_time_ms/1000).toFixed(1)+'s load' : ''} · ${meta.scrape_method || 'playwright'}`);

    // Score bars
    this.renderScoreBar('bar-technical', scores.technical, 'Technical SEO');
    this.renderScoreBar('bar-content',   scores.content,   'Content');
    this.renderScoreBar('bar-blackhat',  scores.blackhat_risk, 'Blackhat risk', true);
  },

  renderScoreBar(id, score, label, inverted = false) {
    const wrap = document.getElementById(id);
    if (!wrap) return;
    const val = score ?? 0;
    const color = inverted
      ? (val <= 15 ? '#1a7f37' : val <= 35 ? 'var(--accent)' : '#cf222e')
      : (val >= 70 ? '#1a7f37' : val >= 40 ? 'var(--accent)' : '#cf222e');
    wrap.innerHTML = `
      <div class="sbi-label">
        <span>${label}</span>
        <span style="color:${color}">${val}</span>
      </div>
      <div class="score-bar-track">
        <div class="score-bar-fill" style="width:${val}%;background:${color};"></div>
      </div>
    `;
  },

  // ── Technical ───────────────────────────────────────────────────────────────

  renderTechnical(technical) {
    if (!technical) return;
    const checks  = technical.checks || [];
    const score   = technical.score ?? 0;

    const critical = checks.filter(c => c.status !== 'pass' && c.severity === 'critical').length;
    const high     = checks.filter(c => c.status !== 'pass' && c.severity === 'high').length;
    const passes   = checks.filter(c => c.status === 'pass').length;

    // Section counts
    const countEl = document.getElementById('technical-counts');
    if (countEl) {
      countEl.innerHTML = this.renderCounts(critical, high, passes, score);
    }

    // Checks list
    const listEl = document.getElementById('technical-checks');
    if (listEl) {
      listEl.innerHTML = checks.map(c => this.renderCheck(c)).join('');
    }
  },

  // ── Content ─────────────────────────────────────────────────────────────────

  renderContent(content) {
    if (!content) return;
    const checks  = content.checks || [];
    const score   = content.score ?? 0;
    const kd      = content.keyword_data || {};

    const warnings = checks.filter(c => c.status === 'warning').length;
    const passes   = checks.filter(c => c.status === 'pass').length;

    const countEl = document.getElementById('content-counts');
    if (countEl) {
      countEl.innerHTML = `
        <span class="sev-badge sev-pass">${score} score</span>
        ${warnings ? `<span class="sev-badge sev-medium">${warnings} warning${warnings>1?'s':''}</span>` : ''}
        <span class="sev-badge sev-pass">${passes} pass</span>
      `;
    }

    const listEl = document.getElementById('content-checks');
    if (listEl) {
      listEl.innerHTML = checks.map(c => this.renderCheck(c)).join('');
    }
  },

  // ── Blackhat ─────────────────────────────────────────────────────────────────

  renderBlackhat(blackhat) {
    if (!blackhat) return;
    const findings = blackhat.findings || [];
    const riskScore = blackhat.risk_score ?? 0;
    const riskLevel = blackhat.risk_level || 'low';
    const detected  = findings.filter(f => f.status === 'detected').length;
    const clean     = findings.filter(f => f.status === 'clean').length;

    const riskColor = riskLevel === 'critical' ? '#cf222e' :
                      riskLevel === 'high'     ? '#9a6700' :
                      riskLevel === 'moderate' ? '#7d4e00' : '#1a7f37';

    const countEl = document.getElementById('blackhat-counts');
    if (countEl) {
      countEl.innerHTML = `
        <span class="sev-badge" style="background:rgba(0,0,0,.05);color:${riskColor};">Risk ${riskScore}</span>
        ${detected ? `<span class="sev-badge sev-critical">${detected} detected</span>` : ''}
        <span class="sev-badge sev-pass">${clean} clean</span>
      `;
    }

    // Section header color for blackhat
    const headerEl = document.getElementById('blackhat-header-title');
    if (headerEl) headerEl.style.color = detected > 0 ? riskColor : 'var(--text-primary)';

    const listEl = document.getElementById('blackhat-checks');
    if (listEl) {
      listEl.innerHTML = findings.map(f => this.renderBlackhatFinding(f)).join('');
    }
  },

  // ── Sidebar ─────────────────────────────────────────────────────────────────

  renderSidebar(data) {
    this.renderRecoveryPriority(data.recovery_priority || []);
    this.renderPageInfo(data.page_info || {}, data.meta || {});
    this.renderKeywordAnalysis(data.content?.keyword_data || {});
  },

  renderRecoveryPriority(items) {
    const el = document.getElementById('recovery-list');
    if (!el) return;
    if (!items.length) {
      el.innerHTML = '<p style="font-size:12px;color:var(--text-muted);">No critical issues found.</p>';
      return;
    }
    el.innerHTML = items.slice(0, 8).map((item, i) => {
      const cls = item.severity === 'critical' ? 'pn-critical' :
                  item.severity === 'high'     ? 'pn-high' : 'pn-medium';
      return `
        <div class="priority-item">
          <div class="priority-num ${cls}">${i + 1}</div>
          <div class="priority-text">${item.title || item.recommendation || '—'}</div>
        </div>
      `;
    }).join('');
  },

  renderPageInfo(pageInfo, meta) {
    const el = document.getElementById('page-info-list');
    if (!el) return;
    const rows = [
      ['Word count',     meta.word_count ?? pageInfo.word_count ?? '—'],
      ['Images',         pageInfo.image_count ?? '—'],
      ['Internal links', pageInfo.internal_link_count ?? '—'],
      ['External links', pageInfo.external_link_count ?? '—'],
      ['Schema',         (pageInfo.schema_types || []).join(', ') || 'None'],
      ['Sitemap',        pageInfo.sitemap?.found ? `${pageInfo.sitemap.url_count} URLs` : 'Not found'],
      ['Load time',      meta.load_time_ms ? (meta.load_time_ms/1000).toFixed(1)+'s' : '—'],
      ['Scraper',        meta.scrape_method || '—'],
    ];
    el.innerHTML = rows.map(([label, val]) => `
      <div class="rc-row">
        <span class="rc-label">${label}</span>
        <span class="rc-val">${val}</span>
      </div>
    `).join('');
  },

  renderKeywordAnalysis(kd) {
    const el = document.getElementById('keyword-list');
    if (!el) return;
    const ka = kd.keyword_analysis || {};
    const kw = kd.target_keyword || '—';

    const yesNo = (val) => val
      ? `<span class="rc-val-pass">Yes</span>`
      : `<span class="rc-val-fail">No</span>`;

    el.innerHTML = `
      <div class="rc-row"><span class="rc-label">Keyword</span><span class="rc-val" style="font-size:11px;">${kw}</span></div>
      <div class="rc-row"><span class="rc-label">Density</span><span class="rc-val">${ka.density != null ? ka.density.toFixed(2)+'%' : '—'}</span></div>
      <div class="rc-row"><span class="rc-label">Occurrences</span><span class="rc-val">${ka.occurrences ?? '—'}</span></div>
      <div class="rc-row"><span class="rc-label">In title</span>${yesNo(ka.in_title)}</div>
      <div class="rc-row"><span class="rc-label">In H1</span>${yesNo(ka.in_h1)}</div>
      <div class="rc-row"><span class="rc-label">In meta desc</span>${yesNo(ka.in_meta_description)}</div>
      <div class="rc-row"><span class="rc-label">In first 100w</span>${yesNo(ka.in_first_100_words)}</div>
      <div class="rc-row"><span class="rc-label">In H2</span>${yesNo(ka.in_h2)}</div>
    `;
  },

  // ── Helpers ──────────────────────────────────────────────────────────────────

  renderCounts(critical, high, passes, score) {
    let html = '';
    if (critical) html += `<span class="sev-badge sev-critical">${critical} critical</span>`;
    if (high)     html += `<span class="sev-badge sev-high">${high} high</span>`;
    html += `<span class="sev-badge sev-pass">${passes} pass</span>`;
    return html;
  },

  renderCheck(check) {
    const statusIcon = check.status === 'pass'
      ? `<svg width="9" height="9" viewBox="0 0 9 9" fill="none"><path d="M1.5 4.5l2 2L7.5 2" stroke="#1a7f37" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>`
      : check.status === 'fail'
      ? `<svg width="9" height="9" viewBox="0 0 9 9" fill="none"><path d="M2 2l5 5M7 2l-5 5" stroke="#cf222e" stroke-width="1.4" stroke-linecap="round"/></svg>`
      : `<svg width="9" height="9" viewBox="0 0 9 9" fill="none"><path d="M4.5 2v3M4.5 6.5v.5" stroke="#9a6700" stroke-width="1.4" stroke-linecap="round"/></svg>`;

    const iconBg = check.status === 'pass' ? 'csi-pass' : check.status === 'fail' ? 'csi-fail' : 'csi-warn';

    const sevClass = check.severity === 'critical' ? 'sev-critical' :
                     check.severity === 'high'     ? 'sev-high' :
                     check.severity === 'medium'   ? 'sev-medium' : 'sev-pass';

    const sevLabel = check.status === 'pass' ? 'Pass' :
                     (check.severity?.charAt(0).toUpperCase() + check.severity?.slice(1)) || 'Low';

    const detail = check.status !== 'pass' ? `
      <div class="check-detail" data-check-id="${check.check_id}">
        <div class="cd-message">${check.message || ''}</div>
        ${check.recommendation ? `<div class="cd-rec">${check.recommendation}</div>` : ''}
        ${check.impact ? `<div class="cd-evidence" style="font-family:var(--font);font-size:11px;margin-top:6px;color:var(--text-secondary);">${check.impact}</div>` : ''}
      </div>
    ` : `
      <div class="check-detail" data-check-id="${check.check_id}">
        <div class="cd-message">${check.message || 'Check passed.'}</div>
      </div>
    `;

    return `
      <div class="check-item">
        <div class="check-trigger" onclick="Results.toggleCheck(this)">
          <div class="check-status-icon ${iconBg}">${statusIcon}</div>
          <div class="check-mid">
            <div class="ck-title">${check.message || check.check_id}</div>
            ${check.value != null && check.status !== 'pass' ? `<div class="ck-preview">${String(check.value).slice(0, 80)}</div>` : ''}
          </div>
          <span class="sev-badge ${sevClass}" style="flex-shrink:0;">${sevLabel}</span>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style="flex-shrink:0;color:var(--text-muted);margin-left:4px;transition:transform .2s;" class="check-chevron"><path d="M3 4.5l3 3 3-3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </div>
        ${detail}
      </div>
    `;
  },

  renderBlackhatFinding(finding) {
    const isDetected = finding.status === 'detected';
    const isClean    = finding.status === 'clean';

    const iconBg = isDetected ? 'csi-fail' : isClean ? 'csi-pass' : 'csi-warn';
    const icon   = isDetected
      ? `<svg width="9" height="9" viewBox="0 0 9 9" fill="none"><path d="M2 2l5 5M7 2l-5 5" stroke="#cf222e" stroke-width="1.4" stroke-linecap="round"/></svg>`
      : isClean
      ? `<svg width="9" height="9" viewBox="0 0 9 9" fill="none"><path d="M1.5 4.5l2 2L7.5 2" stroke="#1a7f37" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>`
      : `<svg width="9" height="9" viewBox="0 0 9 9" fill="none"><path d="M4.5 2v3M4.5 6.5v.5" stroke="#9a6700" stroke-width="1.4" stroke-linecap="round"/></svg>`;

    const sevClass = finding.severity === 'critical' ? 'sev-critical' :
                     finding.severity === 'high'     ? 'sev-high' :
                     finding.severity === 'medium'   ? 'sev-medium' : 'sev-pass';

    const sevLabel = isClean ? 'Clean' :
                     (finding.severity?.charAt(0).toUpperCase() + finding.severity?.slice(1)) || 'Low';

    const evidenceHtml = (finding.evidence || []).length
      ? `<div class="cd-evidence">${finding.evidence.join('<br>')}</div>`
      : '';

    return `
      <div class="check-item">
        <div class="check-trigger" onclick="Results.toggleCheck(this)">
          <div class="check-status-icon ${iconBg}">${icon}</div>
          <div class="check-mid">
            <div class="ck-title">${finding.title}</div>
            <div class="ck-preview">${finding.message || ''}</div>
          </div>
          <span class="sev-badge ${sevClass}" style="flex-shrink:0;">${sevLabel}</span>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style="flex-shrink:0;color:var(--text-muted);margin-left:4px;transition:transform .2s;" class="check-chevron"><path d="M3 4.5l3 3 3-3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </div>
        <div class="check-detail">
          <div class="cd-message">${finding.message || ''}</div>
          ${finding.fix ? `<div class="cd-rec">${finding.fix.replace(/\n/g, '<br>')}</div>` : ''}
          ${evidenceHtml}
        </div>
      </div>
    `;
  },

  toggleCheck(trigger) {
    const detail  = trigger.nextElementSibling;
    const chevron = trigger.querySelector('.check-chevron');
    if (!detail) return;
    const open = detail.classList.toggle('open');
    if (chevron) chevron.style.transform = open ? 'rotate(180deg)' : '';
  },

  bindAccordions() {
    document.querySelectorAll('.section-trigger').forEach(trigger => {
      trigger.addEventListener('click', () => {
        const list    = trigger.nextElementSibling;
        const chevron = trigger.querySelector('.chevron');
        if (!list) return;
        const open = list.classList.toggle('open');
        if (chevron) chevron.classList.toggle('open', open);
      });
    });
  },

  async rerun() {
    if (!this.data) return;
    const url = this.data.meta?.url;
    const kw  = this.data.content?.keyword_data?.target_keyword;
    if (!url) return;

    sessionStorage.setItem('pending_audit', JSON.stringify({
      url, keyword: kw || '', secondary: '', brandName: '', cloaking: false,
    }));
    window.location.href = './audit-loading.html';
  },

  // ── Competitor comparison ───────────────────────────────────────────────────

  async loadComparison(ids, mainData) {
    const loadingEl = document.getElementById('comparison-loading');
    const tableWrap = document.getElementById('comparison-table-wrap');

    try {
      const compList = await Promise.all(
        ids.map(id => AuditAPI.getResults(id).catch(() => null))
      );
      const valid = compList.filter(Boolean);

      loadingEl.style.display = 'none';
      tableWrap.style.display = 'block';

      if (valid.length === 0) {
        tableWrap.innerHTML = '<p style="font-size:12px;color:#8b949e;padding:16px;">No competitor results available.</p>';
        return;
      }

      tableWrap.innerHTML = this.renderComparisonTable(mainData, valid);
      this.bindComparisonDropdowns();
    } catch (err) {
      loadingEl.textContent = 'Failed to load competitor data.';
    }
  },

  renderComparisonTable(mainData, compList) {
    const all = [mainData, ...compList];

    const colHeaders = all.map((d, i) => {
      const url = d.meta?.url || '';
      const label = url.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '');
      const isMain = i === 0;
      return `<th style="min-width:150px;max-width:210px;padding:10px 14px;text-align:left;font-weight:400;
        ${isMain ? 'background:rgba(240,136,62,.04);border-bottom:2px solid var(--accent);' : ''}">
        <div style="font-size:10px;color:#8b949e;margin-bottom:2px;text-transform:uppercase;letter-spacing:.04em;">
          ${isMain ? 'Your page' : `Competitor ${i}`}
        </div>
        <div style="font-size:12px;font-weight:500;color:#e6edf3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:190px;" title="${label}">
          ${label || '—'}
        </div>
      </th>`;
    }).join('');

    const metricRow = (label, values, lowerBetter = false, suffix = '') => {
      const nums = values.map(v => (typeof v === 'number' && !isNaN(v)) ? v : null);
      const valid = nums.filter(v => v !== null);
      const best  = valid.length ? (lowerBetter ? Math.min(...valid) : Math.max(...valid)) : null;
      const worst = valid.length ? (lowerBetter ? Math.max(...valid) : Math.min(...valid)) : null;

      const cells = nums.map((v, i) => {
        if (v === null) return `<td style="padding:9px 14px;font-size:12px;color:#484f58;${i===0?'background:rgba(240,136,62,.02);':''}">—</td>`;
        const isBest  = best !== null && v === best;
        const isWorst = worst !== null && v === worst && best !== worst;
        const bg    = isBest ? 'rgba(26,127,55,.07)' : isWorst ? 'rgba(207,34,46,.05)' : i === 0 ? 'rgba(240,136,62,.02)' : 'transparent';
        const color = isBest ? '#1a7f37' : isWorst ? '#cf222e' : '#e6edf3';
        return `<td style="padding:9px 14px;font-size:12px;font-weight:500;background:${bg};color:${color};">
          ${v}${suffix}
        </td>`;
      }).join('');

      return `<tr style="border-top:0.5px solid #21262d;">
        <td style="padding:9px 14px;font-size:12px;color:#8b949e;white-space:nowrap;">${label}</td>
        ${cells}
      </tr>`;
    };

    const yesNoRow = (label, values) => {
      const cells = values.map((v, i) => {
        const isYes = v === 'Yes';
        return `<td style="padding:9px 14px;font-size:12px;font-weight:500;color:${isYes ? '#1a7f37' : '#cf222e'};${i===0?'background:rgba(240,136,62,.02);':''}">
          ${v ?? '—'}
        </td>`;
      }).join('');
      return `<tr style="border-top:0.5px solid #21262d;">
        <td style="padding:9px 14px;font-size:12px;color:#8b949e;">${label}</td>
        ${cells}
      </tr>`;
    };

    const groupHeader = (label, targetId) => `
      <tbody>
        <tr class="cmp-group-header" data-target="${targetId}" style="cursor:pointer;background:#161b22;">
          <td colspan="${all.length + 1}" style="padding:8px 14px;font-size:10px;font-weight:500;text-transform:uppercase;letter-spacing:.05em;color:#8b949e;">
            <span class="cmp-chevron" style="display:inline-block;margin-right:6px;transition:transform .2s;font-size:9px;">▶</span>
            ${label}
          </td>
        </tr>
      </tbody>`;

    // Data extraction
    const overallScores   = all.map(d => d.scores?.overall    ?? null);
    const techScores      = all.map(d => d.scores?.technical  ?? null);
    const contentScores   = all.map(d => d.scores?.content    ?? null);
    const bhScores        = all.map(d => d.scores?.blackhat_risk ?? null);
    const wordCounts      = all.map(d => d.meta?.word_count   ?? d.summary?.content_word_count ?? null);
    const loadTimes       = all.map(d => d.meta?.load_time_ms ? Math.round(d.meta.load_time_ms / 100) / 10 : null);
    const internalLinks   = all.map(d => d.page_info?.internal_link_count ?? null);
    const externalLinks   = all.map(d => d.page_info?.external_link_count ?? null);
    const imageCounts     = all.map(d => d.page_info?.image_count ?? null);
    const techCritical    = all.map(d => d.summary?.technical_critical ?? null);
    const techHigh        = all.map(d => d.summary?.technical_high     ?? null);
    const techPasses      = all.map(d => d.summary?.technical_passes   ?? null);
    const kwInTitle       = all.map(d => d.content?.keyword_data?.keyword_analysis?.in_title            != null ? (d.content.keyword_data.keyword_analysis.in_title    ? 'Yes' : 'No') : '—');
    const kwInH1          = all.map(d => d.content?.keyword_data?.keyword_analysis?.in_h1               != null ? (d.content.keyword_data.keyword_analysis.in_h1       ? 'Yes' : 'No') : '—');
    const kwInMeta        = all.map(d => d.content?.keyword_data?.keyword_analysis?.in_meta_description != null ? (d.content.keyword_data.keyword_analysis.in_meta_description ? 'Yes' : 'No') : '—');
    const kwDensity       = all.map(d => { const v = d.content?.keyword_data?.keyword_analysis?.density; return v != null ? parseFloat(v.toFixed(2)) : null; });
    const bhDetected      = all.map(d => d.blackhat?.detected_count ?? d.summary?.blackhat_detected_count ?? null);

    // Overall score row — prominent pill treatment
    const overallRow = `<tr>
      <td style="padding:12px 14px;font-size:13px;font-weight:500;color:#e6edf3;">Overall score</td>
      ${all.map((d, i) => {
        const v = d.scores?.overall ?? null;
        if (v === null) return `<td style="padding:12px 14px;${i===0?'background:rgba(240,136,62,.02);':''}">—</td>`;
        const bestVal = Math.max(...overallScores.filter(s => s !== null));
        const color = v >= 70 ? '#1a7f37' : v >= 40 ? 'var(--accent)' : '#cf222e';
        const bg    = v >= 70 ? 'rgba(26,127,55,.1)' : v >= 40 ? 'rgba(240,136,62,.1)' : 'rgba(207,34,46,.1)';
        return `<td style="padding:12px 14px;${i===0?'background:rgba(240,136,62,.02);':''}">
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
          <span style="font-size:11px;color:#8b949e;margin-left:auto;">${all.length} page${all.length > 1 ? 's' : ''}</span>
        </div>
        <div style="overflow-x:auto;">
          <table style="width:100%;border-collapse:collapse;min-width:${120 + all.length * 170}px;">
            <thead>
              <tr style="border-bottom:0.5px solid #30363d;">
                <th style="padding:10px 14px;text-align:left;font-size:11px;font-weight:500;color:#8b949e;min-width:120px;background:#0d1117;">Metric</th>
                ${colHeaders}
              </tr>
            </thead>

            <!-- Scores — always visible -->
            <tbody>
              ${overallRow}
              ${metricRow('Technical score',  techScores)}
              ${metricRow('Content score',    contentScores)}
              ${metricRow('Blackhat risk',    bhScores, true)}
            </tbody>

            ${groupHeader('Page metrics', 'cmp-page')}
            <tbody id="cmp-page" style="display:none;">
              ${metricRow('Word count',      wordCounts)}
              ${metricRow('Load time',       loadTimes, true, 's')}
              ${metricRow('Internal links',  internalLinks)}
              ${metricRow('External links',  externalLinks)}
              ${metricRow('Images',          imageCounts)}
            </tbody>

            ${groupHeader('Technical issues', 'cmp-technical')}
            <tbody id="cmp-technical" style="display:none;">
              ${metricRow('Critical issues', techCritical, true)}
              ${metricRow('High issues',     techHigh,     true)}
              ${metricRow('Passing checks',  techPasses)}
            </tbody>

            ${groupHeader('Keyword signals', 'cmp-keyword')}
            <tbody id="cmp-keyword" style="display:none;">
              ${yesNoRow('In title',      kwInTitle)}
              ${yesNoRow('In H1',         kwInH1)}
              ${yesNoRow('In meta desc',  kwInMeta)}
              ${metricRow('Density',      kwDensity, false, '%')}
            </tbody>

            ${groupHeader('Blackhat signals', 'cmp-blackhat')}
            <tbody id="cmp-blackhat" style="display:none;">
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
};

document.addEventListener('DOMContentLoaded', () => Results.init());
