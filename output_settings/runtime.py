"""Load explicit local settings before importing native scientific components."""
from __future__ import annotations
from copy import deepcopy
from contextlib import ExitStack
from dataclasses import fields
import importlib
import json
import os
from pathlib import Path
import sys
import math
from SRD46_research_agent.NIST_SRD46_db_agent.general_db_query_engine.general_argo_engine_helpers.provider_request_options import (
    endpoint, header_options, request_options)

ROOT = Path(__file__).absolute().parents[1]
SETTINGS_FILE = ROOT / 'srd46_analysis_settings.json'
MODEL_ROLES = ('MODEL', 'VERDICT_MODEL', 'PLANNER_MODEL', 'L1_MODEL', 'L2_MODEL',
               'LC1_1_MODEL', 'LC1_2_MODEL', 'LC1_3_QUERY_MODEL', 'LC1_3_PARSER_MODEL')
MODEL_IDS = {
    'claudeopus47': 'claude-opus-4-7', 'claudeopus55': 'claude-opus-5-5',
    'claudesonnet47': 'claude-sonnet-4-7',
    'gpt55': 'gpt-5.5', 'gpt6astra': 'gpt-6-astra', 'gpt6sol': 'gpt-6-sol',
}
_settings = {}
_query_session = None
_analysis_defaults = None

def _import_path(path):
    text = str(path)
    if os.name != 'nt' or text.startswith('\\\\?\\'):
        return text
    if text.startswith('\\\\'):
        return '\\\\?\\UNC\\' + text[2:]
    return '\\\\?\\' + text


def import_paths():
    paths = [str(ROOT), str(ROOT / 'output_settings'),
             _import_path(ROOT / 'SRD46_research_agent'),
             _import_path(ROOT / 'SRD46_research_agent/NIST_SRD46_database_browser')]
    for path in reversed(paths):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    existing = os.environ.get('PYTHONPATH', '').split(os.pathsep)
    os.environ['PYTHONPATH'] = os.pathsep.join(dict.fromkeys([*(str(p) for p in paths), *filter(None, existing)]))

def read_settings(path=None, **overrides):
    file = Path(path) if path and not isinstance(path, dict) else SETTINGS_FILE
    settings = deepcopy(path) if isinstance(path, dict) else json.loads(file.read_text('utf-8-sig'))
    if settings.get('schema') != 'srd46-analysis-settings/v1':
        raise ValueError('Unsupported SRD-46 settings schema')
    for key, value in overrides.items():
        if value is not None:
            settings[key] = value
    for key in ('api_url', 'api_model', 'api_timeout'):
        if settings.get(key) == 'default':
            settings[key] = None
    # A dictionary is an already resolved snapshot (also used for restoration).
    settings['api_user'] = settings.get('api_user', '') if isinstance(path, dict) else (
        settings.get('api_user') or os.environ.get('SRD46_ANALYSIS_ARGO_API_USER', ''))
    if settings.get('api_key_env') and (not isinstance(settings['api_key_env'], str) or not settings['api_key_env'].isidentifier()):
        raise ValueError('api_key_env must name an environment variable; never supply a credential')
    if settings.get('provider') not in ('argo', 'anthropic', 'openai'):
        raise ValueError('Provider must be argo, anthropic or openai')
    if settings.get('model') not in MODEL_IDS:
        raise ValueError('Unknown model alias; configure an explicit model preset')
    if not isinstance(settings.get('reasoning_effort', 'default'), str) or not settings.get('reasoning_effort', 'default').strip():
        raise ValueError('Invalid reasoning effort')
    if settings.get('thinking_mode', 'default') not in ('default', 'adaptive', 'enabled', 'disabled', 'between_tools'):
        raise ValueError('Invalid thinking mode')
    if settings['provider'] == 'argo' and (settings.get('reasoning_effort', 'default') != 'default' or settings.get('thinking_mode', 'default') != 'default'):
        raise ValueError('This Argo interface exposes provider-default reasoning only; explicit reasoning/thinking requires a direct provider')
    if settings['provider'] == 'openai' and (not settings['model'].startswith('gpt') or settings.get('thinking_mode', 'default') != 'default'):
        raise ValueError('OpenAI requires a GPT alias; use reasoning_effort, not an Anthropic thinking mode')
    if settings['provider'] == 'anthropic' and not settings['model'].startswith('claude'):
        raise ValueError('Anthropic requires a Claude alias')
    for key in ('topology_cleanup', 'lv_write_artifacts', 'estimate_missing_equilibria'):
        if type(settings.get(key)) is not bool:
            raise ValueError(key + ' must be true or false')
    if type(settings.get('openai_max_completion_tokens')) is not int or settings['openai_max_completion_tokens'] <= 0:
        raise ValueError('openai_max_completion_tokens must be a positive integer')
    if settings.get('api_url'):
        endpoint(settings['api_url'])
    if settings.get('api_model') is not None and (not isinstance(settings['api_model'], str) or not settings['api_model'].strip()):
        raise ValueError('api_model must be a nonempty provider model ID')
    timeout = settings.get('api_timeout')
    if timeout is not None and (type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0):
        raise ValueError('api_timeout must be a positive number')
    request_options(settings.get('api_parameters', {}))
    header_options(settings.get('api_headers', {}))
    header_options(settings.get('api_header_env', {}), env_names=True)
    aliases = settings.get('api_response_models', [])
    if not isinstance(aliases, list) or any(not isinstance(v, str) or not v.strip() for v in aliases):
        raise ValueError('api_response_models must list provider response model IDs')
    direct_options = ('api_url', 'api_model', 'api_timeout', 'api_parameters', 'api_headers', 'api_header_env', 'api_response_models')
    if settings['provider'] == 'argo' and any(settings.get(key) for key in direct_options):
        raise ValueError('Direct API options require --provider openai or anthropic; Argo uses argo_api_url')
    return settings

def provider_config(settings=None):
    s = settings or _settings
    if s['provider'] == 'argo':
        return None
    result = {'provider': s['provider'], 'model_map': {s['model']: s.get('api_model') or MODEL_IDS[s['model']]},
              'api_key_env': s.get('api_key_env') or ('OPENAI_API_KEY' if s['provider'] == 'openai' else 'ANTHROPIC_API_KEY')}
    if s['provider'] == 'openai':
        result['max_completion_tokens'] = s['openai_max_completion_tokens']
    if s.get('reasoning_effort', 'default') != 'default':
        result['reasoning_effort'] = s['reasoning_effort']
    if s.get('thinking_mode', 'default') != 'default':
        result['thinking_mode'] = s['thinking_mode']
    if s.get('api_model'):
        result['allow_custom_model'] = True
    for source, target in (('api_url', 'api_url'), ('api_timeout', 'timeout_override'),
                           ('api_parameters', 'request_parameters'), ('api_headers', 'headers'),
                           ('api_header_env', 'header_env'), ('api_response_models', 'response_model_aliases')):
        if s.get(source):
            result[target] = deepcopy(s[source])
    return result

def validate_credentials(settings):
    if settings['provider'] == 'argo':
        if not settings['api_user'].strip() or settings['api_user'] == 'local':
            raise ValueError('Set --api-user or SRD46_ANALYSIS_ARGO_API_USER to your authorized Argo account')
    else:
        cfg = provider_config(settings)
        if not cfg['api_key_env'].isidentifier() or not os.environ.get(cfg['api_key_env']):
            raise ValueError('Set credential environment variable ' + cfg['api_key_env'])

def _topology_setting(enabled):
    """Bind the existing solver switch, including already imported consumers."""
    os.environ['SRD46_TOPOLOGY_FIX'] = '1' if enabled else '0'
    prefix = 'NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_core_numcalc_pipeline.'
    for name, module in tuple(sys.modules.items()):
        if name.startswith(prefix) and hasattr(module, 'TOPO_FIX_ENABLE'):
            module.TOPO_FIX_ENABLE = enabled


def configure(path=None, *, require_credentials=True, settings=None, **overrides):
    global _settings, _analysis_defaults
    s = read_settings(settings if settings is not None else path, **overrides)
    if require_credentials:
        validate_credentials(s)
    import_paths()
    logical_user = s.get('api_user') or ('local' if s['provider'] != 'argo' else '')
    os.environ['SRD46_ANALYSIS_ARGO_API_USER'] = logical_user
    os.environ['ARGO_API_USER'] = logical_user
    os.environ['SRD46_QUERY_MODEL_OVERRIDE'] = s['model']
    os.environ['ARGO_API_URL'] = s['argo_api_url']
    _topology_setting(s['topology_cleanup'])
    root = Path(s.get('output_root', '_output'))
    root = root if root.is_absolute() else ROOT / root
    os.environ['SRD46_OUTPUT_ROOT'] = str(root.absolute())
    import output_paths
    output_paths.OUTPUT_ROOT = root.absolute()
    module = importlib.import_module('NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.SRD46_analysis_argo_config')
    config = module.AGENT_CONFIG
    if _analysis_defaults is None:
        _analysis_defaults = {field.name: deepcopy(getattr(config, field.name)) for field in fields(config)}
    for key, value in _analysis_defaults.items():
        setattr(config, key, deepcopy(value))
    for role in MODEL_ROLES:
        setattr(config, role, s['model'])
    config.API_USER, config.API_URL = logical_user, s['argo_api_url']
    config.LV_WRITE_ARTIFACTS = s['lv_write_artifacts']
    for key, value in s.get('analysis', {}).items():
        if key in MODEL_ROLES or key in {'API_USER', 'API_URL', 'HEADERS', 'LV_WRITE_ARTIFACTS', 'LC1_3_ESTIMATE_EQ_STABILITY_ENABLED'} or not hasattr(config, key):
            raise ValueError('Unknown or reserved analysis setting: ' + key)
        previous = getattr(config, key)
        if previous is not None and type(value) is not type(previous):
            raise ValueError('Wrong type for analysis setting: ' + key)
        setattr(config, key, value)
    q = importlib.import_module('NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_config')
    q.API_USER, q.API_URL = logical_user, s['argo_api_url']
    transport = sys.modules.get('NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_client')
    if transport is not None:
        transport.API_USER, transport.API_URL = logical_user, s['argo_api_url']
    for name in ('MODEL', 'PLANNER_MODEL', 'VERDICT_MODEL', 'ENRICHER_MODEL', 'CLAIM_CLASSIFIER_MODEL', 'GROUNDER_MODEL'):
        setattr(q, name, s['model'])
    for name in ('CLAIM_CLASSIFIER_MODEL_FALLBACKS', 'GROUNDER_MODEL_FALLBACKS'):
        setattr(q, name, (s['model'],))
    _settings = s
    return deepcopy(s)

def current_settings():
    return deepcopy(_settings)

def restore_configuration(settings):
    return configure(settings=settings, require_credentials=False)

def restore_data():
    from zip_images.large_file_packs import self_check
    result = self_check(ROOT, honour_env=False)
    if result.get('errors') or result.get('stripped_missing'):
        raise RuntimeError('Packed databases could not be restored; inspect the large-file check report')
    return result

def begin_session(session, **kwargs):
    """Validate launch settings; scientific files are written by the native API."""
    global _query_session
    validate_credentials(_settings)
    if kwargs.get('session_kind') == 'query':
        from NIST_SRD46_db_agent.general_db_query_engine.general_first_principle_API_call_reconstruct import ReconstructionSession
        from NIST_SRD46_db_agent.NIST_SRD46_query_agent.query_artifacts import query_artifact_scope
        recorder = ReconstructionSession(mode='regular', output_dir=Path(session) / 'run_provenance/first_principle_reconstruction/attempt_0001', live_provider=provider_config(), live_api_user=_settings.get('api_user') or None)
        recorder.query_replay_enabled = True
        _query_session = ExitStack()
        _query_session.enter_context(recorder)
        _query_session.enter_context(query_artifact_scope(session))

def finish_session():
    global _query_session
    if _query_session is not None:
        _query_session.__exit__(None, None, None)
        _query_session = None
