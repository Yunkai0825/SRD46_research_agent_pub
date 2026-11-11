"""Native Query tool checkpoints and parent-owned MCP HTTP replay.

MCP metadata carries only execution control. It is never a tool argument or
model message. A completed tool replays its recorded return; an interrupted
tool executes its native code and replays each child HTTP request exactly.
"""
from __future__ import annotations

import asyncio
from contextvars import ContextVar
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

from .controller import current_session, AuthorizationInterrupted, ReconstructionMismatch
from .paths import filesystem_path

_child = ContextVar('native_mcp_reconstruction_bridge', default=None)
MCP_BRIDGE_ENV = 'SRD46_NATIVE_MCP_RECONSTRUCTION_ROOT'


def enabled():
    session = current_session()
    return session is not None and getattr(session, 'query_replay_enabled', False)


def query_clock():
    if enabled():
        from .runtime import clock
        return clock(time.time)
    return time.time()


def configure_child_environment(environment):
    """Keep transport control under the model-hidden native root ledger."""
    if enabled():
        environment[MCP_BRIDGE_ENV] = str(current_session().output_dir / 'mcp_bridge')
    else:
        environment.pop(MCP_BRIDGE_ENV, None)


def _write(path, value):
    from ..general_checkpointing import replace_with_retry
    path = filesystem_path(path)
    temporary = path.with_name(path.name + '.writing')
    temporary.write_text(json.dumps(value, ensure_ascii=False), 'utf8')
    replace_with_retry(temporary, path)


def child_http(post, url, **kwargs):
    directory = _child.get()
    if directory is None:
        return post(url, **kwargs)
    # Authentication remains in the native parent sender, never in files.
    if set(kwargs) - {'json', 'timeout', 'headers'} or not isinstance(kwargs.get('json'), dict):
        raise RuntimeError('Unsupported native MCP request form')
    stem = uuid.uuid4().hex
    _write(directory / (stem + '.request.json'),
           {'url': url, 'payload': kwargs['json'], 'timeout': kwargs.get('timeout', 600)})
    reply = filesystem_path(directory / (stem + '.response.json'))
    deadline = time.monotonic() + float(kwargs.get('timeout', 600)) + 30
    while not reply.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError('Native MCP HTTP bridge did not return')
        time.sleep(.025)
    value = json.loads(reply.read_text('utf8'))
    if value.get('control'):
        raise AuthorizationInterrupted('Native parent stopped the MCP request')
    if value.get('error'):
        from .controller import ReconstructionSession
        ReconstructionSession._replay_exception(value['error'], value.get('message'), value.get('args'))
    from .transport import RecordedResponse
    response = RecordedResponse(value['status'], value['text'])
    response.replayed = value.get('replayed', False)
    return response


def server_class(base):
    class NativeReplayMCP(base):
        async def call_tool(self, name, arguments):
            context = self.get_context()
            meta = context.request_context.meta
            binding = getattr(meta, 'srd46_reconstruction', None) if meta else None
            if binding is None:
                return await super().call_tool(name, arguments)
            root = os.environ.get(MCP_BRIDGE_ENV)
            if not root or not isinstance(binding, dict) or set(binding) != {'bridge'}:
                raise RuntimeError('Invalid native MCP reconstruction metadata')
            directory = Path(binding['bridge'])
            directory.resolve().relative_to(Path(root).resolve())
            token = _child.set(directory)
            try:
                return await super().call_tool(name, arguments)
            finally:
                _child.reset(token)
    return NativeReplayMCP


async def recorded_tool(client, name, arguments, artifact_dir):
    if not enabled():
        return await client.call_tool(name, arguments)
    if artifact_dir is None:
        raise ReconstructionMismatch('Embedded Query replay needs its native artifact scope')
    session = current_session()
    from fastmcp.client.client import CallToolResult
    from pydantic import TypeAdapter
    from mcp.types import ContentBlock
    content_adapter = TypeAdapter(list[ContentBlock])
    identity = {'scope': str(artifact_dir), 'tool': name, 'arguments': arguments}
    digest = hashlib.sha256(json.dumps(session.canonicalize(identity), sort_keys=True).encode()).hexdigest()
    # Independent parallel calls have independent replay lanes. Repeated equal
    # calls consume that lane in their original sequence.
    lane = session.current_lane + ':mcp:' + digest
    if not session.live:
        lane = session.recorded_operation_lane('query.mcp_tool', identity) or lane
    native_result = []

    async def live():
        directory = session.output_dir / 'mcp_bridge' / uuid.uuid4().hex
        filesystem_path(directory).mkdir(parents=True)
        pending = asyncio.create_task(client.call_tool(name, arguments,
            meta={'srd46_reconstruction': {'bridge': str(directory)}}))
        handled = set()
        try:
            while not pending.done():
                for path in sorted(filesystem_path(directory).glob('*.request.json')):
                    if path.name in handled:
                        continue
                    handled.add(path.name)
                    request = json.loads(path.read_text('utf8'))
                    target = path.with_name(path.name.replace('.request.json', '.response.json'))

                    def send():
                        import requests
                        return session.http_call(request['payload'],
                            lambda: requests.post(request['url'], json=request['payload'],
                                                  timeout=request['timeout']),
                            transport='argo', request_timeout=request['timeout'], send_payload=lambda p: requests.post(
                                request['url'], json=p, timeout=request['timeout']))
                    try:
                        response = await asyncio.to_thread(send)
                    except BaseException as exc:
                        if not isinstance(exc, Exception):
                            _write(target, {'control': type(exc).__name__})
                            raise
                        exception_args = list(exc.args)
                        try:
                            json.dumps(exception_args, allow_nan=False)
                        except (TypeError, ValueError):
                            exception_args = None
                        _write(target, {'error': type(exc).__module__ + '.' + type(exc).__qualname__,
                                        'message': str(exc), 'args': exception_args})
                    else:
                        _write(target, {'status': response.status_code, 'text': response.text,
                                        'replayed': getattr(response, 'replayed', False)})
                await asyncio.sleep(.025)
            result = await pending
            native_result.append(result)
            return {'content': content_adapter.dump_python(result.content, mode='json'),
                    'structured_content': result.structured_content, 'meta': result.meta,
                    'is_error': result.is_error}
        finally:
            if not pending.done():
                pending.cancel()
                try:
                    await pending
                except BaseException:
                    pass

    with session.lane(lane):
        result = await session.async_operation('query.mcp_tool', identity, live)
    if native_result:
        return native_result[0]
    # The protocol result is JSON. Client-created Pydantic output objects are
    # reconstructed by the same installed client parser, never serialized as
    # executable Python state or passed to the model as replacement text.
    parser = getattr(client, '_parse_call_tool_result', None)
    if parser is not None:
        from mcp.types import CallToolResult as ProtocolResult
        return await parser(name, ProtocolResult(
            content=content_adapter.validate_python(result['content']),
            structuredContent=result['structured_content'],
            _meta=result['meta'], isError=result['is_error']))
    return CallToolResult(content=content_adapter.validate_python(result['content']),
                          **{k: v for k, v in result.items() if k != 'content'})
