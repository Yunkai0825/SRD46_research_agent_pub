"""Command-line bindings for direct-provider request settings."""
import json
from pathlib import Path
from copy import deepcopy
from SRD46_research_agent.NIST_SRD46_db_agent.general_db_query_engine.general_argo_engine_helpers.provider_request_options import merge


def add_flags(parser):
    parser.add_argument('--api-url', help='Full OpenAI Chat Completions or Anthropic Messages endpoint')
    parser.add_argument('--api-model', help='Provider model ID; --model keeps the native model-family alias')
    parser.add_argument('--api-timeout', type=float, help='Seconds per physical HTTP request; overrides native per-call timeouts')
    parser.add_argument('--api-response-model', action='append', dest='api_response_models', help='Additional accepted response model ID')
    parser.add_argument('--api-params-file', type=Path, help='JSON object of physical request parameters')
    parser.add_argument('--api-param', action='append', default=[], metavar='FIELD=JSON', help='Physical request override; dotted fields supported')
    parser.add_argument('--api-header', action='append', default=[], metavar='NAME=VALUE', help='Non-secret provider header, e.g. anthropic-beta')
    parser.add_argument('--api-header-env', action='append', default=[], metavar='NAME=ENV', help='Read an extra header value from an environment variable')
    parser.add_argument('--anthropic-max-tokens', type=int, help='Messages total output allowance, including thinking')
    parser.add_argument('--thinking-budget-tokens', type=int, help='Anthropic manual thinking budget; requires enabled thinking')
    parser.add_argument('--thinking-display', help='Anthropic thinking display, e.g. summarized or omitted')
    parser.add_argument('--temperature', type=float)
    parser.add_argument('--top-p', type=float)
    parser.add_argument('--top-k', type=int)
    parser.add_argument('--seed', type=int)
    parser.add_argument('--verbosity', help='OpenAI output verbosity')
    parser.add_argument('--service-tier')


def _pair(value):
    key, sep, data = value.partition('=')
    if not sep or not key.strip():
        raise ValueError('Expected NAME=VALUE: ' + value)
    return key.strip(), data


def _set(data, name, value):
    keys = name.split('.')
    if any(not key for key in keys):
        raise ValueError('Empty field in API parameter path')
    for key in keys[:-1]:
        if key in data and not isinstance(data[key], dict):
            raise ValueError('Conflicting API parameter paths: ' + name)
        data = data.setdefault(key, {})
    data[keys[-1]] = value


def apply_flags(settings, args):
    result = deepcopy(settings)
    for key in ('api_url', 'api_model', 'api_timeout', 'api_response_models'):
        value = getattr(args, key)
        if value is not None:
            result[key] = value
    params = deepcopy(result.get('api_parameters', {}))
    if args.api_params_file:
        supplied = json.loads(args.api_params_file.read_text('utf-8-sig'))
        if not isinstance(supplied, dict):
            raise ValueError('--api-params-file must contain an object')
        params = merge(params, supplied)
    for value in args.api_param:
        key, text = _pair(value)
        _set(params, key, json.loads(text))
    named = {'anthropic_max_tokens': 'max_tokens', 'thinking_budget_tokens': 'thinking.budget_tokens',
             'thinking_display': 'thinking.display', 'temperature': 'temperature', 'top_p': 'top_p',
             'top_k': 'top_k', 'seed': 'seed', 'verbosity': 'verbosity', 'service_tier': 'service_tier'}
    for arg, key in named.items():
        value = getattr(args, arg)
        if value is not None:
            if arg in {'anthropic_max_tokens', 'thinking_budget_tokens', 'thinking_display', 'top_k'} and result['provider'] != 'anthropic':
                raise ValueError('--' + arg.replace('_', '-') + ' requires Anthropic')
            if arg in {'verbosity', 'seed'} and result['provider'] != 'openai':
                raise ValueError('--' + arg.replace('_', '-') + ' requires OpenAI')
            _set(params, key, value)
    if args.reasoning_effort is not None:
        field = 'reasoning_effort' if result['provider'] == 'openai' else 'output_config.effort'
        if args.reasoning_effort != 'default':
            _set(params, field, args.reasoning_effort)
        elif result['provider'] == 'openai':
            params.pop('reasoning_effort', None)
        elif isinstance(params.get('output_config'), dict):
            params['output_config'].pop('effort', None)
            if not params['output_config']:
                params.pop('output_config')
    if args.thinking_mode is not None:
        if args.thinking_mode == 'default':
            if args.thinking_budget_tokens is not None or args.thinking_display is not None:
                raise ValueError('Explicit thinking parameters require an explicit thinking mode')
            params.pop('thinking', None)
        else:
            _set(params, 'thinking.type', args.thinking_mode)
    if args.openai_max_completion_tokens is not None:
        if result['provider'] != 'openai':
            raise ValueError('--max-completion-tokens requires OpenAI')
        params['max_completion_tokens'] = args.openai_max_completion_tokens
    if params:
        result['api_parameters'] = params
    else:
        result.pop('api_parameters', None)
    for arg, target in (('api_header', 'api_headers'), ('api_header_env', 'api_header_env')):
        for value in getattr(args, arg):
            key, text = _pair(value)
            result.setdefault(target, {})[key] = text
    return result
