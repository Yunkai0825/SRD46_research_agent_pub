(function () {
  const annotationDocScript = document.getElementById('annotationDocData');
  const annotationEditToggle = document.getElementById('toggleAnnotationEditMode');
  const annotationEditBanner = document.getElementById('annotationEditBanner');
  const undoAnnotationChangeButton = document.getElementById('undoAnnotationChange');
  const redoAnnotationChangeButton = document.getElementById('redoAnnotationChange');
  const restorePristineAnnotationsButton = document.getElementById('restorePristineAnnotations');
  const annotationEditorModalEl = document.getElementById('annotationEditorModal');
  const annotationParagraphSourceEl = document.getElementById('annotationParagraphSource');
  const annotationEditorContextEl = document.getElementById('annotationEditorContext');
  const annotationSelectionWarningEl = document.getElementById('annotationSelectionWarning');
  const annotationSelectionMetaEl = document.getElementById('annotationSelectionMeta');
  const annotationClaimTextEl = document.getElementById('annotationClaimText');
  const annotationClaimTypeEl = document.getElementById('annotationClaimType');
  const annotationSupportClassEl = document.getElementById('annotationSupportClass');
  const annotationCanonicalIdsEl = document.getElementById('annotationCanonicalIds');
  const annotationEvidenceSnippetEl = document.getElementById('annotationEvidenceSnippet');
  const annotationParagraphIndexEl = document.getElementById('annotationParagraphIndex');
  const annotationClaimIndexEl = document.getElementById('annotationClaimIndex');
  const annotationClaimStartEl = document.getElementById('annotationClaimStart');
  const annotationClaimEndEl = document.getElementById('annotationClaimEnd');
  const annotationEditorModeLabelEl = document.getElementById('annotationEditorModeLabel');
  const captureAnnotationSelectionButton = document.getElementById('captureAnnotationSelection');
  const saveAnnotationButton = document.getElementById('saveAnnotationButton');
  const deleteAnnotationButton = document.getElementById('deleteAnnotationButton');

  let annotationDoc = null;
  let annotationEditMode = false;

  if (annotationDocScript?.textContent) {
    try {
      annotationDoc = JSON.parse(annotationDocScript.textContent);
    } catch (error) {
      annotationDoc = null;
    }
  }

  const annotationEditorModal = annotationEditorModalEl && window.bootstrap
    ? window.bootstrap.Modal.getOrCreateInstance(annotationEditorModalEl)
    : null;

  function canonicalIdsToText(ids) {
    return Array.isArray(ids) ? ids.join('\n') : '';
  }

  function parseCanonicalIdsInput(text) {
    return Array.from(new Set(
      String(text || '')
        .split(/[\n,]+/)
        .map(value => value.trim())
        .filter(Boolean)
    ));
  }

  function getAnnotationParagraph(paragraphIndex) {
    return annotationDoc?.paragraphs?.find(paragraph => paragraph.paragraph_index === paragraphIndex) || null;
  }

  function getGroundedClaim(paragraph, claimIndex) {
    return paragraph?.grounded_claims?.find(grounded => grounded.claim_index === claimIndex) || null;
  }

  function setAnnotationWarning(message) {
    if (!annotationSelectionWarningEl) return;
    if (!message) {
      annotationSelectionWarningEl.classList.add('d-none');
      annotationSelectionWarningEl.textContent = '';
      return;
    }
    annotationSelectionWarningEl.textContent = message;
    annotationSelectionWarningEl.classList.remove('d-none');
  }

  function updateSelectionMeta(start, end) {
    if (!annotationSelectionMetaEl) return;
    if (Number.isInteger(start) && Number.isInteger(end) && end > start) {
      annotationSelectionMetaEl.textContent = `Selected chars ${start}-${end} (${end - start} chars).`;
      return;
    }
    annotationSelectionMetaEl.textContent = 'Select the exact claim span inside this source text.';
  }

  function setAnnotationEditMode(enabled) {
    annotationEditMode = Boolean(enabled && annotationDoc);
    document.body.classList.toggle('annotation-edit-mode', annotationEditMode);
    annotationEditToggle?.classList.toggle('is-active', annotationEditMode);
    if (annotationEditToggle) {
      annotationEditToggle.dataset.editMode = annotationEditMode ? 'on' : 'off';
      annotationEditToggle.innerHTML = annotationEditMode
        ? '<i class="bi bi-lock"></i> Disable Annotation Edit Mode'
        : '<i class="bi bi-pencil-square"></i> Enable Annotation Edit Mode';
    }
    annotationEditBanner?.classList.toggle('d-none', !annotationEditMode);

    if (!annotationEditMode && annotationEditorModal) {
      annotationEditorModal.hide();
    }

    if (annotationEditMode) {
      showAllReferences();
    }
  }

  function populateAnnotationSelection(start, end, text) {
    if (!annotationClaimStartEl || !annotationClaimEndEl || !annotationClaimTextEl) return;
    annotationClaimStartEl.value = String(start);
    annotationClaimEndEl.value = String(end);
    annotationClaimTextEl.value = text;
    updateSelectionMeta(start, end);
  }

  function captureAnnotationSelection() {
    if (!annotationParagraphSourceEl) return;
    const start = annotationParagraphSourceEl.selectionStart;
    const end = annotationParagraphSourceEl.selectionEnd;
    if (!Number.isInteger(start) || !Number.isInteger(end) || end <= start) {
      setAnnotationWarning('Select a non-empty text span in the paragraph source before saving.');
      return;
    }
    populateAnnotationSelection(start, end, annotationParagraphSourceEl.value.slice(start, end));
    setAnnotationWarning('');
  }

  function openAnnotationEditor(paragraphIndex, claimIndex = null) {
    if (!annotationDoc || !annotationEditorModal || !annotationParagraphSourceEl) return;

    const paragraph = getAnnotationParagraph(paragraphIndex);
    if (!paragraph) return;

    annotationParagraphSourceEl.value = paragraph.text || '';
    annotationParagraphIndexEl.value = String(paragraphIndex);
    annotationClaimIndexEl.value = claimIndex === null ? '' : String(claimIndex);
    annotationCanonicalIdsEl.value = '';
    annotationEvidenceSnippetEl.value = '';
    setAnnotationWarning('');
    updateSelectionMeta();

    if (claimIndex !== null && paragraph.claims?.[claimIndex]) {
      const claim = paragraph.claims[claimIndex];
      const grounded = getGroundedClaim(paragraph, claimIndex);
      populateAnnotationSelection(claim.start, claim.end, claim.text || '');
      annotationClaimTypeEl.value = claim.claim_type || annotationClaimTypeEl.value;
      annotationSupportClassEl.value = grounded?.support_class || 'unsupported';
      annotationCanonicalIdsEl.value = canonicalIdsToText(grounded?.canonical_ids || []);
      annotationEvidenceSnippetEl.value = grounded?.evidence_snippet || '';
      annotationEditorContextEl.textContent = `Paragraph ${paragraphIndex} · Editing claim ${claimIndex}`;
      annotationEditorModeLabelEl.textContent = 'Editing existing annotation';
      deleteAnnotationButton?.classList.remove('d-none');
      setTimeout(() => {
        annotationParagraphSourceEl.focus();
        annotationParagraphSourceEl.setSelectionRange(claim.start, claim.end);
      }, 120);
    } else {
      annotationClaimStartEl.value = '';
      annotationClaimEndEl.value = '';
      annotationClaimTextEl.value = '';
      if (annotationClaimTypeEl?.querySelector('option[value="listing"]')) {
        annotationClaimTypeEl.value = 'listing';
      }
      if (annotationSupportClassEl?.querySelector('option[value="unsupported"]')) {
        annotationSupportClassEl.value = 'unsupported';
      }
      annotationEditorContextEl.textContent = `Paragraph ${paragraphIndex} · New annotation`;
      annotationEditorModeLabelEl.textContent = 'New annotation';
      deleteAnnotationButton?.classList.add('d-none');
      setTimeout(() => annotationParagraphSourceEl.focus(), 120);
    }

    annotationEditorModal.show();
  }

  async function saveAnnotationChange() {
    const context = getEvalApiContext();
    if (!context) return;

    const paragraphIndex = Number(annotationParagraphIndexEl?.value || '');
    const claimIndexRaw = annotationClaimIndexEl?.value || '';
    const start = Number(annotationClaimStartEl?.value || '');
    const end = Number(annotationClaimEndEl?.value || '');
    const text = annotationClaimTextEl?.value || '';

    if (!Number.isInteger(paragraphIndex)) {
      setAnnotationWarning('Paragraph context is missing. Close the editor and try again.');
      return;
    }
    if (!Number.isInteger(start) || !Number.isInteger(end) || end <= start || !text) {
      setAnnotationWarning('Select a non-empty span from the paragraph source before saving.');
      return;
    }

    const payload = {
      start,
      end,
      text,
      claim_type: annotationClaimTypeEl?.value || '',
      support_class: annotationSupportClassEl?.value || 'unsupported',
      canonical_ids: parseCanonicalIdsInput(annotationCanonicalIdsEl?.value || ''),
      evidence_snippet: annotationEvidenceSnippetEl?.value || '',
    };

    const isEdit = claimIndexRaw !== '';
    const url = isEdit
      ? `${context.apiBase}/annotations/${context.model}/${context.qid}/${context.batch}/claims/${paragraphIndex}/${claimIndexRaw}`
      : `${context.apiBase}/annotations/${context.model}/${context.qid}/${context.batch}/claims/${paragraphIndex}`;

    if (saveAnnotationButton) {
      saveAnnotationButton.disabled = true;
      saveAnnotationButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    }
    if (deleteAnnotationButton) {
      deleteAnnotationButton.disabled = true;
    }
    setAnnotationWarning('');

    try {
      const response = await fetch(url, {
        method: isEdit ? 'PUT' : 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.error || `HTTP ${response.status}`);
      }
      window.location.reload();
    } catch (error) {
      setAnnotationWarning(error.message || 'Failed to save annotation.');
      if (saveAnnotationButton) {
        saveAnnotationButton.disabled = false;
        saveAnnotationButton.innerHTML = '<i class="bi bi-floppy"></i> Save Annotation';
      }
      if (deleteAnnotationButton) {
        deleteAnnotationButton.disabled = false;
      }
    }
  }

  async function deleteAnnotationChange() {
    const context = getEvalApiContext();
    if (!context) return;

    const paragraphIndex = Number(annotationParagraphIndexEl?.value || '');
    const claimIndexRaw = annotationClaimIndexEl?.value || '';
    if (!claimIndexRaw) return;

    if (!window.confirm('Delete this annotation from the manual override?')) {
      return;
    }

    if (deleteAnnotationButton) {
      deleteAnnotationButton.disabled = true;
    }
    if (saveAnnotationButton) {
      saveAnnotationButton.disabled = true;
    }
    setAnnotationWarning('');

    try {
      const response = await fetch(
        `${context.apiBase}/annotations/${context.model}/${context.qid}/${context.batch}/claims/${paragraphIndex}/${claimIndexRaw}`,
        {method: 'DELETE'}
      );
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.error || `HTTP ${response.status}`);
      }
      window.location.reload();
    } catch (error) {
      setAnnotationWarning(error.message || 'Failed to delete annotation.');
      if (deleteAnnotationButton) {
        deleteAnnotationButton.disabled = false;
      }
      if (saveAnnotationButton) {
        saveAnnotationButton.disabled = false;
      }
    }
  }

  async function resetManualAnnotations() {
    const context = getEvalApiContext();
    if (!context) return;
    if (!window.confirm('Restore the pristine generated annotations and remove all manual edit history for this run?')) {
      return;
    }

    try {
      await runToolbarRequest(
        restorePristineAnnotationsButton,
        `${context.apiBase}/annotations/${context.model}/${context.qid}/${context.batch}/restore`,
        {method: 'POST'},
        'Failed to restore the pristine annotations.'
      );
    } catch (error) {
      window.alert(error.message || 'Failed to restore the pristine annotations.');
    }
  }

  async function undoAnnotationChange() {
    const context = getEvalApiContext();
    if (!context) return;
    try {
      await runToolbarRequest(
        undoAnnotationChangeButton,
        `${context.apiBase}/annotations/${context.model}/${context.qid}/${context.batch}/undo`,
        {method: 'POST'},
        'Failed to undo the last annotation change.'
      );
    } catch (error) {
      window.alert(error.message || 'Failed to undo the last annotation change.');
    }
  }

  async function redoAnnotationChange() {
    const context = getEvalApiContext();
    if (!context) return;
    try {
      await runToolbarRequest(
        redoAnnotationChangeButton,
        `${context.apiBase}/annotations/${context.model}/${context.qid}/${context.batch}/redo`,
        {method: 'POST'},
        'Failed to redo the last annotation change.'
      );
    } catch (error) {
      window.alert(error.message || 'Failed to redo the last annotation change.');
    }
  }

  async function runToolbarRequest(button, url, options, fallbackMessage) {
    if (!button || button.disabled) {
      throw new Error(fallbackMessage);
    }

    const originalHtml = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

    try {
      const response = await fetch(url, options);
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.error || `HTTP ${response.status}`);
      }
      window.location.reload();
    } catch (error) {
      button.disabled = false;
      button.innerHTML = originalHtml;
      throw error;
    }
  }

  function handleAnnotationClaimActivation(element, event) {
    if (!annotationEditMode) {
      return false;
    }
    const paragraphEl = element.closest('.claim-paragraph');
    const paragraphIndex = Number(paragraphEl?.dataset.paragraphIndex || '');
    const claimIndex = Number(element.dataset.claimIdx || '');
    if (Number.isInteger(paragraphIndex) && Number.isInteger(claimIndex)) {
      event?.preventDefault();
      event?.stopPropagation();
      openAnnotationEditor(paragraphIndex, claimIndex);
      return true;
    }
    return false;
  }

  window.evalAnnotationEditor = {
    handleClaimActivation: handleAnnotationClaimActivation,
  };

  annotationEditToggle?.addEventListener('click', function () {
    setAnnotationEditMode(!annotationEditMode);
  });

  undoAnnotationChangeButton?.addEventListener('click', undoAnnotationChange);
  redoAnnotationChangeButton?.addEventListener('click', redoAnnotationChange);
  restorePristineAnnotationsButton?.addEventListener('click', resetManualAnnotations);
  captureAnnotationSelectionButton?.addEventListener('click', captureAnnotationSelection);
  saveAnnotationButton?.addEventListener('click', saveAnnotationChange);
  deleteAnnotationButton?.addEventListener('click', deleteAnnotationChange);

  annotationParagraphSourceEl?.addEventListener('select', function () {
    updateSelectionMeta(this.selectionStart, this.selectionEnd);
  });

  annotationEditorModalEl?.addEventListener('hidden.bs.modal', function () {
    if (saveAnnotationButton) {
      saveAnnotationButton.disabled = false;
      saveAnnotationButton.innerHTML = '<i class="bi bi-floppy"></i> Save Annotation';
    }
    if (deleteAnnotationButton) {
      deleteAnnotationButton.disabled = false;
    }
    setAnnotationWarning('');
  });

  document.querySelectorAll('.claim-paragraph').forEach(paragraphEl => {
    paragraphEl.addEventListener('click', function (event) {
      if (!annotationEditMode) return;
      if (event.target.closest('.claim') || event.target.closest('.claim-row') || event.target.closest('a') || event.target.closest('button')) {
        return;
      }
      const paragraphIndex = Number(this.dataset.paragraphIndex || '');
      if (!Number.isInteger(paragraphIndex)) return;
      event.preventDefault();
      openAnnotationEditor(paragraphIndex);
    });
  });
})();