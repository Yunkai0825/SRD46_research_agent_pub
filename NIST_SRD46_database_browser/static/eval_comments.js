(function () {
  const scoringBar = document.getElementById('scoringBar');
  if (!scoringBar) return;

  const context = getEvalApiContext();
  if (!context) return;

  const {model, qid, batch, apiBase} = context;

  function addMarkerBadge(marker) {
    const container = document.getElementById('markersContainer');
    if (!container) return;
    const span = document.createElement('span');
    span.className = `badge bg-${marker.color} marker-badge`;
    span.dataset.markerId = marker.id;
    span.dataset.source = marker.source;
    let inner = '';
    if (marker.source === 'agent') inner += '<i class="bi bi-robot me-1"></i>';
    inner += marker.text;
    if (marker.source === 'manual') {
      inner += ' <button type="button" class="btn-close btn-close-white ms-1 marker-delete" style="font-size:0.5em;" aria-label="Remove"></button>';
    }
    span.innerHTML = inner;
    container.appendChild(span);
    bindDeleteButton(span);
  }

  function bindDeleteButton(badge) {
    const button = badge.querySelector('.marker-delete');
    if (!button) return;
    button.addEventListener('click', function (event) {
      event.stopPropagation();
      const markerId = badge.dataset.markerId;
      fetch(`${apiBase}/markers/${model}/${qid}/${batch}/${markerId}`, {method: 'DELETE'})
        .then(response => response.json())
        .then(data => {
          if (data.ok) badge.remove();
        });
    });
  }

  document.getElementById('saveScoring')?.addEventListener('click', function () {
    const note = document.getElementById('scoringNote')?.value || '';
    const scoreEl = document.getElementById('scoringScore');
    const score = scoreEl?.value ? parseInt(scoreEl.value, 10) : null;
    const button = this;
    button.disabled = true;
    button.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

    fetch(`${apiBase}/scoring/${model}/${qid}/${batch}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({note, score}),
    })
      .then(response => response.json())
      .then(() => {
        button.innerHTML = '<i class="bi bi-check-lg"></i> Saved';
        setTimeout(() => {
          button.innerHTML = '<i class="bi bi-floppy"></i> Save';
          button.disabled = false;
        }, 1500);
      })
      .catch(() => {
        button.innerHTML = '<i class="bi bi-floppy"></i> Save';
        button.disabled = false;
      });
  });

  document.querySelectorAll('.marker-badge').forEach(bindDeleteButton);

  document.getElementById('addMarker')?.addEventListener('click', function () {
    const textEl = document.getElementById('markerText');
    const colorEl = document.getElementById('markerColor');
    const text = (textEl?.value || '').replace(/\s+/g, ' ').trim();
    if (!text) return;

    fetch(`${apiBase}/markers/${model}/${qid}/${batch}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text, color: colorEl?.value || 'info'}),
    })
      .then(response => response.json())
      .then(data => {
        if (data.ok) {
          addMarkerBadge(data);
          textEl.value = '';
        }
      });
  });

  document.getElementById('markerText')?.addEventListener('keydown', function (event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      document.getElementById('addMarker')?.click();
    }
  });
})();