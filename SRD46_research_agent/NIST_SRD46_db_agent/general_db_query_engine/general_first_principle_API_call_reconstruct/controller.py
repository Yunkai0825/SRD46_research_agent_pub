"""Strict event replay with a single authorization-defined live boundary.

This module does not construct agent prompts, select scientific evidence or
retry failed work. Native code supplies requests and explicitly replayable
operations. Saved results pass through that same native code on reconstruction.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
import hashlib
import inspect
import json
from pathlib import Path
import re
import sys
import threading
import time
from types import ModuleType
from typing import Any, Callable, Iterator

from .transport import RecordedResponse, authorization_denied
from .paths import display_path, filesystem_path
try:  # the package is loaded under several prefixes; its parent is always general_db_query_engine
    from ..general_checkpointing import replace_with_retry
except ImportError:  # pragma: no cover - a copy loaded without that parent package
    from NIST_SRD46_db_agent.general_db_query_engine.general_checkpointing import replace_with_retry

_RUNTIME_KEY = "_general_first_principle_reconstruction_runtime_v1"
# LC2 and L0 load this package under different prefixes. Keep one controller,
# signal class identity and ContextVars even when Python loads both aliases.
_runtime = sys.modules.setdefault(_RUNTIME_KEY, ModuleType(_RUNTIME_KEY))
if not hasattr(_runtime, "lock"):
    _runtime.lock = threading.RLock()
    _runtime.active = None
    _runtime.lane = ContextVar("first_principle_reconstruction_lane", default="")
    _runtime.parents = ContextVar("first_principle_reconstruction_parents", default=())

    class _ControlSignal(BaseException):
        """Must pass through native tools' ordinary Exception handlers."""

    class _AuthorizationInterrupted(_ControlSignal):
        pass

    class _BreakpointReached(_ControlSignal):
        pass

    class _ReconstructionMismatch(_ControlSignal):
        pass

    _runtime.AuthorizationInterrupted = _AuthorizationInterrupted
    _runtime.BreakpointReached = _BreakpointReached
    _runtime.ReconstructionMismatch = _ReconstructionMismatch

AuthorizationInterrupted = _runtime.AuthorizationInterrupted
BreakpointReached = _runtime.BreakpointReached
ReconstructionMismatch = _runtime.ReconstructionMismatch


def current_session() -> "ReconstructionSession | None":
    """Return the process session, including worker threads and module aliases."""
    return _runtime.active


def _bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    path = filesystem_path(path)
    temporary = path.with_name(path.name + ".writing")
    temporary.write_text(data, encoding="utf-8")
    replace_with_retry(temporary, path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _poison_on_mismatch(function):
    if inspect.iscoroutinefunction(function):
        @wraps(function)
        async def asynchronous(self, *args, **kwargs):
            try:
                return await function(self, *args, **kwargs)
            except ReconstructionMismatch:
                self._invalid = True
                raise
        return asynchronous
    @wraps(function)
    def wrapped(self, *args, **kwargs):
        try:
            return function(self, *args, **kwargs)
        except ReconstructionMismatch:
            self._invalid = True
            raise
    return wrapped


class ReconstructionSession:
    """Record or reconstruct one process-local run in a new ledger directory.

    ``path_bindings`` is an explicit sequence of (old_root, new_root) pairs.
    Only these declared path substrings are canonicalized for comparison; raw
    recorded request bytes remain unchanged. Other prompt differences fail.

    Named lanes preserve ordering within each agent while allowing independent
    agents to interleave differently. Unnamed historical calls retain their
    original global order. A replay mismatch never permits a live fallback.
    """

    def __init__(self, *, mode: str, output_dir: str | Path,
                 source_dir: str | Path | None = None,
                 stop_at_breakpoint: bool = False,
                 path_bindings: tuple = (),
                 resume_boundary: dict | None = None,
                 live_api_user: str | None = None, live_provider: dict | None = None):
        if mode not in {"regular", "reconstruction"}:
            raise ValueError("mode must be regular or reconstruction")
        if (mode == "reconstruction") != (source_dir is not None):
            raise ValueError("reconstruction requires source_dir; regular forbids it")
        if resume_boundary is not None:
            if mode != "reconstruction" or not isinstance(resume_boundary, dict):
                raise ValueError("an explicit resume boundary requires reconstruction")
            if (resume_boundary.get("kind") not in {
                    "planned_operation", "interrupted_http", "interrupted_operation", "restart_before_http"}
                    or type(resume_boundary.get("event_id")) is not int
                    or resume_boundary["event_id"] < 1):
                raise ValueError("invalid explicit resume boundary")
            if resume_boundary["kind"] not in {"interrupted_http", "restart_before_http"} and not resume_boundary.get("name"):
                raise ValueError("an operation boundary requires its recorded name")
            if resume_boundary["kind"] == "restart_before_http":
                digest = resume_boundary.get("request_sha256")
                if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                    raise ValueError("a request rewind requires its exact recorded request SHA-256")
        if live_api_user is not None and (
                not isinstance(live_api_user, str) or not live_api_user.strip()
                or live_api_user != live_api_user.strip()):
            raise ValueError("live_api_user must be a nonempty account name")
        self.live_api_user = live_api_user
        from .providers import validate_provider
        self.live_provider = validate_provider(live_provider)
        self.resume_boundary = json.loads(_bytes(resume_boundary)) if resume_boundary is not None else None
        self.mode = mode
        self.output_dir = display_path(output_dir).resolve()
        self.source_dir = display_path(source_dir).resolve() if source_dir is not None else None
        if self.source_dir is not None and (
            self.output_dir == self.source_dir
            or self.source_dir in self.output_dir.parents
            or self.output_dir in self.source_dir.parents
        ):
            raise ValueError("source and output must be separate, non-nested directories")
        self.stop_at_breakpoint = bool(stop_at_breakpoint)
        self.path_bindings = tuple((str(old), str(new)) for old, new in path_bindings)
        if any(not old or not new or old == new for old, new in self.path_bindings):
            raise ValueError("path bindings require distinct nonempty roots")
        self._lock = threading.RLock()
        self._sequence = 0
        self._records: list[dict] = []
        self._consumed: set[int] = set()
        self._active = False
        self._interrupted = False
        self._invalid = False
        self._operation_resume_claimed = False
        self._live = mode == "regular"
        self.live_started_monotonic: float | None = None
        self.live_clock_anchor: float | None = None
        self._boundary: dict | None = None
        self._source: list[dict] = []
        if self.source_dir is not None:
            self._load_source()

    @property
    def live(self) -> bool:
        return self._live

    @property
    def breakpoint(self) -> dict | None:
        return dict(self._boundary) if self._boundary else None

    def __enter__(self) -> "ReconstructionSession":
        with _runtime.lock:
            if _runtime.active is not None:
                raise RuntimeError("another reconstruction/recording session is active")
            if self._active:
                raise RuntimeError("session is already active")
            output_io = filesystem_path(self.output_dir)
            if output_io.exists() and any(output_io.iterdir()):
                raise FileExistsError("output ledger must be empty")
            output_io.mkdir(parents=True, exist_ok=True)
            (output_io / "calls").mkdir()
            (output_io / "operations").mkdir()
            _write_json(self.output_dir / "session.json", {
                "schema": "first-principle-reconstruction/v1", "mode": self.mode,
                "created": _now(), "source_dir": str(self.source_dir) if self.source_dir else None,
                "path_bindings": self.path_bindings,
                "stop_at_breakpoint": self.stop_at_breakpoint,
                "boundary": self._boundary,
                "credentials_headers_cookies_not_recorded": True,
                **({"live_api_user": self.live_api_user} if self.live_api_user is not None else {}),
                **({"live_provider": self.live_provider} if self.live_provider is not None else {}),
                **({"resume_boundary": self.resume_boundary} if self.resume_boundary is not None else {}),
            })
            if self.source_dir is not None:
                self._archive_source_provenance()
            self._active = True
            if self._live:
                self.live_started_monotonic = time.monotonic()
            _runtime.active = self
        return self

    def _archive_source_provenance(self) -> None:
        """Keep inherited evidence self-contained, separate from replay events.

        A completed operation may replace an entire nested agent/tool tree.
        Its original requests, responses and receipts remain available here,
        even though no executable child events enter the new replay stream.
        Content-addressed objects merge across generations without recursive
        copies of previous continuation folders.
        """
        assert self.source_dir is not None
        archive = self.output_dir / "inherited_provenance"
        objects = archive / "objects"
        filesystem_path(objects).mkdir(parents=True, exist_ok=True)
        rows: dict[tuple[str, str, str], dict] = {}

        def retain(path: Path, expected: str | None = None) -> str:
            path = filesystem_path(path)
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise ReconstructionMismatch("inherited provenance cannot contain links")
            try:
                data = path.read_bytes()
            except OSError as exc:
                raise ReconstructionMismatch("inherited provenance artifact is missing") from exc
            digest = _sha(data)
            if expected is not None and digest != expected:
                raise ReconstructionMismatch("inherited provenance artifact changed")
            target = filesystem_path(objects / digest)
            if not target.exists():
                target.write_bytes(data)
            elif _sha(target.read_bytes()) != digest:
                raise ReconstructionMismatch("inherited provenance object checksum mismatch")
            return digest

        previous = self.source_dir / "inherited_provenance" / "manifest.json"
        if filesystem_path(previous).is_file():
            inherited = json.loads(filesystem_path(previous).read_text(encoding="utf-8"))
            if inherited.get("schema") != "reconstruction-inherited-provenance/v1":
                raise ReconstructionMismatch("unsupported inherited provenance schema")
            for row in inherited.get("files", []):
                digest = str(row.get("sha256", ""))
                if not re.fullmatch(r"[a-f0-9]{64}", digest):
                    raise ReconstructionMismatch("invalid inherited provenance object address")
                retain(previous.parent / "objects" / digest, digest)
                rows[(row["source_identity"], row["path"], digest)] = dict(row)

        source_files: list[Path] = []
        for folder in ("calls", "operations"):
            directory = self.source_dir / folder
            if filesystem_path(directory).is_dir():
                source_files.extend(directory / path.name for path in filesystem_path(directory).iterdir()
                                    if path.is_file() and path.suffix in {".json", ".txt"})
        for name in ("session.json", "events.jsonl", "breakpoint.json", "exit.json",
                     "analysis_run.json", "capture_contract.json"):
            path = self.source_dir / name
            if filesystem_path(path).is_file():
                source_files.append(path)
        if not filesystem_path(self.source_dir / "session.json").is_file():
            source_files.extend(self.source_dir / path.name for path in filesystem_path(self.source_dir).iterdir()
                                if path.is_file() and any(path.name.endswith(suffix)
                                for suffix in (".request.json", ".response.txt", ".receipt.json")))
        identities = sorted((path.relative_to(self.source_dir).as_posix(), retain(path))
                            for path in source_files)
        source_identity = _sha(_bytes(identities))
        for relative, digest in identities:
            row = {"source_identity": source_identity, "path": relative,
                   "sha256": digest, "bytes": filesystem_path(objects / digest).stat().st_size}
            rows[(source_identity, relative, digest)] = row
        _write_json(archive / "manifest.json", {
            "schema": "reconstruction-inherited-provenance/v1",
            "historical_provenance_only": True,
            "not_executable_replay_events": True,
            "files": [rows[key] for key in sorted(rows)],
        })

    def __exit__(self, exc_type, exc, tb) -> bool:
        with _runtime.lock:
            _write_json(self.output_dir / "exit.json", {
                "finished": _now(), "live": self._live,
                "interrupted": self._interrupted,
                "invalid_reconstruction": self._invalid,
                "consumed_source_records": sorted(self._consumed),
                "exception_type": exc_type.__name__ if exc_type else None,
            })
            if _runtime.active is self:
                _runtime.active = None
            self._active = False
        return False

    @contextmanager
    def lane(self, name: str) -> Iterator[None]:
        if not isinstance(name, str) or not name:
            raise ValueError("lane name must be a nonempty string")
        token = _runtime.lane.set(name)
        try:
            yield
        finally:
            _runtime.lane.reset(token)

    def _canonical(self, value: Any) -> Any:
        if isinstance(value, str):
            # Both spellings map to the same explicit placeholder. Do not
            # normalize numbers, whitespace, clocks or arbitrary prompt text.
            for index, (old, new) in enumerate(self.path_bindings):
                marker = f"<RECONSTRUCTION_PATH_{index}>"
                for old_form, new_form in self._path_forms(old, new):
                    value = value.replace(old_form, marker).replace(new_form, marker)
            return value
        if isinstance(value, list):
            return [self._canonical(item) for item in value]
        if isinstance(value, dict):
            return {key: self._canonical(item) for key, item in value.items()}
        return value

    def canonicalize(self, value: Any) -> Any:
        """Canonicalize only the explicitly declared relocation bindings."""
        return self._canonical(value)

    def rebind(self, value: Any) -> Any:
        """Relocate recorded path strings while retaining original source bytes."""
        if isinstance(value, str):
            for old, new in self.path_bindings:
                for old_form, new_form in self._path_forms(old, new):
                    value = value.replace(old_form, new_form)
            return value
        if isinstance(value, list):
            return [self.rebind(item) for item in value]
        if isinstance(value, dict):
            return {key: self.rebind(item) for key, item in value.items()}
        return value

    @staticmethod
    def _path_forms(old: str, new: str) -> list[tuple[str, str]]:
        # Paths appear directly in prompts, inside JSON tool arguments, and
        # inside a JSON response envelope containing those arguments. These
        # are representations of the declared roots, not additional bindings.
        result = [(old, new)]
        for _ in range(2):
            old = json.dumps(old, ensure_ascii=False)[1:-1]
            new = json.dumps(new, ensure_ascii=False)[1:-1]
            if (old, new) not in result:
                result.append((old, new))
        return sorted(result, key=lambda pair: len(pair[0]), reverse=True)

    @_poison_on_mismatch
    def recorded_operation_lane(self, name: str, arguments: Any) -> str | None:
        """Resolve an agent's recorded lane after explicit path relocation.

        Only the next unconsumed event in each lane may match. Identical
        sequential entries use original order; callers must reject concurrent
        indistinguishable agents rather than guessing which owns which state.
        """
        self._ensure_active()
        if self._live:
            return None
        with self._lock:
            next_by_lane: dict[str, dict] = {}
            for row in self._source:
                if row["id"] not in self._consumed:
                    next_by_lane.setdefault(row.get("lane", ""), row)
            actual = _bytes(self._canonical(arguments))
            candidates = [row for row in next_by_lane.values()
                          if row["kind"] == "operation" and row.get("name") == name
                          and _bytes(self._canonical(row.get("arguments"))) == actual]
            if not candidates:
                raise ReconstructionMismatch("no recorded agent entry matches this initial context")
            return min(candidates, key=lambda row: row["start_sequence"]).get("lane", "")

    def _ensure_active(self) -> None:
        if not self._active or _runtime.active is not self:
            raise RuntimeError("use ReconstructionSession as a context manager")
        if self._invalid:
            raise ReconstructionMismatch("session stopped after a reconstruction mismatch")
        if self._interrupted:
            raise AuthorizationInterrupted("session stopped at authorization denial")

    def reject(self, reason: str) -> None:
        """Stop every lane when an integration detects unreconstructable state."""
        self._invalid = True
        raise ReconstructionMismatch(reason)

    def _event(self, event: str, **values: Any) -> int:
        with self._lock:
            self._sequence += 1
            row = {"sequence": self._sequence, "event": event, "time": _now(), **values}
            with filesystem_path(self.output_dir / "events.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                stream.flush()
            return self._sequence

    def _begin(self, kind: str, lane: str, **values: Any) -> dict:
        with self._lock:
            values = json.loads(_bytes(values))
            recorded_wall = values.pop("recorded_wall_time", None)
            if recorded_wall is None:
                recorded_wall = (
                    self.live_clock_anchor + max(0.0, time.monotonic() - self.live_started_monotonic)
                    if self.live_clock_anchor is not None and self.live_started_monotonic is not None
                    else time.time()
                )
            metadata = {"parent_ids": list(_runtime.parents.get()),
                        "started": _now(), "wall_time": recorded_wall}
            seq = self._event("started", kind=kind, lane=lane, **metadata, **values)
            record = {"id": seq, "kind": kind, "lane": lane, "start_sequence": seq,
                      **metadata, **values}
            self._records.append(record)
            return record

    def _finish(self, record: dict, **values: Any) -> None:
        with self._lock:
            record.update(values)
            record["end_sequence"] = self._event("completed", id=record["id"], **values)
            folder = "calls" if record["kind"] == "http" else "operations"
            _write_json(self.output_dir / folder / f"{record['id']:06d}.receipt.json", record)

    def _load_source(self) -> None:
        if self.resume_boundary is not None:
            self._load_explicit_source()
            return
        assert self.source_dir is not None
        root = self.source_dir
        if filesystem_path(root / "session.json").is_file():
            meta = json.loads(filesystem_path(root / "session.json").read_text(encoding="utf-8"))
            if meta.get("schema") != "first-principle-reconstruction/v1":
                raise ReconstructionMismatch("unsupported reconstruction ledger schema")
            for folder in ("calls", "operations"):
                for receipt in sorted(filesystem_path(root / folder).glob("*.receipt.json")):
                    row = json.loads(receipt.read_text(encoding="utf-8"))
                    row["_folder"] = str(root / folder)
                    self._source.append(row)
            journal = root / "events.jsonl"
            if not filesystem_path(journal).is_file():
                raise ReconstructionMismatch("source event journal is missing")
            events = [json.loads(line) for line in filesystem_path(journal).read_text(encoding="utf-8").splitlines() if line]
            starts = {row["sequence"] for row in events if row.get("event") == "started"}
            receipts = {row["id"] for row in self._source}
            if starts != receipts or len(receipts) != len(self._source):
                raise ReconstructionMismatch("source has missing, duplicate or uncommitted event receipts")
            if [row.get("sequence") for row in events] != list(range(1, len(events) + 1)):
                raise ReconstructionMismatch("source event journal order is invalid")
            for receipt in self._source:
                started = events[receipt["start_sequence"] - 1]
                ended = events[receipt["end_sequence"] - 1]
                if (receipt["end_sequence"] <= receipt["start_sequence"]
                        or started.get("event") != "started"
                        or ended.get("event") != "completed"
                        or ended.get("id") != receipt["id"]):
                    raise ReconstructionMismatch("source event boundaries differ from receipts")
                for event in (started, ended):
                    for key, value in event.items():
                        if key not in {"event", "sequence", "time"} and receipt.get(key) != value:
                            raise ReconstructionMismatch("source event journal and receipt disagree")
        else:
            # Read-only compatibility with the existing passive HTTP capture.
            for receipt in sorted(filesystem_path(root).glob("*.receipt.json")):
                old = json.loads(receipt.read_text(encoding="utf-8"))
                if old.get("schema") != "srd46-native-argo-http-attempt/v1":
                    continue
                attempt = int(old["attempt"])
                row = dict(old, id=attempt, kind="http", lane="", transport="argo",
                           start_sequence=attempt * 2, end_sequence=attempt * 2 + 1,
                           parent_ids=[], _folder=str(root))
                self._source.append(row)
        if not self._source:
            raise ReconstructionMismatch("source contains no recorded execution")
        self._source.sort(key=lambda row: row["start_sequence"])
        denied: list[dict] = []
        for row in sorted(self._source, key=lambda item: item["end_sequence"]):
            if row["kind"] != "http":
                continue
            if not row.get("request_file") or not row.get("response_file"):
                # A transport exception is replayable only if its type was
                # preserved. It is never an authorization boundary.
                if row.get("exception_type") and row.get("request_file"):
                    self._request_payload(row)
                    if not isinstance(row.get("exception_message"), str):
                        raise ReconstructionMismatch("recorded transport failure lacks its exact message")
                    continue
                raise ReconstructionMismatch("source HTTP record lacks request or response")
            self._request_payload(row)
            response = self._read_verified(row, "response").decode("utf-8")
            if authorization_denied(row["http_status"], response):
                denied.append(row)
                break
        if not denied:
            raise ReconstructionMismatch("source has no authorization-denied API return")
        self._boundary = min(denied, key=lambda row: row["end_sequence"])
        cutoff = self._boundary["end_sequence"]
        # Never consume later quota-contaminated requests or tool outcomes.
        self._source = [row for row in self._source if row["start_sequence"] <= cutoff]

    def _load_explicit_source(self) -> None:
        """Validate a declared planned/manual frontier without inferring success.

        Only the selected interrupted event and its enclosing operations may
        lack completion receipts. A saved HTTP response without a committed
        receipt remains ambiguous and is never silently submitted again.
        """
        root = self.source_dir
        declaration = self.resume_boundary
        meta = json.loads(filesystem_path(root / "session.json").read_text("utf-8"))
        if meta.get("schema") != "first-principle-reconstruction/v1":
            raise ReconstructionMismatch("explicit resume requires a native event ledger")
        events = [json.loads(line) for line in filesystem_path(root / "events.jsonl")
                  .read_text("utf-8").splitlines() if line]
        if [row.get("sequence") for row in events] != list(range(1, len(events) + 1)):
            raise ReconstructionMismatch("source event journal order is invalid")
        starts = {row["sequence"]: row for row in events if row.get("event") == "started"}
        finishes = {}
        for row in events:
            if row.get("event") == "completed":
                if row.get("id") not in starts or row["id"] in finishes:
                    raise ReconstructionMismatch("duplicate or orphan completed event")
                finishes[row["id"]] = row
            elif row.get("event") not in {
                    "started", "breakpoint_reached", "planned_stage_reached", "resume_boundary_reached"}:
                raise ReconstructionMismatch("unknown source journal event")
        selected = starts.get(declaration["event_id"])
        expected_kind = "http" if declaration["kind"] in {"interrupted_http", "restart_before_http"} else "operation"
        if (selected is None or selected.get("kind") != expected_kind
                or (expected_kind == "operation" and selected.get("name") != declaration["name"])):
            raise ReconstructionMismatch("explicit boundary does not match its recorded event")
        for event in starts.values():
            if event.get("kind") not in {"http", "operation"}:
                raise ReconstructionMismatch("unknown source event kind")
            parents = event.get("parent_ids", [])
            if not isinstance(parents, list) or len(set(parents)) != len(parents):
                raise ReconstructionMismatch("invalid operation ancestry")
            for index, parent_id in enumerate(parents):
                parent = starts.get(parent_id)
                if (parent is None or parent_id >= event["sequence"]
                        or parent.get("kind") != "operation"
                        or parent.get("parent_ids", []) != parents[:index]):
                    raise ReconstructionMismatch("invalid operation ancestry")
        permitted_open = {selected["sequence"], *selected.get("parent_ids", [])}
        receipts = {}
        for folder in ("calls", "operations"):
            for path in sorted(filesystem_path(root / folder).glob("*.receipt.json")):
                row = json.loads(path.read_text("utf-8"))
                event_id = row.get("id")
                if (event_id in receipts or event_id not in starts
                        or path.name != f"{event_id:06d}.receipt.json"):
                    raise ReconstructionMismatch("duplicate, orphan or misnamed source receipt")
                row["_folder"] = str(root / folder)
                receipts[event_id] = row
        rows = []
        for event_id, started in starts.items():
            finished = finishes.get(event_id)
            row = receipts.get(event_id)
            if row is None:
                if (declaration["kind"] == "planned_operation" or event_id not in permitted_open
                        or finished is not None):
                    raise ReconstructionMismatch("source has an uncommitted event outside the selected frontier")
                row = {key: value for key, value in started.items()
                       if key not in {"event", "sequence", "time"}}
                row.update(id=event_id, start_sequence=event_id, end_sequence=len(events) + 1,
                           status="interrupted", _uncommitted=True,
                           _folder=str(root / ("calls" if row["kind"] == "http" else "operations")))
                if row["kind"] == "http":
                    request = filesystem_path(root / "calls" / f"{event_id:06d}.request.json")
                    if filesystem_path(root / "calls" / f"{event_id:06d}.response.txt").exists():
                        raise ReconstructionMismatch("uncommitted HTTP response requires reconciliation")
                    try:
                        data = request.read_bytes()
                        json.loads(data)
                    except (OSError, ValueError) as exc:
                        raise ReconstructionMismatch("interrupted HTTP request is absent or invalid") from exc
                    expected = declaration.get("request_sha256") or started.get("request_sha256")
                    if expected is not None and expected != _sha(data):
                        raise ReconstructionMismatch("interrupted HTTP request checksum differs")
                    row.update(request_file=request.name, request_sha256=_sha(data))
                    logical = request.with_name(f"{event_id:06d}.logical_request.json")
                    if logical.is_file():
                        row.update(logical_request_file=logical.name,
                                   logical_request_sha256=_sha(logical.read_bytes()))
            else:
                if finished is None or row.get("start_sequence") != event_id:
                    raise ReconstructionMismatch("source receipt has no matching completed journal event")
                if row.get("end_sequence") != finished["sequence"] or row["end_sequence"] <= event_id:
                    raise ReconstructionMismatch("source event boundaries differ from receipts")
                if (row.get("kind") == "http") != (Path(row["_folder"]).name == "calls"):
                    raise ReconstructionMismatch("source receipt is in the wrong event directory")
                for event in (started, finished):
                    for key, value in event.items():
                        if key not in {"event", "sequence", "time"} and row.get(key) != value:
                            raise ReconstructionMismatch("source journal and receipt disagree")
                if row.get("status") == "interrupted" and event_id not in permitted_open:
                    raise ReconstructionMismatch("interrupted sibling is outside the selected frontier")
            if row["kind"] == "http":
                self._request_payload(row)
                if row.get("response_file"):
                    response = self._read_verified(row, "response").decode("utf-8")
                    if authorization_denied(row["http_status"], response):
                        raise ReconstructionMismatch("authorization denial requires the authorization policy")
                elif not row.get("_uncommitted") and not (
                        row.get("exception_type") and isinstance(row.get("exception_message"), str)):
                    raise ReconstructionMismatch("source HTTP failure lacks its exact outcome")
            elif row.get("status") in {"ok", "failed"}:
                self._read_verified(row, "result")
            elif row.get("status") != "interrupted":
                raise ReconstructionMismatch("unsupported operation state at manual frontier")
            rows.append(row)
        boundary = next(row for row in rows if row["id"] == declaration["event_id"])
        by_id = {row["id"]: row for row in rows}
        for row in rows:
            for parent_id in row.get("parent_ids", []):
                if (parent_id in finishes and row["id"] in finishes
                        and by_id[parent_id]["end_sequence"] <= row["end_sequence"]):
                    raise ReconstructionMismatch("child completion lies outside its parent operation")
        if declaration["kind"] == "planned_operation":
            if boundary.get("status") != "ok":
                raise ReconstructionMismatch("planned boundary must be a committed successful operation")
            for row in rows:
                if (row["start_sequence"] > boundary["end_sequence"] or
                        (row["end_sequence"] > boundary["end_sequence"] and
                         (row["id"] not in boundary.get("parent_ids", []) or row.get("status") != "interrupted"))):
                    raise ReconstructionMismatch("execution continued beyond the planned boundary")
        elif declaration["kind"] == "restart_before_http":
            # An explicit rewind is a branch from the intact, verified ledger.
            # Its old response and later work remain in that source, but are
            # never supplied to the reconstructed agent or restored workspace.
            if (boundary.get("status") != "response_received" or boundary.get("_uncommitted")
                    or boundary.get("request_sha256") != declaration["request_sha256"]):
                raise ReconstructionMismatch("request rewind requires the selected committed HTTP request")
            prefix = [row for row in rows if row["start_sequence"] <= boundary["start_sequence"]]
            for row in prefix:
                if (row["id"] != boundary["id"]
                        and row["end_sequence"] >= boundary["start_sequence"]
                        and row["id"] not in boundary.get("parent_ids", [])):
                    raise ReconstructionMismatch("request rewind crosses an unfinished sibling operation")
            rows = prefix
            boundary["end_sequence"] = boundary["start_sequence"]
        else:
            if boundary.get("status") != "interrupted":
                raise ReconstructionMismatch("manual boundary is not an interrupted event")
            # Completed children may follow an interrupted operation's start.
            # Preserve that entire committed prefix, never only its first row.
            boundary["end_sequence"] = len(events) + 1
        self._source = sorted(rows, key=lambda row: row["start_sequence"])
        self._boundary = boundary

    @property
    def current_lane(self) -> str:
        return _runtime.lane.get()

    def verified_source_records(self) -> list[dict]:
        """Return detached metadata for the already verified source prefix."""
        return json.loads(_bytes([{**{key: value for key, value in row.items()
                                     if not key.startswith("_")},
                                   "source_receipt_committed": not row.get("_uncommitted", False)}
                                  for row in self._source]))

    def verified_operation_result(self, event_id: int, *, rebind: bool = True) -> Any:
        row = next((row for row in self._source if row["id"] == event_id), None)
        if row is None or row["kind"] != "operation" or row.get("status") not in {"ok", "failed"}:
            raise ReconstructionMismatch("selected operation has no committed result")
        value = json.loads(self._read_verified(row, "result"))
        return self.rebind(value) if rebind else value

    def _explicit_crossover(self, row: dict) -> None:
        self._ensure_active()
        outstanding = [item["id"] for item in self._source
                       if item["id"] not in self._consumed]
        if outstanding:
            raise ReconstructionMismatch("explicit crossover has unconsumed prefix events")
        self._event("resume_boundary_reached", source_id=row["id"], lane=row.get("lane", ""),
                    boundary_kind=self.resume_boundary["kind"])
        if self.stop_at_breakpoint:
            raise BreakpointReached("explicit resume boundary reached; no live work performed")
        self._live = True
        self.live_started_monotonic = time.monotonic()
        self.live_clock_anchor = max(float(item.get("wall_time", 0)) for item in self._source)

    @_poison_on_mismatch
    def resume_operation(self, name: str, arguments: Any, live_call: Callable[[], Any], *,
                         restore: Callable[[Any], None] | None = None,
                         consume_completed_descendants: bool = False, lane: str = "") -> Any:
        """Cross only the explicitly selected native operation boundary.

        Interrupted operations must first be entered through ``operation``.
        To fast-forward completed descendants, the adapter's restore callback
        receives their verified records/results before they are consumed. It
        must validate and restore their native state. Siblings cannot be skipped.
        Planned callbacks instead receive the gate's saved snapshot.
        """
        self._ensure_active()
        if self.resume_boundary is None or self.resume_boundary["kind"] in {"interrupted_http", "restart_before_http"}:
            raise ReconstructionMismatch("no explicit operation boundary is selected")
        if self.live:
            raise ReconstructionMismatch("explicit resume boundary was already crossed")
        with self._lock:
            self._ensure_active()
            if self._operation_resume_claimed:
                raise ReconstructionMismatch("explicit operation continuation is already claimed")
            self._operation_resume_claimed = True
        row = self._boundary
        lane = lane or _runtime.lane.get()
        if (row.get("name") != name or row.get("lane", "") != lane
                or _bytes(self._canonical(arguments)) != _bytes(self._canonical(row["arguments"]))):
            raise ReconstructionMismatch("resume operation differs from the selected boundary")
        skippable = {row["id"]}
        if consume_completed_descendants and self.resume_boundary["kind"] == "interrupted_operation":
            skippable.update(item["id"] for item in self._source
                             if row["id"] in item.get("parent_ids", []))
        if any(item["id"] not in self._consumed and item["id"] not in skippable for item in self._source):
            raise ReconstructionMismatch("explicit crossover has unconsumed prefix events")
        if self.resume_boundary["kind"] == "planned_operation":
            self._match("operation", lane, arguments, name=name)
            value = self.verified_operation_result(row["id"])
            if value.get("has_snapshot"):
                if restore is None:
                    raise ReconstructionMismatch("planned boundary requires its native snapshot restorer")
                try:
                    restore(value["snapshot"])
                except Exception as exc:
                    raise ReconstructionMismatch("planned boundary state restoration failed") from exc
            record = self._begin("operation", lane, name=name, arguments=arguments,
                                 source_id=row["id"], recorded_wall_time=row.get("wall_time"))
            self._save_operation(record, value, replayed=True)
        elif row["id"] not in self._consumed:
            raise ReconstructionMismatch("enter the interrupted operation before its continuation seam")
        descendants = [item for item in self._source if item["id"] not in self._consumed
                       and row["id"] in item.get("parent_ids", [])]
        if consume_completed_descendants and descendants:
            if restore is None or self.resume_boundary["kind"] != "interrupted_operation":
                raise ReconstructionMismatch("completed descendants require a native restoration callback")
            if any(item.get("status") not in {"ok", "failed", "response_received", "transport_exception"}
                   for item in descendants):
                raise ReconstructionMismatch("cannot fast-forward an uncommitted descendant")
            saved = [{"record": {key: value for key, value in item.items() if not key.startswith("_")},
                      "value": self.verified_operation_result(item["id"])
                      if item["kind"] == "operation" else None} for item in descendants]
            try:
                restore(saved)
            except Exception as exc:
                raise ReconstructionMismatch("completed descendant state restoration failed") from exc
            self._consumed.update(item["id"] for item in descendants)
        self._explicit_crossover(row)
        return live_call()

    def _read_verified(self, row: dict, role: str) -> bytes:
        folder = Path(row["_folder"]).resolve()
        filename = row.get(f"{role}_file")
        if not isinstance(filename, str) or not row.get(f"{role}_sha256"):
            raise ReconstructionMismatch(f"recorded {role} receipt is incomplete")
        path = (folder / filename).resolve()
        if folder not in path.parents:
            raise ReconstructionMismatch("source artifact escapes its ledger folder")
        try:
            data = filesystem_path(path).read_bytes()
        except OSError as exc:
            raise ReconstructionMismatch("recorded artifact is missing") from exc
        if _sha(data) != row.get(f"{role}_sha256"):
            raise ReconstructionMismatch("recorded artifact checksum mismatch")
        return data

    def _request_payload(self, row: dict) -> Any:
        """Verify the sent request and the optional pre-account-switch request."""
        wire = json.loads(self._read_verified(row, "request"))
        if not row.get("logical_request_file"):
            return wire
        logical = json.loads(self._read_verified(row, "logical_request"))
        if (row.get("transport") != "argo" or not isinstance(wire, dict)
                or not isinstance(logical, dict) or set(wire) != set(logical)
                or not isinstance(wire.get("user"), str) or not wire["user"].strip()
                or not isinstance(logical.get("user"), str) or not logical["user"].strip()
                or _bytes({k: v for k, v in wire.items() if k != "user"})
                != _bytes({k: v for k, v in logical.items() if k != "user"})):
            raise ReconstructionMismatch("account switch changed more than the Argo user")
        return logical

    def _match(self, kind: str, lane: str, actual: Any, *, name: str = "") -> dict:
        with self._lock:
            pending = [row for row in self._source
                       if row["id"] not in self._consumed and row.get("lane", "") == lane]
            if not pending:
                raise ReconstructionMismatch(f"no recorded event remains in lane {lane!r}")
            row = pending[0]
            if row["kind"] != kind:
                raise ReconstructionMismatch(f"expected {row['kind']}, received {kind}")
            if name and row.get("name", row.get("transport", "")) != name:
                raise ReconstructionMismatch("recorded operation/transport differs")
            if kind == "http":
                expected = self._request_payload(row)
            else:
                expected = row["arguments"]
            if _bytes(self._canonical(actual)) != _bytes(self._canonical(expected)):
                raise ReconstructionMismatch(f"request/arguments differ at source event {row['id']}")
            self._consumed.add(row["id"])
            return row

    @_poison_on_mismatch
    def http_call(self, payload: Any, live_call: Callable[[], Any], *,
                  transport: str = "argo", lane: str = "",
                  send_payload: Callable[[Any], Any] | None = None,
                  request_timeout: float | None = None) -> Any:
        """Return the saved response or perform this exact request after denial."""
        self._ensure_active()
        lane = lane or _runtime.lane.get()
        # Validate serializability before either recording or performing I/O.
        _bytes(payload)
        source = None
        with self._lock:
            if not self._live:
                source = self._match("http", lane, payload, name=transport)
                assert self._boundary is not None
                if source["id"] == self._boundary["id"]:
                    if self.resume_boundary is not None:
                        if self.resume_boundary["kind"] not in {"interrupted_http", "restart_before_http"}:
                            raise ReconstructionMismatch("explicit boundary is not an HTTP call")
                        self._explicit_crossover(source)
                    else:
                        outstanding = [row["id"] for row in self._source
                                       if row["id"] not in self._consumed
                                       and row["end_sequence"] < self._boundary["end_sequence"]]
                        if outstanding:
                            raise ReconstructionMismatch(
                                "authorization crossover reached before other recorded lanes were replayed"
                            )
                        self._event("breakpoint_reached", source_id=source["id"], lane=lane)
                        if self.stop_at_breakpoint:
                            raise BreakpointReached("authorization breakpoint reached; no live call made")
                        self._live = True
                        self.live_started_monotonic = time.monotonic()
                        self.live_clock_anchor = source.get("wall_time")
                        if self.live_clock_anchor is None and source.get("started"):
                            self.live_clock_anchor = datetime.fromisoformat(source["started"]).timestamp()
                elif source["end_sequence"] >= self._boundary["end_sequence"]:
                    raise ReconstructionMismatch("source result was not committed before authorization denial")
        replay = source is not None and source["id"] != self._boundary["id"]
        wire_payload = payload
        if replay and source.get("logical_request_file"):
            # Keep the matched payload's path spelling. Only the physical
            # account may differ from the logical request in this ledger.
            source_wire = json.loads(self._read_verified(source, "request"))
            wire_payload = dict(payload, user=source_wire["user"])
        elif not replay and self.live_api_user is not None and transport == "argo":
            if not isinstance(payload, dict) or not isinstance(payload.get("user"), str):
                self.reject("live account switch requires an Argo request with a user")
            wire_payload = dict(payload, user=self.live_api_user)
            if wire_payload != payload and send_payload is None:
                self.reject("live account switch requires the native payload sender")
        record = self._begin("http", lane, transport=transport,
                             source_id=source["id"] if source else None,
                             recorded_wall_time=source.get("wall_time") if source else None)
        folder = self.output_dir / "calls"
        request_file = f"{record['id']:06d}.request.json"
        request_data = (json.dumps(wire_payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
        filesystem_path(folder / request_file).write_bytes(request_data)
        record.update(request_file=request_file, request_sha256=_sha(request_data))
        if _bytes(wire_payload) != _bytes(payload):
            logical_file = f"{record['id']:06d}.logical_request.json"
            logical_data = (json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
            filesystem_path(folder / logical_file).write_bytes(logical_data)
            record.update(logical_request_file=logical_file, logical_request_sha256=_sha(logical_data))
        started = time.monotonic()
        try:
            if replay:
                if source.get("exception_type"):
                    self._replay_exception(source["exception_type"],
                                           source.get("exception_message"),
                                           source.get("exception_args"))
                response = RecordedResponse(source["http_status"],
                                            self.rebind(self._read_verified(source, "response").decode("utf-8")))
            else:
                self._ensure_active()
                if self.live_provider is not None and transport == "argo":
                    from .providers import send_provider
                    provider = dict(self.live_provider)
                    if request_timeout is not None:
                        provider['timeout'] = request_timeout
                    response = send_provider(wire_payload, provider, self.output_dir)
                else:
                    response = send_payload(wire_payload) if send_payload is not None else live_call()
        except Exception as exc:
            exception_args = list(exc.args)
            try:
                _bytes(exception_args)
            except (TypeError, ValueError):
                # requests sometimes wraps an urllib3 exception object. Its
                # verbatim message remains the native caller's context input;
                # never serialize arbitrary Python objects or invent a summary.
                exception_args = None
            self._finish(record, status="transport_exception", replayed=replay,
                         exception_type=type(exc).__module__ + "." + type(exc).__qualname__,
                         exception_message=str(exc), exception_args=exception_args,
                         elapsed_s=time.monotonic() - started)
            raise
        response_text = response.text
        if not isinstance(response_text, str):
            raise ReconstructionMismatch("transport response text is not a string")
        response_file = f"{record['id']:06d}.response.txt"
        response_data = response_text.encode("utf-8")
        filesystem_path(folder / response_file).write_bytes(response_data)
        denied = authorization_denied(response.status_code, response_text)
        self._finish(record, status="response_received", replayed=replay,
                     response_file=response_file, response_sha256=_sha(response_data),
                     http_status=int(response.status_code), authorization_denied=denied,
                     elapsed_s=time.monotonic() - started)
        if denied:
            with self._lock:
                self._interrupted = True
                if not filesystem_path(self.output_dir / "breakpoint.json").exists():
                    _write_json(self.output_dir / "breakpoint.json", record)
            raise AuthorizationInterrupted(f"authorization denied at recorded API event {record['id']}")
        self._ensure_active()
        return response

    @staticmethod
    def _replay_exception(type_name: str, message: str | None,
                          arguments: list | None) -> None:
        import requests
        allowed = {
            "requests.exceptions.ReadTimeout": requests.ReadTimeout,
            "requests.exceptions.ConnectTimeout": requests.ConnectTimeout,
            "requests.exceptions.Timeout": requests.Timeout,
            "requests.exceptions.ConnectionError": requests.ConnectionError,
            "requests.exceptions.HTTPError": requests.HTTPError,
        }
        cls = allowed.get(type_name)
        if cls is None:
            raise ReconstructionMismatch(f"unsupported recorded transport exception {type_name}")
        if not isinstance(message, str):
            raise ReconstructionMismatch("recorded transport failure lacks its exact message")
        exception = cls(*arguments) if isinstance(arguments, list) else cls(message)
        if str(exception) != message:
            exception = cls(message)
        if str(exception) != message:
            raise ReconstructionMismatch("recorded transport failure text cannot be reproduced")
        raise exception

    def _restored_worker_events(self, source: dict, contexts: list[dict]) -> list[int]:
        """Account for historical thread workers whose contextvars were absent.

        Only exact saved initial contexts in a restored operation snapshot may
        bind a detached lane. Every event of that lane must be committed and
        entirely enclosed by the restored operation. Timing alone is not proof.
        """
        covered = []
        for context in contexts:
            matches = [row for row in self._source
                       if row.get("name") == "runtime.agent_enter"
                       and not row.get("parent_ids")
                       and source["start_sequence"] < row["start_sequence"] < source["end_sequence"]
                       and _bytes(self._canonical(row["arguments"])) == _bytes(self._canonical(context))]
            if len(matches) > 1:
                raise ReconstructionMismatch("restored worker context has ambiguous ownership")
            if not matches:
                continue  # Native parent-linked or already-collapsed worker.
            entry = matches[0]
            lane = [row for row in self._source if row.get("lane") == entry.get("lane")]
            entries = [row for row in lane if row.get("name") == "runtime.agent_enter"]
            if len(entries) != 1 or min(row["start_sequence"] for row in lane) != entry["id"]:
                raise ReconstructionMismatch("restored worker lane has multiple or misplaced agent entries")
            if any(row.get("parent_ids")
                   or not (source["start_sequence"] < row["start_sequence"] < row["end_sequence"] < source["end_sequence"])
                   or row.get("status") not in {"ok", "failed", "response_received", "transport_exception"}
                   or (row["kind"] == "operation" and row.get("name") not in {"runtime.agent_enter", "runtime.clock"})
                   for row in lane):
                raise ReconstructionMismatch("restored worker lane exceeds its verified snapshot")
            covered.extend(row["id"] for row in lane)
        return sorted(set(covered))

    @_poison_on_mismatch
    def operation(self, name: str, arguments: Any, live_call: Callable[[], Any], *,
                  snapshot: Callable[[], Any] | None = None,
                  restore: Callable[[Any], None] | None = None,
                  restored_agent_contexts: Callable[[Any], list[dict]] | None = None,
                  lane: str = "") -> Any:
        """Replay an explicitly registered operation and its saved state.

        Results and snapshots must be JSON-safe. An operation containing the
        breakpoint re-enters its native body; completed children replay until
        the denied request. No Python pickle or arbitrary loader is executed.
        """
        self._ensure_active()
        lane = lane or _runtime.lane.get()
        _bytes(arguments)
        source = None
        if not self._live:
            source = self._match("operation", lane, arguments, name=name)
            assert self._boundary is not None
            if source.get("status") in {"ok", "failed"} and source["end_sequence"] < self._boundary["end_sequence"]:
                value = self.rebind(json.loads(self._read_verified(source, "result")))
                if value.get("has_snapshot"):
                    if restore is None:
                        raise ReconstructionMismatch("recorded state requires a restore callback")
                    try:
                        restore(value["snapshot"])
                    except Exception as exc:
                        raise ReconstructionMismatch("recorded state could not be restored") from exc
                covered = []
                if restored_agent_contexts is not None:
                    if not value.get("has_snapshot") or restore is None:
                        raise ReconstructionMismatch("worker coverage requires a restored snapshot")
                    covered = self._restored_worker_events(source, restored_agent_contexts(value["snapshot"]))
                with self._lock:
                    for child in self._source:
                        if source["id"] in child.get("parent_ids", []):
                            self._consumed.add(child["id"])
                    self._consumed.update(covered)
                record = self._begin("operation", lane, name=name, arguments=arguments,
                                     source_id=source["id"], recorded_wall_time=source.get("wall_time"),
                                     **({"restored_worker_events": covered} if covered else {}))
                failure = value.get("failure")
                self._save_operation(record, value, replayed=True, failed=bool(failure))
                if failure:
                    self._raise_operation_failure(failure)
                return value["result"]
            selected_interrupted_operation = (
                self.resume_boundary is not None
                and self.resume_boundary["kind"] == "interrupted_operation"
                and source["id"] == self._boundary["id"]
            )
            if source["id"] not in self._boundary.get("parent_ids", []) and not selected_interrupted_operation:
                raise ReconstructionMismatch("incomplete operation is outside the authorization breakpoint ancestry")
        record = self._begin("operation", lane, name=name, arguments=arguments,
                             source_id=source["id"] if source else None,
                             recorded_wall_time=source.get("wall_time") if source else None)
        token = _runtime.parents.set((*_runtime.parents.get(), record["id"]))
        try:
            result = live_call()
            state = snapshot() if snapshot else None
            value = {"result": result, "snapshot": state, "has_snapshot": snapshot is not None}
            _bytes(value)
            self._save_operation(record, value, replayed=False)
            return result
        except BaseException as exc:
            if isinstance(exc, Exception):
                failure = {"type": type(exc).__module__ + "." + type(exc).__qualname__,
                           "args": list(exc.args)}
                try:
                    state = snapshot() if snapshot else None
                    value = {"failure": failure, "snapshot": state, "has_snapshot": snapshot is not None}
                    _bytes(value)
                except Exception:
                    self._finish(record, status="failed", exception_type=type(exc).__name__)
                else:
                    self._save_operation(record, value, replayed=False, failed=True)
            else:
                self._finish(record, status="interrupted", exception_type=type(exc).__name__)
            raise
        finally:
            _runtime.parents.reset(token)

    @_poison_on_mismatch
    async def async_operation(self, name: str, arguments: Any, live_call: Callable[[], Any], *,
                  snapshot: Callable[[], Any] | None = None,
                  restore: Callable[[Any], None] | None = None,
                  restored_agent_contexts: Callable[[Any], list[dict]] | None = None,
                  lane: str = "") -> Any:
        """Replay an explicitly registered operation and its saved state.

        Results and snapshots must be JSON-safe. An operation containing the
        breakpoint re-enters its native body; completed children replay until
        the denied request. No Python pickle or arbitrary loader is executed.
        """
        self._ensure_active()
        lane = lane or _runtime.lane.get()
        _bytes(arguments)
        source = None
        if not self._live:
            source = self._match("operation", lane, arguments, name=name)
            assert self._boundary is not None
            if source.get("status") in {"ok", "failed"} and source["end_sequence"] < self._boundary["end_sequence"]:
                value = self.rebind(json.loads(self._read_verified(source, "result")))
                if value.get("has_snapshot"):
                    if restore is None:
                        raise ReconstructionMismatch("recorded state requires a restore callback")
                    try:
                        restore(value["snapshot"])
                    except Exception as exc:
                        raise ReconstructionMismatch("recorded state could not be restored") from exc
                covered = []
                if restored_agent_contexts is not None:
                    if not value.get("has_snapshot") or restore is None:
                        raise ReconstructionMismatch("worker coverage requires a restored snapshot")
                    covered = self._restored_worker_events(source, restored_agent_contexts(value["snapshot"]))
                with self._lock:
                    for child in self._source:
                        if source["id"] in child.get("parent_ids", []):
                            self._consumed.add(child["id"])
                    self._consumed.update(covered)
                record = self._begin("operation", lane, name=name, arguments=arguments,
                                     source_id=source["id"], recorded_wall_time=source.get("wall_time"),
                                     **({"restored_worker_events": covered} if covered else {}))
                failure = value.get("failure")
                self._save_operation(record, value, replayed=True, failed=bool(failure))
                if failure:
                    self._raise_operation_failure(failure)
                return value["result"]
            selected_interrupted_operation = (
                self.resume_boundary is not None
                and self.resume_boundary["kind"] == "interrupted_operation"
                and source["id"] == self._boundary["id"]
            )
            if source["id"] not in self._boundary.get("parent_ids", []) and not selected_interrupted_operation:
                raise ReconstructionMismatch("incomplete operation is outside the authorization breakpoint ancestry")
        record = self._begin("operation", lane, name=name, arguments=arguments,
                             source_id=source["id"] if source else None,
                             recorded_wall_time=source.get("wall_time") if source else None)
        token = _runtime.parents.set((*_runtime.parents.get(), record["id"]))
        try:
            result = await live_call()
            state = snapshot() if snapshot else None
            value = {"result": result, "snapshot": state, "has_snapshot": snapshot is not None}
            _bytes(value)
            self._save_operation(record, value, replayed=False)
            return result
        except BaseException as exc:
            if isinstance(exc, Exception):
                failure = {"type": type(exc).__module__ + "." + type(exc).__qualname__,
                           "args": list(exc.args)}
                try:
                    state = snapshot() if snapshot else None
                    value = {"failure": failure, "snapshot": state, "has_snapshot": snapshot is not None}
                    _bytes(value)
                except Exception:
                    self._finish(record, status="failed", exception_type=type(exc).__name__)
                else:
                    self._save_operation(record, value, replayed=False, failed=True)
            else:
                self._finish(record, status="interrupted", exception_type=type(exc).__name__)
            raise
        finally:
            _runtime.parents.reset(token)

    @staticmethod
    def _raise_operation_failure(failure: dict) -> None:
        allowed = {f"builtins.{cls.__name__}": cls for cls in (
            ValueError, TypeError, RuntimeError, KeyError, IndexError, LookupError,
            AssertionError, FileNotFoundError, PermissionError, OSError,
            ZeroDivisionError, NotImplementedError,
        )}
        cls = allowed.get(failure.get("type"))
        if cls is None:
            raise ReconstructionMismatch("recorded operation exception type is unsupported")
        raise cls(*failure.get("args", []))

    def _save_operation(self, record: dict, value: Any, *, replayed: bool, failed: bool = False) -> None:
        filename = f"{record['id']:06d}.result.json"
        data = _bytes(value)
        filesystem_path(self.output_dir / "operations" / filename).write_bytes(data)
        self._finish(record, status="failed" if failed else "ok", result_file=filename,
                     result_sha256=_sha(data), replayed=replayed)
