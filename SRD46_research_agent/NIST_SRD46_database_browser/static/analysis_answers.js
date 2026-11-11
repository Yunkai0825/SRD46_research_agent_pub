/* Answer selection of the analysis results browser (matrix, compare, detail and web-answer pages).
 *
 * The ticked answers live in sessionStorage, so filtering the matrix, opening a run or
 * coming back from a compare view keeps them.  The page sets window.SRD46_ANSWERS =
 * {page, compareUrl, referenceUrl}; base.html's prefix helper (__pfx__) is honoured when
 * the browser is mounted under the master launcher.
 */
(function () {
  "use strict";
  var KEY = "srd46.analysis.answerSelection";
  var MATRIX_KEY = "srd46.analysis.matrixQuery";
  var cfg = window.SRD46_ANSWERS || {};
  var pfx = window.__pfx__ || function (u) { return u; };

  function load() { try { return JSON.parse(sessionStorage.getItem(KEY) || "[]"); } catch (e) { return []; } }
  function save(items) { try { sessionStorage.setItem(KEY, JSON.stringify(items)); } catch (e) { /* private mode */ } }
  function indexOf(items, id) { for (var i = 0; i < items.length; i++) { if (items[i].id === id) return i; } return -1; }

  function toggle(item, on) {
    var items = load(), i = indexOf(items, item.id);
    if (on && i < 0) items.push(item);
    else if (!on && i >= 0) items.splice(i, 1);
    save(items);
    render();
  }
  function clear() { save([]); render(); }

  function status(items) {
    if (!items.length) {
      return {text: "Tick answers to compare 2–3 of one prompt side by side, or tick one to set it as the reference answer.", compare: false, ref: false};
    }
    var pids = {}, n = 0;
    items.forEach(function (it) { if (!pids[it.pid || "?"]) { pids[it.pid || "?"] = true; n++; } });
    if (n > 1) {
      return {text: items.length + " selected across " + n + " prompts — compare needs answers of one prompt; the reference needs exactly one answer.", compare: false, ref: false};
    }
    if (items.length === 1) {
      return {text: "1 selected (" + items[0].pid + "): tick one or two more answers of " + items[0].pid + " to compare, or set this one as the reference.", compare: false, ref: true};
    }
    if (items.length <= 3) {
      return {text: items.length + " selected (" + items[0].pid + ") — ready to compare.", compare: true, ref: false};
    }
    return {text: items.length + " selected (" + items[0].pid + ") — compare shows at most 3: untick " + (items.length - 3) + ".", compare: false, ref: false};
  }

  function render() {
    var items = load(), ids = {};
    items.forEach(function (it) { ids[it.id] = true; });
    document.querySelectorAll("input.answer-pick").forEach(function (box) {
      box.checked = !!ids[box.dataset.id];
      var chip = box.closest(".answer-chip");
      if (chip) chip.classList.toggle("is-picked", box.checked);
    });
    var bar = document.getElementById("answer-selection-bar");
    if (!bar) return;
    var st = status(items);
    bar.classList.toggle("has-items", items.length > 0);
    bar.querySelector(".sel-text").textContent = st.text;
    var list = bar.querySelector(".sel-list");
    list.innerHTML = "";
    items.forEach(function (it) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "btn btn-sm btn-outline-secondary sel-item";
      b.title = "untick " + it.label;
      b.textContent = it.label + " ✕";
      b.addEventListener("click", function () { toggle(it, false); });
      list.appendChild(b);
    });
    bar.querySelector(".sel-compare").disabled = !st.compare;
    bar.querySelector(".sel-ref").disabled = !st.ref;
    bar.querySelector(".sel-clear").disabled = !items.length;
  }

  function compareUrl(items) {
    return pfx(cfg.compareUrl) + "?" + items.map(function (it) { return "a=" + encodeURIComponent(it.id); }).join("&");
  }

  function toast(text, kind) {
    var box = document.getElementById("answer-toast");
    if (!box) {
      box = document.createElement("div");
      box.id = "answer-toast";
      box.setAttribute("role", "status");
      document.body.appendChild(box);
    }
    box.className = "alert alert-" + (kind || "success") + " shadow";
    box.textContent = text;
    box.style.display = "block";
    clearTimeout(box._timer);
    box._timer = setTimeout(function () { box.style.display = "none"; }, 5000);
  }

  function setReference(pid, id, label, done) {
    if (!pid) { toast("This answer carries no prompt id, so it cannot be a reference.", "warning"); return; }
    fetch(pfx(cfg.referenceUrl) + encodeURIComponent(pid), {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({answer: id})
    }).then(function (response) {
      return response.json().then(function (data) {
        if (!response.ok) throw new Error(data.error || "could not save the reference");
        return data;
      });
    }).then(function (data) {
      var file = (data.file || "_answer_selection.json").split(/[\\\/]/).pop();
      toast(id ? (pid + " reference → " + label + " (saved in " + file + ")") : (pid + ": reference cleared"));
      if (done) done(data);
    }).catch(function (error) { toast(error.message, "danger"); });
  }

  function wire() {
    document.querySelectorAll("input.answer-pick").forEach(function (box) {
      box.addEventListener("change", function () {
        toggle({id: box.dataset.id, pid: box.dataset.pid, label: box.dataset.label}, box.checked);
      });
    });
    // The whole chip toggles the tick; only its text opens the answer.
    document.querySelectorAll(".answer-chip").forEach(function (chip) {
      chip.addEventListener("click", function (ev) {
        if (ev.target.closest("a") || ev.target.tagName === "INPUT") return;
        var box = chip.querySelector("input.answer-pick");
        if (!box) return;
        box.checked = !box.checked;
        box.dispatchEvent(new Event("change"));
      });
    });
    var bar = document.getElementById("answer-selection-bar");
    if (bar) {
      bar.querySelector(".sel-compare").addEventListener("click", function () { window.location.href = compareUrl(load()); });
      bar.querySelector(".sel-clear").addEventListener("click", clear);
      bar.querySelector(".sel-ref").addEventListener("click", function () {
        var it = load()[0];
        if (!it) return;
        setReference(it.pid, it.id, it.label, function () { clear(); window.location.reload(); });
      });
    }
    document.querySelectorAll("[data-set-reference]").forEach(function (el) {
      var handler = function () {
        var id = el.getAttribute("data-set-reference") || null;   // "" clears the reference
        if (!id && !window.confirm("Clear the reference answer of " + el.dataset.pid + "?")) { render(); return; }
        setReference(el.dataset.pid, id, el.dataset.label || "", function () { window.location.reload(); });
      };
      el.addEventListener(el.tagName === "INPUT" ? "change" : "click", handler);
    });
    document.querySelectorAll("[data-row-compare]").forEach(function (button) {
      button.addEventListener("click", function () {
        var row = button.closest("tr"), picked = [];
        row.querySelectorAll("td.answer-cell").forEach(function (cell) {
          var box = cell.querySelector("input.answer-pick");   // the newest answer of the column
          if (box && picked.length < 3) picked.push({id: box.dataset.id, pid: box.dataset.pid, label: box.dataset.label});
        });
        if (picked.length < 2) { toast("This prompt has fewer than two answers in the visible columns.", "warning"); return; }
        save(picked);
        window.location.href = compareUrl(picked);
      });
    });
    document.querySelectorAll("select[data-jump]").forEach(function (select) {
      select.addEventListener("change", function () { if (select.value) window.location.href = pfx(select.value); });
    });
    // Filters apply as soon as they change; text boxes apply on Enter.
    document.querySelectorAll("form[data-autosubmit] select, form[data-autosubmit] input[type=checkbox], form[data-autosubmit] input[type=radio]").forEach(function (el) {
      el.addEventListener("change", function () { el.form.submit(); });
    });
    // Live row filter of the matrix while typing (the same box filters server-side on Enter).
    var live = document.getElementById("matrix-live-filter");
    if (live) {
      var apply = function () {
        var needle = live.value.trim().toLowerCase(), shown = 0;
        document.querySelectorAll("tr[data-row-text]").forEach(function (tr) {
          var hit = !needle || tr.dataset.rowText.indexOf(needle) >= 0;
          tr.style.display = hit ? "" : "none";
          if (hit) shown++;
        });
        var counter = document.getElementById("matrix-row-count");
        if (counter) counter.textContent = shown;
      };
      live.addEventListener("input", apply);
      apply();
    }
    var fullToggle = document.getElementById("full-toggle");
    if (fullToggle) {
      fullToggle.addEventListener("change", function () {
        document.getElementById("compare-row").classList.toggle("compare-full", fullToggle.checked);
        try {
          var url = new URL(window.location.href);
          if (fullToggle.checked) url.searchParams.set("full", "1"); else url.searchParams.delete("full");
          window.history.replaceState(null, "", url.toString());
        } catch (e) { /* ignore */ }
      });
    }
    // The matrix tab returns to the last matrix view (its filters) from other pages.
    if (cfg.page === "matrix") {
      try { sessionStorage.setItem(MATRIX_KEY, window.location.search); } catch (e) { /* ignore */ }
    } else {
      var query = "";
      try { query = sessionStorage.getItem(MATRIX_KEY) || ""; } catch (e) { /* ignore */ }
      if (query) {
        document.querySelectorAll("a[data-matrix-link]").forEach(function (a) {
          a.setAttribute("href", a.getAttribute("href").split("?")[0] + query);
        });
      }
    }
    render();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
  else wire();
})();
