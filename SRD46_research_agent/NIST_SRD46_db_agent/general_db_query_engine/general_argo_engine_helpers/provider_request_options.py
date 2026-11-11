"""Explicit physical API options for the native text-response protocol."""
from copy import deepcopy
import json
import math
import re
from urllib.parse import urlsplit, parse_qsl

PROTECTED = {'model', 'messages', 'system', 'prompt', 'tools', 'tool_choice',
             'functions', 'function_call', 'stream_options', 'audio'}


def endpoint(value):
    if not isinstance(value, str):
        raise ValueError('api_url must be a complete HTTP(S) endpoint')
    parsed = urlsplit(value)
    if (parsed.scheme not in {'http', 'https'} or not parsed.netloc or parsed.username
            or parsed.password or parsed.fragment
            or any(key.lower().replace('-', '_') in {'key', 'api_key', 'apikey', 'token', 'access_token'} for key, _ in parse_qsl(parsed.query))):
        raise ValueError('api_url must be HTTP(S), without embedded credentials or a fragment')
    return value


def request_options(value):
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        raise ValueError('API request parameters must be a JSON object')
    if PROTECTED.intersection(value):
        raise ValueError('The pipeline owns model, conversation and tool framing: ' + ', '.join(sorted(PROTECTED.intersection(value))))
    if value.get('stream', False) is not False or type(value.get('n', 1)) is not int or value.get('n', 1) != 1:
        raise ValueError('The native adapter requires a non-streaming response with one text choice')
    if 'modalities' in value and value['modalities'] != ['text']:
        raise ValueError('The native adapter consumes text responses only')
    json.dumps(value, allow_nan=False)
    return deepcopy(value)


def merge(target, updates):
    result = deepcopy(target)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def header_options(values, *, env_names=False):
    if not isinstance(values, dict):
        raise ValueError('API headers must be an object')
    for key, value in values.items():
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9-]+', key):
            raise ValueError('Invalid API header name')
        if key.lower() in {'content-type', 'content-length', 'host'} or (not env_names and key.lower() in {'authorization', 'x-api-key', 'api-key', 'apikey', 'proxy-authorization'}):
            raise ValueError('Use api_key_env for authentication; transport headers are managed by the adapter')
        if not isinstance(value, str) or '\r' in value or '\n' in value:
            raise ValueError('API header values must be single-line strings')
        if env_names and not value.isidentifier():
            raise ValueError('Header environment bindings must name environment variables')
    return dict(values)


def apply_options(physical, config):
    options = request_options(config.get('request_parameters', {}))
    result = merge(physical, options)
    if result.get('output_config') is not None and not isinstance(result['output_config'], dict):
        raise ValueError('output_config must be an object or null')
    maximum = 'max_completion_tokens' if config['provider'] == 'openai' else 'max_tokens'
    if config['provider'] == 'openai' and 'max_tokens' in options:
        if 'max_completion_tokens' in options and options['max_completion_tokens'] is not None:
            raise ValueError('Choose max_tokens or max_completion_tokens, not both')
        result.pop('max_completion_tokens', None)
        maximum = 'max_tokens'
    if type(result.get(maximum)) is not int or result[maximum] <= 0:
        raise ValueError(maximum + ' must be a positive integer')
    thinking = result.get('thinking')
    if config['provider'] == 'openai' and thinking is not None:
        raise ValueError('thinking is an Anthropic parameter; OpenAI uses reasoning_effort')
    if config['provider'] == 'anthropic' and thinking is not None:
        if not isinstance(thinking, dict) or thinking.get('type') not in {'adaptive', 'enabled', 'disabled', 'between_tools'}:
            raise ValueError('Invalid Anthropic thinking configuration')
        budget = thinking.get('budget_tokens')
        if thinking['type'] == 'enabled':
            if type(budget) is not int or not 1024 <= budget < result['max_tokens']:
                raise ValueError('Enabled thinking needs budget_tokens >=1024 and below max_tokens')
        elif budget is not None:
            raise ValueError('budget_tokens applies only to enabled thinking, not adaptive thinking')
    for name in ('temperature', 'top_p', 'top_k'):
        if name in result and result[name] is not None:
            number = result[name]
            if type(number) not in (int, float) or not math.isfinite(number) or number < 0:
                raise ValueError(name + ' must be a finite nonnegative number')
    return result


def validate_generation(config):
    """Check explicit generation options without inventing a native call budget."""
    options = request_options(config.get('request_parameters', {}))
    physical = {}
    if config['provider'] == 'openai':
        physical['max_completion_tokens'] = config.get('max_completion_tokens', 32000)
    else:
        if config.get('thinking_mode'):
            physical['thinking'] = {'type': config['thinking_mode']}
        thinking = merge(physical, options).get('thinking')
        budget = thinking.get('budget_tokens', 0) if isinstance(thinking, dict) else 0
        # The upper bound is checked against each native call when no override is supplied.
        physical['max_tokens'] = max(1025, budget + 1) if type(budget) is int else 1025
    apply_options(physical, config)
