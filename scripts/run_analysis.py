"""Benchmark selection and process scheduling around the native Analysis API."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import json
import logging
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).absolute().parents[1]
sys.path.insert(0, str(ROOT))
from output_settings.runtime import (read_settings, configure, restore_data,
                                     provider_config, validate_credentials)
from output_settings.api_flags import add_flags, apply_flags
from output_settings.freeform_markdown import load_prompt, bind_run_metadata

GUIDE = r"""# Native benchmark runner

| --preset | Provider | Model | Topology cleanup |
|---|---|---|---|
| `opus47` | Argo | Opus 4.7 | On |
| `opus47_no_topo` | Argo | Opus 4.7 | Off |
| `opus47_anthropic` | Anthropic | Opus 4.7 | On |
| `opus55_anthropic` | Anthropic | Opus 5.5 | On |
| `gpt55` | Argo | GPT-5.5 | On |
| `gpt55_openai` | OpenAI | GPT-5.5 | On |
| `gpt6sol_openai` | OpenAI | GPT-6 Sol | On |
| `gpt6astra_openai` | OpenAI | GPT-6 Astra | On |
| `sonnet47_anthropic` | Anthropic | Sonnet 4.7 (unverified example) | On |

Select a preset with `python scripts/run_analysis.py --preset NAME`.
Explicit flags override its values. Without `--run`, the command prints a plan
without starting model calls or creating run folders. Model availability depends
on your endpoint and account.

Examples (from the repository root):

```powershell
python scripts/run_analysis.py --preset opus47_no_topo --prompt-group L1
python scripts/run_analysis.py --preset gpt55_openai --prompts L1_4 --run
python scripts/run_analysis.py --preset gpt6sol_openai --prompt-group L1 --reasoning-effort high --run
python scripts/run_analysis.py --check
```

## Select inputs

`--list` prints the native catalog, including full original questions.
`--prompts L1_4 L1_5` selects specific short IDs or full catalog labels.
`--prompt-group` accepts `L1`, `L2`, `L3`, `L4`, the corresponding catalog tags
`DIAG`, `MULTI`, `HYPO`, `HALL`, `all`, `draft`, or `speciation`.
`--exclude L1_9` removes individual IDs. `--order speciation-first` moves the
four speciation-focused level-1 prompts to the front of the selected set.

The `draft` group is ordered L1_9, L1_4, L1_1, L1_2, L1_3, L1_10, L1_11.
The `speciation` group is L1_4, L1_5, L1_7, L1_9. These selections do not rewrite
the questions or constrain the calculations an agent chooses to perform.

Numbered benchmark batches exclude FF_1. Run it separately, across models if
desired, using separate fresh destinations:

```powershell
python scripts/run_ff1.py --preset opus47_anthropic --run
python scripts/run_ff1.py --preset gpt55_openai --run
```

FF_1 retains its catalog estimation flag and L0 budget defaults. For arbitrary
questions use `scripts/run_analysis.py --prompt "..."` or `--prompt-file question.md`. Plain text is also accepted.
The supplied `examples/FF_1.md` has YAML metadata and an explicit user_prompt field.

## Settings and output

| Flag | Effect |
|---|---|
| `--settings FILE` | Read an alternative settings JSON. |
| `--provider`, `--model` | Select the API and bind every model role. |
| `--api-user`, `--api-key-env` | Authorized Argo identity or credential environment-variable name. |
| `--reasoning-effort` | `default` omits the field; explicit values use a direct provider. |
| `--thinking-mode` | `default`, or explicit Anthropic `adaptive`, `enabled`, `disabled`, `between_tools`. |
| `--api-url`, `--api-model` | Full custom endpoint and physical model ID; native `--model` remains the family alias. |
| `--api-timeout` | Explicit HTTP timeout in seconds, including embedded Query calls. |
| `--api-response-model` | Additional accepted response model ID; repeat for aliases. |
| `--api-param FIELD=JSON`, `--api-params-file FILE` | Physical request parameters; dotted nested fields are supported. |
| `--api-header NAME=VALUE`, `--api-header-env NAME=ENV` | Non-secret headers or environment-bound header values. |
| `--anthropic-max-tokens`, `--thinking-budget-tokens` | Total Messages output allowance and manual thinking budget. |
| `--temperature`, `--top-p`, `--top-k`, `--seed` | Explicit sampling controls; support depends on the provider/model. |
| `--thinking-display`, `--verbosity`, `--service-tier` | Provider-specific output and service controls. |
| `--openai-max-completion-tokens` | Total direct OpenAI reasoning plus output allowance. |
| `--[no-]topology-cleanup` | Native topology cleanup; enabled by default. |
| `--[no-]lv-write-artifacts` | Whether LV writes its own folder; false by default. |
| `--[no-]estimate-missing-equilibria` | Native estimation mode. |
| `--set FIELD=JSON` | Typed native Analysis configuration field, such as `L1_MAX_ITERATIONS=10`. |
| `--max-iterations`, `--reasoning-timeout` | Native L0 turn/reminder-time settings. |
| `--output-root DIR` | Parent for generated model/preset folders. |
| `--session-dir DIR` | Exact fresh destination, for one prompt only. |
| `--date YYYYMMDD` | Date component of the run folder; no time or hash suffix. |
| `--jobs N` | Independent processes for complete runs; default 1. |
| `--stop-on-failure` | Sequential dispatch stops after a non-complete result. |
| `--stop-file FILE` | Stop new dispatches when FILE exists; active work completes. |
| `--run` | Execute; otherwise show a plan without model calls or output folders. |

Defaults resolve as settings JSON → Markdown settings → preset → explicit flags.
Markdown `run` fields supply launcher defaults; explicit command-line flags win.
The default marker inherits settings; reasoning_effort and thinking_mode set to
default explicitly omit those provider fields. Native `analysis`
fields in JSON and `--set` cannot override reserved model/account fields; use
their named options. Default output is `_output/<configuration>/<ID>_<YYYYMMDD>`.
The configuration folder uses the selected preset name when it matches the
resolved settings; otherwise it uses `<model>_<provider>`. Topology, reasoning,
and thinking suffixes are added when applicable. Choose a new root or exact
destination to repeat a prompt on the same date.
Existing output folders are never overwritten, resumed, or archived implicitly.

There is no private phase hook or injected solver pause. For native exact
reconstruction use the native API and its verified ledger contract; this
fresh-run launcher does not substitute summaries for context.

## Direct API parameters

Both entry points accept the same flags. The endpoint must implement OpenAI Chat
Completions or Anthropic Messages, with one non-streaming text response.
`--api-model` changes the physical model ID; retain a compatible native family
alias in `--model`. Conversation framing and pipeline tools are not replaceable
through request parameters. Unsupported model options are reported by the endpoint;
no options are silently removed and no model fallback is used.

OpenAI defaults to 32,000 total completion tokens. `--max-completion-tokens` is
an alias for `--openai-max-completion-tokens`; this ceiling includes reasoning
and visible output. There is no independent OpenAI reasoning-token budget.
Anthropic defaults to the native per-call max_tokens; `--anthropic-max-tokens`
overrides it for every call. Manual thinking requires `--thinking-mode enabled`
and a budget of at least 1,024 below the total max_tokens. Adaptive thinking uses
`--thinking-mode adaptive --reasoning-effort high`, without a manual budget.
Leaving effort/thinking at default omits those fields. Model support varies.

```powershell
python scripts/run_analysis.py --preset gpt55_openai --prompts L1_4 --api-url https://api.example.org/v1/chat/completions --api-model custom-gpt --reasoning-effort high --max-completion-tokens 48000
python scripts/run_ff1.py --preset opus47_anthropic --thinking-mode enabled --thinking-budget-tokens 4096 --anthropic-max-tokens 16000
python scripts/run_ff1.py --preset opus47_anthropic --thinking-mode adaptive --reasoning-effort high --api-header anthropic-beta=YOUR_SUPPORTED_BETA
```

These examples print plans; append `--run` to execute. Use a JSON parameters
file to avoid shell quoting, for example `{"temperature": 0.3, "service_tier": "auto"}`.
Parameters merge in this order: settings/Markdown api_parameters, parameters file,
repeated --api-param values, explicit named generation flags. Named flags win.
A request override applies to all new live calls, including embedded Query.
Native per-stage settings remain adjustable with --set; a physical API override
takes precedence over them. Credentials belong in environment variables only.

## Freeform Markdown

`examples/FF_1.md` lists every supported metadata field and its explicit defaults.
FF_1 selects Argo/Opus 4.7, estimation enabled, 14 L0 iterations, a 1,200-second
L0 reasoning timeout, topology cleanup on and LV artifact writing off. CLI
presets and flags can override these values. `default` marks account, endpoint
or destination values supplied by the selected provider or launch environment. Its YAML frontmatter
uses schema `srd46-freeform-run/v1`, a filesystem-safe id, layer FREEFORM,
user_prompt, settings, run, and api_overrides, in that order. Write user_prompt
as a YAML literal block (`user_prompt: |`) immediately after layer. Only the
parsed user_prompt string is sent to the model; settings are not prompt text.
Keep all fields inside the opening and closing `---`; no trailing body is used. `settings` accepts the fields from
srd46_analysis_settings.json (except schema); nested analysis contains native
configuration overrides. `run` accepts preset, output_root, session_dir, date
(as a quoted YYYYMMDD string), jobs, order, debug, stop_file, stop_on_failure,
max_iterations and reasoning_timeout. Relative paths are resolved from the
launch working directory, except settings.output_root, which is relative to
the repository. `api_overrides` contains the native estimate_missing_equilibria,
l0_max_iterations and l0_reasoning_timeout_s defaults. Explicit launcher flags
override those defaults. Metadata cannot launch API work: --run is required.

API references: https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create
and https://platform.claude.com/docs/en/api/messages/create .
"""

DRAFT = ('L1_9', 'L1_4', 'L1_1', 'L1_2', 'L1_3', 'L1_10', 'L1_11')
SPECIATION = ('L1_4', 'L1_5', 'L1_7', 'L1_9')
PRESETS = {
    'opus47': {'model': 'claudeopus47', 'provider': 'argo'},
    'opus47_no_topo': {'model': 'claudeopus47', 'provider': 'argo', 'topology_cleanup': False},
    'opus47_anthropic': {'model': 'claudeopus47', 'provider': 'anthropic'},
    'opus55_anthropic': {'model': 'claudeopus55', 'provider': 'anthropic'},
    'gpt55': {'model': 'gpt55', 'provider': 'argo'},
    'gpt55_openai': {'model': 'gpt55', 'provider': 'openai'},
    'gpt6sol_openai': {'model': 'gpt6sol', 'provider': 'openai'},
    'gpt6astra_openai': {'model': 'gpt6astra', 'provider': 'openai'},
    'sonnet47_anthropic': {'model': 'claudesonnet47', 'provider': 'anthropic'},
}

def catalog():
    file = ROOT / 'SRD46_research_agent/NIST_SRD46_db_agent/NIST_SRD46_analysis_agent/_DEBUG_input/TEST_PROMPTS.md'
    rows = []
    for line in file.read_text('utf-8-sig').splitlines():
        cells = [x.strip() for x in line.strip().strip('|').split('|')]
        if len(cells) >= 4 and cells[0].isdigit():
            label = cells[2].strip('`')
            match = re.match(r'(L[1-4]_\d+)(?:_|$)', label)
            if match:
                rows.append({'id': match[1], 'label': label, 'group': cells[1], 'prompt': '|'.join(cells[3:])})
    rows.extend(load_prompt(path) for path in sorted((ROOT / 'examples').glob('FF_*.md')))
    if len({x['id'] for x in rows}) != len(rows):
        raise ValueError('Duplicate prompt IDs')
    return rows

def select(args, *, ff1=False):
    rows = catalog()
    if args.prompt or args.prompt_file:
        if args.prompt_file:
            return [load_prompt(args.prompt_file)]
        question = args.prompt
        if not question.strip():
            raise ValueError('Empty prompt')
        return [{'id': 'freeform', 'label': 'freeform', 'group': 'FREEFORM', 'prompt': question.strip()}]
    ids = args.prompts or ([args.debug_id] if args.debug_id else None)
    if ids:
        lookup = {key: row for row in rows for key in (row['id'], row['label'])}
        missing = set(ids) - lookup.keys()
        if missing:
            raise ValueError('Unknown prompt IDs: ' + ', '.join(sorted(missing)))
        selected = list({lookup[x]['id']: lookup[x] for x in ids}.values())
    elif ff1:
        selected = [x for x in rows if x['id'] == 'FF_1']
    elif args.prompt_group == 'draft':
        selected = [next(x for x in rows if x['id'] == pid) for pid in DRAFT]
    elif args.prompt_group == 'speciation':
        selected = [next(x for x in rows if x['id'] == pid) for pid in SPECIATION]
    else:
        selected = [x for x in rows if x['group'] != 'FREEFORM' and
                    (args.prompt_group in (None, 'all') or x['group'] == args.prompt_group or x['id'].split('_')[0] == args.prompt_group)]
    selected = [x for x in selected if x['id'] not in (args.exclude or [])]
    if not ff1 and any(x['id'].startswith('FF_') for x in selected):
        raise ValueError('Use scripts/run_ff1.py for FF_1; it is separate from numbered benchmarks')
    if args.order == 'speciation-first':
        selected.sort(key=lambda x: (x['id'] not in SPECIATION,))
    if not selected:
        raise ValueError('No prompts selected')
    return selected

class RunParser(argparse.ArgumentParser):
    def parse_known_args(self, args=None, namespace=None):
        values = list(sys.argv[1:] if args is None else args)
        result, rest = super().parse_known_args(values, namespace)
        result._explicit = {self._option_string_actions[word.split('=', 1)[0]].dest
                            for word in values if word.split('=', 1)[0] in self._option_string_actions}
        return result, rest


def parser():
    p = RunParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False,
        epilog="Examples:\n"
               "  %(prog)s --preset gpt55_openai --prompts L1_4 --run\n"
               "  %(prog)s --preset opus47_no_topo --prompt-group L1\n"
               "  %(prog)s --guide  (presets, scheduling, settings, and output rules)")
    p.add_argument('--preset', choices=PRESETS, help='Model/provider preset; explicit flags override its settings')
    source = p.add_mutually_exclusive_group()
    source.add_argument('--prompts', nargs='+', help='Short IDs, e.g. L1_4 L1_5, or exact catalog labels')
    source.add_argument('--debug-id')
    source.add_argument('--prompt')
    source.add_argument('--prompt-file', type=Path)
    source.add_argument('--prompt-group', choices=['all', 'L1', 'L2', 'L3', 'L4', 'DIAG', 'MULTI', 'HYPO', 'HALL', 'draft', 'speciation'])
    p.add_argument('--exclude', nargs='*')
    p.add_argument('--order', choices=['catalog', 'speciation-first'], default='catalog')
    p.add_argument('--settings', type=Path)
    p.add_argument('--provider', choices=['argo', 'anthropic', 'openai'])
    p.add_argument('--model')
    p.add_argument('--api-user')
    p.add_argument('--api-key-env', help='Environment variable NAME only; never pass a key')
    p.add_argument('--reasoning-effort', help='Provider effort level, or default to omit it')
    p.add_argument('--thinking-mode', choices=['default', 'adaptive', 'enabled', 'disabled', 'between_tools'])
    p.add_argument('--openai-max-completion-tokens', '--max-completion-tokens', type=int)
    add_flags(p)
    for name in ('topology-cleanup', 'lv-write-artifacts', 'estimate-missing-equilibria'):
        p.add_argument('--' + name, action=argparse.BooleanOptionalAction, default=None)
    p.add_argument('--set', action='append', default=[], metavar='FIELD=JSON', help='Typed native AGENT_CONFIG override; model/account settings use named flags')
    p.add_argument('--output-root', type=Path)
    p.add_argument('--session-dir', type=Path, help='Fresh exact folder for a single selected prompt')
    p.add_argument('--date', default=date.today().strftime('%Y%m%d'), help='YYYYMMDD output date')
    p.add_argument('--jobs', type=int, default=1, help='Concurrent complete native runs, each in its own process')
    p.add_argument('--max-iterations', type=int)
    p.add_argument('--reasoning-timeout', type=float)
    p.add_argument('--stop-file', type=Path, help='Stop dispatching new runs when this file exists; active runs finish')
    p.add_argument('--stop-on-failure', action='store_true', help='Sequential mode only; stop after a non-complete native result')
    p.add_argument('--debug', action='store_true')
    p.add_argument('--guide', action='store_true', help='Print the complete embedded usage guide; no model calls')
    p.add_argument('--list', action='store_true')
    p.add_argument('--check', action='store_true', help='Offline native import and database checks')
    p.add_argument('--run', action='store_true', help='Make model calls; without this flag print the plan only')
    p.add_argument('--_worker', action='store_true', help=argparse.SUPPRESS)
    return p

def resolve(args, preset=None, ff1=False):
    rows = select(args, ff1=ff1)
    document_settings = bind_run_metadata(args, rows)
    chosen = args.preset or preset
    if chosen and chosen not in PRESETS:
        raise ValueError('Unknown preset: ' + chosen)
    overrides = dict(document_settings, **PRESETS.get(chosen, {}))
    for key in ('provider', 'model', 'api_user', 'api_key_env', 'reasoning_effort', 'thinking_mode',
                'openai_max_completion_tokens', 'topology_cleanup', 'lv_write_artifacts', 'estimate_missing_equilibria'):
        if getattr(args, key) is not None:
            overrides[key] = getattr(args, key)
    if args.output_root is not None:
        overrides['output_root'] = str(args.output_root.absolute())
    s = read_settings(args.settings, **overrides)
    s = read_settings(apply_flags(s, args))
    if s['provider'] != 'argo':
        from SRD46_research_agent.NIST_SRD46_db_agent.general_db_query_engine.general_argo_engine_helpers.provider_request_options import validate_generation
        validate_generation(provider_config(s))
    for item in args.set:
        key, sep, value = item.partition('=')
        if not sep:
            raise ValueError('--set expects FIELD=JSON')
        s.setdefault('analysis', {})[key] = json.loads(value)
    if args.order not in ('catalog', 'speciation-first'):
        raise ValueError('Unknown prompt ordering')
    if args.jobs < 1 or args.stop_on_failure and args.jobs != 1:
        raise ValueError('jobs must be positive; stop-on-failure requires jobs=1')
    import math
    if args.max_iterations is not None and args.max_iterations < 1:
        raise ValueError('max-iterations must be positive')
    if args.reasoning_timeout is not None and (not math.isfinite(args.reasoning_timeout) or args.reasoning_timeout <= 0):
        raise ValueError('reasoning-timeout must be finite and positive')
    if not re.fullmatch(r'\d{8}', args.date):
        raise ValueError('Date must be YYYYMMDD')
    if args.session_dir and len(rows) != 1:
        raise ValueError('--session-dir requires exactly one prompt')
    root = Path(s['output_root'])
    root = root if root.is_absolute() else ROOT / root
    preset_matches = chosen and not s.get('api_model') and all(s[key] == value for key, value in PRESETS[chosen].items())
    model_label = re.sub(r'[^A-Za-z0-9_.-]', '_', s.get('api_model') or s['model']).strip('._')[:64]
    family = chosen if preset_matches else (model_label or 'model') + '_' + s['provider']
    if not s['topology_cleanup'] and 'no_topo' not in family:
        family += '_no_topo'
    if s['reasoning_effort'] != 'default':
        family += '_' + re.sub(r'[^A-Za-z0-9_-]', '_', s['reasoning_effort'])[:32]
    if s['thinking_mode'] != 'default':
        family += '_' + s['thinking_mode']
    for row in rows:
        row['session_dir'] = str((args.session_dir or root / family / (row['id'] + '_' + args.date)).absolute())
        row['estimate_missing_equilibria'] = (args.estimate_missing_equilibria if args.estimate_missing_equilibria is not None
            else row.get('api_overrides', {}).get('estimate_missing_equilibria', s['estimate_missing_equilibria']))
    return s, rows

def worker(settings, row, args):
    restore_data()
    configure(settings=settings)
    session = Path(row['session_dir'])
    session.mkdir(parents=True, exist_ok=False)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format='%(asctime)s %(name)s %(levelname)s %(message)s',
                        handlers=[logging.StreamHandler(), logging.FileHandler(session / '_run.log', encoding='utf-8')], force=True)
    from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent import SRD46_analysis_run
    extra = row.get('api_overrides', {})
    result = SRD46_analysis_run(row['prompt'], session_dir=session, debug=args.debug,
        estimate_missing_equilibria=row['estimate_missing_equilibria'],
        l0_max_iterations=args.max_iterations if args.max_iterations is not None else extra.get('l0_max_iterations'),
        l0_reasoning_timeout_s=args.reasoning_timeout if args.reasoning_timeout is not None else extra.get('l0_reasoning_timeout_s'),
        reconstruction_mode='regular', live_provider=provider_config(settings), live_api_user=settings.get('api_user') or None)
    print(json.dumps({'id': row['id'], 'session_dir': str(session), 'completion_status': result.get('completion_status')}, ensure_ascii=False), flush=True)
    return 0 if result.get('completion_status') == 'complete' else 2

def main(argv=None, *, preset=None, ff1=False):
    p = parser()
    args = p.parse_args(argv)
    if args.guide:
        print(GUIDE)
        return 0
    if args._worker:
        payload = json.load(sys.stdin)
        return worker(payload['settings'], payload['row'], args)
    if args.list:
        for row in catalog():
            print(f"{row['id']}\t{row['group']}\t{row['label']}\t{row['prompt']}")
        return 0
    try:
        settings, rows = resolve(args, preset, ff1)
        if args.check:
            configure(settings=settings, require_credentials=False)
            restore_data()
            from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent import SRD46_analysis_run
            print('Native Analysis API, settings, and database imports: OK')
            return 0
        print(json.dumps({'settings': settings, 'jobs': args.jobs, 'runs': rows}, indent=2, ensure_ascii=False), flush=True)
        if not args.run:
            return 0
        validate_credentials(settings)
        existing = [r['session_dir'] for r in rows if Path(r['session_dir']).exists()]
        if existing:
            raise ValueError('Existing run folders are never overwritten: ' + ', '.join(existing))
        restore_data()  # restore once before parallel children start
        def launch(row):
            if args.stop_file and args.stop_file.exists():
                return 3
            command = [sys.executable, '-B', '-u', str(Path(__file__).absolute()), '--_worker']
            if args.debug:
                command.append('--debug')
            if args.max_iterations is not None:
                command.extend(['--max-iterations', str(args.max_iterations)])
            if args.reasoning_timeout is not None:
                command.extend(['--reasoning-timeout', str(args.reasoning_timeout)])
            return subprocess.run(command, input=json.dumps({'settings': settings, 'row': row}), text=True, encoding='utf-8').returncode
        if args.jobs == 1:
            codes = []
            for row in rows:
                code = launch(row)
                codes.append(code)
                if code == 3 or args.stop_on_failure and code:
                    break
        else:
            with ThreadPoolExecutor(max_workers=args.jobs) as pool:
                codes = list(pool.map(launch, rows))
        return max(codes, default=0)
    except (ValueError, OSError) as exc:
        p.error(str(exc))

if __name__ == '__main__':
    raise SystemExit(main())
