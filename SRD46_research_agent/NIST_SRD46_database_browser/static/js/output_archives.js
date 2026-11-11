/* Output files are readable while they remain in their ZIP archives. */
(() => {
  async function status() {
    const response = await fetch('/output-archives/status', {cache: 'no-store'});
    if (!response.ok) throw new Error('Could not check output archives.');
    return response.json();
  }
  async function start() {
    const state = await status();
    if (state.check_state === 'checking') {
      setTimeout(() => start().catch(error => console.error('Output archives:', error)), 500);
      return;
    }
    if (state.check_state === 'failed') throw new Error(state.check_error);
    if (!state.needs_unpack) return;
    const key = 'srd46-output-archives-startup';
    let seen = false;
    try { seen = localStorage.getItem(key) === state.startup; } catch (_) {}
    if (seen) return;
    const dialog = document.getElementById('output-archives-dialog');
    const text = document.getElementById('output-archives-message');
    const unpack = document.getElementById('output-archives-unpack');
    const keep = document.getElementById('output-archives-keep');
    text.textContent = `${state.missing_runs} archives have output files that are not unpacked. The browser reads ZIP files directly and prefers unpacked files when present. Unpack missing output files to disk? Existing files will be kept.`;
    function acknowledge() { try { localStorage.setItem(key, state.startup); } catch (_) {} }
    keep.onclick = () => { acknowledge(); dialog.close(); };
    dialog.addEventListener('cancel', acknowledge);
    async function monitor() {
      const current = await status();
      text.textContent = `${current.written} files unpacked; ${current.skipped} existing files kept. ${current.run || ''}`;
      if (current.state === 'running') {
        setTimeout(() => monitor().catch(showError), 1500);
      } else if (current.state === 'failed') {
        showError(new Error(current.error));
      } else {
        text.textContent += ' Extraction complete. Reload the page to refresh the results.';
        keep.textContent = 'Close';
        unpack.hidden = true;
      }
    }
    function showError(error) {
      text.textContent = error.message;
      unpack.disabled = false;
      keep.textContent = 'Close';
    }
    unpack.onclick = async () => {
      unpack.disabled = true;
      acknowledge();
      try {
        const response = await fetch('/output-archives/extract', {
          method: 'POST', headers: {'X-Archive-Startup': state.startup}
        });
        if (!response.ok) throw new Error('Could not start extraction.');
        keep.textContent = 'Continue browsing';
        await monitor();
      } catch (error) { showError(error); }
    };
    dialog.showModal();
    if (state.state === 'running') {
      unpack.disabled = true;
      keep.textContent = 'Continue browsing';
      await monitor();
    }
  }
  start().catch(error => console.error('Output archives:', error));
})();
