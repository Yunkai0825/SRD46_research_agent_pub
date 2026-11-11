"""Freeform Markdown documents with an explicit user_prompt and run settings."""
from copy import deepcopy
from pathlib import Path
import re
import math
import yaml


def load_prompt(path):
    path = Path(path)
    text = path.read_text('utf-8-sig')
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != '---':
        if not text.strip():
            raise ValueError('Empty prompt file')
        return {'id': 'freeform', 'label': path.stem, 'group': 'FREEFORM', 'prompt': text}
    end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == '---'), None)
    if end is None:
        raise ValueError('Markdown metadata needs a closing --- line')
    try:
        meta = yaml.safe_load(''.join(lines[1:end]))
    except yaml.YAMLError as exc:
        raise ValueError('Invalid Markdown metadata') from exc
    if not isinstance(meta, dict) or meta.get('schema') != 'srd46-freeform-run/v1':
        raise ValueError('Expected srd46-freeform-run/v1 Markdown metadata')
    allowed = {'schema', 'id', 'layer', 'user_prompt', 'settings', 'run', 'api_overrides'}
    if set(meta) - allowed:
        raise ValueError('Unknown freeform metadata fields: ' + ', '.join(sorted(set(meta) - allowed)))
    label = meta.get('id')
    if not isinstance(label, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', label):
        raise ValueError('Freeform id must use letters, numbers, underscores or hyphens')
    if meta.get('layer') != 'FREEFORM':
        raise ValueError('Freeform layer must be FREEFORM')
    for key in ('settings', 'run', 'api_overrides'):
        if not isinstance(meta.get(key, {}), dict):
            raise ValueError(key + ' metadata must be an object')
    for key, value in meta.get('api_overrides', {}).items():
        types = {'estimate_missing_equilibria': bool, 'l0_max_iterations': int, 'l0_reasoning_timeout_s': (int, float)}
        if key not in types or isinstance(value, bool) and key != 'estimate_missing_equilibria' or not isinstance(value, types.get(key, type(None))):
            raise ValueError('Unknown or invalid freeform API override: ' + key)
        if key != 'estimate_missing_equilibria' and (not math.isfinite(value) or value <= 0):
            raise ValueError(key + ' must be positive')
    prompt = meta.get('user_prompt')
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError('Markdown metadata requires a nonempty user_prompt string')
    if ''.join(lines[end + 1:]).strip():
        raise ValueError('Put the question in user_prompt; text after the metadata is not accepted')
    match = re.match(r'FF_\d+', label)
    return {'id': match[0] if match else label, 'label': label, 'group': 'FREEFORM', 'prompt': prompt,
            'api_overrides': deepcopy(meta.get('api_overrides', {})), 'metadata': meta}


def bind_run_metadata(args, rows):
    if len(rows) != 1 or 'metadata' not in rows[0]:
        return {}
    meta = rows[0]['metadata']
    from .runtime import SETTINGS_FILE
    import json
    known = set(json.loads(SETTINGS_FILE.read_text('utf-8-sig'))) - {'schema'}
    unknown = set(meta.get('settings', {})) - known
    if unknown:
        raise ValueError('Unknown freeform settings: ' + ', '.join(sorted(unknown)))
    types = {'preset': str, 'output_root': Path, 'session_dir': Path, 'date': str, 'jobs': int,
             'order': str, 'debug': bool, 'stop_file': Path, 'stop_on_failure': bool,
             'max_iterations': int, 'reasoning_timeout': float}
    explicit = getattr(args, '_explicit', set())
    for key, value in meta.get('run', {}).items():
        if key not in types:
            raise ValueError('Unknown freeform run setting: ' + key)
        if value is None or value == 'default' or key in explicit:
            continue
        kind = types[key]
        if kind is Path:
            if not isinstance(value, str):
                raise ValueError(key + ' must be a path string')
            value = Path(value)
        elif kind is float and type(value) in (int, float):
            value = float(value)
        elif type(value) is not kind:
            raise ValueError('Wrong type for freeform run setting: ' + key)
        setattr(args, key, value)
    return {key: deepcopy(value) for key, value in meta.get('settings', {}).items()
            if value is not None and (value != 'default' or key in {'reasoning_effort', 'thinking_mode'})}
