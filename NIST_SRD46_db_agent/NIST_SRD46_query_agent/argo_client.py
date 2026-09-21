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


log = logging.getLogger("SRD46-UI")



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

    Despite the legacy name (kept for test/back-compat), this matches any
    `ResponsibleAIPolicyViolation` where one of the categories in
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
        return requests.post(API_URL, headers=HEADERS, json=payload, timeout=timeout)


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
            "user": API_USER,
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


def call_argo(prompt: str, system: str, stop: list = None,
              model: str = None, max_tokens: int = None) -> str:
    """Send a prompt to the Argo LLM API with retry logic.

    Parameters
    ----------
    model : str or None
        Override the default MODEL.  Used by the verdict agent to
        call gpt52 instead of gpt5.
    """
    if stop is None:
        stop = ["</tool_call>"]
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
            "user": API_USER,
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

            elapsed = time.time() - start
            body = r.json()
            text = body.get("response", "")
            if isinstance(text, dict):
                # handle {"response": {"error": ...}} shape
                text = json.dumps(text)
            if not isinstance(text, str):
                text = str(text or "")
            log.info("<< Argo responded in %.1f s  (%d chars)", elapsed, len(text))


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
                            f"argoapi rejected the request for user '{API_USER}' / model "
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

