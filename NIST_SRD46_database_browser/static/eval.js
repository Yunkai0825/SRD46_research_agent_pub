/* ── Evaluation page JavaScript ─────────────────────────────── */

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function applyFixedColumnWidth(element, widthPx) {
  const rounded = `${Math.round(widthPx)}px`;
  element.style.flex = `0 0 ${rounded}`;
  element.style.width = rounded;
}

function resetResizableColumns() {
  ['evalMainPanels', 'evalSidePanels', 'evalSidebar'].forEach(id => {
    const element = document.getElementById(id);
    if (!element) return;
    element.style.removeProperty('flex');
    element.style.removeProperty('width');
  });
}

function getMinWidth(element, fallback) {
  const minWidth = Number.parseFloat(window.getComputedStyle(element).minWidth);
  return Number.isFinite(minWidth) ? minWidth : fallback;
}

function syncHorizontalSplitters() {
  const isNarrow = window.matchMedia('(max-width: 1200px)').matches;
  document.querySelectorAll('.eval-splitter[data-axis="x"]').forEach(splitter => {
    const prev = document.getElementById(splitter.dataset.resizePrev || '');
    const next = document.getElementById(splitter.dataset.resizeNext || '');
    const sidebarTargetCollapsed = next?.id === 'evalSidebar' && next.classList.contains('collapsed');
    splitter.hidden = isNarrow || !prev || !next || sidebarTargetCollapsed;
  });
}

function setSidebarCollapsed(collapsed) {
  const sidebar = document.getElementById('evalSidebar');
  const layout = document.getElementById('evalLayout');
  if (!sidebar) return;
  sidebar.classList.toggle('collapsed', collapsed);
  layout?.classList.toggle('sidebar-collapsed', collapsed);
  syncHorizontalSplitters();
}

function initHorizontalSplitters() {
  const splitters = Array.from(document.querySelectorAll('.eval-splitter[data-axis="x"]'));
  if (splitters.length === 0) return;

  const breakpoint = window.matchMedia('(max-width: 1200px)');
  const syncResponsiveState = () => {
    if (breakpoint.matches) {
      resetResizableColumns();
    }
    syncHorizontalSplitters();
  };

  if (typeof breakpoint.addEventListener === 'function') {
    breakpoint.addEventListener('change', syncResponsiveState);
  } else {
    breakpoint.addListener(syncResponsiveState);
  }
  window.addEventListener('resize', syncHorizontalSplitters);
  syncResponsiveState();

  splitters.forEach(splitter => {
    splitter.addEventListener('pointerdown', event => {
      if (breakpoint.matches || splitter.hidden) return;

      const prev = document.getElementById(splitter.dataset.resizePrev || '');
      const next = document.getElementById(splitter.dataset.resizeNext || '');
      if (!prev || !next || next.classList.contains('collapsed')) return;

      event.preventDefault();
      splitter.classList.add('is-dragging');
      document.body.classList.add('eval-layout-resizing');

      const startX = event.clientX;
      const prevWidth = prev.getBoundingClientRect().width;
      const nextWidth = next.getBoundingClientRect().width;
      const totalWidth = prevWidth + nextWidth;
      const prevMinWidth = getMinWidth(prev, 320);
      const nextMinWidth = getMinWidth(next, 280);

      applyFixedColumnWidth(prev, prevWidth);
      applyFixedColumnWidth(next, nextWidth);

      const handlePointerMove = moveEvent => {
        const deltaX = moveEvent.clientX - startX;
        const newPrevWidth = clamp(prevWidth + deltaX, prevMinWidth, totalWidth - nextMinWidth);
        applyFixedColumnWidth(prev, newPrevWidth);
        applyFixedColumnWidth(next, totalWidth - newPrevWidth);
      };

      const stopDragging = () => {
        splitter.classList.remove('is-dragging');
        document.body.classList.remove('eval-layout-resizing');
        window.removeEventListener('pointermove', handlePointerMove);
        window.removeEventListener('pointerup', stopDragging);
        window.removeEventListener('pointercancel', stopDragging);
      };

      window.addEventListener('pointermove', handlePointerMove);
      window.addEventListener('pointerup', stopDragging);
      window.addEventListener('pointercancel', stopDragging);
    });
  });
}

setSidebarCollapsed(document.getElementById('evalSidebar')?.classList.contains('collapsed'));
initHorizontalSplitters();

// Toggle sidebar visibility
document.getElementById('toggleSidebar')?.addEventListener('click', function () {
  const sidebar = document.getElementById('evalSidebar');
  if (!sidebar) return;
  setSidebarCollapsed(!sidebar.classList.contains('collapsed'));
});

// ═══════════════════════════════════════════════════════════════
// Panel layout dropdown — toggle which side panels are visible
// ═══════════════════════════════════════════════════════════════

document.querySelectorAll('.panel-toggle').forEach(item => {
  item.addEventListener('click', function (e) {
    e.preventDefault();
    e.stopPropagation();
    this.classList.toggle('active');
    const checkIcon = this.querySelector('.bi-check2');
    if (checkIcon) checkIcon.classList.toggle('invisible');
  });
});

document.getElementById('applyPanelLayout')?.addEventListener('click', function (e) {
  e.preventDefault();
  const selected = [];
  document.querySelectorAll('.panel-toggle.active').forEach(item => {
    selected.push(item.dataset.panel);
  });
  const url = new URL(window.location.href);
  url.searchParams.set('panels', selected.join(','));
  window.location.href = url.toString();
});

// Show immediate feedback when enrichment starts (before navigation).
const enrichButtons = Array.from(document.querySelectorAll('.enrich-action'));
enrichButtons.forEach(btn => {
  btn.addEventListener('click', function () {
    const loadingText = this.getAttribute('data-loading-text') || 'Starting enrichment...';
    enrichButtons.forEach(b => {
      b.classList.add('disabled');
      b.setAttribute('aria-disabled', 'true');
    });
    this.innerHTML = `<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>${loadingText}`;
  });
});

function getEvalApiContext() {
  const bar = document.getElementById('scoringBar');
  if (!bar) return null;
  return {
    model: bar.dataset.model,
    qid: bar.dataset.qid,
    batch: bar.dataset.batch,
    apiBase: '/eval/api',
  };
}

// ═══════════════════════════════════════════════════════════════
// Claim click-to-filter sidebar
// ═══════════════════════════════════════════════════════════════

let activeClaimEl = null;
const claimSupportScope = document.getElementById('claimSupportScope');
const claimSupportTabs = Array.from(document.querySelectorAll('#claimSupportTabs [data-support-filter]'));

function formatSupportLabel(support) {
  return (support || 'unsupported')
    .split('_')
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function supportBadgeClass(support) {
  return `claim-support-badge claim-support-badge-${support || 'unsupported'}`;
}

function applyClaimSupportFilter(filter) {
  if (!claimSupportScope) return;

  const activeFilter = filter || 'all';
  claimSupportScope.dataset.supportFilter = activeFilter;

  claimSupportTabs.forEach(button => {
    button.classList.toggle('active', button.dataset.supportFilter === activeFilter);
  });

  claimSupportScope.querySelectorAll('[data-support][data-claim-idx]').forEach(element => {
    const support = element.dataset.support || 'unsupported';
    const isDimmed = activeFilter !== 'all' && support !== activeFilter;
    element.classList.toggle('support-filter-dimmed', isDimmed);
  });
}

// ── Tool snippets panel helper ─────────────────────────────
function renderSnippetsPanel(snippets, evidence, support) {
  let html = '<div id="snippetPanel" class="snippet-panel mb-2">';
  html += `<div class="snippet-panel-header d-flex justify-content-between align-items-center">`;
  html += `<strong><i class="bi bi-database"></i> Tool Result Evidence</strong>`;
  html += `<span class="${supportBadgeClass(support)}">${escapeHtml(formatSupportLabel(support))}</span>`;
  html += `</div>`;

  if (evidence) {
    html += `<div class="snippet-evidence"><em>${escapeHtml(evidence)}</em></div>`;
  }

  if (snippets && snippets.length > 0) {
    for (const s of snippets) {
      html += `<div class="snippet-card">`;
      html += `<div class="snippet-step">`;
      if (s.step) html += `<span class="badge bg-secondary me-1">${escapeHtml(s.step)}</span>`;
      if (s.tool) html += `<code>${escapeHtml(s.tool)}</code>`;
      html += `</div>`;
      html += `<div class="snippet-text">${escapeHtml(s.snippet)}</div>`;
      html += `</div>`;
    }
  } else {
    html += `<div class="text-muted small p-2">No tool result snippets linked to this claim.</div>`;
  }
  html += '</div>';
  return html;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function showSnippetsInSidebar(span) {
  // Remove old snippet panel
  document.getElementById('snippetPanel')?.remove();

  const snippetsRaw = span.dataset.snippets || '';
  const support = span.dataset.support || 'unsupported';
  const evidence = span.title?.split('Evidence: ')[1] || '';

  let snippets = [];
  if (snippetsRaw) {
    try { snippets = JSON.parse(snippetsRaw); } catch (e) {}
  }

  const sidebar = document.getElementById('evalSidebar');
  if (!sidebar) return;

  const refArea = sidebar.querySelector('.sidebar-body') || sidebar.querySelector('.card-body');
  if (!refArea) return;

  refArea.insertAdjacentHTML('afterbegin', renderSnippetsPanel(snippets, evidence, support));
}

function filterSidebarByIds(refIds) {
  const idSet = new Set(refIds);
  const allCards = document.querySelectorAll('.ref-card');
  const allGroups = document.querySelectorAll('.ref-group');
  let visibleCount = 0;

  allCards.forEach(card => {
    const pid = card.dataset.prefixedId;
    if (idSet.has(pid)) {
      card.style.display = '';
      visibleCount++;
      // Auto-expand parent group
      const collapseEl = card.closest('.collapse');
      if (collapseEl && !collapseEl.classList.contains('show')) {
        collapseEl.classList.add('show');
      }
    } else {
      card.style.display = 'none';
    }
  });

  // Hide groups with no visible cards
  allGroups.forEach(group => {
    const visCards = group.querySelectorAll('.ref-card:not([style*="display: none"])');
    group.style.display = visCards.length > 0 ? '' : 'none';
  });

  // Update status
  const statusEl = document.getElementById('refFilterStatus');
  const showAllBtn = document.getElementById('showAllRefs');
  if (statusEl) {
    statusEl.textContent = `Showing ${visibleCount} reference${visibleCount !== 1 ? 's' : ''} for selected claim`;
    statusEl.style.display = '';
  }
  if (showAllBtn) {
    showAllBtn.style.display = '';
  }

  // Open sidebar if collapsed
  const sidebar = document.getElementById('evalSidebar');
  if (sidebar && sidebar.classList.contains('collapsed')) {
    setSidebarCollapsed(false);
  }
}

function hideAllReferences() {
  // Hide all cards and groups — for claims with no refs
  document.querySelectorAll('.ref-card').forEach(c => c.style.display = 'none');
  document.querySelectorAll('.ref-group').forEach(g => g.style.display = 'none');
  const statusEl = document.getElementById('refFilterStatus');
  const showAllBtn = document.getElementById('showAllRefs');
  if (statusEl) {
    statusEl.textContent = 'No references linked to this claim';
    statusEl.style.display = '';
  }
  if (showAllBtn) showAllBtn.style.display = '';
}

function showAllReferences() {
  document.querySelectorAll('.ref-card').forEach(c => c.style.display = '');
  document.querySelectorAll('.ref-group').forEach(g => g.style.display = '');
  const statusEl = document.getElementById('refFilterStatus');
  const showAllBtn = document.getElementById('showAllRefs');
  if (statusEl) statusEl.style.display = 'none';
  if (showAllBtn) showAllBtn.style.display = 'none';
  document.getElementById('snippetPanel')?.remove();
  clearToolResultHighlights();
  if (activeClaimEl) {
    activeClaimEl.classList.remove('claim-active');
    activeClaimEl = null;
  }
}

// ── Tool results panel: highlight + scroll to step ────────────
function clearToolResultHighlights() {
  document.querySelectorAll('.tool-step-highlight').forEach(el => {
    el.classList.remove('tool-step-highlight');
  });
}

function handleClaimActivation(element, event) {
  if (window.evalAnnotationEditor?.handleClaimActivation?.(element, event)) {
    return;
  }

  if (activeClaimEl) activeClaimEl.classList.remove('claim-active');

  if (activeClaimEl === element) {
    showAllReferences();
    return;
  }

  activeClaimEl = element;
  element.classList.add('claim-active');

  showSnippetsInSidebar(element);

  let snippets = [];
  const snippetsRaw = element.dataset.snippets || '';
  if (snippetsRaw) {
    try { snippets = JSON.parse(snippetsRaw); } catch (e) {}
  }

  highlightToolSteps(snippets);

  const refIds = (element.dataset.refIds || '').split(',').filter(Boolean);
  if (refIds.length > 0) {
    filterSidebarByIds(refIds);
  } else {
    hideAllReferences();
  }

  const sidebar = document.getElementById('evalSidebar');
  if (sidebar && sidebar.classList.contains('collapsed')) {
    setSidebarCollapsed(false);
  }
}

function highlightToolSteps(snippets) {
  clearToolResultHighlights();
  if (!snippets || snippets.length === 0) return;

  const toolPanel = document.getElementById('toolResultsBody');
  if (!toolPanel) return;

  // Ensure tool results panel is expanded
  if (!toolPanel.classList.contains('show')) {
    toolPanel.classList.add('show');
  }

  let firstAnchor = null;
  for (const s of snippets) {
    // Try to find matching step anchor
    const stepNum = (s.step || '').replace(/\D/g, '');
    if (!stepNum) continue;
    const anchor = document.getElementById(`tool-step-${stepNum}`);
    if (anchor) {
      // Highlight the step heading's parent (the h2/h3 element)
      const heading = anchor.closest('h2, h3') || anchor.parentElement;
      if (heading) heading.classList.add('tool-step-highlight');
      if (!firstAnchor) firstAnchor = anchor;
    }
  }

  // Scroll only the tool-results pane, not the whole browser window.
  if (firstAnchor) {
    const panelRect = toolPanel.getBoundingClientRect();
    const anchorRect = firstAnchor.getBoundingClientRect();
    const targetTop = toolPanel.scrollTop + (anchorRect.top - panelRect.top) - 24;
    toolPanel.scrollTo({
      top: Math.max(targetTop, 0),
      behavior: 'smooth',
    });
  }
}

// Click on claim spans (and claim-table rows, which carry the same `claim` class).
// NOTE: Every table-row claim has BOTH `.claim` and `.claim-row` classes, so a
// dual-selector loop attaches the click handler twice and immediately toggles
// the active state off. Use a single `.claim` selector for both span and row
// elements, and only set the cursor on inline span claims.
document.querySelectorAll('.claim').forEach(el => {
  if (el.tagName !== 'TR') {
    el.style.cursor = 'pointer';
  }
  el.addEventListener('click', function (event) {
    handleClaimActivation(this, event);
  });
});

// Show all button
document.getElementById('showAllRefs')?.addEventListener('click', showAllReferences);
claimSupportTabs.forEach(button => {
  button.addEventListener('click', function () {
    applyClaimSupportFilter(this.dataset.supportFilter);
  });
});
applyClaimSupportFilter(claimSupportScope?.dataset.supportFilter || 'all');

/**
 * Lazy-load a reference card via the /eval/api/ref/<id> endpoint.
 */
function loadRefCard(prefixedId, headerEl) {
  const cardEl = headerEl.closest('.ref-card');
  const bodyEl = cardEl.querySelector('.ref-card-body');

  // Toggle visibility
  if (bodyEl.style.display !== 'none') {
    bodyEl.style.display = 'none';
    return;
  }

  // If already loaded, just show
  if (bodyEl.dataset.loaded === '1') {
    bodyEl.style.display = 'block';
    return;
  }

  bodyEl.innerHTML = '<em class="text-muted">Loading…</em>';
  bodyEl.style.display = 'block';

  fetch(`/eval/api/ref/${encodeURIComponent(prefixedId)}`)
    .then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then(data => {
      bodyEl.innerHTML = renderCardData(data);
      bodyEl.dataset.loaded = '1';
    })
    .catch(err => {
      bodyEl.innerHTML = `<span class="text-danger">Error: ${err.message}</span>`;
    });
}

/**
 * Render a data card object as an HTML table.
 */
function renderCardData(data) {
  if (!data || data.error) {
    return `<span class="text-muted">${data?.error || 'No data'}</span>`;
  }

  // Skip internal fields
  const skip = new Set(['type', 'id']);
  let html = '<table>';

  for (const [key, value] of Object.entries(data)) {
    if (skip.has(key)) continue;
    if (value === null || value === undefined || value === '') continue;

    if (Array.isArray(value)) {
      // Measurements array: render as mini-table
      if (value.length > 0 && typeof value[0] === 'object') {
        html += `<tr><td colspan="2"><strong>${key}</strong></td></tr>`;
        const subKeys = Object.keys(value[0]).slice(0, 6);
        html += '<tr><td colspan="2"><table class="table table-sm mb-0" style="font-size:0.7rem">';
        html += '<thead><tr>' + subKeys.map(k => `<th>${k}</th>`).join('') + '</tr></thead><tbody>';
        for (const item of value.slice(0, 10)) {
          html += '<tr>' + subKeys.map(k => `<td>${item[k] ?? ''}</td>`).join('') + '</tr>';
        }
        if (value.length > 10) {
          html += `<tr><td colspan="${subKeys.length}" class="text-muted">… ${value.length - 10} more</td></tr>`;
        }
        html += '</tbody></table></td></tr>';
      }
      continue;
    }

    // Truncate long values
    let displayValue = String(value);
    if (displayValue.length > 80) {
      displayValue = displayValue.substring(0, 77) + '…';
    }
    html += `<tr><td>${key}</td><td>${displayValue}</td></tr>`;
  }

  html += '</table>';
  return html;
}

// Highlight matching canon-id links when hovering a sidebar reference
document.querySelectorAll('.ref-card').forEach(card => {
  const pid = card.dataset.prefixedId;
  card.addEventListener('mouseenter', () => {
    document.querySelectorAll(`a.canon-id[data-prefixed-id="${pid}"]`).forEach(el => {
      el.style.outline = '2px solid #ff9900';
      el.style.outlineOffset = '1px';
    });
  });
  card.addEventListener('mouseleave', () => {
    document.querySelectorAll(`a.canon-id[data-prefixed-id="${pid}"]`).forEach(el => {
      el.style.outline = '';
      el.style.outlineOffset = '';
    });
  });
});

