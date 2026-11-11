# =============================================================
#  Argo API call
# =============================================================

import json
import logging
import hashlib
import re
import threading
import time
from typing import List, Optional

import requests

from NIST_SRD46_db_agent.NIST_SRD46_query_agent import argo_config
from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_config import (
    API_URL,
    API_USER,
    HEADERS,
    MAX_TOKENS,
    TEMPERATURE,
    TOP_P,
)

# The Argo username a browser run bills (output_paths.argo_api_user_scope, bound per
# run by the run's launcher) wins over the module constant at call time, so two
# concurrent runs of different users in one process each bill their own; without
# the master (command line) nothing is bound and API_USER (patched per process by
# the browser's _apply_api_user) decides.
try:
    from output_paths import argo_api_user as _bound_argo_api_user
except Exception as _exc:  # noqa: BLE001 -- standalone: no master on sys.path (ImportError), else broken
    if not isinstance(_exc, ImportError):
        logging.getLogger("SRD46-UI").warning(
            "output_paths unavailable (%s): Argo calls bill the configured user", _exc)

    def _bound_argo_api_user():
        return None


def _api_user() -> str:
    """The Argo username the current call bills."""
    return _bound_argo_api_user() or API_USER


log = logging.getLogger("SRD46-UI")

# ── Best-effort token tally bridge to the master browser (optional) ──────────
_MASTER_RT = None
_MASTER_RT_TRIED = False

# ── Output-budget record of the last successful call on this thread ──────────
# ``call_argo`` returns model text only.  The usage block and any finish reason
# in the HTTP envelope are kept here so the agent loop can attach them to its
# per-round model history (``consume_last_call_info``) and downstream stages
# can tell a capped answer from a complete one.
_LAST_CALL = threading.local()
_TRUNCATION_FINISH_REASONS = frozenset({"length", "max_tokens"})
_NATURAL_FINISH_REASONS = frozenset({"stop", "end_turn", "stop_sequence", "tool_use"})


def _set_last_call_info(info: Optional[dict]) -> None:
    _LAST_CALL.info = info


def consume_last_call_info() -> Optional[dict]:
    """Return and clear the output-budget record of the last ``call_argo``.

    ``None`` when no call completed on this thread since the last consume,
    or when a monkeypatched client did not record one.
    """
    info = getattr(_LAST_CALL, "info", None)
    _LAST_CALL.info = None
    return info


def _output_budget_record(body, *, max_tokens: int, output_chars: int) -> dict:
    """Summarize usage and stop reason from an Argo response envelope.

    ``output_truncated`` is True when the finish reason says the cap was hit
    or when completion tokens reached ``max_tokens``; False when the envelope
    shows a natural stop or a count below the cap; None when the envelope
    carries neither (older proxies).
    """
    usage = body.get("usage") if isinstance(body, dict) else None
    prompt_tokens = completion_tokens = None
    if isinstance(usage, dict):
        prompt_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
        completion_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
    finish_reason = None
    if isinstance(body, dict):
        for key in ("finish_reason", "stop_reason"):
            value = body.get(key)
            if isinstance(value, str) and value.strip():
                finish_reason = value.strip()
                break
        choices = body.get("choices")
        if finish_reason is None and isinstance(choices, list) and choices:
            first = choices[0]
            value = first.get("finish_reason") if isinstance(first, dict) else None
            if isinstance(value, str) and value.strip():
                finish_reason = value.strip()
    truncated: Optional[bool] = None
    if finish_reason is not None and finish_reason.lower() in _TRUNCATION_FINISH_REASONS:
        truncated = True
    elif isinstance(completion_tokens, int) and not isinstance(completion_tokens, bool) and max_tokens:
        truncated = completion_tokens >= int(max_tokens)
    elif finish_reason is not None and finish_reason.lower() in _NATURAL_FINISH_REASONS:
        truncated = False
    return {
        "max_tokens": int(max_tokens) if max_tokens else None,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "finish_reason": finish_reason,
        "output_truncated": truncated,
        "output_chars": int(output_chars),
    }


def _record_master_tokens(agent: str, body, *, input_chars: int, output_chars: int) -> None:
    """Forward an Argo call's usage/char counts to the shared master tracker.

    No-op when the master runtime is not importable (standalone agent runs).
    """
    global _MASTER_RT, _MASTER_RT_TRIED
    if not _MASTER_RT_TRIED:
        _MASTER_RT_TRIED = True
        try:
            import master_runtime as _rt  # type: ignore
            _MASTER_RT = _rt
        except Exception:
            _MASTER_RT = None
    if _MASTER_RT is None:
        return
    usage = body.get("usage") if isinstance(body, dict) else None
    pt = ct = tt = None
    if isinstance(usage, dict):
        pt = usage.get("prompt_tokens")
        ct = usage.get("completion_tokens")
        tt = usage.get("total_tokens")
    try:
        _MASTER_RT.record_tokens(
            agent, prompt_tokens=pt, completion_tokens=ct, total_tokens=tt,
            input_chars=input_chars, output_chars=output_chars,
        )
    except Exception:
        pass


_ARGO_REQUEST_GATE_LOCK = threading.Lock()
_ARGO_REQUEST_LIMIT = 0
_ARGO_REQUEST_GATE: threading.BoundedSemaphore | None = None


def _coerce_positive_int(value: int | None, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = fallback
    return max(1, parsed)


def configure_argo_request_limit(limit: int | None = None) -> int:
    """Configure the process-wide concurrency cap for direct Argo HTTP calls."""

    global _ARGO_REQUEST_GATE, _ARGO_REQUEST_LIMIT

    fallback = getattr(argo_config, "ARGO_MAX_CONCURRENT_REQUESTS", 5)
    resolved = _coerce_positive_int(limit, fallback)
    with _ARGO_REQUEST_GATE_LOCK:
        if _ARGO_REQUEST_GATE is None or _ARGO_REQUEST_LIMIT != resolved:
            _ARGO_REQUEST_GATE = threading.BoundedSemaphore(resolved)
            _ARGO_REQUEST_LIMIT = resolved
    return _ARGO_REQUEST_LIMIT


def get_argo_request_limit() -> int:
    if _ARGO_REQUEST_GATE is None:
        return configure_argo_request_limit()
    return _ARGO_REQUEST_LIMIT


def _argo_request_gate() -> threading.BoundedSemaphore:
    configure_argo_request_limit()
    assert _ARGO_REQUEST_GATE is not None
    return _ARGO_REQUEST_GATE


def _truncate_for_log(text: str, limit: int | None = None) -> str:
    preview_limit = _coerce_positive_int(
        limit,
        getattr(argo_config, "ARGO_ERROR_BODY_PREVIEW_CHARS", 1000),
    )
    if len(text) <= preview_limit:
        return text
    return f"{text[:preview_limit]}...<truncated {len(text) - preview_limit} chars>"


def _single_line_preview(text: str, limit: int = 200) -> str:
    compact = " ".join(text.split())
    return _truncate_for_log(compact, limit)


def _sanitize_argo_text(text: str) -> str:
    if not text:
        return text

    chars: list[str] = []
    changed = False
    for ch in text:
        codepoint = ord(ch)
        if ch in "\n\r\t" or (0x20 <= codepoint and not 0xD800 <= codepoint <= 0xDFFF):
            chars.append(ch)
        else:
            chars.append(" ")
            changed = True

    sanitized = "".join(chars).encode("utf-8", "replace").decode("utf-8")
    if changed or sanitized != text:
        log.debug("Sanitized Argo text payload (%d -> %d chars)", len(text), len(sanitized))
    return sanitized


def _response_preview(response: requests.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        preview = response.text
    else:
        preview = json.dumps(body, ensure_ascii=False)
    return _truncate_for_log(preview)


def _request_id(model: str, system: str, prompt: str, stop: list[str]) -> str:
    seed = "\0".join([model, system, prompt, "|".join(stop)])
    return hashlib.sha1(seed.encode("utf-8", "replace")).hexdigest()[:12]


def _response_body_text(response: requests.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text
    try:
        return json.dumps(body, ensure_ascii=False)
    except TypeError:
        return str(body)


# Categories under Azure OpenAI ResponsibleAIPolicyViolation that we want to
# wrap with a scientific-data safety context. Any of these tripping with
# filtered=true indicates a benign chemistry payload was misclassified.
_RAI_FILTER_CATEGORIES: tuple[str, ...] = (
    "self_harm",
    "hate",
    "violence",
    "sexual",
    "jailbreak",
)


def _is_self_harm_filter_response(response: requests.Response) -> bool:
    """Return True for any Azure RAI content-filter rejection.

    Matches any `ResponsibleAIPolicyViolation` where one of the categories in
    ``_RAI_FILTER_CATEGORIES`` was flagged with ``filtered: true``.
    """
    body_text = _response_body_text(response).lower()
    if "content_filter" not in body_text:
        return False
    if "responsibleaipolicyviolation" not in body_text:
        return False
    for category in _RAI_FILTER_CATEGORIES:
        if category not in body_text:
            continue
        pattern = rf"{category}.{{0,200}}?filtered['\"]?\s*:\s*true"
        if re.search(pattern, body_text, re.DOTALL):
            return True
    return False


def _apply_self_harm_fallback_to_system(system: str) -> str:
    note = getattr(argo_config, "ARGO_SELF_HARM_FALLBACK_SYSTEM_NOTE", "").strip()
    if not note or note in system:
        return system
    return f"{system.rstrip()}\n\n{note}"


def _apply_self_harm_fallback_to_prompt(prompt: str) -> str:
    prefix = getattr(argo_config, "ARGO_SELF_HARM_FALLBACK_PROMPT_PREFIX", "")
    suffix = getattr(argo_config, "ARGO_SELF_HARM_FALLBACK_PROMPT_SUFFIX", "")
    if not prefix and not suffix:
        return prompt
    if prefix and prefix in prompt:
        return prompt
    return f"{prefix}{prompt}{suffix}"


def _post_argo(payload: dict, *, timeout: int) -> requests.Response:
    with _argo_request_gate():
        from NIST_SRD46_db_agent.general_db_query_engine.general_first_principle_API_call_reconstruct.query_bridge import enabled
        if not enabled():
            return requests.post(API_URL, headers=HEADERS, json=payload, timeout=timeout)
        from NIST_SRD46_db_agent.general_db_query_engine.general_first_principle_API_call_reconstruct import http_post
        return http_post(payload, lambda: requests.post(API_URL, headers=HEADERS, json=payload, timeout=timeout),
                         request_timeout=timeout,
                         send_payload=lambda p: requests.post(API_URL, headers=HEADERS, json=p, timeout=timeout))


def _access_revoked(response) -> Optional[tuple]:
    """``(notice, envelope_id)`` when the envelope is Argo's access-revoked block.

    Argo relays a spent usage allowance as HTTP 200 with the notice in an
    Anthropic-style ``content`` block and no ``response`` field; read as an
    empty reply it would consume every retry. The detection lives
    with the API-call reconstruction layer, which records the same denial.
    """
    from NIST_SRD46_db_agent.general_db_query_engine.general_first_principle_API_call_reconstruct import (
        access_revoked_notice,
    )
    text = getattr(response, "text", None)
    if not isinstance(text, str):
        # Stand-in responses (tests, replay shims) may expose json() only.
        try:
            text = json.dumps(response.json())
        except Exception:  # noqa: BLE001 - detection is best-effort
            return None
    return access_revoked_notice(response.status_code, text)


def _access_revoked_error(**fields):
    from NIST_SRD46_db_agent.general_db_query_engine.general_first_principle_API_call_reconstruct import (
        ArgoAccessRevokedError,
    )
    return ArgoAccessRevokedError(**fields)


configure_argo_request_limit()

try:
    from langchain.memory import ConversationBufferMemory
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import (
        AIMessage,
        BaseMessage,
        HumanMessage,
        SystemMessage,
        ToolMessage,
    )
    from langchain_core.outputs import ChatGeneration, ChatResult
    _LANGCHAIN_IMPORT_ERROR = None
except ImportError as exc:
    ConversationBufferMemory = None
    BaseChatModel = object
    BaseMessage = HumanMessage = SystemMessage = ToolMessage = object
    AIMessage = object
    ChatGeneration = ChatResult = None
    _LANGCHAIN_IMPORT_ERROR = exc


def _require_langchain() -> None:
    if _LANGCHAIN_IMPORT_ERROR is not None:
        raise ModuleNotFoundError(
            "ArgoLLM/LLMEngine requires langchain, langchain_core, and related packages."
        ) from _LANGCHAIN_IMPORT_ERROR


class ArgoLLM(BaseChatModel):

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, **kwargs) -> ChatResult:
        _require_langchain()
        from NIST_SRD46_db_agent.NIST_SRD46_query_agent.agent_runtime import SYSTEM_PROMPT

        api_messages = []

        for msg in messages:
            # Map LangChain roles → API roles
            if isinstance(msg, SystemMessage):
                role = "system"
            elif isinstance(msg, AIMessage):
                role = "assistant"
            elif isinstance(msg, ToolMessage):
                role = "tool"
            else:
                role = "user"

            # IMPORTANT: pass content verbatim
            # content may be str OR list[dict] (multimodal)
            api_messages.append({
                "role": role,
                "content": msg.content
            })

        system_msg = {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
        api_messages.insert(0, system_msg)

        payload = {
            "user": _api_user(),
            "model": argo_config.MODEL,
            "messages": api_messages,
            "stop": stop or [],
            "temperature": 0.1,
            "top_p": 0.9,
        }
        print("")
        print("[PAYLOAD]")
        print(payload)
        print("")

        r = requests.post(API_URL, data=json.dumps(payload), headers=HEADERS, timeout=600)
        # print("")
        # print("[RESPONSE]")
        # print(r)
        # print("")
        response_json = r.json()
        content = response_json["response"]
        # body = r.json()
        # text = body.get("response", "")
        # if isinstance(text, dict):
        #     # handle {"response": {"error": ...}} shape
        #     text = json.dumps(text)
        # # Re-append the stop token if it was stripped
        # if "<tool_call>" in text and "</tool_call>" not in text:
        #     text += "</tool_call>"
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(content=content)
                )
            ]
        )

    @property
    def _llm_type(self) -> str:
        return "argo_llm"


class LLMEngine:
    def __init__(self):
        self.mcp_manager = None
        self.tools = None
        self.tool_index = None
        self.current_k = 4
        self.similarity_threshold = 0.43
        self.memory = None
        self.db = None
        self.agent = None
        self.mcp_client = None

    async def startup(self):
        _require_langchain()
        from NIST_SRD46_db_agent.NIST_SRD46_query_agent.agent_runtime import MCPManager

        self.memory = ConversationBufferMemory(return_messages=True)

        '''Initializing LLM Agent'''
        self.agent = ArgoLLM()

        '''MCP server setup'''
        self.mcp_manager = MCPManager()
        self.tools, self.tool_index = await self.mcp_manager.setup()

    async def ask_agent(self, prompt, image_path):
        _require_langchain()
        from NIST_SRD46_db_agent.NIST_SRD46_query_agent.agent_runtime import file_to_data_url

        if image_path is not None:
            image_url = file_to_data_url(str(image_path))
            content = [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"{image_url}"}}]
        else:
            content = [{"type": "text", "text": prompt}]

        self.memory.chat_memory.add_user_message(HumanMessage(content=content))
        messages = self.memory.chat_memory.messages
        result = self.agent.invoke(messages)
        self.memory.chat_memory.add_ai_message(result)

        return result

    async def query(self, prompt: str) -> str:
        from NIST_SRD46_db_agent.NIST_SRD46_query_agent.agent_runtime import SYSTEM_PROMPT, coerce_tool_calls, extract_tool_call
        prompt_len = sum(len(p) for p in prompt) if isinstance(prompt, list) else len(prompt)
        log.info(">> Argo request: system=%d chars, prompt=%d chars, max_tokens=%d", len(SYSTEM_PROMPT), prompt_len,
                 MAX_TOKENS)
        last_err = None

        planner_pack = json.dumps({
            "role": "planner",
            "task": prompt,
        }, ensure_ascii=False)
        print(planner_pack)

        self.memory.chat_memory.add_user_message(HumanMessage(content=planner_pack))
        # messages = self.memory.chat_memory.messages

        planner_text = self.agent.invoke(planner_pack).content
        print("")
        print("[PLANNER TEXT ]")
        print(planner_text)
        print("")

        tool_call = extract_tool_call(planner_text)
        tool_calls = coerce_tool_calls(tool_call)
        if not tool_calls:
            raise ValueError("Planner did not return a valid tool call.")
        tool_name = tool_calls[0].get("name", "")
        tool_args = tool_calls[0].get("arguments", {})

        result = await self.mcp_manager.call_tool(tool_name, tool_args)
        # self.memory.chat_memory.add_ai_message(result)

        # memory.append({
        #     "role": "user",
        #     "content": f"<tool_result>\n{tool_result}\n</tool_result>",
        # })

        print("")
        print("[TOOL RESULT]")
        print(result)
        print("")

        print("")
        print("[TOOL RESULT 1]")
        print(result.content[0].text)
        print("")

        planner_text = self.agent.invoke(result.content[0].text).content

        print("")
        print("[2nd CALL]")
        print(planner_text)
        print("")

        # results = await asyncio.gather(
        #     self.mcp_client0.call_tool("tool1", args1),
        #     self.mcp_client0.call_tool("tool2", args2),
        #     self.mcp_client0.call_tool("tool3", args3),
        # )

        # tool_call = extract_tool_call(planner_text)

        # try:
        #     result = await self.mcp_manager.call_tool(tool_name, tool_args)
        #     error_text = result.content[0].text
        #     print(error_text)
        #     # print("")
        #     # print("[TOOL RESULT]")
        #     # print(result)
        #     # print("")
        #
        #     # ---------- Extract result content (text/path/uri) ----------
        #     text_parts: List[str] = []
        #     out_path, out_uri = None, None
        #     for c in result.content:
        #         ctype = _get_attr(c, "type", "").lower() or c.__class__.__name__.lower()
        #         if ctype in ("text", "textcontent"):
        #             t = _get_attr(c, "text", "")
        #             if t:
        #                 text_parts.append(t)
        #         elif ctype in ("path", "pathcontent"):
        #             p = _get_attr(c, "path", None)
        #             if p:
        #                 out_path = p
        #         elif ctype in ("uri", "uricontent"):
        #             u = _get_attr(c, "uri", None)
        #             if u:
        #                 out_uri = u
        #         elif ctype in ("image", "imagecontent"):
        #             out_screen = _get_attr(c, "data", "")
        #
        #     tool_text = "\n".join(text_parts).strip()
        #     if out_path and not os.path.isabs(out_path):
        #         out_path = os.path.abspath(out_path)
        #
        #     # ---------- Final answer with RAG + tool result ----------
        #     final_prompt = FINAL_ANSWER_TEMPLATE.format(
        #         user_msg=text,
        #         snippets=snippets_text,
        #         tool_name=tool_name,
        #         tool_args=json.dumps(tool_args, ensure_ascii=False),
        #         tool_text=tool_text,
        #         tool_path=out_path or "",
        #         tool_uri=out_uri or "",
        #     )
        #     if image_path is not None:
        #         image_url = file_to_data_url(str(image_path))
        #         content = [{"type": "text", "text": final_prompt},
        #                    {"type": "image_url", "image_url": {"url": f"{image_url}"}}]
        #     else:
        #         content = [{"type": "text", "text": final_prompt}]
        #
        #     self.memory.chat_memory.add_user_message(HumanMessage(content=content))
        #     messages = self.memory.chat_memory.messages
        #     final_answer = self.agent.invoke(messages)
        #     out_message = final_answer.content
        #
        # except Exception as e:
        #     print(f"[tool error] {e}")
        #     final_prompt = text
        #     if image_path is not None:
        #         image_url = file_to_data_url(str(image_path))
        #         content = [{"type": "text", "text": final_prompt},
        #                    {"type": "image_url", "image_url": {"url": f"{image_url}"}}]
        #     else:
        #         content = [{"type": "text", "text": final_prompt}]
        #
        #     self.memory.chat_memory.add_user_message(HumanMessage(content=content))
        #     messages = self.memory.chat_memory.messages
        #     final_answer = self.agent.invoke(messages)
        #     out_message = final_answer.content
        #
        # self.memory.chat_memory.add_ai_message(final_answer)

        return planner_text


# A line that is exactly a heading of the agent's own transcript rendering
# (query_agent renders memory as "## User" / "## Assistant" sections); a model
# turn can never legitimately contain one (see _cut_reply_past_stop).
_HOST_HEADING_RE = re.compile(r"^## (?:User|Assistant)[ \t]*\r?$", re.MULTILINE)
_HOST_TOOL_RESULT_OPEN = "<tool_result>"
_TOOL_CALL_BLOCK_RE = re.compile(r"<tool_call>.*?</tool_call>", re.DOTALL)


def _cut_reply_past_stop(text: str, stop: list) -> tuple[str, Optional[dict]]:
    """Cut a reply that ran past the end of the model's turn.

    When Argo applies no stop sequence, the model can generate up to
    ``max_tokens`` and, after its real tool call, write the host's side of
    the conversation itself
    (``## User`` / ``<tool_result>`` blocks with invented results, then
    further ``## Assistant`` turns).  This agent's format is one tool-call
    block per turn (a batch is a JSON list inside the block), so the turn
    ends at the first stop sequence of the request, kept inclusive so the
    block stays parseable, unless a host-only marker comes first: a
    ``<tool_result>`` tag or a bare ``## User`` / ``## Assistant`` heading
    line, which no model turn can legitimately contain, ends the turn right
    there (a prose answer followed by a fabricated turn with its own tool
    call, or a reply without any stop sequence).  Markers are searched
    outside tool-call bodies only.  A reply that would be cut to nothing
    passes unchanged.

    Returns ``(kept_text, record)``; ``record`` is None when nothing was cut,
    else ``{"cut_at": <stop sequence> | "host_marker", "kept_chars",
    "dropped_chars", "dropped_head"}``.
    """
    if not text:
        return text, None
    stop_end = None
    stop_seq = None
    for seq in stop or []:
        seq = str(seq)
        if not seq:
            continue
        pos = text.find(seq)
        if pos >= 0 and (stop_end is None or pos + len(seq) < stop_end):
            stop_end, stop_seq = pos + len(seq), seq
    # Blank out complete tool-call blocks (offsets preserved) so that quoted
    # text inside arguments can never be taken for a marker.
    masked = _TOOL_CALL_BLOCK_RE.sub(lambda m: " " * len(m.group(0)), text)
    hits = []
    pos = masked.find(_HOST_TOOL_RESULT_OPEN)
    if pos >= 0:
        hits.append(pos)
    heading = _HOST_HEADING_RE.search(masked)
    if heading is not None:
        hits.append(heading.start())
    marker = min(hits) if hits else None
    if stop_end is not None and (marker is None or stop_end <= marker):
        end, cut_at = stop_end, stop_seq
        kept = text[:end]
    elif marker is not None:
        end, cut_at = marker, "host_marker"
        kept = text[:end].rstrip()
    else:
        return text, None
    if not text[end:].strip() or not kept.strip():
        return text, None
    return kept, {
        "cut_at": cut_at,
        "kept_chars": len(kept),
        "dropped_chars": len(text) - len(kept),
        "dropped_head": text[len(kept):len(kept) + 120],
    }


def call_argo(prompt: str, system: str, stop: list = None,
              model: str = None, max_tokens: int = None) -> str:
    """Send a prompt to the Argo LLM API with retry logic.

    Parameters
    ----------
    model : str or None
        Override the default MODEL for this call.
    """
    if stop is None:
        stop = ["</tool_call>"]
    _set_last_call_info(None)
    _model = model or argo_config.MODEL
    clean_system = _sanitize_argo_text(system)
    clean_prompt = _sanitize_argo_text(prompt)
    clean_stop = [_sanitize_argo_text(str(item)) for item in stop]
    current_system = clean_system
    current_prompt = clean_prompt
    fallback_applied = False
    max_attempts = max(3, _coerce_positive_int(getattr(argo_config, "ARGO_MAX_ATTEMPTS", 4), 4))
    last_err = None
    for attempt in range(1, max_attempts + 1):
        payload = {
            "user": _api_user(),
            "model": _model,
            "system": current_system,
            "prompt": [current_prompt],
            "stop": clean_stop,
            "temperature": TEMPERATURE,
            "max_tokens": max_tokens or MAX_TOKENS,
        }
        if not argo_config.is_claude_model(_model):
            payload["top_p"] = TOP_P
        prompt_len = sum(len(p) for p in payload["prompt"]) if isinstance(payload["prompt"], list) else len(
            payload["prompt"])
        request_id = _request_id(_model, current_system, current_prompt, clean_stop)
        log.info(">> Argo request: system=%d chars, prompt=%d chars, max_tokens=%d, request_id=%s",
                 len(current_system), prompt_len, payload["max_tokens"], request_id)
        start = time.time()
        log.info(">> Calling Argo API (model=%s, attempt=%d/%d, request_id=%s) ...",
                 _model, attempt, max_attempts, request_id)
        try:
            log.debug("   ... POST to %s (timeout=600s)", API_URL)
            r = _post_argo(payload, timeout=600)
            http_elapsed = time.time() - start
            log.debug("   ... HTTP %d received in %.1f s", r.status_code, http_elapsed)
            if r.status_code == 500:
                preview = _response_preview(r)
                log.warning("[!] API returned 500 (attempt %d/%d, %.1fs, request_id=%s): %s",
                            attempt, max_attempts, http_elapsed, request_id, preview)
                last_err = f"500 Server Error: {preview}"
                time.sleep(2 * attempt)
                continue
            r.raise_for_status()

            # Not transient: a revoked allowance cannot be retried into success.
            revoked = _access_revoked(r)
            if revoked is not None:
                notice, response_id = revoked
                log.error(
                    "[!] Argo access revoked (request_id=%s, envelope id=%s): %s",
                    request_id, response_id or "-", notice,
                )
                raise _access_revoked_error(
                    status_code=r.status_code,
                    notice=notice,
                    response_id=response_id,
                    model=_model,
                    api_user=_api_user(),
                )

            elapsed = time.time() - start
            body = r.json()
            text = body.get("response", "")
            if isinstance(text, dict):
                # handle {"response": {"error": ...}} shape
                text = json.dumps(text)
            if not isinstance(text, str):
                text = str(text or "")
            raw_output_chars = len(text)
            text, reply_cut = _cut_reply_past_stop(text, clean_stop)
            if reply_cut is not None:
                log.info(
                    "<< reply ran past %s: kept %d chars, dropped %d chars of "
                    "model-written continuation (Argo applied no stop sequence; "
                    "request_id=%s; dropped head: %r)",
                    reply_cut["cut_at"], reply_cut["kept_chars"],
                    reply_cut["dropped_chars"], request_id, reply_cut["dropped_head"],
                )
            log.info("<< Argo responded in %.1f s  (%d chars)", elapsed, len(text))

            # Best-effort token tally for the master browser's live display.
            _record_master_tokens(
                "SRD46-query", body,
                input_chars=len(current_system) + prompt_len,
                output_chars=len(text) if isinstance(text, str) else 0,
            )
            budget = _output_budget_record(
                body, max_tokens=payload["max_tokens"], output_chars=len(text),
            )
            budget["raw_output_chars"] = raw_output_chars
            budget["stop_cut_chars"] = reply_cut["dropped_chars"] if reply_cut else 0
            budget["stop_cut_at"] = reply_cut["cut_at"] if reply_cut else None
            _set_last_call_info(budget)
            if budget["output_truncated"]:
                log.warning(
                    "[!] Argo output reached max_tokens=%s (completion_tokens=%s, "
                    "finish_reason=%s, request_id=%s); the answer is cut",
                    budget["max_tokens"], budget["completion_tokens"],
                    budget["finish_reason"], request_id,
                )

            # An HTTP-200 envelope with no model text is not a valid agent
            # turn.  Treat it as a transient API failure here, while the exact
            # request is still available, instead of letting the workflow
            # publish an empty answer or restart already-completed pair work.
            if not text.strip():
                last_err = (
                    "HTTP 200 contained an empty model response "
                    f"(request_id={request_id})"
                )
                log.warning(
                    "[!] Empty Argo response (attempt %d/%d, request_id=%s); "
                    "retrying the identical request",
                    attempt,
                    max_attempts,
                    request_id,
                )
                if attempt < max_attempts:
                    time.sleep(2 * attempt)
                    continue
                break

            # Re-append the stop token if it was stripped
            if "<tool_call>" in text and "</tool_call>" not in text:
                text += "</tool_call>"
            return text

        except requests.ReadTimeout:
            http_elapsed = time.time() - start
            log.error("[!] READ TIMEOUT after %.1f s (attempt %d/%d, request_id=%s)",
                      http_elapsed, attempt, max_attempts, request_id)
            last_err = f"ReadTimeout after {http_elapsed:.0f}s"
            time.sleep(2 * attempt)
        except requests.ConnectionError as e:
            http_elapsed = time.time() - start
            log.error("[!] CONNECTION ERROR after %.1f s (attempt %d/%d, request_id=%s): %s",
                      http_elapsed, attempt, max_attempts, request_id, e)
            last_err = str(e)
            time.sleep(2 * attempt)
        except requests.RequestException as e:
            http_elapsed = time.time() - start
            response = getattr(e, "response", None)
            if response is not None:
                preview = _response_preview(response)
                log.warning(
                    "[!] Request failed after %.1f s (attempt %d/%d, request_id=%s, status=%s): %s | body=%s",
                    http_elapsed,
                    attempt,
                    max_attempts,
                    request_id,
                    response.status_code,
                    e,
                    preview,
                )
                if 400 <= response.status_code < 500:
                    log.warning(
                        "    request_id=%s model=%s stop=%d prompt_preview=%r",
                        request_id,
                        _model,
                        len(clean_stop),
                        _single_line_preview(current_prompt),
                    )
                    if not fallback_applied and _is_self_harm_filter_response(response):
                        fallback_system = _apply_self_harm_fallback_to_system(current_system)
                        fallback_prompt = _apply_self_harm_fallback_to_prompt(current_prompt)
                        if fallback_system != current_system or fallback_prompt != current_prompt:
                            fallback_applied = True
                            current_system = fallback_system
                            current_prompt = fallback_prompt
                            log.warning(
                                "    request_id=%s applying self-harm fallback context (system=%d chars, prompt=%d chars)",
                                request_id,
                                len(current_system),
                                len(current_prompt),
                            )
                            last_err = f"{e}; body={preview}"
                            continue
                    # Authentication / authorization failures are NOT transient
                    # — retrying the same credentials cannot succeed. Fail fast
                    # with an actionable message instead of burning all attempts.
                    if response.status_code in (401, 403):
                        raise RuntimeError(
                            f"Argo authentication failed (HTTP {response.status_code}). The ANL "
                            f"argoapi rejected the request for user '{_api_user()}' / model "
                            f"'{_model}' at {API_URL}. This is an upstream credential/endpoint "
                            f"issue, not a problem with your prompt. Check that: (1) your ANL "
                            f"username is correct, (2) you are on the ANL network/VPN, and (3) the "
                            f"endpoint and model are currently available (override the endpoint with "
                            f"the ARGO_API_URL env var if the dev endpoint is down). "
                            f"Server said: {preview}"
                        ) from e
                last_err = f"{e}; body={preview}"
            else:
                log.warning("[!] Request failed after %.1f s (attempt %d/%d, request_id=%s): %s",
                            http_elapsed, attempt, max_attempts, request_id, e)
                last_err = str(e)
            time.sleep(2 * attempt)
    raise RuntimeError(f"Argo API failed after {max_attempts} attempts: {last_err}")

