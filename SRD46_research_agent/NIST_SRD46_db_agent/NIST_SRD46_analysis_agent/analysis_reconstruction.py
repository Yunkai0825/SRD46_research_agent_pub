"""SRD46 bindings for explicit native replay boundaries.

The engine owns ordering, matching and the switch to live API calls. This
adapter owns only Analysis workspace files and the state of its pipeline tool.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import shutil
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import fields
from functools import wraps
from pathlib import Path

from ..general_db_query_engine.general_first_principle_API_call_reconstruct import (
    ReconstructionMismatch, ReconstructionSession, current_session,
)
from ..general_db_query_engine.general_first_principle_API_call_reconstruct.paths import filesystem_path


# These are execution state, not user-supplied scientific inputs. Launchers may
# create _run.log and unrelated input documents before starting a fresh run.
_STATE_NAMES = {
    "_checkpoints", "working_memory.json", "manifest.json", "answer.md",
    "run_history.jsonl", "run_history.md", "run_stats.json", "run_stats.md",
    "l0_tool_calls.md", "l0_tool_calls.jsonl", "final_full_context.md",
    "verdict.json", "verdict.md", "final_context.json",
}
_active_analysis_root = ContextVar('native_analysis_invocation_root', default=None)


def _is_analysis_state(relative):
    first = Path(relative).parts[0].lower()
    return (first in _STATE_NAMES or first.startswith(("l1_call_", "lv_"))
            or first == "lv")


def require_fresh_analysis_root(root, *, current_ledger=None):
    """Reject a report/checkpoint restart before any files or API calls change."""
    root = filesystem_path(root)
    if not root.exists():
        return
    for path in root.iterdir():
        if _is_analysis_state(path.name):
            raise ReconstructionMismatch(
                "Existing Analysis state requires first-principle reconstruction: " + path.name)
    parent = root / 'run_provenance/first_principle_reconstruction'
    if parent.exists():
        allowed = set()
        if current_ledger is not None:
            ledger = filesystem_path(current_ledger)
            if ledger.parent.resolve() == parent.resolve():
                allowed = {ledger.name, 'latest.json'}
        if not allowed or any(p.name not in allowed for p in parent.iterdir()):
            raise ReconstructionMismatch(
                'Existing Analysis ledger requires first-principle reconstruction')


def require_analysis_entry(root):
    """Guard direct L0 callers as well as the public Analysis API."""
    session = current_session()
    if session is not None and getattr(session, 'analysis_root', None) is not None:
        if filesystem_path(session.analysis_root).resolve() != filesystem_path(root).resolve():
            raise ReconstructionMismatch('Analysis entry belongs to another reconstruction session')
        if getattr(session, 'analysis_entry_started', False):
            raise ReconstructionMismatch('L0 cannot be restarted inside an existing invocation')
        if session.mode != 'reconstruction':
            require_fresh_analysis_root(root, current_ledger=session.output_dir)
        elif session.source_dir is None:
            raise ReconstructionMismatch('Analysis reconstruction has no verified source ledger')
        session.analysis_entry_started = True
    else:
        require_fresh_analysis_root(root)


def _validate_initial_workspace(replay):
    """A recording that began with synthetic report recovery is not a replay source."""
    rows = [r for r in replay.verified_source_records()
            if r.get('name') == 'analysis.initial_workspace']
    if len(rows) != 1:
        raise ReconstructionMismatch('Original Analysis initial workspace is missing or ambiguous')
    files = replay.verified_operation_result(rows[0]['id'])['snapshot']
    if any(_is_analysis_state(entry['path']) for entry in files):
        raise ReconstructionMismatch(
            'Source began with existing Analysis state, not first-principle reconstruction')


def analysis_entrypoint(function):
    """Admit one fresh or reconstructed L0 invocation, including its live retries."""
    signature = inspect.signature(function)
    @wraps(function)
    def invoke(*args, **kwargs):
        root = signature.bind(*args, **kwargs).arguments['session_dir']
        require_analysis_entry(root)
        token = _active_analysis_root.set(filesystem_path(root).resolve())
        try:
            return function(*args, **kwargs)
        finally:
            _active_analysis_root.reset(token)
    return invoke


def require_pipeline_entry(root):
    """Stage journals may support this invocation, never restart an old agent."""
    root = filesystem_path(root)
    admitted = _active_analysis_root.get()
    if admitted is not None:
        if root.resolve().is_relative_to(admitted):
            return
        raise ReconstructionMismatch('Pipeline output is outside its Analysis invocation')
    session = current_session()
    owner = getattr(session, 'analysis_root', None) if session else None
    if owner is not None and getattr(session, 'analysis_entry_started', False):
        if root.resolve().is_relative_to(filesystem_path(owner).resolve()):
            return
        raise ReconstructionMismatch('Pipeline output is outside its Analysis invocation')
    if root.exists() and any((root / name).exists() for name in (
            '_checkpoints', 'LC1', 'LC2', 'LC3', 'source_repair', 'solver')):
        raise ReconstructionMismatch(
            'Existing pipeline stages require first-principle reconstruction')


def _encode(value):
    if isinstance(value, Path):
        return {"__path__": str(value)}
    if isinstance(value, tuple):
        return {"__tuple__": [_encode(v) for v in value]}
    if isinstance(value, list):
        return [_encode(v) for v in value]
    if isinstance(value, dict):
        return {k: _encode(v) for k, v in value.items()}
    return value


def _decode(value):
    if isinstance(value, dict):
        if set(value) == {"__path__"}:
            return Path(value["__path__"])
        if set(value) == {"__tuple__"}:
            return tuple(_decode(v) for v in value["__tuple__"])
        return {k: _decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decode(v) for v in value]
    return value


def _hash_file(path):
    with filesystem_path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _capture_files(root, *, exclude_provenance=False):
    """Content-addressed copies preserve versions, including overwritten files."""
    session = current_session()
    root = filesystem_path(root)
    blobs = filesystem_path(session.output_dir / 'artifacts')
    blobs.mkdir(exist_ok=True)
    result = []
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if exclude_provenance and relative.parts[0] == 'run_provenance':
            continue
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            raise ReconstructionMismatch(f'Artifact link is not replayable: {relative}')
        if not path.is_file():
            continue
        digest = _hash_file(path)
        blob = blobs / digest
        if not blob.exists():
            shutil.copyfile(path, blob)
        if _hash_file(blob) != digest:
            raise ReconstructionMismatch(f'Artifact changed during capture: {relative}')
        result.append({'path': relative.as_posix(), 'sha256': digest,
                       'bytes': path.stat().st_size})
    return result


def _restore_files(root, inventory):
    session = current_session()
    root = filesystem_path(root)
    for entry in inventory:
        relative = Path(entry['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ReconstructionMismatch('Artifact path escaped its workspace')
        destination = root / relative
        try:
            destination.resolve().relative_to(root.resolve())
        except ValueError as exc:
            raise ReconstructionMismatch('Artifact destination escaped its workspace') from exc
        source = filesystem_path(session.source_dir / 'artifacts' / entry['sha256'])
        if (not source.is_file() or source.stat().st_size != entry['bytes']
                or _hash_file(source) != entry['sha256']):
            raise ReconstructionMismatch(f'Missing or changed artifact: {relative}')
        # Keep the reconstructed ledger independently reusable if access is
        # denied again later. Never rely on the old source's blob directory.
        retained = filesystem_path(session.output_dir / 'artifacts' / entry['sha256'])
        retained.parent.mkdir(exist_ok=True)
        if not retained.exists():
            shutil.copyfile(source, retained)
        if _hash_file(retained) != entry['sha256']:
            raise ReconstructionMismatch(f'Changed retained artifact: {relative}')
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_symlink():
            raise ReconstructionMismatch('Artifact destination is a link')
        shutil.copyfile(source, destination)
        if _hash_file(destination) != entry['sha256']:
            raise ReconstructionMismatch(f'Artifact restore failed: {relative}')


def reconstruction_reads(tools):
    """Replay explicitly read-only Analysis tools; commits still execute."""
    names = {'list_session_files', 'read_session_file', 'list_outputs',
             'read_output_file', 'inspect_verdict_section', 'inspect_topology_feature'}

    def wrap(name, function):
        @wraps(function)
        def read(*args, **kwargs):
            session = current_session()
            if session is None:
                return function(*args, **kwargs)
            return session.operation('analysis.read.' + name,
                                     {'args': list(args), 'kwargs': kwargs},
                                     lambda: function(*args, **kwargs))
        return read

    return {name: wrap(name, function) if name in names else function
            for name, function in tools.items()}


def _source_ledger(source):
    source = Path(source).absolute()
    if filesystem_path(source / 'session.json').is_file():
        return source
    pointer = source / 'run_provenance/first_principle_reconstruction/latest.json'
    if not filesystem_path(pointer).is_file():
        raise ValueError(
            'This run has no first-principle ledger. Passive HTTP captures need '
            'an explicit checkpoint/context adapter; they are not a native replay session.'
        )
    relative = Path(json.loads(filesystem_path(pointer).read_text('utf-8'))['ledger'])
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Invalid reconstruction ledger pointer')
    return pointer.parent / relative


@contextmanager
def analysis_execution(*, mode, session_dir, source=None, stop_at_breakpoint=False,
                       settings=None, live_api_user=None, boundary=None, live_provider=None):
    """Record each invocation; reconstruct into a fresh, separate output root."""
    if mode not in {'regular', 'reconstruction', 'resume'}:
        raise ValueError('reconstruction_mode must be regular, reconstruction or resume')
    if boundary is not None:
        if mode != 'reconstruction':
            raise ValueError('An explicit request boundary requires reconstruction into a fresh folder')
        if not isinstance(boundary, dict) or boundary.get('kind') not in {'interrupted_http', 'restart_before_http'}:
            raise ValueError('Analysis requires an interrupted_http or restart_before_http request boundary')
    root = Path(session_dir).absolute()
    source_ledger = _source_ledger(source) if source is not None else None
    bindings = []
    continuation = None
    if mode == "regular":
        require_fresh_analysis_root(root)
    if mode in {'reconstruction', 'resume'}:
        if source_ledger is None:
            raise ValueError('reconstruction_source is required')
        if mode == 'reconstruction' and filesystem_path(root).exists() and any(filesystem_path(root).iterdir()):
            raise ValueError('Reconstruction requires a fresh output folder')
        launch = json.loads(filesystem_path(source_ledger / 'analysis_run.json').read_text('utf-8'))
        if (settings.get('estimate_missing_equilibria') and launch.get('query_replay_schema') != 1
                or filesystem_path(source_ledger / 'completed_query_imports.json').exists()):
            raise ReconstructionMismatch(
                'Native Query/MCP replay records are required; completed-turn imports are unsupported')
        old_root = Path(launch['session_dir'])
        if mode == 'reconstruction' and (root.resolve() == old_root.resolve() or old_root.resolve() in root.resolve().parents):
            raise ValueError('Reconstruction cannot overwrite or nest within the source run')
        # Explicit path relocation only; preserve all original captured bytes.
        for old, new in [(str(old_root), str(root)), (old_root.as_posix(), root.as_posix()),
                         (str(old_root.resolve()), str(root.resolve()))]:
            if old != new and (old, new) not in bindings:
                bindings.append((old, new))
        if launch.get('settings') != settings:
            raise ValueError('Reconstruction question/settings differ from the recorded run')
        if mode == 'resume':
            from .analysis_continuation import inspect_handover
            continuation = inspect_handover(source_ledger, root, settings)
    elif source is not None:
        raise ValueError('regular mode does not accept reconstruction_source')
    parent = root / 'run_provenance/first_principle_reconstruction'
    index = 1
    while filesystem_path(parent / f'attempt_{index:04d}').exists():
        index += 1
    ledger = parent / f'attempt_{index:04d}'
    # Construction validates every source receipt before creating output files.
    # Manual HTTP replay uses the ordinary reconstruction path, not the
    # prepared-solver hooks (which require their own clocks and stage snapshots).
    replay = ReconstructionSession(mode='reconstruction' if mode == 'resume' else mode,
                                   output_dir=ledger, source_dir=source_ledger,
                                   stop_at_breakpoint=stop_at_breakpoint,
                                   path_bindings=tuple(bindings),
                                   resume_boundary=continuation['boundary'] if continuation else boundary,
                                   live_api_user=live_api_user, live_provider=live_provider)
    if source_ledger is not None:
        _validate_initial_workspace(replay)
    with replay as session:
        session.analysis_root = root
        session.query_replay_enabled = True
        if continuation:
            session.analysis_continuation = continuation
        filesystem_path(ledger / 'analysis_run.json').write_text(json.dumps({
            'session_dir': str(root), 'settings': settings,
            'scope': 'native Analysis and embedded Query/MCP requests, tools and clocks',
            'query_replay_schema': 1,
        }, indent=2)+'\n', encoding='utf-8')
        filesystem_path(parent / 'latest.json').write_text(json.dumps({'ledger': ledger.name})+'\n', encoding='utf-8')
        # Record fresh scientific inputs. Existing execution state is rejected
        # before creating the ledger; continuation must replay a verified prefix.
        restore_initial = lambda files: _restore_files(root, files)
        if continuation:
            from .analysis_continuation import preserve_initial_files
            restore_initial = preserve_initial_files
        session.operation('analysis.initial_workspace', settings, lambda: None,
                          snapshot=lambda: _capture_files(root, exclude_provenance=True),
                          restore=restore_initial, lane='analysis.workspace')
        yield session



def _restored_lc2_worker_contexts(root, saved):
    """Bind historical detached LC2 lanes to their checksum-restored contexts."""
    files = {entry['path'] for entry in saved['files']}
    contexts = []
    for name in sorted(files):
        if not (name.startswith('LC2/LC2_3/') and name.endswith('/agent_context_manifest.json')):
            continue
        folder = Path(name).parent
        names = {key: (folder / filename).as_posix() for key, filename in (
            ('system_prompt', 'system_prompt.md'), ('user_message', 'user_message.md'), ('memory', 'memory.json'))}
        if not all(path in files for path in names.values()):
            continue
        manifest = json.loads(filesystem_path(root / name).read_text('utf-8'))
        if manifest.get('stage_id') != 'LC2_3.group_dedup':
            continue
        context = {'entrypoint': 'agent_turn'}
        for key, path in names.items():
            text = filesystem_path(root / path).read_text('utf-8')
            context[key] = json.loads(text) if key == 'memory' else text
        contexts.append(context)
    return contexts


def pipeline_reconstruction(state, function):
    """Cache a completed pipeline with its state/files; enter interrupted ones."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        session = current_session()
        if session is None:
            return function(*args, **kwargs)
        from .analysis_agent_orchestration.L1_subagent.l1_state import _SESSION

        def snapshot():
            wm = _SESSION.get('working_memory')
            history = _SESSION.get('history')
            stats = _SESSION.get('stats')
            return {'state': _encode({f.name: getattr(state, f.name) for f in fields(state)}),
                    'working_memory': _encode(wm.as_dict()) if wm is not None else None,
                    # Operation JSON is canonicalized with sorted keys. Memory
                    # is rendered into model context in insertion order, so
                    # retain its exact serialization separately from that map.
                    'working_memory_json': json.dumps(_encode(wm.as_dict()), ensure_ascii=False)
                    if wm is not None else None,
                    'history': history.path.read_text('utf-8')
                    if history is not None and history.path.exists() else None,
                    'stats': stats.as_dict() if stats is not None else None,
                    'files': _capture_files(state.call_dir)}

        def restore(saved):
            _restore_files(state.call_dir, saved['files'])
            for name, value in _decode(saved['state']).items():
                setattr(state, name, value)
            wm = _SESSION.get('working_memory')
            if wm is not None and saved['working_memory'] is not None:
                memory = saved['working_memory']
                if saved.get('working_memory_json') is not None:
                    ordered = json.loads(saved['working_memory_json'])
                    if ordered != memory:
                        raise ReconstructionMismatch('Ordered working memory differs from its saved values')
                    memory = ordered
                wm._store = _decode(memory)
                wm._flush()
            history = _SESSION.get('history')
            if history is not None and saved.get('history') is not None:
                history.path.write_text(saved['history'], encoding='utf-8')
                history.log('reconstruction_pipeline_reused', call=state.idx,
                            source_ledger=str(session.source_dir), new_solver_calls=0)
            stats = _SESSION.get('stats')
            if stats is not None and saved.get('stats') is not None:
                stats._counters = saved['stats']

        return session.operation(
            'analysis.build_and_solve',
            {'call': state.idx, 'purpose': state.purpose, 'tasks': state.tasks_text,
             'args': list(args), 'kwargs': kwargs},
            lambda: function(*args, **kwargs), snapshot=snapshot, restore=restore,
            restored_agent_contexts=lambda saved: _restored_lc2_worker_contexts(state.call_dir, saved),
        )
    return wrapped
