"""Display recorded analysis duration with solver execution time removed."""
import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime

from zip_images.output_zips.output_reader import OutputPath
from zip_images.output_zips.output_timing import checkpoint_events

_CACHE = {}


def _json(path):
    try:
        return json.loads(path.read_text('utf-8'))
    except (OSError, ValueError):
        return {}


def _history(path):
    try:
        lines = path.read_text('utf-8').splitlines()
    except OSError:
        return []
    result = []
    for line in lines:
        try:
            result.append(json.loads(line))
        except ValueError:
            pass
    return result


def _events(path):
    if isinstance(path, OutputPath) and not path.local.is_file():
        rel = path.archives.rel(path.local)
        found = path.archives.file(rel)
        if found:
            target, record = found
            item = path.archives.runs[target].get('solver_events', {}).get(rel[len(target) + 1:])
            if item and item.get('sha256') == record['sha256']:
                return item['events']
        if path.stat().st_size > 4 * 1024 * 1024:
            return None
        with closing(sqlite3.connect(':memory:')) as connection:
            connection.deserialize(path.read_bytes())
            return list(connection.execute('SELECT seq, committed_at, event FROM checkpoint_events ORDER BY seq'))
    return checkpoint_events(path.local if isinstance(path, OutputPath) else path)


def _union(intervals):
    total, end = 0.0, float('-inf')
    for start, stop in sorted(intervals):
        if stop > max(start, end):
            total += stop - max(start, end)
        end = max(end, stop)
    return total


def _solver_pairs(events, window):
    pending, intervals, incomplete = None, [], False
    for _, stamp, event in events:
        stamp = float(stamp)
        if event == 'solver_started':
            if pending is not None and window[0] <= pending <= window[1]:
                incomplete = True
            pending = stamp
        elif event == 'solver_checkpoint_committed' and pending is not None:
            start, stop = max(pending, window[0]), min(stamp, window[1])
            if stop > start:
                intervals.append((start, stop))
            pending = None
    incomplete |= pending is not None and window[0] <= pending <= window[1]
    return intervals, incomplete


def _log_pairs(path):
    text = path.read_text('utf-8')
    intervals = []
    pending, incomplete = False, False
    for line in text.splitlines():
        if 'Running full N-D solver pipeline' in line:
            incomplete |= pending
            pending = True
        match = re.search(r'^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\].*Solver pipeline done \([^\r\n]*?, ([0-9.]+)s,', line)
        if match and pending:
            # Relative log timestamps retain overlap without assuming a host timezone.
            stamp = (datetime.strptime(match[1], '%Y-%m-%d %H:%M:%S') - datetime(1970, 1, 1)).total_seconds()
            intervals.append((stamp - float(match[2]), stamp))
            pending = False
    return intervals, pending or incomplete


def _serial_driver_time(path, history, wall):
    """Use full-driver durations only for a complete, serial, single-session log."""
    starts = [row for row in history if row.get('event') == 'L0_start']
    ends = [row for row in history if row.get('event') == 'L0_end']
    if len(starts) != 1 or len(ends) != 1:
        return None
    if abs(float(ends[0]['ts']) - float(starts[0]['ts']) - wall) > 2:
        return None
    opened, closed, intervals = {}, set(), []
    for row in history:
        if row.get('event') == 'L1_start':
            call = row['call']
            if call in opened or call in closed:
                return None
            opened[call] = float(row['ts'])
        elif row.get('event') == 'L1_end':
            call = row['call']
            if call not in opened:
                return None
            intervals.append((opened.pop(call), float(row['ts'])))
            closed.add(call)
    if opened or any(stop < start for start, stop in intervals):
        return None
    ordered = sorted(intervals)
    if any(left[1] > right[0] for left, right in zip(ordered, ordered[1:])):
        return None
    pending, durations = None, []
    for line in path.read_text('utf-8').splitlines():
        start = re.match(r'^\[(pH_sweep|freeform_sweep|titration_sweep)\] System:', line)
        done = re.match(r'^\[(pH_sweep|freeform_sweep|titration_sweep)\] Done in ([0-9.]+)s(?: \([^\r\n]*\))?\s*$', line)
        if start:
            if pending is not None:
                return None
            pending = start[1]
        elif done:
            if pending != done[1]:
                return None
            durations.append(float(done[2]))
            pending = None
    return sum(durations) if durations and pending is None else None


def analysis_timing(sdir, manifest=None):
    manifest = manifest if manifest is not None else _json(sdir / 'manifest.json')
    history_path = sdir / 'run_history.jsonl'
    calls = sorted(sdir.glob('L1_call_*'))
    sources = [history_path, sdir / 'manifest.json', sdir / '_run.log']
    for call in calls:
        sources.extend([call / '_checkpoints/solver_result.sqlite3', call / 'solver/sweep_log.txt'])
    stamps = []
    for source in sources:
        try:
            stat = source.stat()
            stamps.append((str(source), stat.st_size, stat.st_mtime_ns))
        except OSError:
            stamps.append((str(source), None))
    key = (str(sdir), manifest.get('elapsed_s'), tuple(stamps))
    if key in _CACHE:
        return _CACHE[key]
    result = {'wall_s': manifest.get('elapsed_s'), 'solver_s': None, 'analysis_s': None,
              'complete': False, 'note': 'Solver-excluded duration is unavailable.'}
    try:
        history = _history(history_path)
        starts = [row for row in history if row.get('event') == 'L0_start']
        ends = [row for row in history if row.get('event') == 'L0_end']
        if result['wall_s'] is None and ends:
            result['wall_s'] = ends[-1].get('elapsed_s')
        if result['wall_s'] is None:
            return result
        wall = float(result['wall_s'])
        stop = float(ends[-1]['ts']) if ends else float('inf')
        start = float(starts[-1]['ts']) if starts else float('-inf')
        window = (max(start, stop - wall) if ends else start, stop)
        epoch_intervals, log_intervals = [], []
        missing_solver_record = False
        has_per_call_timing = False
        for call in calls:
            checkpoint = call / '_checkpoints/solver_result.sqlite3'
            log = call / 'solver/sweep_log.txt'
            if checkpoint.is_file():
                has_per_call_timing = True
                events = _events(checkpoint)
                if events is None:
                    return result
                intervals, incomplete = _solver_pairs(events, window)
                if incomplete:
                    return result
                epoch_intervals.extend(intervals)
            elif log.is_file() and len(starts) <= 1:
                has_per_call_timing = True
                intervals, incomplete = _log_pairs(log)
                if incomplete or not intervals:
                    return result
                log_intervals.extend(intervals)
            elif (call / 'solver').is_dir():
                missing_solver_record = True
        # Epoch and naive-log clocks cannot be merged safely in the same session.
        if epoch_intervals and log_intervals:
            return result
        solver = _union(epoch_intervals or log_intervals)
        if missing_solver_record:
            if has_per_call_timing or not (sdir / '_run.log').is_file():
                return result
            solver = _serial_driver_time(sdir / '_run.log', history, wall)
            if solver is None:
                return result
        if solver > wall + 2:
            return result
        result.update(solver_s=min(wall, solver), analysis_s=max(0.0, wall - solver), complete=True,
                      note='Recorded run time excluding solver execution; overlapping solver intervals count once.')
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
        pass
    if len(_CACHE) > 512:
        _CACHE.clear()
    _CACHE[key] = result
    return result
