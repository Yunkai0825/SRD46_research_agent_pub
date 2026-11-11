// Eval mode of an analysis run: link the highlights in the answer with the rows beside it.
(function () {
  const layout = document.getElementById('evalLayout');
  if (!layout) return;
  const answer = document.getElementById('evalAnswer');
  const controls = document.getElementById('evalControls');

  function marks(id) {
    return Array.from(answer.querySelectorAll('[data-x]')).filter(function (el) {
      return el.dataset.x.split(' ').indexOf(id) >= 0;
    });
  }

  function clearActive() {
    layout.querySelectorAll('.is-active').forEach(function (el) { el.classList.remove('is-active'); });
  }

  function showPane(name) {
    layout.querySelectorAll('[data-pane]').forEach(function (pane) { pane.hidden = pane.dataset.pane !== name; });
    layout.querySelectorAll('[data-tab]').forEach(function (tab) { tab.classList.toggle('is-on', tab.dataset.tab === name); });
  }

  function activate(id, scrollAnswer) {
    clearActive();
    const hits = marks(id).filter(function (el) { return el.tagName === 'MARK'; });
    hits.forEach(function (el) { el.classList.add('is-active'); });
    const row = layout.querySelector('.xrow[data-x="' + id + '"]');
    if (row) {
      showPane(row.closest('[data-pane]').dataset.pane);
      row.classList.add('is-active');
      if (!scrollAnswer) row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
    if (scrollAnswer && hits.length) hits[0].scrollIntoView({ block: 'center', behavior: 'smooth' });
  }

  answer.addEventListener('click', function (event) {
    const selection = window.getSelection();
    if (selection && !selection.isCollapsed) return;  // the click ended a text selection
    const hit = event.target.closest('[data-x]');
    if (!hit) return;
    const owners = hit.dataset.x.split(' ');
    const coreOn = !layout.classList.contains('eval-off-c');
    const excerptOn = !layout.classList.contains('eval-off-e');
    const usable = owners.filter(function (id) {
      return id.charAt(0) === 'c' ? coreOn : excerptOn;
    });
    if (!usable.length) return;
    // Repeated clicks on a stretch held by two owners step through them.
    const current = layout.querySelector('.xrow.is-active');
    const at = current ? usable.indexOf(current.dataset.x) : -1;
    activate(usable[(at + 1) % usable.length], false);
  });

  layout.querySelectorAll('.xrow').forEach(function (row) {
    row.addEventListener('click', function () { activate(row.dataset.x, true); });
  });
  layout.querySelectorAll('[data-tab]').forEach(function (tab) {
    tab.addEventListener('click', function () { showPane(tab.dataset.tab); });
  });

  if (controls) {
    controls.querySelectorAll('input[data-layer]').forEach(function (box) {
      box.addEventListener('change', function () {
        layout.classList.toggle('eval-off-' + box.dataset.layer, !box.checked);
      });
    });
    controls.querySelectorAll('button[data-mark]').forEach(function (button) {
      button.addEventListener('click', function () {
        const on = !button.classList.contains('is-on');
        button.classList.toggle('is-on', on);
        button.setAttribute('aria-pressed', on ? 'true' : 'false');
        layout.classList.toggle('eval-off-' + button.dataset.mark, !on);
      });
    });
  }

  // #x=<row id> opens that row, e.g. the one just saved in the editor.
  const named = /^#x=(.+)$/.exec(window.location.hash);
  if (named && layout.querySelector('.xrow[data-x="' + CSS.escape(decodeURIComponent(named[1])) + '"]')) {
    activate(decodeURIComponent(named[1]), true);
  }
})();
