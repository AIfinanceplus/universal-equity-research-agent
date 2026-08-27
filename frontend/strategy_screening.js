(() => {
  const host = document.querySelector('#strategyScreening');
  const summaryHost = document.querySelector('#strategySummary');

  if (!host || !summaryHost) {
    return;
  }

  const escHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
  }[char]));

  function fmtActual(value) {
    if (value === null || value === undefined || value === '') return '-';
    if (typeof value === 'number') {
      const abs = Math.abs(value);
      if (abs > 0 && abs < 1) return `${(value * 100).toFixed(2)}%`;
      return Number(value).toFixed(abs >= 100 ? 1 : 2);
    }
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  }

  function verdictClass(verdict) {
    return String(verdict || 'INSUFFICIENT_DATA').toLowerCase();
  }

  function renderStrategyScreening(screening) {
    if (!screening || !screening.results) {
      summaryHost.innerHTML = '';
      host.innerHTML = '<div class="strategy-empty">等待 Strategy Screening Hub 完成…</div>';
      return;
    }

    const counts = screening.verdict_counts || {};
    summaryHost.innerHTML = [
      ['PASS', counts.PASS || 0],
      ['FAIL', counts.FAIL || 0],
      ['PARTIAL', counts.PARTIAL || 0],
      ['INSUFFICIENT', counts.INSUFFICIENT_DATA || 0],
    ].map(([label, value]) => `<span class="pill"><strong>${escHtml(label)}</strong> ${escHtml(value)}</span>`).join('');

    const order = [
      'graham', 'buffett', 'lynch', 'fisher', 'greenblatt',
      'hohn', 'druckenmiller', 'tepper', 'klarman', 'ackman_smith'
    ];

    host.innerHTML = order.map(key => {
      const item = screening.results[key] || {};
      const rules = item.rules || [];
      const counts = item.counts || {};
      const coverage = Number(item.coverage || 0);

      return `
        <article class="strategy-card ${verdictClass(item.verdict)}">
          <div class="strategy-card-head">
            <div>
              <h3>${escHtml(item.title || key)}</h3>
              <div class="strategy-meta">
                coverage ${(coverage * 100).toFixed(0)}% ·
                pass ${escHtml(counts.pass || 0)} ·
                fail ${escHtml(counts.fail || 0)} ·
                unknown ${escHtml(counts.unknown || 0)}
              </div>
            </div>
            <span class="strategy-verdict">${escHtml(item.verdict || 'UNKNOWN')}</span>
          </div>
          <details>
            <summary>查看 ${rules.length} 条规则</summary>
            <div class="strategy-rules">
              ${rules.map(rule => `
                <div class="strategy-rule">
                  <div class="rule-status ${escHtml(rule.status)}">${escHtml(rule.status)}</div>
                  <div>
                    <div class="rule-label">${escHtml(rule.label)}</div>
                    ${rule.note ? `<div class="rule-note">${escHtml(rule.note)}</div>` : ''}
                  </div>
                  <div class="rule-actual">实际: ${escHtml(fmtActual(rule.actual))}</div>
                  <div class="rule-threshold">标准: ${escHtml(rule.threshold || '-')}</div>
                </div>
              `).join('')}
            </div>
          </details>
        </article>
      `;
    }).join('');

    const methodology = document.querySelector('#strategyMethodology');
    if (methodology) {
      methodology.textContent = screening.methodology || '';
    }
  }

  const originalRenderResults = renderResults;
  renderResults = function strategyAwareRenderResults(state) {
    originalRenderResults(state);
    renderStrategyScreening(state?.strategy_screening);
  };

  const originalResetExecution = resetExecution;
  resetExecution = function strategyAwareResetExecution(options) {
    originalResetExecution(options);
    renderStrategyScreening(null);
    const methodology = document.querySelector('#strategyMethodology');
    if (methodology) methodology.textContent = '';
  };

  renderStrategyScreening(null);
})();
