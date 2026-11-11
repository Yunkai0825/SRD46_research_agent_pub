"""Strict text-only OpenAI Chat Completions protocol adapter.

No SDK, provider I/O, credentials, prompts, or agent state live in this module.
Compatibility policy is explicit in the frozen operator configuration.

``openai_max_completion_tokens`` is a separate configuration value, default
32,000 total tokens (reasoning plus visible output). It does not change the
native Argo ``max_tokens`` setting or guarantee a fixed visible-output length.
``reasoning_effort`` is omitted for provider-default reasoning. Returned text
is not clipped to a visible-token quota. The existing local stop-delimiter
contract is retained; the transport saves the complete physical response.

Usage: ``physical = translate(native_request, config)`` followed by transport
dispatch, then ``native_response, metadata = response(body, native_request,
config)``. Config must declare logical_user, openai_model_map and
openai_compatibility={"temperature": "omit", "top_p": "omit", "stop": "local"}.
Set openai_max_completion_tokens explicitly to change the total allowance.
"""
from __future__ import annotations
import math

URL = 'https://api.openai.com/v1/chat/completions'
DEFAULT_MAX_COMPLETION_TOKENS = 32000
MODEL_MAP = {'gpt55': 'gpt-5.5', 'gpt6astra': 'gpt-6-astra', 'gpt6sol': 'gpt-6-sol'}
RESPONSE_MODELS = {
    'gpt-5.5': {'gpt-5.5', 'gpt-5.5-2026-04-23'},
    'gpt-6-astra': {'gpt-6-astra'},
    'gpt-6-sol': {'gpt-6-sol'},
}


def _model_map(config, error):
    selected = config.get('openai_model_map')
    if (not isinstance(selected, dict) or not selected
            or any(key not in MODEL_MAP or not isinstance(value, str) or not value.strip()
                   or (not config.get('allow_custom_model') and MODEL_MAP[key] != value)
                   for key, value in selected.items())):
        raise error('Invalid direct OpenAI model mapping')
    return selected


def translate(payload, config, error=ValueError):
    selected = _model_map(config, error)
    if not isinstance(payload, dict):
        raise error('Invalid direct OpenAI model mapping')
    if payload.get('model') not in selected or payload.get('user') != config.get('logical_user'):
        raise error('OpenAI logical model/account mismatch')
    if set(payload) - {'user','model','system','prompt','messages','stop','max_tokens','temperature','top_p'}:
        raise error('Unsupported OpenAI logical request fields')
    native_maximum = payload.get('max_tokens')
    if type(native_maximum) is not int or not 0 < native_maximum <= 128000:
        raise error('Native max_tokens must be a positive integer at most 128000')
    # Argo's existing variable remains intact. Direct OpenAI gets an explicit
    # total allowance covering both reasoning and visible completion tokens.
    maximum = config.get('openai_max_completion_tokens', DEFAULT_MAX_COMPLETION_TOKENS)
    if type(maximum) is not int or maximum <= 0:
        raise error('openai_max_completion_tokens must be a positive integer')
    system = payload.get('system', '')
    if not isinstance(system, str):
        raise error('Native system prompt must be text')
    messages = []
    if 'messages' in payload:
        if 'prompt' in payload or not isinstance(payload['messages'], list) or not payload['messages']:
            raise error('Invalid or mixed native message format')
        for index, message in enumerate(payload['messages']):
            if (not isinstance(message, dict) or set(message) != {'role','content'}
                    or not isinstance(message['content'], str)):
                raise error('Unsupported native message structure')
            if message['role'] == 'system':
                if index != 0 or system:
                    raise error('Ambiguous native system message')
                system = message['content']
            elif message['role'] in {'user','assistant'}:
                messages.append(dict(message))
            else:
                raise error('Unsupported native message role')
        if not messages:
            raise error('Native messages contain no conversation')
    else:
        prompt = payload.get('prompt')
        if isinstance(prompt, list) and all(isinstance(value, str) for value in prompt):
            prompt = '\n'.join(prompt)
        if not isinstance(prompt, str):
            raise error('Native prompt must be text or a list of text')
        messages = [{'role':'user', 'content':prompt}]
    if system:
        messages.insert(0, {'role':'system', 'content':system})
    physical = {'model': selected[payload['model']], 'messages':messages,
                'max_completion_tokens':maximum}
    policy = config.get('openai_compatibility')
    if policy != {'temperature':'omit','top_p':'omit','stop':'local'}:
        raise error('OpenAI requires the validated omit-sampling/local-stop policy')
    for key in ('temperature','top_p'):
        if policy[key] not in {'forward','omit'}:
            raise error('Invalid OpenAI sampling policy')
        if key in payload:
            value = payload[key]
            upper = 2 if key == 'temperature' else 1
            if type(value) not in (int,float) or not math.isfinite(value) or not 0 <= value <= upper:
                raise error('Invalid native sampling parameter')
    stop = payload.get('stop', [])
    if not isinstance(stop,list) or any(not isinstance(s,str) or not s for s in stop):
        raise error('Invalid native stop sequences')
    if policy['stop'] not in {'forward','local'}:
        raise error('Invalid OpenAI stop policy')
    effort = config.get('reasoning_effort')
    if effort is not None:
        if not isinstance(effort, str) or not effort.strip():
            raise error('Invalid explicit reasoning effort')
        physical['reasoning_effort'] = effort
    return physical


def response(body, payload, config, error=ValueError):
    selected = _model_map(config, error)
    if payload.get('model') not in selected:
        raise error('OpenAI response has an unconfigured logical model')
    model = selected[payload['model']]
    expected = RESPONSE_MODELS.get(model, {model}) | set(config.get('response_model_aliases', []))
    if not isinstance(body,dict) or body.get('model') not in expected:
        raise error('Successful OpenAI response has an unexpected model identity')
    choices = body.get('choices')
    if not isinstance(choices,list) or len(choices) != 1 or not isinstance(choices[0],dict):
        raise error('Expected exactly one OpenAI text choice')
    choice = choices[0]
    message = choice.get('message')
    if not isinstance(message,dict) or message.get('role') != 'assistant':
        raise error('OpenAI assistant message is absent')
    if message.get('tool_calls') or message.get('function_call'):
        raise error('Unexpected structured tool call; native tools use text')
    text = message.get('content')
    if not isinstance(text,str):
        raise error('OpenAI returned no text content')
    record = {'finish_reason':choice.get('finish_reason'), 'response_model':body['model'],
              'local_stop_applied':False}
    if config['openai_compatibility']['stop'] == 'local':
        matches = [(text.find(stop), stop) for stop in payload.get('stop',[]) if stop in text]
        if matches:
            offset, stop = min(matches, key=lambda value: value[0])
            record.update(local_stop_applied=True, stop_sequence=stop,
                          returned_text_characters=offset, physical_text_characters=len(text))
            text = text[:offset]
    translated = {'response':text, 'finish_reason':choice.get('finish_reason')}
    usage = body.get('usage')
    if isinstance(usage,dict):
        translated['usage'] = dict(usage)
    return translated, record
