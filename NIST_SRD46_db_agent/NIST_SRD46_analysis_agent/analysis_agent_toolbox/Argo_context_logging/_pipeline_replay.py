"""Replay tool — re-run pipeline stages with simulated agent output.

Reads a ``pipeline_transcript.jsonl`` produced by
:mod:`_pipeline_transcript` and re-executes selected pieces of the
pipeline while *replaying* the recorded LLM responses instead of
issuing new Argo calls.  This lets you debug a deterministic stage
(e.g. ``run_lc2_4`` validator, ``wrap_run_calculation`` plotting) over and
over without spending API budget.

Three modes are supplied (composable):

1. ``mock_argo(transcript_path)`` — context manager that monkey-patches
   ``ArgoClient.call`` so it returns the next recorded response from
   the transcript instead of hitting the API.  Matches by exact
   ``(system, prompt)`` tuple first, then falls back to FIFO order.

2. ``replay_py_call(transcript_path, function, *, occurrence=0)`` —
   look up a recorded ``py_call`` for a deterministic wrapper (e.g.
   ``wrap_run_calculation``) and re-invoke it with the recorded
   ``args``/``kwargs``.  Useful for re-running L3 plotting after
   tweaking the plotter without paying for the L0/L1/L2 chain again.

3. ``replay_l0(transcript_path, *, session_dir, prompt=None)`` — full
   end-to-end replay of an L0 run with all LLM calls served from the
   transcript.  ``prompt`` defaults to the user message extracted from
   the first ``agent_turn_start`` record.

CLI examples::

    # Re-run the L3 calculation step from the recorded inputs:
    python -m NIST_SRD46_db_agent.NIST_SRD46_analysis_agent\
        .analysis_agent_orchestration._pipeline_replay py-call \
        path/to/pipeline_transcript.jsonl wrap_run_calculation \
        --output-dir /tmp/replay_l3

    # Replay the full L0 turn with mocked LLM responses:
    python -m ... _pipeline_replay l0 \
        path/to/pipeline_transcript.jsonl --session-dir /tmp/replay_l0
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import logging
import sys
from collections import deque
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterable, List, Optional, Tuple

log = logging.getLogger("pipeline_replay")


# ── Transcript loader ────────────────────────────────────────────

def load_transcript(path: Path | str) -> List[Dict[str, Any]]:
    """Read a JSONL transcript into a list of dicts."""
    p = Path(path)
    out: List[Dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                log.warning("skip malformed line %d: %s", len(out) + 1, exc)
    return out


def filter_records(records: Iterable[Dict[str, Any]], kind: str,
                   **filters: Any) -> List[Dict[str, Any]]:
    """Return records of ``kind`` matching all key=value filters."""
    out = []
    for r in records:
        if r.get("kind") != kind:
            continue
        if any(r.get(k) != v for k, v in filters.items()):
            continue
        out.append(r)
    return out


# ── Mode 1: mock_argo (replay LLM calls) ─────────────────────────

class _LLMReplayQueue:
    """FIFO queue of recorded LLM responses with prompt/system lookup.

    Tries an exact ``(system, prompt)`` lookup first (so the first
    matching recorded call wins); falls back to strict FIFO order if
    the live caller's prompt diverges from the recording.
    """

    def __init__(self, records: List[Dict[str, Any]]):
        # Preserve order; allow consumed entries to be re-found by key
        # when the live caller repeats a prompt (rare but possible).
        self._fifo: Deque[Dict[str, Any]] = deque()
        self._by_key: Dict[Tuple[str, str], Deque[Dict[str, Any]]] = {}
        for rec in records:
            if rec.get("kind") != "llm_call":
                continue
            self._fifo.append(rec)
            key = (rec.get("system", "") or "", rec.get("prompt", "") or "")
            self._by_key.setdefault(key, deque()).append(rec)

    def total(self) -> int:
        return len(self._fifo)

    def remaining(self) -> int:
        return sum(1 for r in self._fifo if not r.get("_consumed"))

    def consume(self, system: str, prompt: str) -> Tuple[Optional[str], Dict[str, Any]]:
        """Return (response_text, matched_record) for one call."""
        key = (system or "", prompt or "")
        bucket = self._by_key.get(key)
        if bucket:
            while bucket:
                rec = bucket.popleft()
                if rec.get("_consumed"):
                    continue
                rec["_consumed"] = True
                return rec.get("response"), rec
        # FIFO fallback
        while self._fifo:
            rec = self._fifo.popleft()
            if rec.get("_consumed"):
                continue
            rec["_consumed"] = True
            return rec.get("response"), rec
        return None, {}


@contextlib.contextmanager
def mock_argo(transcript_path: Path | str,
              *,
              strict: bool = False,
              fallback: Optional[Callable[[str, str], str]] = None):
    """Context manager: replay LLM calls from *transcript_path*.

    Parameters
    ----------
    strict : bool
        If True, raise when the queue is exhausted.  Otherwise calls
        ``fallback`` (default: returns an empty string and logs).
    fallback : callable, optional
        ``fallback(system, prompt) -> str`` invoked when the queue is
        exhausted.  Use this to plug in a real Argo call for the
        residual messages.
    """
    records = load_transcript(transcript_path)
    queue = _LLMReplayQueue(records)
    log.info("mock_argo: %d recorded LLM calls in %s",
             queue.total(), transcript_path)

    mod = importlib.import_module(
        "NIST_SRD46_db_agent.general_db_query_engine."
        "general_argo_engine_helpers.argo_client_caller"
    )
    cls = mod.ArgoClient
    original_call = cls.call

    def replay_call(self, prompt, system, **kwargs):
        response, rec = queue.consume(system, prompt)
        if response is None:
            msg = (f"replay queue exhausted; tier={getattr(self, '_tier', '')}, "
                   f"prompt_len={len(prompt)}, system_len={len(system)}")
            if strict:
                raise RuntimeError(msg)
            log.warning(msg)
            if fallback is not None:
                return fallback(system, prompt)
            return ""
        if rec.get("system") != system or rec.get("prompt") != prompt:
            log.debug("replay diverged (FIFO match); recorded tier=%s, "
                      "live tier=%s",
                      rec.get("layer"), getattr(self, "_tier", ""))
        return response

    cls.call = replay_call  # type: ignore[method-assign]
    try:
        yield queue
    finally:
        cls.call = original_call  # type: ignore[method-assign]


# ── Mode 2: replay_py_call (re-run a deterministic wrapper) ──────

def _resolve_callable(qualname: str) -> Callable:
    """Resolve ``module.path.attr`` into a callable, after the recorder
    has had a chance to wrap it (so we get the wrapped version that
    keeps recording into the new sink)."""
    parts = qualname.split(".")
    # Try progressively shorter module paths.
    for split in range(len(parts) - 1, 0, -1):
        mod_path = ".".join(parts[:split])
        attr_path = parts[split:]
        try:
            mod = importlib.import_module(mod_path)
        except ImportError:
            continue
        obj: Any = mod
        ok = True
        for a in attr_path:
            if not hasattr(obj, a):
                ok = False
                break
            obj = getattr(obj, a)
        if ok and callable(obj):
            return obj
    raise LookupError(f"could not resolve callable {qualname}")


def find_py_calls(transcript_path: Path | str,
                  function: str) -> List[Dict[str, Any]]:
    """Return all ``py_call`` records whose ``function`` ends with
    *function* (so callers can pass a short name)."""
    records = load_transcript(transcript_path)
    out = []
    for r in records:
        if r.get("kind") != "py_call":
            continue
        fq = r.get("function", "")
        if fq == function or fq.endswith("." + function):
            out.append(r)
    return out


def replay_py_call(transcript_path: Path | str,
                   function: str,
                   *,
                   occurrence: int = 0,
                   override_kwargs: Optional[Dict[str, Any]] = None) -> Any:
    """Re-invoke *function* using the recorded args/kwargs.

    Parameters
    ----------
    function : str
        Either a fully-qualified ``module.path.func`` or just ``func``
        (matched against the trailing component of the recorded
        ``function`` field).
    occurrence : int
        Which recorded invocation to replay (0 = first).
    override_kwargs : dict, optional
        Replace specific recorded kwargs (useful e.g. to redirect
        ``output_dir`` to a fresh path).
    """
    matches = find_py_calls(transcript_path, function)
    if not matches:
        raise LookupError(f"no py_call recorded for {function!r}")
    if occurrence >= len(matches):
        raise IndexError(
            f"occurrence {occurrence} ≥ {len(matches)} recorded calls "
            f"for {function!r}")
    rec = matches[occurrence]
    fq = rec["function"]
    fn = _resolve_callable(fq)

    args = list(rec.get("args") or [])
    kwargs = dict(rec.get("kwargs") or {})
    if override_kwargs:
        kwargs.update(override_kwargs)

    log.info("replay_py_call: %s (occurrence=%d) "
             "with %d positional, %d keyword args",
             fq, occurrence, len(args), len(kwargs))
    return fn(*args, **kwargs)


# ── Mode 3: replay_l0 (full end-to-end with mocked LLMs) ─────────

def _extract_l0_prompt(records: List[Dict[str, Any]]) -> Optional[str]:
    """Pull the original L0 user message from the recorded session."""
    for r in records:
        if (r.get("kind") == "agent_turn_start"
                and (r.get("layer") or "").startswith("L0")):
            return r.get("user_message")
    # Fallback: any agent_turn_start.
    for r in records:
        if r.get("kind") == "agent_turn_start":
            return r.get("user_message")
    return None


def replay_l0(transcript_path: Path | str,
              *,
              session_dir: Path | str,
              prompt: Optional[str] = None,
              debug: bool = True,
              record_replay: bool = True) -> Any:
    """Re-run :func:`L0_orchestrator.run` with all LLM calls replayed.

    Parameters
    ----------
    session_dir : Path
        Where to write the new session artefacts (NOT the original).
    prompt : str, optional
        User message; defaults to the one captured in the transcript.
    record_replay : bool
        Also install the transcript recorder for the new session so
        the replayed run produces a fresh JSONL — useful for diffing
        deterministic outputs against the original.
    """
    records = load_transcript(transcript_path)
    if prompt is None:
        prompt = _extract_l0_prompt(records)
    if not prompt:
        raise ValueError("could not infer L0 prompt; pass --prompt explicitly")

    sess = Path(session_dir)
    sess.mkdir(parents=True, exist_ok=True)

    if record_replay:
        from . import _pipeline_transcript
        _pipeline_transcript.install(sess, filename="pipeline_transcript_replay.jsonl")

    from ...analysis_agent_orchestration.L0_orchestrator import run as run_l0
    with mock_argo(transcript_path):
        return run_l0(prompt, session_dir=sess, debug=debug)


# ── CLI ──────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="_pipeline_replay",
        description=(
            "Replay pipeline stages from a recorded "
            "pipeline_transcript.jsonl without re-issuing LLM calls."
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_index = sub.add_parser(
        "index", help="Print a one-line summary of every record.")
    p_index.add_argument("transcript", type=Path)

    p_py = sub.add_parser(
        "py-call",
        help="Re-run a recorded deterministic Python wrapper "
             "(e.g. wrap_run_calculation).")
    p_py.add_argument("transcript", type=Path)
    p_py.add_argument("function",
                      help="short name (run_lc2_4) or fully-qualified path")
    p_py.add_argument("--occurrence", type=int, default=0)
    p_py.add_argument("--set", action="append", default=[],
                      metavar="KEY=VALUE",
                      help="override a kwarg (repeatable); VALUE is JSON")

    p_l0 = sub.add_parser(
        "l0",
        help="Replay the full L0 turn, mocking all LLM calls.")
    p_l0.add_argument("transcript", type=Path)
    p_l0.add_argument("--session-dir", type=Path, required=True)
    p_l0.add_argument("--prompt", default=None,
                      help="override prompt (default: from transcript)")
    p_l0.add_argument("--no-record", action="store_true",
                      help="do not install a recorder for the replayed run")
    return p


def _parse_overrides(items: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"bad --set {item!r}; expected KEY=VALUE")
        k, v = item.split("=", 1)
        try:
            out[k] = json.loads(v)
        except json.JSONDecodeError:
            out[k] = v  # treat as raw string
    return out


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    args = _build_parser().parse_args(argv)

    if args.cmd == "index":
        for r in load_transcript(args.transcript):
            tag = (r.get("tool") or r.get("function") or r.get("model") or "")
            print(f"{r.get('seq', '?'):>4} {r.get('layer', ''):<14} "
                  f"{r.get('kind', ''):<22} {tag}")
        return 0

    if args.cmd == "py-call":
        result = replay_py_call(
            args.transcript, args.function,
            occurrence=args.occurrence,
            override_kwargs=_parse_overrides(args.set),
        )
        print(json.dumps({"ok": True, "result_repr": repr(result)[:2000]},
                         indent=2))
        return 0

    if args.cmd == "l0":
        result = replay_l0(
            args.transcript,
            session_dir=args.session_dir,
            prompt=args.prompt,
            record_replay=not args.no_record,
        )
        if isinstance(result, dict):
            print(json.dumps({k: (v if isinstance(v, (int, float, str, bool, list, dict)) else repr(v))
                              for k, v in result.items()},
                             indent=2, default=str)[:4000])
        else:
            print(repr(result)[:4000])
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
