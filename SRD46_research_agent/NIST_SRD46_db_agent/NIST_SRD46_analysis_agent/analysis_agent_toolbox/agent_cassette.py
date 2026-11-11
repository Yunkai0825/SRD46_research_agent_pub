"""agent_cassette.py — record/replay LLM calls for deterministic agent reruns.

The lowest I/O boundary inside the ReAct loop is
:meth:`ArgoClient.call`, which sends one prompt and returns one
response string.  All branching, tool dispatch, memory bookkeeping,
and hooks happen *deterministically* in Python around it.  By taping
the inputs and outputs of every ``client.call(...)`` we can later
replay the full agent turn (including hooks, tool calls, validation
loops, compaction) **without ever calling Argo**.

Two cooperating subclasses
--------------------------

* :class:`RecordingArgoClient` — wraps a real
  :class:`SRD46AnalysisClient` (or any ``ArgoClient``).  Forwards each
  ``.call()`` to the underlying transport and appends one JSONL line
  per call to a cassette file.  Each line stores the full
  ``(system, prompt, stop, model, response, elapsed_s)`` plus content
  hashes so we can detect divergence on replay.

* :class:`ReplayArgoClient` — eagerly loads a cassette and serves the
  recorded responses in the order they were recorded.  Matches
  ``(system_hash, prompt_hash, stop, model)`` of the live call against
  the next cassette entry; on mismatch raises
  :class:`CassetteMismatchError` with a dump of the first divergent
  bytes so the test driver can pinpoint what changed.

Convenience helpers
-------------------

* :func:`open_cassette` — context manager that yields the right client
  for the requested mode (``"record"``, ``"replay"``, ``"off"``) and
  flushes the cassette on exit.
* :func:`client_from_env` — picks mode from environment variables
  ``SRD46_AGENT_CASSETTE_MODE`` / ``SRD46_AGENT_CASSETTE_PATH``.

Cassette format
---------------

JSONL.  One header line followed by N call lines:

    {"_kind": "header", "version": 1, "created_at": "...", "label": "..."}
    {"_kind": "call", "idx": 0, "model": "...", "stop": [...],
     "system_hash": "sha256:...", "prompt_hash": "sha256:...",
     "system": "...", "prompt": "...", "response": "...",
     "elapsed_s": 1.23}
    {"_kind": "call", "idx": 1, ...}
    ...

The full ``system`` and ``prompt`` strings are stored (not just
hashes) so the cassette is self-describing and can be inspected /
hand-edited.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, List, Optional

from ...general_db_query_engine.general_argo_engine_helpers._argo_engine_entry_point import ArgoClient


CASSETTE_VERSION = 1


# ════════════════════════════════════════════════════════════════════
#  Errors
# ════════════════════════════════════════════════════════════════════

class CassetteError(RuntimeError):
    """Base class for all cassette-replay problems."""


class CassetteExhaustedError(CassetteError):
    """Replay was asked for more calls than the cassette contains."""


class CassetteMismatchError(CassetteError):
    """Live call diverged from the recorded call at the same index."""


# ════════════════════════════════════════════════════════════════════
#  Hashing
# ════════════════════════════════════════════════════════════════════

def _sha(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _diff_excerpt(a: str, b: str, *, ctx: int = 80) -> str:
    """Return a human-readable excerpt around the first differing char."""
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    if i == n and len(a) == len(b):
        return "(strings are equal)"
    lo = max(0, i - ctx)
    hi = min(max(len(a), len(b)), i + ctx)
    return (
        f"first diff @ char {i} (live len={len(a)}, recorded len={len(b)}):\n"
        f"  live    : ...{a[lo:hi]!r}...\n"
        f"  recorded: ...{b[lo:hi]!r}..."
    )


# ════════════════════════════════════════════════════════════════════
#  Recording client
# ════════════════════════════════════════════════════════════════════

@dataclass
class RecordingArgoClient(ArgoClient):
    """Drop-in subclass that tapes every ``.call()`` into a cassette file.

    Construct via :meth:`from_client` to inherit configuration from an
    existing live client (model, tier, retries, etc.) without
    duplicating constructor arguments.
    """

    cassette_path: Optional[Path] = None
    label:         str            = ""

    # internals
    _entries:      List[dict]     = field(default_factory=list, repr=False)
    _opened:       bool           = field(default=False, repr=False)

    @classmethod
    def from_client(
        cls,
        live: ArgoClient,
        *,
        cassette_path: str | Path,
        label: str = "",
    ) -> "RecordingArgoClient":
        return cls(
            model=live.model,
            temperature=live.temperature,
            top_p=live.top_p,
            max_tokens=live.max_tokens,
            stop=list(live.stop),
            max_retries=live.max_retries,
            retry_backoff=live.retry_backoff,
            http_timeout=live.http_timeout,
            api_url=live.api_url,
            api_user=live.api_user,
            _tier=getattr(live, "_tier", ""),
            cassette_path=Path(cassette_path),
            label=label,
        )

    def _ensure_open(self) -> None:
        if self._opened or self.cassette_path is None:
            return
        self.cassette_path.parent.mkdir(parents=True, exist_ok=True)
        header = {
            "_kind":      "header",
            "version":    CASSETTE_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "label":      self.label,
            "model":      self.model,
            "tier":       getattr(self, "_tier", ""),
        }
        with self.cassette_path.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps(header, ensure_ascii=False) + "\n")
        self._opened = True

    def call(
        self,
        prompt: str,
        system: str,
        *,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        model: str | None = None,
    ) -> str:
        self._ensure_open()
        t0 = time.time()
        # Use the parent .call() so the actual HTTP transport runs.
        response = ArgoClient.call(
            self, prompt, system,
            max_tokens=max_tokens, stop=stop, model=model,
        )
        elapsed = time.time() - t0

        eff_stop  = list(stop) if stop is not None else list(self.stop)
        eff_model = model or self.model

        entry = {
            "_kind":       "call",
            "idx":         len(self._entries),
            "model":       eff_model,
            "stop":        eff_stop,
            "max_tokens":  max_tokens or self.max_tokens,
            "system_hash": _sha(system),
            "prompt_hash": _sha(prompt),
            "system":      system,
            "prompt":      prompt,
            "response":    response,
            "elapsed_s":   round(elapsed, 4),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        self._entries.append(entry)
        if self.cassette_path is not None:
            with self.cassette_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return response

    def n_recorded(self) -> int:
        return len(self._entries)


# ════════════════════════════════════════════════════════════════════
#  Replay client
# ════════════════════════════════════════════════════════════════════

@dataclass
class ReplayArgoClient(ArgoClient):
    """ArgoClient that returns recorded responses instead of calling Argo.

    Construct via :meth:`from_cassette`.  Replay matches the live call
    against ``cassette[next_idx]`` by ``(system_hash, prompt_hash,
    stop, model)``.  On mismatch raises :class:`CassetteMismatchError`
    with a diff excerpt so the caller can see what changed.
    """

    cassette_path: Optional[Path] = None
    strict_hash:   bool           = True
    _cursor:       int            = field(default=0, repr=False)
    _entries:      List[dict]     = field(default_factory=list, repr=False)
    _header:       Optional[dict] = field(default=None, repr=False)

    @classmethod
    def from_cassette(
        cls,
        cassette_path: str | Path,
        *,
        strict_hash: bool = True,
        live_template: ArgoClient | None = None,
    ) -> "ReplayArgoClient":
        path = Path(cassette_path)
        entries: List[dict] = []
        header: Optional[dict] = None
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if obj.get("_kind") == "header":
                    header = obj
                elif obj.get("_kind") == "call":
                    entries.append(obj)
        if header is None:
            raise CassetteError(f"no header found in cassette {path}")
        if header.get("version") != CASSETTE_VERSION:
            raise CassetteError(
                f"cassette {path} has version {header.get('version')!r}; "
                f"expected {CASSETTE_VERSION}"
            )

        # Inherit model / tier defaults from header so logging stays sane.
        kwargs: dict = {}
        if live_template is not None:
            kwargs.update(
                model=live_template.model,
                temperature=live_template.temperature,
                top_p=live_template.top_p,
                max_tokens=live_template.max_tokens,
                stop=list(live_template.stop),
                _tier=getattr(live_template, "_tier", ""),
            )
        else:
            kwargs.update(
                model=header.get("model") or "",
                _tier=header.get("tier", "") + "-replay",
            )
        return cls(
            cassette_path=path,
            strict_hash=strict_hash,
            _entries=entries,
            _header=header,
            **kwargs,
        )

    def call(
        self,
        prompt: str,
        system: str,
        *,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        model: str | None = None,
    ) -> str:
        if self._cursor >= len(self._entries):
            raise CassetteExhaustedError(
                f"cassette {self.cassette_path} has {len(self._entries)} "
                f"calls; live agent asked for call #{self._cursor}"
            )
        entry = self._entries[self._cursor]
        idx   = self._cursor
        self._cursor += 1

        if self.strict_hash:
            problems: List[str] = []
            live_sys_hash = _sha(system)
            live_pmt_hash = _sha(prompt)
            if live_sys_hash != entry["system_hash"]:
                problems.append("system_hash")
            if live_pmt_hash != entry["prompt_hash"]:
                problems.append("prompt_hash")
            eff_stop  = list(stop) if stop is not None else list(self.stop)
            eff_model = model or self.model
            if eff_stop != entry.get("stop", []):
                problems.append(f"stop (live={eff_stop!r}, "
                                f"recorded={entry.get('stop')!r})")
            if eff_model != entry.get("model"):
                problems.append(f"model (live={eff_model!r}, "
                                f"recorded={entry.get('model')!r})")
            if problems:
                detail = []
                if "system_hash" in problems:
                    detail.append("SYSTEM " + _diff_excerpt(
                        system, entry.get("system", "")))
                if "prompt_hash" in problems:
                    detail.append("PROMPT " + _diff_excerpt(
                        prompt, entry.get("prompt", "")))
                raise CassetteMismatchError(
                    f"replay mismatch at call #{idx} ({', '.join(problems)}):\n"
                    + "\n".join(detail)
                )
        return entry["response"]

    def remaining(self) -> int:
        return len(self._entries) - self._cursor


# ════════════════════════════════════════════════════════════════════
#  High-level helpers
# ════════════════════════════════════════════════════════════════════

@contextlib.contextmanager
def open_cassette(
    *,
    mode: str,
    cassette_path: str | Path,
    live_client: Optional[ArgoClient] = None,
    label: str = "",
    strict_hash: bool = True,
) -> Iterator[ArgoClient]:
    """Yield a cassette-aware ArgoClient.

    Parameters
    ----------
    mode
        ``"record"``    — wrap ``live_client`` in
        :class:`RecordingArgoClient`.
        ``"replay"``    — load cassette, return
        :class:`ReplayArgoClient`.
        ``"off"``       — pass ``live_client`` straight through.
    cassette_path
        Where to write/read the JSONL cassette.
    live_client
        Required for ``record`` and ``off``.  Optional template for
        ``replay`` (used to copy logging tier).
    label
        Free-text tag stored in the cassette header.
    strict_hash
        Enforce ``(system, prompt, stop, model)`` match on replay.
    """
    mode = (mode or "off").lower()
    cassette_path = Path(cassette_path)
    if mode == "off":
        if live_client is None:
            raise CassetteError("mode='off' requires a live_client")
        yield live_client
        return
    if mode == "record":
        if live_client is None:
            raise CassetteError("mode='record' requires a live_client")
        rec = RecordingArgoClient.from_client(
            live_client, cassette_path=cassette_path, label=label,
        )
        try:
            yield rec
        finally:
            rec._ensure_open()  # ensure header even if no calls happened
        return
    if mode == "replay":
        rep = ReplayArgoClient.from_cassette(
            cassette_path,
            strict_hash=strict_hash,
            live_template=live_client,
        )
        yield rep
        return
    raise CassetteError(f"unknown cassette mode: {mode!r}")


def client_from_env(
    *,
    live_client_factory,
    default_cassette_path: str | Path,
    label: str = "",
) -> "contextlib.AbstractContextManager[ArgoClient]":
    """Return an ``open_cassette(...)`` context driven by env vars.

    Reads:

    * ``SRD46_AGENT_CASSETTE_MODE`` — ``record``/``replay``/``off``
      (default ``off``).
    * ``SRD46_AGENT_CASSETTE_PATH`` — overrides
      ``default_cassette_path``.
    * ``SRD46_AGENT_CASSETTE_STRICT`` — ``"0"`` to disable hash check
      on replay (default strict).

    ``live_client_factory`` is a zero-arg callable that returns a real
    :class:`ArgoClient`.  In replay mode it is **not invoked**, so this
    helper is safe to call when no Argo credentials are present.
    """
    mode = os.environ.get("SRD46_AGENT_CASSETTE_MODE", "off").lower()
    path = os.environ.get("SRD46_AGENT_CASSETTE_PATH", str(default_cassette_path))
    strict = os.environ.get("SRD46_AGENT_CASSETTE_STRICT", "1") != "0"
    live = live_client_factory() if mode in ("record", "off") else None
    return open_cassette(
        mode=mode,
        cassette_path=path,
        live_client=live,
        label=label,
        strict_hash=strict,
    )


__all__ = [
    "CASSETTE_VERSION",
    "CassetteError",
    "CassetteExhaustedError",
    "CassetteMismatchError",
    "RecordingArgoClient",
    "ReplayArgoClient",
    "open_cassette",
    "client_from_env",
]
