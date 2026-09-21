"""Untruncated pipeline transcript recorder.

Monkey-patches three categories of pipeline entry points so that every
inter-layer hand-off is captured to a JSONL file *before* any
truncation, compaction, or summarisation:

  1. **LLM round-trips** — every ``ArgoClient.call(prompt, system, ...)``
     records one ``llm_call`` event with the full ``system``, ``prompt``,
     ``response``, ``model``, ``elapsed_s`` and the originating ``_tier``.
  2. **ReAct tool dispatch** — every ``agent_turn`` invocation records a
     start / end pair plus one ``tool_call`` event per tool dispatch
     containing the full ``args`` and full ``result`` (captured *before*
     the engine's ``truncate_result`` shrinks it).
  3. **Deterministic Python wrappers** — ``_run_l2_chain``,
     ``run_l2_1_1``..``run_l2_2_2`` and the ``wrap_*`` calc wrappers each
     emit a ``py_call`` record with full ``args``/``kwargs``/result.

All records share the schema::

    {"seq": int, "ts": "...", "pid": int, "tid": int,
     "layer": str, "kind": str, ...}

Usage::

    from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent\
        .analysis_agent_orchestration._pipeline_transcript import install
    transcript_path = install(session_dir)

The installer is **idempotent** — calling :func:`install` again with
the same session merely re-points the JSONL sink; calling it with a
fresh session opens a new sink.  The first call is the one that
applies the monkey-patches.
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger("pipeline_transcript")

# ── Module-level state ────────────────────────────────────────────

_SINK: Dict[str, Any] = {
    "path": None,        # Path to current JSONL file
    "fh": None,          # open file handle (line-buffered)
    "lock": threading.Lock(),
    "seq": 0,
    "patched": False,
}

_DETERMINISTIC_TARGETS: List[Tuple[str, str, str]] = [
    # (module_path, attr_name, layer_label)
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_orchestration.L1_subagent.l1_subagent",
     "_run_l2_chain", "L1-chain"),
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_orchestration.L2_card_assembler."
     "L2_1_free_energy_card.l2_1_1_eq_map_validator",
     "run_l2_1_1", "L2_1_1"),
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_orchestration.L2_card_assembler."
     "L2_1_free_energy_card.l2_1_2_card_builder",
     "run_l2_1_2", "L2_1_2"),
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_orchestration.L2_card_assembler."
     "L2_1_free_energy_card.lc2_3_dedup_agent",
     "run_lc2_3", "LC2_3"),
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_orchestration.L2_card_assembler."
     "L2_1_free_energy_card.lc2_4_validator_agent",
     "run_lc2_4", "LC2_4"),
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_orchestration.L2_card_assembler."
     "L2_2_solver_para_card.l3_1_method_agent",
     "run_l3_1", "L3_1"),
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_orchestration.L2_card_assembler."
     "L2_2_solver_para_card.l2_2_2_sweep_designer_agent",
     "run_l2_2_2", "L2_2_2"),
    # calc-wrapper module — every wrap_* gets the same layer tag
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_toolbox.calc_wrappers",
     "wrap_build_or_load_ref_card", "calc_wrap"),
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_toolbox.calc_wrappers",
     "wrap_merge_ref_cards", "calc_wrap"),
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_toolbox.calc_wrappers",
     "wrap_enrich_card", "calc_wrap"),
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_toolbox.calc_wrappers",
     "wrap_parse_card", "calc_wrap"),
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_toolbox.calc_wrappers",
     "wrap_validate_calc_input", "calc_wrap"),
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_toolbox.calc_wrappers",
     "wrap_run_calculation", "calc_wrap"),
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_toolbox.calc_wrappers",
     "wrap_extract_topology", "calc_wrap"),
]

# Modules that re-import any of the deterministic targets *by name*.
# Each tuple is (importer_module_path, attr_name).  The patcher will
# also replace the binding in these modules so that a caller which did
# ``from .calc_wrappers import wrap_run_calculation`` sees the wrapped
# version too.
_DETERMINISTIC_REIMPORTERS: List[Tuple[str, str]] = [
    # L2_card_assembler package re-exports run_l2_1_1..run_l2_2_2
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_orchestration.L2_card_assembler", "run_l2_1_1"),
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_orchestration.L2_card_assembler", "run_l2_1_2"),
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_orchestration.L2_card_assembler", "run_lc2_3"),
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_orchestration.L2_card_assembler", "run_lc2_4"),
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_orchestration.L2_card_assembler", "run_l3_1"),
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_orchestration.L2_card_assembler", "run_l2_2_2"),
    # l1_subagent re-imports run_l2_1_1..run_l2_2_2 at module load
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_orchestration.L1_subagent.l1_subagent", "run_l2_1_1"),
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_orchestration.L1_subagent.l1_subagent", "run_l2_1_2"),
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_orchestration.L1_subagent.l1_subagent", "run_lc2_3"),
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_orchestration.L1_subagent.l1_subagent", "run_lc2_4"),
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_orchestration.L1_subagent.l1_subagent", "run_l3_1"),
    ("NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
     "analysis_agent_orchestration.L1_subagent.l1_subagent", "run_l2_2_2"),
]

# Modules that ``from ... import agent_turn`` at top level.  These must
# also be patched so the wrapped agent_turn is used by the L0/L1 layers.
_AGENT_TURN_REIMPORTERS: List[str] = [
    "NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
    "analysis_agent_orchestration.L0_orchestrator.orchestrator",
    "NIST_SRD46_db_agent.NIST_SRD46_analysis_agent."
    "analysis_agent_orchestration.L1_subagent.l1_subagent",
    # general engine entry point also re-exports it
    "NIST_SRD46_db_agent.general_db_query_engine."
    "general_argo_engine_helpers._argo_engine_entry_point",
    "NIST_SRD46_db_agent.general_db_query_engine."
    "general_argo_engine_helpers",
]


# ── Public API ────────────────────────────────────────────────────

def install(session_dir: Path | str,
            *,
            filename: str = "pipeline_transcript.jsonl") -> Path:
    """Activate the recorder for *session_dir*.

    On first call, monkey-patches ``ArgoClient.call``, ``agent_turn``
    and the deterministic ``run_l2_*`` / ``wrap_*`` functions.  On
    subsequent calls, just re-points the sink to a new JSONL file.

    Returns the absolute path to the JSONL sink.
    """
    session_dir = Path(session_dir)
    session_dir.mkdir(parents=True, exist_ok=True)
    new_path = session_dir / filename

    with _SINK["lock"]:
        # Close the previous sink (if any) before opening the new one.
        old_fh = _SINK["fh"]
        if old_fh is not None:
            try:
                old_fh.flush()
                old_fh.close()
            except Exception:  # noqa: BLE001
                pass
        _SINK["path"] = new_path
        _SINK["fh"] = open(new_path, "a", encoding="utf-8", buffering=1)
        _SINK["seq"] = 0

    _emit("install", layer="recorder", path=str(new_path),
          schema="pipeline_transcript/v1")

    if not _SINK["patched"]:
        _patch_argo_client()
        _patch_agent_turn()
        _patch_deterministic()
        _SINK["patched"] = True

    return new_path


def close() -> None:
    """Close the current sink (the patches stay installed)."""
    with _SINK["lock"]:
        fh = _SINK["fh"]
        if fh is not None:
            try:
                fh.flush()
                fh.close()
            except Exception:  # noqa: BLE001
                pass
        _SINK["fh"] = None
        _SINK["path"] = None


# ── Emit helper ───────────────────────────────────────────────────

def _emit(kind: str, **fields: Any) -> None:
    rec: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "pid": os.getpid(),
        "tid": threading.get_ident(),
        "kind": kind,
    }
    rec.update(fields)
    with _SINK["lock"]:
        _SINK["seq"] += 1
        rec["seq"] = _SINK["seq"]
        # Move seq to the front for readability.
        rec = {"seq": rec.pop("seq"), **rec}
        fh = _SINK["fh"]
        if fh is None:
            return
        try:
            fh.write(json.dumps(rec, default=_json_safe, ensure_ascii=False))
            fh.write("\n")
        except Exception as exc:  # noqa: BLE001
            log.error("transcript emit failed (kind=%s): %s", kind, exc)


def _json_safe(obj: Any) -> Any:
    """Best-effort serialisation for non-JSON-native objects."""
    if isinstance(obj, Path):
        return str(obj)
    if hasattr(obj, "to_dict"):
        try:
            return obj.to_dict()
        except Exception:  # noqa: BLE001
            pass
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items()
                if not k.startswith("_")}
    return repr(obj)


# ── Patch: ArgoClient.call ────────────────────────────────────────

def _patch_argo_client() -> None:
    try:
        mod = importlib.import_module(
            "NIST_SRD46_db_agent.general_db_query_engine."
            "general_argo_engine_helpers.argo_client_caller"
        )
    except ImportError as exc:
        log.warning("argo_client_caller import failed: %s", exc)
        return

    cls = getattr(mod, "ArgoClient", None)
    if cls is None or getattr(cls.call, "_transcript_wrapped", False):
        return

    original_call = cls.call

    def wrapped_call(self, prompt, system, **kwargs):
        layer = getattr(self, "_tier", "") or "argo"
        model = getattr(self, "model", "")
        t0 = time.time()
        err: Optional[str] = None
        response: Any = None
        try:
            response = original_call(self, prompt, system, **kwargs)
            return response
        except Exception as exc:  # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            _emit(
                "llm_call",
                layer=layer,
                model=model,
                system=system,
                prompt=prompt,
                response=response if isinstance(response, str) else _json_safe(response),
                error=err,
                elapsed_s=round(time.time() - t0, 3),
                kwargs={k: _json_safe(v) for k, v in kwargs.items()},
            )

    wrapped_call._transcript_wrapped = True  # type: ignore[attr-defined]
    cls.call = wrapped_call  # type: ignore[method-assign]


# ── Patch: agent_turn (ReAct loop entry) ──────────────────────────

def _patch_agent_turn() -> None:
    try:
        rl_mod = importlib.import_module(
            "NIST_SRD46_db_agent.general_db_query_engine."
            "general_argo_engine_helpers.engine_react_helpers.react_loop"
        )
    except ImportError as exc:
        log.warning("react_loop import failed: %s", exc)
        return

    original_agent_turn = getattr(rl_mod, "agent_turn", None)
    if original_agent_turn is None or getattr(
            original_agent_turn, "_transcript_wrapped", False):
        return

    def wrapped_agent_turn(user_message, **kwargs):
        # Tag layer from the client (if supplied).
        client = kwargs.get("client")
        layer = getattr(client, "_tier", "") if client is not None else ""

        # Wrap each tool so every dispatch is captured *before* truncation.
        tools = kwargs.get("tools")
        if isinstance(tools, dict):
            kwargs["tools"] = {
                name: _wrap_tool(name, fn, layer=layer or "tool")
                for name, fn in tools.items()
            }

        _emit(
            "agent_turn_start",
            layer=layer or "agent_turn",
            user_message=user_message,
            tool_names=sorted(list(tools.keys())) if isinstance(tools, dict) else [],
            client_model=getattr(client, "model", "") if client else "",
            is_subagent=bool(kwargs.get("is_subagent")),
        )
        t0 = time.time()
        err: Optional[str] = None
        result: Any = None
        try:
            result = original_agent_turn(user_message, **kwargs)
            return result
        except Exception as exc:  # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            _emit(
                "agent_turn_end",
                layer=layer or "agent_turn",
                error=err,
                elapsed_s=round(time.time() - t0, 3),
                final_answer=getattr(result, "answer", None),
                iterations=getattr(result, "iterations", None),
                tool_history_len=len(getattr(result, "tool_history", []) or []),
            )

    wrapped_agent_turn._transcript_wrapped = True  # type: ignore[attr-defined]
    rl_mod.agent_turn = wrapped_agent_turn  # type: ignore[attr-defined]

    # Replace re-imported bindings so callers see the wrapped version.
    for mod_path in _AGENT_TURN_REIMPORTERS:
        try:
            m = importlib.import_module(mod_path)
        except ImportError:
            continue
        if hasattr(m, "agent_turn"):
            setattr(m, "agent_turn", wrapped_agent_turn)


def _wrap_tool(name: str, fn: Callable, *, layer: str) -> Callable:
    if getattr(fn, "_transcript_wrapped", False):
        return fn

    def wrapped(*args, **kwargs):
        t0 = time.time()
        err: Optional[str] = None
        result: Any = None
        try:
            result = fn(*args, **kwargs)
            return result
        except Exception as exc:  # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            _emit(
                "tool_call",
                layer=layer,
                tool=name,
                args=[_json_safe(a) for a in args],
                kwargs={k: _json_safe(v) for k, v in kwargs.items()},
                result=_json_safe(result),
                error=err,
                elapsed_s=round(time.time() - t0, 3),
            )

    wrapped._transcript_wrapped = True  # type: ignore[attr-defined]
    # Preserve simple metadata used by the engine introspection.
    for attr in ("__name__", "__doc__", "__qualname__"):
        try:
            setattr(wrapped, attr, getattr(fn, attr))
        except Exception:  # noqa: BLE001
            pass
    return wrapped


# ── Patch: deterministic Python wrappers ──────────────────────────

def _patch_deterministic() -> None:
    # First, wrap the source-of-truth functions.
    wrapped_by_key: Dict[Tuple[str, str], Callable] = {}
    for mod_path, attr, layer in _DETERMINISTIC_TARGETS:
        try:
            mod = importlib.import_module(mod_path)
        except ImportError as exc:
            log.warning("deterministic import failed (%s): %s", mod_path, exc)
            continue
        original = getattr(mod, attr, None)
        if original is None:
            continue
        if getattr(original, "_transcript_wrapped", False):
            wrapped_by_key[(attr, mod_path)] = original
            continue
        wrapped = _wrap_py_call(original, layer=layer,
                                qualname=f"{mod_path}.{attr}")
        setattr(mod, attr, wrapped)
        wrapped_by_key[(attr, mod_path)] = wrapped

    # Now propagate to re-importers (modules that did
    # ``from … import run_l2_1_4`` etc. at load time).
    for mod_path, attr in _DETERMINISTIC_REIMPORTERS:
        try:
            m = importlib.import_module(mod_path)
        except ImportError:
            continue
        # Find any wrapped entry whose attr matches.
        for (w_attr, _src), wrapped_fn in wrapped_by_key.items():
            if w_attr == attr and hasattr(m, attr):
                setattr(m, attr, wrapped_fn)


def _wrap_py_call(fn: Callable, *, layer: str, qualname: str) -> Callable:
    def wrapped(*args, **kwargs):
        t0 = time.time()
        err: Optional[str] = None
        result: Any = None
        try:
            result = fn(*args, **kwargs)
            return result
        except Exception as exc:  # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            _emit(
                "py_call",
                layer=layer,
                function=qualname,
                args=[_json_safe(a) for a in args],
                kwargs={k: _json_safe(v) for k, v in kwargs.items()},
                result=_json_safe(result),
                error=err,
                elapsed_s=round(time.time() - t0, 3),
            )

    wrapped._transcript_wrapped = True  # type: ignore[attr-defined]
    for attr in ("__name__", "__doc__", "__qualname__", "__module__"):
        try:
            setattr(wrapped, attr, getattr(fn, attr))
        except Exception:  # noqa: BLE001
            pass
    return wrapped


# ── Self-test ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="transcript_selftest_"))
    p = install(tmp)
    print(f"sink -> {p}")
    _emit("test_event", layer="self-test", value=42, msg="hello")
    close()
    print(p.read_text(encoding="utf-8"))
