r"""Model-call cost of the stored benchmark runs: tokens per call, cost per prompt and per layer, and the cost figure.

Reads only this repository: the run folders under ``_benchmark/<model folder>/<prompt>_<date>/`` and the two tables in
``reference/`` next to this file.  For every prompt the latest stored run is used.  Needs numpy and matplotlib.

Call records, per attempt (first that exists):
  provider_calls  run_provenance/first_principle_reconstruction/attempt_*/provider_calls   raw provider reply with its usage block
  calls           .../attempt_*/calls                                                      request text and reply; usage where the reply carries it

Tokens of a call
  reported   the usage block of the reply: input includes every cached part, output includes thinking or reasoning tokens
  estimated  characters / (characters per token) of the call's layer, for replies saved without a usage block:
               Opus 4.7   reference/opus47_chars_per_token.csv (calibration on calls with reported Opus 4.7 usage); a layer the table
                          lacks takes the ratio of the stored Opus 4.7 calls with reported usage
               Opus 5.5   the stored Opus 5.5 calls with reported usage
               GPT-5.5    the stored GPT-6 Sol calls with reported usage, output counted as visible text only (the GPT-5.5 replies
                          carry no reasoning count)
               GPT-6 Sol  its own calls with reported usage
             A layer needs at least 20 calls with reported usage for its own ratio; otherwise the ratio over all layers is used.

Cost = input tokens x input price + output tokens x output price, list prices, no cache discount.
Left out as not billed: calls answered from an earlier attempt's record (replayed) and calls with an HTTP status other than 200.
A run resumed from an attempt that is not stored takes that attempt's call sizes from reference/resumed_attempt_calls.csv.

Only sizes, token counts and layer names are written; request headers and account fields are not read into any table.

Output, for one figure (Extended Data Fig. E6).  The tables have one header row and can be pasted into a plotting
program; the picture shows what the figure looks like:
  output/cost_per_prompt_by_layer.tiff   the four-panel figure, 300 dpi (uncompressed TIFF)
  output/csv/panel_<a-d>_<model>.csv      one panel: prompt, the stacked segments from the bottom up, total, X mark
  output/csv/stack_segments.csv           the segments from the bottom up: colour and the layers summed into each
  output/csv/figure_bars.csv              the bars of all four panels in one table
  output/csv/...                          call table, characters-per-token ratios, per-prompt costs, summary

usage:
  python cost_audit.py                 read the runs, write the tables and the figure
  python cost_audit.py --reuse-calls   recompute tables and figure from the written calls.csv without reading the runs again
"""
import argparse
import csv
import json
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(os.path.abspath(__file__)).parent
BENCHMARK = HERE.parents[1]
REFERENCE = HERE / 'reference'

# key, run folder, model name in the call records, panel title, (input, output) price in $ per million tokens
SETS = [
    ('opus47', 'Opus4.7', 'claudeopus47', 'Opus-4.7 (high)', (5.0, 25.0)),
    ('opus55', 'Opus5.5', 'claudeopus55', 'Opus-5.5 (medium)', (4.0, 20.0)),
    ('gpt55', 'GPT-5.5', 'gpt55', 'GPT-5.5 (medium)', (5.0, 30.0)),
    ('gpt6sol', 'GPT-6 Sol', 'gpt6sol', 'GPT-6 Sol (medium)', (2.0, 10.0)),
]
FOLDER = {k: f for k, f, _, _, _ in SETS}
MODEL = {k: m for k, _, m, _, _ in SETS}
PRICE = {k: p for k, _, _, _, p in SETS}
MIN_CALLS_FOR_LAYER_RATIO = 20

L0, L1, LD = 'L0 orchestrator', 'L1 pipeline sub-agent', 'LD validator'
LC1_1, LC1_2 = 'LC1_1 ID alignment', 'LC1_2 eq-map node validator'
LC1_3P, LC1_3Q = 'LC1_3 speciation parser', 'LC1_3 query agent'
LC2_3S, LC2_3G, LC2_3N = 'LC2_3 element-instruction supervisor', 'LC2_3 per-group dedup', 'LC2_3 singleton dedup'
LC3_1, LC3_2 = 'LC3_1 method picker', 'LC3_2 initial-condition designer'
LC3_3, LC3_4 = 'LC3_3 constraint designer', 'LC3_4 sweep designer'
REPAIR, COMPRESS = 'LC1 source repair', 'Context compression'
REPLAYED = 'replayed'
LAYERS = [L0, L1, LD, LC1_1, LC1_2, LC1_3P, LC1_3Q, LC2_3S, LC2_3G, LC2_3N, LC3_1, LC3_2, LC3_3, LC3_4, REPAIR, COMPRESS]

# The layer of a call is read from the opening of its system prompt.
SYSTEM_PATTERNS = [
    (re.compile(r'L0 Orchestrator'), L0),
    (re.compile(r'L1 Pipeline Sub-agent'), L1),
    (re.compile(r'LD Validator|LV Validator'), LD),
    (re.compile(r'^#\s*LC1_1\b', re.M), LC1_1),
    (re.compile(r'^#\s*LC1_2\b', re.M), LC1_2),
    (re.compile(r'electrochemist supervising element-level', re.S), LC2_3S),
    (re.compile(r'LC2_3 per-group deduplication subagent'), LC2_3G),
    (re.compile(r'LC2_3 singleton-batch deduplication subagent'), LC2_3N),
    (re.compile(r'^#\s*L3_1\b', re.M), LC3_1),
    (re.compile(r'^#\s*L3_2\b', re.M), LC3_2),
    (re.compile(r'^#\s*L3_3\b', re.M), LC3_3),
    (re.compile(r'^#\s*L3_4\b', re.M), LC3_4),
    (re.compile(r'Source-backed equilibrium selection repair'), REPAIR),
    (re.compile(r'subagent that answers and explores chemistry|Plan Evaluator|Strategy Planner'), LC1_3Q),
    (re.compile(r'downstream equilibrium-entry parser'), LC1_3P),
    (re.compile(r'data-compression assistant|managing conversation memory|reviewing a compressed version'), COMPRESS),
]

TEXT_COLUMNS = ['set', 'id', 'run', 'attempt', 'layer', 'record', 'model']
NUMBER_COLUMNS = ['system_chars', 'prompt_chars', 'response_chars', 'input_tokens', 'output_tokens', 'reasoning_tokens', 'cached_tokens', 'http_status']
PRICED_COLUMNS = ['billed', 'token_source', 'input_tokens_used', 'output_tokens_used', 'cost_usd']

# Figure: stack order from the bottom, (legend label, colour, layers summed into the segment).
FIGURE_STACK = [
    ('LC1_1 ID alignment', '#6fd09a', [LC1_1]),
    ('LC1_2 eq-map inspect', '#37ad6b', [LC1_2, REPAIR]),
    ('LC1_3 parser', '#257448', [LC1_3P]),
    ('LC1_3 query agent', '#184e31', [LC1_3Q]),
    ('LC2_3 singleton dedup', '#8db8f1', [LC2_3N]),
    ('LC2_3 per-group dedup', '#5e9aec', [LC2_3G]),
    ('LC2_3 main dedup', '#114a97', [LC2_3S]),
    ('LC3_1 calc method', '#feb381', [LC3_1]),
    ('LC3_2 initial condition', '#fe944e', [LC3_2]),
    ('LC3_3 constraint', '#fb6501', [LC3_3]),
    ('LC3_4 sweep', '#a74301', [LC3_4]),
    ('LD validator', '#c597e6', [LD]),
    ('L1 subagents', '#b177de', [L1, COMPRESS]),
    ('L0 orchestrator', '#7d2db9', [L0]),
]
FAMILY_ORDER = {'L1': 0, 'L2': 1, 'L3': 2, 'L4': 3, 'FF': 4}
FAMILY_LABELS = [('Diagram build', 5.6), ('Multi-step', 15.3), ('Hypothesis', 22.2), ('Impossible', 28.7)]
# Prompts whose outcome is not "Complete" in the outcome table of the paper; drawn with an X above the bar.
NOT_COMPLETE = {'gpt6sol': ['L1_2', 'L1_4', 'L1_5', 'L1_8', 'L1_10', 'L1_11']}


def prompt_key(prompt_id):
    family, number = prompt_id.split('_')
    return FAMILY_ORDER[family], int(number)


def load_json(path):
    try:
        with open(path, encoding='utf-8', errors='replace') as handle:
            raw = handle.read()
    except OSError:
        return None, ''
    try:
        return json.loads(raw), raw
    except ValueError:
        return None, raw


def find_request(obj):
    """The mapping that holds the system prompt and the prompt or messages, wherever the record nests it."""
    if isinstance(obj, dict):
        if 'system' in obj and ('prompt' in obj or 'messages' in obj):
            return obj
        for key in ('body', 'payload', 'json', 'request', 'data'):
            if key in obj:
                found = find_request(obj[key])
                if found:
                    return found
    return None


def text_len(value):
    if isinstance(value, str):
        return len(value)
    if isinstance(value, list):
        return sum(text_len(item) for item in value)
    if isinstance(value, dict):
        return text_len(value.get('content')) if 'content' in value else text_len(value.get('text', ''))
    return 0


def system_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ' '.join(block.get('text', '') for block in value if isinstance(block, dict))
    return ''


def classify_system(system):
    head = (system or '')[:3000]
    for pattern, layer in SYSTEM_PATTERNS:
        if pattern.search(head):
            return layer
    return 'unclassified: ' + re.sub(r'\s+', ' ', head.replace('<system_prompt>', '').strip())[:70]


def read_usage(reply):
    """(input tokens with every cached part, output tokens with thinking or reasoning, reasoning tokens, cached input tokens) or None."""
    usage = reply.get('usage') if isinstance(reply, dict) else None
    if not usage:
        return None
    if 'input_tokens' in usage:
        created, read = usage.get('cache_creation_input_tokens') or 0, usage.get('cache_read_input_tokens') or 0
        thinking = (usage.get('output_tokens_details') or {}).get('thinking_tokens') or 0
        return (usage.get('input_tokens') or 0) + created + read, usage.get('output_tokens') or 0, thinking, created + read
    if 'prompt_tokens' in usage:
        reasoning = (usage.get('completion_tokens_details') or {}).get('reasoning_tokens') or 0
        cached = (usage.get('prompt_tokens_details') or {}).get('cached_tokens') or 0
        return usage.get('prompt_tokens') or 0, usage.get('completion_tokens') or 0, reasoning, cached
    return None


def reply_text_len(reply, raw):
    """Visible characters of the reply."""
    if not isinstance(reply, dict):
        return len(raw)
    if isinstance(reply.get('response'), str):
        return len(reply['response'])
    if isinstance(reply.get('content'), list):
        return sum(len(block.get('text') or '') for block in reply['content'] if isinstance(block, dict) and block.get('type') == 'text')
    choices = reply.get('choices')
    if isinstance(choices, list) and choices:
        return len(((choices[0] or {}).get('message') or {}).get('content') or '')
    return 0


def read_call(task):
    record, stem, base = task
    receipt = load_json(stem + '.receipt.json')[0] or {}
    row = dict(base, record=record, http_status=receipt.get('http_status'), input_tokens=None, output_tokens=None, reasoning_tokens=None, cached_tokens=None)
    if record == 'calls' and receipt.get('replayed'):
        return dict(row, layer=REPLAYED, model='', system_chars=0, prompt_chars=0, response_chars=0)
    request_file = '.logical.json' if record == 'provider_calls' else '.request.json'
    request = find_request(load_json(stem + request_file)[0] or {}) or {}
    reply, raw = load_json(stem + '.response.txt')
    usage = read_usage(reply or {})
    row.update(layer=classify_system(system_text(request.get('system'))), model=request.get('model') or receipt.get('logical_model', ''),
               system_chars=text_len(request.get('system')), prompt_chars=text_len(request.get('prompt') or request.get('messages')),
               response_chars=reply_text_len(reply, raw))
    if usage:
        row.update(input_tokens=usage[0], output_tokens=usage[1], reasoning_tokens=usage[2], cached_tokens=usage[3])
    return row


def latest_runs(set_dir):
    """prompt id -> the latest dated run folder of that prompt."""
    latest = {}
    for entry in os.scandir(set_dir):
        match = re.match(r'^((?:FF|L\d)_\d+)_(\d{8})$', entry.name)
        if entry.is_dir() and match and (match.group(1) not in latest or match.group(2) > latest[match.group(1)][0]):
            latest[match.group(1)] = (match.group(2), Path(entry.path))
    return {prompt: path for prompt, (_, path) in sorted(latest.items(), key=lambda kv: prompt_key(kv[0]))}


def resumed_from(attempt_dir, run_dir):
    """(run folder, attempt) this attempt was resumed from when that is another run; else None."""
    source = str((load_json(attempt_dir / 'session.json')[0] or {}).get('source_dir') or '')
    match = re.search(r'[\\/]([^\\/]+)[\\/]run_provenance[\\/]first_principle_reconstruction[\\/](attempt_\d+)', source)
    return (match.group(1), match.group(2)) if match and match.group(1) != run_dir.name else None


def call_tasks(record_dir, record, base):
    stems = sorted(entry.path[:-len('.response.txt')] for entry in os.scandir(record_dir) if entry.name.endswith('.response.txt'))
    return [(record, stem, base) for stem in stems]


def to_number(text):
    if text in ('', None):
        return None
    value = float(text)
    return int(value) if value == int(value) else value


def read_call_table(path):
    with open(path, encoding='utf-8', newline='') as handle:
        return [{**{c: r.get(c, '') for c in TEXT_COLUMNS}, **{c: to_number(r.get(c, '')) for c in NUMBER_COLUMNS}} for r in csv.DictReader(handle)]


def resumed_attempt_rows(key, run, source_run):
    rows = [r for r in read_call_table(REFERENCE / 'resumed_attempt_calls.csv') if (r['set'], r['run'], r['attempt']) == (key, run, 'resumed_from_' + source_run)]
    if not rows:
        raise FileNotFoundError('%s/%s was resumed from %s, which is neither stored nor listed in resumed_attempt_calls.csv' % (key, run, source_run))
    print('%s %s: %d calls of the attempt it was resumed from (%s) taken from reference/resumed_attempt_calls.csv' % (key, run, len(rows), source_run))
    return rows


def extract_calls(jobs):
    """One row per recorded call of the latest run of every prompt, in the four model folders."""
    tasks, reference_rows = [], []
    for key, folder, _, _, _ in SETS:
        for prompt, run_dir in latest_runs(BENCHMARK / folder).items():
            base = {'set': key, 'id': prompt, 'run': run_dir.name}
            reconstruction = run_dir / 'run_provenance' / 'first_principle_reconstruction'
            attempts = sorted(name for name in os.listdir(reconstruction) if name.startswith('attempt')) if reconstruction.is_dir() else []
            if not attempts:
                raise FileNotFoundError('no call records under %s' % reconstruction)
            for attempt in attempts:
                provider, calls = reconstruction / attempt / 'provider_calls', reconstruction / attempt / 'calls'
                found = call_tasks(provider, 'provider_calls', dict(base, attempt=attempt)) if provider.is_dir() else []
                if not found and calls.is_dir():
                    found = call_tasks(calls, 'calls', dict(base, attempt=attempt))
                tasks += found
                source = resumed_from(reconstruction / attempt, run_dir)
                if source is None:
                    continue
                source_calls = run_dir.parent / source[0] / 'run_provenance' / 'first_principle_reconstruction' / source[1] / 'calls'
                if source_calls.is_dir():
                    tasks += call_tasks(source_calls, 'calls', dict(base, attempt='resumed_from_' + source[0]))
                else:
                    reference_rows += resumed_attempt_rows(key, run_dir.name, source[0])
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        rows = list(pool.map(read_call, tasks))
    return rows + reference_rows


def chars_per_token(calls, visible_output=False):
    """layer -> (input characters per token, output characters per token) from calls with reported usage; 'ALL' = all layers."""

    def pair(group):
        answered = [c for c in group if c['response_chars'] > 0]
        output = sum(c['output_tokens'] - ((c['reasoning_tokens'] or 0) if visible_output else 0) for c in answered)
        input_tokens = sum(c['input_tokens'] for c in group)
        return (sum(c['input_chars'] for c in group) / input_tokens if input_tokens else math.nan,
                sum(c['response_chars'] for c in answered) / output if output else math.nan)

    calls = [c for c in calls if c['reported']]
    ratios = {'ALL': pair(calls)}
    for layer in LAYERS:
        group = [c for c in calls if c['layer'] == layer]
        if len(group) >= MIN_CALLS_FOR_LAYER_RATIO:
            ratios[layer] = pair(group)
    return ratios


def opus47_calibration():
    with open(REFERENCE / 'opus47_chars_per_token.csv', encoding='utf-8', newline='') as handle:
        return {r['layer']: (float(r['in_chars_per_token']), float(r['out_chars_per_token'])) for r in csv.DictReader(handle) if r['used_for_estimation'] == 'True'}


def price_calls(calls):
    """Sets the billed flag, the tokens used (reported or estimated) and the cost on every call; returns the ratio table."""
    for c in calls:
        c['billed'] = c['layer'] != REPLAYED and c['http_status'] in (None, 200)
        c['input_chars'] = c['system_chars'] + c['prompt_chars']
        c['reported'] = c['billed'] and c['input_tokens'] is not None
    billed = [c for c in calls if c['billed']]
    replayed = sum(c['layer'] == REPLAYED for c in calls)
    print('calls %d; replayed %d and HTTP status other than 200 %d are left out' % (len(calls), replayed, len(calls) - len(billed) - replayed))
    unclassified = sorted({c['layer'] for c in billed} - set(LAYERS))
    if unclassified:
        raise ValueError('system prompts without a layer: %s' % unclassified)
    other_model = sorted({(c['set'], c['model']) for c in billed if c['model'] != MODEL[c['set']]})
    if other_model:
        raise ValueError('calls to a model other than the set model: %s' % other_model)

    calibration = opus47_calibration()
    own = {key: chars_per_token([c for c in billed if c['set'] == key]) for key in FOLDER}
    sol_visible = chars_per_token([c for c in billed if c['set'] == 'gpt6sol'], visible_output=True)

    def ratio(key, layer):
        if key == 'opus47':
            if layer in calibration:
                return calibration[layer], 'Opus 4.7 calibration table'
            if layer in own['opus47']:
                return own['opus47'][layer], 'stored Opus 4.7 calls with reported usage'
            return calibration['GLOBAL'], 'Opus 4.7 calibration table, all layers'
        source, name = (sol_visible, 'stored GPT-6 Sol calls, visible output') if key == 'gpt55' else (own[key], 'stored calls of the same model')
        return (source[layer], name) if layer in source else (source['ALL'], name + ', all layers')

    for c in calls:
        c['token_source'] = 'reported' if c['reported'] else 'estimated' if c['billed'] else ''
        c['input_tokens_used'] = c['output_tokens_used'] = c['cost_usd'] = None
        if not c['billed']:
            continue
        if c['reported']:
            c['input_tokens_used'], c['output_tokens_used'] = c['input_tokens'], c['output_tokens']
        else:
            per_input, per_output = ratio(c['set'], c['layer'])[0]
            c['input_tokens_used'], c['output_tokens_used'] = c['input_chars'] / per_input, c['response_chars'] / per_output
        c['cost_usd'] = (c['input_tokens_used'] * PRICE[c['set']][0] + c['output_tokens_used'] * PRICE[c['set']][1]) / 1e6

    table = []
    for key in FOLDER:
        for layer in LAYERS:
            group = [c for c in billed if c['set'] == key and c['layer'] == layer]
            if group:
                (per_input, per_output), origin = ratio(key, layer)
                table.append({'set': key, 'layer': layer, 'input_chars_per_token': round(per_input, 4), 'output_chars_per_token': round(per_output, 4),
                              'from': origin, 'calls_estimated': sum(not c['reported'] for c in group)})
    return table


def timed_out(key, run):
    manifest = load_json(BENCHMARK / FOLDER[key] / run / 'manifest.json')[0]
    return bool(manifest.get('timed_out', False)) if isinstance(manifest, dict) else ''


def per_prompt_tables(calls):
    """set key -> one row per prompt: cost per layer, call counts and tokens (reported and estimated parts)."""
    tables = {}
    for key in FOLDER:
        group = [c for c in calls if c['billed'] and c['set'] == key]
        rows = []
        for prompt, run in sorted({(c['id'], c['run']) for c in group}, key=lambda pr: prompt_key(pr[0])):
            part = [c for c in group if c['run'] == run]
            reported, estimated = [c for c in part if c['reported']], [c for c in part if not c['reported']]
            cost = {layer: sum(c['cost_usd'] for c in part if c['layer'] == layer) for layer in LAYERS}
            rows.append({'family': prompt.split('_')[0], 'id': prompt, 'session': run, 'estimated': int(bool(estimated)), 'timed_out': timed_out(key, run),
                         'cost_total_usd': round(sum(cost.values()), 4), **{layer: round(cost[layer], 4) for layer in LAYERS},
                         'calls': len(part), 'calls_with_real_usage': len(reported),
                         'input_tokens': int(sum(c['input_tokens_used'] for c in part)), 'output_tokens': int(sum(c['output_tokens_used'] for c in part)),
                         'input_tokens_reported': int(sum(c['input_tokens_used'] for c in reported)), 'output_tokens_reported': int(sum(c['output_tokens_used'] for c in reported)),
                         'input_tokens_estimated': int(sum(c['input_tokens_used'] for c in estimated)), 'output_tokens_estimated': int(sum(c['output_tokens_used'] for c in estimated))})
        tables[key] = rows
    return tables


def summary_table(calls, tables):
    rows = []
    for key in FOLDER:
        group = [c for c in calls if c['billed'] and c['set'] == key]
        cost = sum(c['cost_usd'] for c in group)
        rows.append({'set': key, 'prompts': len(tables[key]), 'calls': len(group), 'calls_real_usage': sum(c['reported'] for c in group),
                     'input_Mtok': round(sum(c['input_tokens_used'] for c in group) / 1e6, 3), 'output_Mtok': round(sum(c['output_tokens_used'] for c in group) / 1e6, 3),
                     'cost_usd': round(cost, 3), 'cost_from_real_usage_usd': round(sum(c['cost_usd'] for c in group if c['reported']), 3),
                     'mean_per_prompt': round(cost / len(tables[key]), 3), 'max_prompt': round(max(r['cost_total_usd'] for r in tables[key]), 3)})
    return rows


def estimate_check(calls):
    """Prints the Opus 4.7 estimate next to the reported cost for the Opus 4.7 calls whose usage is reported."""
    part = [c for c in calls if c['set'] == 'opus47' and c['reported']]
    if not part:
        return
    calibration, own = opus47_calibration(), chars_per_token(part)
    runs = {}
    for c in part:
        per_input, per_output = calibration.get(c['layer']) or own.get(c['layer']) or calibration['GLOBAL']
        estimate = (c['input_chars'] / per_input * PRICE['opus47'][0] + c['response_chars'] / per_output * PRICE['opus47'][1]) / 1e6
        total = runs.setdefault(c['run'], [0.0, 0.0])
        total[0] += estimate
        total[1] += c['cost_usd']
    estimated, reported = sum(t[0] for t in runs.values()), sum(t[1] for t in runs.values())
    per_run = [t[0] / t[1] for t in runs.values()]
    print('estimate check, Opus 4.7 calls with reported usage (%d): estimated $%.2f, reported $%.2f, ratio %.3f; per run %.3f to %.3f'
          % (len(part), estimated, reported, estimated / reported, min(per_run), max(per_run)))


def figure_table(tables):
    """One row per bar: set, prompt and the fourteen stacked segments."""
    rows = []
    for key in FOLDER:
        for r in tables[key]:
            segments = {label: round(sum(r[layer] for layer in layers), 4) for label, _, layers in FIGURE_STACK}
            rows.append({'set': key, 'id': r['id'], 'session': r['session'], **segments, 'total': round(sum(segments.values()), 4)})
    return rows


def panel_tables(bars):
    """file name -> rows of one panel, ready to plot as stacked columns; and the table of the segments."""
    segments = [label for label, _, _ in FIGURE_STACK]
    panels = {}
    for letter, (key, folder, _, _, _) in zip('abcd', SETS):
        marked = NOT_COMPLETE.get(key, [])
        panels['panel_%s_%s.csv' % (letter, folder.replace(' ', '_'))] = [
            {'prompt': r['id'], **{s: r[s] for s in segments}, 'total': r['total'], 'not complete': 'X' if r['id'] in marked else ''}
            for r in bars if r['set'] == key]
    stack = [{'segment': label, 'colour': colour, 'layers': ' + '.join(layers)} for label, colour, layers in FIGURE_STACK]
    return panels, stack


def draw_figure(bars, out_dir):
    import io

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.ticker import MultipleLocator
    from PIL import Image

    plt.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'Liberation Sans', 'DejaVu Sans'], 'font.size': 7.5,
                         'axes.linewidth': 0.6})
    fig = plt.figure(figsize=(6.867, 4.063), dpi=300)
    boxes = {'opus47': (0.0609, 0.4742, 0.9185, 0.4663), 'opus55': (0.0609, 0.1066, 0.2733, 0.2351),
             'gpt55': (0.3842, 0.1066, 0.2733, 0.2351), 'gpt6sol': (0.7027, 0.1066, 0.2738, 0.2351)}
    for letter, (key, _, _, title, _) in zip('abcd', SETS):
        part = [r for r in bars if r['set'] == key]
        prompts = [r['id'] for r in part]
        ax = fig.add_axes(boxes[key])
        x = np.arange(1, len(part) + 1)
        bottom = np.zeros(len(part))
        for label, colour, _ in FIGURE_STACK:
            height = np.array([r[label] for r in part])
            ax.bar(x, height, 0.8, bottom=bottom, color=colour, edgecolor='black', linewidth=0.5, label=label)
            bottom += height
        ax.set_xlim(0.5, len(part) + 0.5)
        ax.set_ylim(0, 80 if key == 'opus47' else 40)
        ax.yaxis.set_major_locator(MultipleLocator(10))
        ax.yaxis.set_minor_locator(MultipleLocator(5))
        ax.tick_params(axis='both', which='major', direction='in', length=3, width=0.6, pad=3)
        ax.tick_params(axis='y', which='minor', direction='in', length=1.8, width=0.6)
        ax.set_xticks(x)
        ax.set_xticklabels([prompt + '_' for prompt in prompts], rotation=90)
        if key in ('opus47', 'opus55'):
            ax.set_ylabel('Costs (~$)', labelpad=2)
        head = ax.text(0.0, 1.03, '(%s)' % letter, transform=ax.transAxes, fontweight='bold', ha='left', va='bottom')
        ax.annotate(' ' + title, xy=(1, 0), xycoords=head, ha='left', va='bottom')
        for prompt in NOT_COMPLETE.get(key, []):
            position = prompts.index(prompt)
            ax.text(position + 1, bottom[position] + 3.2, 'X', fontweight='bold', fontsize=9, ha='center', va='center')
        if key == 'opus47':
            families = [prompt.split('_')[0] for prompt in prompts]
            for position in range(1, len(families)):
                if families[position] != families[position - 1]:
                    ax.axvline(position + 0.5, color='#808080', linewidth=0.5)
            for text, centre in FAMILY_LABELS:
                ax.text(centre, 75.3, text, ha='center', va='center', fontsize=8)
            handles, labels = ax.get_legend_handles_labels()
            legend = ax.legend(handles[::-1], labels[::-1], loc='upper right', bbox_to_anchor=(0.9615, 0.892), fontsize=6.3, frameon=True, fancybox=False, edgecolor='black',
                               framealpha=1.0, borderpad=0.25, labelspacing=0.14, handlelength=1.8, handleheight=1.0, handletextpad=0.5, borderaxespad=0.0)
            legend.get_frame().set_linewidth(0.6)
    # Pillow writes the TIFF uncompressed with its own writer; a compressed TIFF needs its libtiff binding, which
    # does not work in every installation.
    rendered = io.BytesIO()
    fig.savefig(rendered, format='png', dpi=300)
    plt.close(fig)
    rendered.seek(0)
    Image.open(rendered).convert('RGB').save(out_dir / 'cost_per_prompt_by_layer.tiff', dpi=(300, 300))


def write_table(path, rows, columns=None):
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns or list(rows[0]), extrasaction='ignore', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description='Cost of the model calls of the stored benchmark runs.')
    parser.add_argument('--out', type=Path, default=HERE / 'output', help='output folder: the figure, and the tables in csv/')
    parser.add_argument('--reuse-calls', action='store_true', help='read the written calls.csv instead of the run folders')
    parser.add_argument('--jobs', type=int, default=8, help='parallel file readers')
    args = parser.parse_args()
    figure_dir = args.out
    tables_dir = figure_dir / 'csv'
    tables_dir.mkdir(parents=True, exist_ok=True)

    calls = read_call_table(tables_dir / 'calls.csv') if args.reuse_calls else extract_calls(args.jobs)
    ratio_table = price_calls(calls)
    tables = per_prompt_tables(calls)
    summary = summary_table(calls, tables)
    bars = figure_table(tables)

    shown = [{**c, 'billed': int(c['billed']), **{k: '' if c[k] is None else round(c[k], 6) for k in ('input_tokens_used', 'output_tokens_used', 'cost_usd')},
              **{k: '' if c[k] is None else c[k] for k in NUMBER_COLUMNS}} for c in calls]
    write_table(tables_dir / 'calls.csv', shown, TEXT_COLUMNS + NUMBER_COLUMNS + PRICED_COLUMNS)
    write_table(tables_dir / 'chars_per_token_used.csv', ratio_table)
    for key, rows in tables.items():
        write_table(tables_dir / ('per_prompt_layer_costs_%s.csv' % key), rows)
    write_table(tables_dir / 'cost_summary.csv', summary)
    write_table(tables_dir / 'figure_bars.csv', bars)
    panels, stack = panel_tables(bars)
    for name, rows in panels.items():
        write_table(tables_dir / name, rows)
    write_table(tables_dir / 'stack_segments.csv', stack)
    draw_figure(bars, figure_dir)

    for row in summary:
        print('  '.join('%s=%s' % kv for kv in row.items()))
    estimate_check(calls)
    print('written to', figure_dir)


if __name__ == '__main__':
    main()
