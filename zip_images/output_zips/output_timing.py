"""Small native checkpoint timing records for ZIP-backed result displays."""
from pathlib import Path
from contextlib import closing
import sqlite3
from urllib.parse import quote


def checkpoint_events(path):
    """Read event metadata without loading solver payloads or changing the database."""
    name = str(path)
    if name.startswith('\\\\?\\UNC\\'):
        name = '\\\\' + name[8:]
    elif name.startswith('\\\\?\\'):
        name = name[4:]
    uri = ('file:////' + quote(name[2:].replace('\\', '/'), safe='/:')
           if name.startswith('\\\\') else Path(name).as_uri())
    with closing(sqlite3.connect(uri + '?mode=ro', uri=True)) as connection:
        return [[int(seq), float(stamp), str(event)] for seq, stamp, event in connection.execute(
            'SELECT seq, committed_at, event FROM checkpoint_events ORDER BY seq')]


def solver_index(target, files, items, previous=None):
    """Keep each cached event list tied to its archived checkpoint bytes."""
    sources = {item.path[len(target) + 1:]: item.local for item in items}
    result = {}
    for item in files:
        name = item['name']
        if not name.endswith('/_checkpoints/solver_result.sqlite3'):
            continue
        cached = (previous or {}).get(name)
        if cached and cached.get('sha256') == item['sha256']:
            result[name] = cached
        elif name in sources:
            try:
                result[name] = {'sha256': item['sha256'], 'events': checkpoint_events(sources[name])}
            except (OSError, sqlite3.Error, ValueError):
                pass
    return result
