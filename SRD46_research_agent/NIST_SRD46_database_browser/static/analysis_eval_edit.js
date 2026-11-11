// Excerpt editor of the eval view: quote passages of the answer as new excerpt rows, change a
// row's parts, labels, mark and comment, or delete it.  Every save is one request that rewrites
// the run's _eval/excerpts.json (routes/analysis.py, analysis_excerpt_edit); the page then reloads.
(function () {
  const data = document.getElementById('evalEditData');
  const form = document.getElementById('evalEditor');
  const answer = document.getElementById('evalAnswer');
  if (!data || !form || !answer) return;
  const config = JSON.parse(data.textContent);
  const rows = {};
  config.rows.forEach(function (row) { rows[row.id] = row; });
  const newButton = document.getElementById('evalNew');
  const hint = document.getElementById('evalSelectionHint');
  const partList = form.querySelector('.ee-parts');
  const selected = form.querySelector('.ee-selected');
  const errorBox = form.querySelector('.ee-error');
  const FIELDS = ['fig', 'badge', 'kind', 'mark', 'statement', 'note', 'verbatim_diff'];
  // The characters Python's str.isspace() accepts: the server collapses whitespace with it.
  const SPACE = /[\t\n\v\f\r \x1c-\x1f\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]/;

  // The answer's text as the server sees it: text nodes in order, chips (row numbers) left out,
  // whitespace runs collapsed to one space, leading whitespace dropped.  pos[i] is the index in
  // that text of a node's i-th character, -1 for a character the collapse drops.
  let textMap = null;
  function answerText() {
    if (textMap) return textMap;
    const walker = document.createTreeWalker(answer, NodeFilter.SHOW_TEXT, {
      acceptNode: function (node) {
        return node.parentElement && node.parentElement.closest('.xm-chip') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
      }
    });
    const nodes = [];
    let text = '';
    let previousSpace = true;
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const pos = new Array(node.data.length);
      for (let i = 0; i < node.data.length; i++) {
        const ch = node.data.charAt(i);
        if (SPACE.test(ch)) {
          if (previousSpace) { pos[i] = -1; continue; }
          text += ' ';
          previousSpace = true;
        } else {
          text += ch;
          previousSpace = false;
        }
        pos[i] = text.length - 1;
      }
      nodes.push({ node: node, pos: pos });
    }
    textMap = { text: text, nodes: nodes };
    return textMap;
  }

  // The current selection inside the answer as {start, end, text}, or null.
  function selectionPart() {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed || !selection.rangeCount) return null;
    const range = selection.getRangeAt(0);
    if (!answer.contains(range.commonAncestorContainer)) return null;
    const map = answerText();
    let first = -1;
    let last = -1;
    map.nodes.forEach(function (item) {
      if (!range.intersectsNode(item.node)) return;
      const from = item.node === range.startContainer ? range.startOffset : 0;
      const to = item.node === range.endContainer ? range.endOffset : item.node.data.length;
      for (let i = from; i < to; i++) {
        const at = item.pos[i];
        if (at >= 0) { if (first < 0) first = at; last = at; }
      }
    });
    if (first < 0) return null;
    let start = first;
    let end = last + 1;
    while (start < end && map.text.charAt(start) === ' ') start++;
    while (end > start && map.text.charAt(end - 1) === ' ') end--;
    return start < end ? { start: start, end: end, text: map.text.slice(start, end) } : null;
  }

  function short(text, size) {
    return text.length > size ? text.slice(0, size - 1) + '…' : text;
  }

  // The latest passage selected in the answer.  Moving the selection into the form keeps it;
  // a click elsewhere in the answer clears it.
  let pending = null;
  document.addEventListener('selectionchange', function () {
    const selection = window.getSelection();
    const part = selectionPart();
    if (part) pending = part;
    else if (selection && selection.anchorNode && answer.contains(selection.anchorNode)) pending = null;
    else return;
    showPending();
  });

  function showPending() {
    const label = pending ? 'Selected: “' + short(pending.text, 160) + '”' : 'Select a passage of the answer to quote it.';
    hint.textContent = label;
    selected.textContent = label;
    newButton.disabled = !pending;
    newButton.title = pending ? 'start a new excerpt with the selected passage' : 'select a passage of the answer first';
    form.querySelectorAll('[data-act="add-part"], [data-act="replace-parts"]').forEach(function (button) {
      button.disabled = !pending;
    });
  }

  // The row being edited: id null for a new one; parts are {keep: index, text} for a stored
  // part and {start, end, text} for a new selection.
  let editing = null;

  function renderParts() {
    partList.innerHTML = '';
    editing.parts.forEach(function (part, index) {
      const item = document.createElement('li');
      const text = document.createElement('span');
      text.className = 'ee-part-text';
      text.textContent = short(part.text, 240);
      item.appendChild(text);
      const stored = 'keep' in part ? rows[editing.id] : null;
      if (stored && stored.missing.indexOf(stored.parts[part.keep]) >= 0) {
        item.insertAdjacentHTML('beforeend', '<span class="ee-part-missing">not found in this answer</span>');
      }
      if (!('keep' in part)) item.insertAdjacentHTML('beforeend', '<span class="ee-part-new">new</span>');
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.title = 'remove this part';
      remove.setAttribute('aria-label', 'remove this part');
      remove.textContent = '✕';
      remove.addEventListener('click', function () {
        editing.parts.splice(index, 1);
        editing.partsChanged = true;
        renderParts();
      });
      item.appendChild(remove);
      partList.appendChild(item);
    });
    if (!editing.parts.length) partList.innerHTML = '<li class="text-muted">no part: add a selection</li>';
  }

  function open(id) {
    const row = id ? rows[id] : null;
    editing = {
      id: id,
      parts: row ? row.parts.map(function (text, index) { return { keep: index, text: text }; }) : (pending ? [pending] : []),
      partsChanged: !row,
    };
    FIELDS.forEach(function (name) {
      const value = row ? row[name] : (name === 'kind' ? 'claim' : '');
      form.elements[name].value = Array.isArray(value) ? value.join(', ') : (value || '');
    });
    form.querySelector('.ee-title').textContent = row ? 'Edit excerpt ' + chipOf(id) : 'New excerpt';
    form.querySelector('[data-act="delete"]').hidden = !row;
    errorBox.hidden = true;
    document.querySelectorAll('.xrow-wrap.is-editing').forEach(function (el) { el.classList.remove('is-editing'); });
    const button = id && document.querySelector('.xrow-edit[data-edit="' + CSS.escape(id) + '"]');
    if (button) button.closest('.xrow-wrap').classList.add('is-editing');
    renderParts();
    showPending();
    form.hidden = false;
    form.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  function close() {
    editing = null;
    form.hidden = true;
    document.querySelectorAll('.xrow-wrap.is-editing').forEach(function (el) { el.classList.remove('is-editing'); });
  }

  function chipOf(id) {
    const chip = document.querySelector('.xrow[data-x="' + CSS.escape(id) + '"] .xm-chip');
    return chip ? chip.textContent : id;
  }

  function fail(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
  }

  function send(body) {
    body.version = config.version;
    form.querySelectorAll('button').forEach(function (button) { button.disabled = true; });
    return fetch(config.url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(function (response) {
      return response.json().catch(function () { return { error: 'HTTP ' + response.status }; });
    }).then(function (result) {
      if (!result.ok) throw new Error(result.error || 'The edit was not saved.');
      // Reload in eval view, on the saved row.
      const url = new URL(window.location.href);
      url.searchParams.set('mode', 'eval');
      url.hash = result.id && body.action !== 'delete' ? 'x=' + encodeURIComponent(result.id) : '';
      window.history.replaceState(null, '', url.toString());
      window.location.reload();
    }).catch(function (error) {
      fail(error.message);
      form.querySelectorAll('button').forEach(function (button) { button.disabled = false; });
      showPending();
    });
  }

  newButton.addEventListener('click', function () { open(null); });
  document.querySelectorAll('.xrow-edit').forEach(function (button) {
    button.addEventListener('click', function () { open(button.dataset.edit); });
  });
  form.querySelector('[data-act="add-part"]').addEventListener('click', function () {
    if (!pending || !editing) return;
    editing.parts.push(pending);
    editing.partsChanged = true;
    renderParts();
  });
  form.querySelector('[data-act="replace-parts"]').addEventListener('click', function () {
    if (!pending || !editing) return;
    editing.parts = [pending];
    editing.partsChanged = true;
    renderParts();
  });
  form.querySelector('[data-act="cancel"]').addEventListener('click', close);
  form.querySelector('[data-act="delete"]').addEventListener('click', function () {
    if (!editing || !editing.id) return;
    if (!window.confirm('Delete excerpt ' + chipOf(editing.id) + '? It is removed from _eval/excerpts.json of this run.')) return;
    send({ action: 'delete', id: editing.id });
  });
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    if (!editing) return;
    if (!editing.parts.length) {
      fail(editing.id ? 'An excerpt needs at least one part; use Delete to remove the row.' : 'Add a selected passage first.');
      return;
    }
    const row = {};
    FIELDS.forEach(function (name) { row[name] = form.elements[name].value; });
    const body = { action: editing.id ? 'update' : 'create', id: editing.id, row: row };
    if (editing.partsChanged) {
      body.parts = editing.parts.map(function (part) {
        return 'keep' in part ? { keep: part.keep } : { start: part.start, end: part.end, text: part.text };
      });
    }
    send(body);
  });
  showPending();
})();
