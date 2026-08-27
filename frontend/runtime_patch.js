(() => {
  const MIN_ZOOM = 0.25;
  const MAX_ZOOM = 1.00;
  const STEP = 0.10;

  function replaceZoomButton(id, handler) {
    const current = document.querySelector(`#${id}`);

    if (!current) {
      return null;
    }

    const replacement = current.cloneNode(true);
    current.replaceWith(replacement);
    replacement.addEventListener('click', handler);
    return replacement;
  }

  replaceZoomButton('zoomOut', () => {
    zoomLevel = Math.max(
      MIN_ZOOM,
      Number((zoomLevel - STEP).toFixed(2))
    );
    applyZoom();
  });

  replaceZoomButton('zoomIn', () => {
    zoomLevel = Math.min(
      MAX_ZOOM,
      Number((zoomLevel + STEP).toFixed(2))
    );
    applyZoom();
  });

  const originalRenderDecision = renderDecision;

  renderDecision = function patchedRenderDecision(decision) {
    originalRenderDecision(decision);

    if (
      decision?.route !== 'success_final'
      || !(decision?.actionable_issues || []).length
    ) {
      return;
    }

    const note = document.createElement('div');
    note.className = 'inspect-section';
    note.innerHTML = `
      <div class="inspect-label">Routing Calibration</div>
      <div class="inspect-text">
        Router 已把纯市场口径 / 定义差异降为 non-blocking caveat。
        这些内容仍保留在 Critic 记录中，但不会单独阻断整份研究。
      </div>
    `;

    decisionCard.appendChild(note);
  };
})();
