"""Explicit live-provider selection below logical request replay.

Secrets are read only at a live send and never written to receipts. Provider
selection cannot alter a saved logical prompt or consume a replay. Physical
generation parameters apply only to new live requests.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import uuid
from pathlib import Path

from .paths import filesystem_path
from .transport import RecordedResponse
from ..general_argo_engine_helpers.provider_request_options import (
    apply_options, endpoint, header_options, request_options)


def validate_provider(config):
    if config is None:
        return None
    allowed = {'provider', 'model_map', 'api_key_env', 'timeout', 'reasoning_effort', 'thinking_mode',
               'max_completion_tokens', 'api_url', 'timeout_override', 'request_parameters',
               'headers', 'header_env', 'allow_custom_model', 'response_model_aliases'}
    if not isinstance(config, dict) or set(config) - allowed:
        raise ValueError('Unsupported live-provider configuration')
    models = {'anthropic': {'claudeopus47': 'claude-opus-4-7', 'claudeopus55': 'claude-opus-5-5', 'claudesonnet47': 'claude-sonnet-4-7'},
              'openai': {'gpt55': 'gpt-5.5', 'gpt6astra': 'gpt-6-astra', 'gpt6sol': 'gpt-6-sol'}}
    provider = config.get('provider')
    mapping = config.get('model_map')
    if (provider not in models or not isinstance(mapping, dict) or not mapping
            or any(k not in models[provider] or not isinstance(v, str) or not v.strip()
                   or (not config.get('allow_custom_model') and models[provider][k] != v) for k, v in mapping.items())):
        raise ValueError('Explicit supported provider/model mapping required')
    key_env = config.get('api_key_env', 'ANTHROPIC_API_KEY' if provider == 'anthropic' else 'OPENAI_API_KEY')
    if not isinstance(key_env, str) or not key_env.isidentifier():
        raise ValueError('api_key_env must name an environment variable, not a key')
    timeout = config.get('timeout', 600)
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('Provider timeout must be positive')
    if 'reasoning_effort' in config and (not isinstance(config['reasoning_effort'], str) or not config['reasoning_effort'].strip()):
        raise ValueError('Invalid explicit reasoning effort')
    if 'thinking_mode' in config and (provider != 'anthropic' or config['thinking_mode'] not in {'adaptive', 'enabled', 'disabled', 'between_tools'}):
        raise ValueError('Explicit thinking mode is an Anthropic setting')
    if 'max_completion_tokens' in config and (provider != 'openai' or type(config['max_completion_tokens']) is not int or config['max_completion_tokens'] <= 0):
        raise ValueError('Invalid OpenAI completion allowance')
    if 'api_url' in config:
        endpoint(config['api_url'])
    if 'timeout_override' in config and (type(config['timeout_override']) not in (int, float)
            or not math.isfinite(config['timeout_override']) or config['timeout_override'] <= 0):
        raise ValueError('Explicit API timeout must be positive')
    request_options(config.get('request_parameters', {}))
    header_options(config.get('headers', {}))
    header_options(config.get('header_env', {}), env_names=True)
    aliases = config.get('response_model_aliases', [])
    if not isinstance(aliases, list) or any(not isinstance(x, str) or not x.strip() for x in aliases):
        raise ValueError('Response model aliases must be a list of model IDs')
    return dict(config, api_key_env=key_env, timeout=timeout)


def _openai_config(payload, config):
    return {'logical_user': payload.get('user'), 'openai_model_map': config['model_map'],
            'openai_max_completion_tokens': config.get('max_completion_tokens', 32000),
            'openai_compatibility': {'temperature': 'omit', 'top_p': 'omit', 'stop': 'local'},
            'allow_custom_model': config.get('allow_custom_model', False),
            'response_model_aliases': config.get('response_model_aliases', []),
            **({'reasoning_effort': config['reasoning_effort']} if 'reasoning_effort' in config else {})}

def translate(payload, config):
    if config['provider'] == 'openai':
        from ..general_argo_engine_helpers import openAI_argo_adapter as adapter
        return apply_options(adapter.translate(payload, _openai_config(payload, config)), config)
    allowed = {'user', 'model', 'system', 'prompt', 'messages', 'stop', 'max_tokens', 'temperature'}
    if not isinstance(payload, dict) or set(payload) - allowed:
        raise ValueError('Unsupported logical request fields for Anthropic')
    model = config['model_map'].get(payload.get('model'))
    if not model:
        raise ValueError('Logical model has no explicit provider mapping')
    limit = payload.get('max_tokens')
    if type(limit) is not int or limit <= 0:
        raise ValueError('A positive explicit token allowance is required')
    system = payload.get('system', '')
    if not isinstance(system, str):
        raise ValueError('System prompt must be text')
    if 'messages' in payload:
        if 'prompt' in payload:
            raise ValueError('Mixed prompt formats')
        messages = []
        for i, message in enumerate(payload['messages']):
            if set(message) != {'role', 'content'} or not isinstance(message['content'], str):
                raise ValueError('Unsupported native message')
            if message['role'] == 'system' and i == 0 and not system:
                system = message['content']
            elif message['role'] in {'user', 'assistant'}:
                messages.append(dict(message))
            else:
                raise ValueError('Unsupported native message role')
    else:
        prompt = payload.get('prompt')
        if isinstance(prompt, list) and all(isinstance(x, str) for x in prompt):
            prompt = '\n'.join(prompt)
        if not isinstance(prompt, str):
            raise ValueError('Prompt must be text or a list of text')
        messages = [{'role': 'user', 'content': prompt}]
    if not messages:
        raise ValueError('Empty conversation')
    stops = payload.get('stop', [])
    if not isinstance(stops, list) or any(not isinstance(x, str) or not x for x in stops):
        raise ValueError('Invalid stop sequences')
    result = {'model': model, 'messages': messages, 'max_tokens': limit}
    if system:
        result['system'] = system
    if stops:
        result['stop_sequences'] = stops
    if 'thinking_mode' in config:
        result['thinking'] = {'type': config['thinking_mode']}
    if 'reasoning_effort' in config:
        result['output_config'] = {'effort': config['reasoning_effort']}
    return apply_options(result, config)


def send_provider(payload, config, output_dir, *, post=None):
    import requests
    config = validate_provider(config)
    physical = translate(payload, config)
    key = os.environ.get(config['api_key_env'])
    if not key:
        raise RuntimeError('Provider credential environment variable is unset')
    folder = filesystem_path(Path(output_dir) / 'provider_calls')
    folder.mkdir(exist_ok=True)
    stem = uuid.uuid4().hex
    receipt = {'schema': 'native-provider-exchange/v1', 'provider': config['provider'],
               'status': 'prepared', 'logical_model': payload['model'],
               'physical_model': physical['model'], 'temperature_omitted': payload.get('temperature') if 'temperature' not in physical else None,
               'thinking_parameters_added': 'thinking' in physical,
               'reasoning_effort': physical.get('reasoning_effort', (physical.get('output_config') or {}).get('effort', 'default'))}

    def retain(role, value):
        data = json.dumps(value, ensure_ascii=False, indent=2).encode('utf8') if not isinstance(value, bytes) else value
        name = stem + '.' + role
        (folder / name).write_bytes(data)
        receipt[role + '_file'] = name
        receipt[role + '_sha256'] = hashlib.sha256(data).hexdigest()

    def save():
        (folder / (stem + '.receipt.json')).write_text(json.dumps(receipt, indent=2), 'utf8')

    retain('logical.json', payload)
    retain('request.json', physical)
    save()
    try:
        url = 'https://api.openai.com/v1/chat/completions' if config['provider'] == 'openai' else 'https://api.anthropic.com/v1/messages'
        url = config.get('api_url', url)
        headers = ({'Authorization': 'Bearer ' + key, 'content-type': 'application/json'} if config['provider'] == 'openai' else
                   {'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
        headers.update(config.get('headers', {}))
        for name, variable in config.get('header_env', {}).items():
            value = os.environ.get(variable)
            if not value or '\r' in value or '\n' in value:
                raise ValueError('Missing or invalid header environment variable: ' + variable)
            headers[name] = value
        receipt.update(api_url=url, timeout_s=config.get('timeout_override', config['timeout']))
        save()
        response = (post or requests.post)(url, json=physical, headers=headers,
                                           timeout=config.get('timeout_override', config['timeout']))
    except BaseException as exc:
        receipt.update(status='transport_exception', exception_type=type(exc).__name__)
        save()
        raise
    retain('response.txt', response.content)
    receipt.update(status='response_received', http_status=response.status_code)
    save()
    status = response.status_code
    if status == 200:
        body = response.json()
        if config['provider'] == 'openai':
            from ..general_argo_engine_helpers import openAI_argo_adapter as adapter
            mapped, metadata = adapter.response(body, payload, _openai_config(payload, config))
            receipt['translation'] = metadata
        else:
            if body.get('model') not in {physical['model'], *config.get('response_model_aliases', [])} or not isinstance(body.get('content'), list):
                raise RuntimeError('Anthropic returned an unexpected model or response format')
            text = ''.join(x['text'] for x in body['content'] if x.get('type') == 'text')
            usage = body.get('usage', {})
            pt, ct = usage.get('input_tokens'), usage.get('output_tokens')
            mapped = {'response': text, 'stop_reason': body.get('stop_reason'),
                      'usage': {'prompt_tokens': pt, 'completion_tokens': ct,
                                'total_tokens': pt + ct if type(pt) is int and type(ct) is int else None}}
        translated = json.dumps(mapped, ensure_ascii=False)
    else:
        translated = response.text
        if status in (503, 529):
            status = 500
    retain('translated.txt', translated.encode('utf8'))
    receipt.update(status='complete', translated_http_status=status)
    save()
    result = RecordedResponse(status, translated)
    result.replayed = False
    return result


def send_anthropic(payload, config, output_dir, *, post=None):
    return send_provider(payload, config, output_dir, post=post)
