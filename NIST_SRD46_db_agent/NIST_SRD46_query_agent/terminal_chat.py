# =============================================================
#  Terminal UI  (prompt_toolkit or fallback)
# =============================================================

import datetime as dt
from pathlib import Path

from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_config import API_USER, MODEL


try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.enums import EditingMode
    from prompt_toolkit.clipboard import InMemoryClipboard

    PTK = True
except ImportError:
    PTK = False

_session = None


def _make_session():
    kb = KeyBindings()
    clip = InMemoryClipboard()

    @kb.add("c-c")
    def _(ev): pass

    @kb.add("c-d")
    def _(ev): raise EOFError

    @kb.add("c-s")
    @kb.add("escape", "enter")
    def _(ev): ev.current_buffer.validate_and_handle()

    @kb.add("enter")
    def _(ev): ev.current_buffer.insert_text("\n")

    def toolbar():
        return "[Enter] new line  |  [Ctrl+S] or [Esc->Enter] send  |  Type 'exit' to quit"

    return PromptSession(
        multiline=True,
        key_bindings=kb,
        editing_mode=EditingMode.EMACS,
        prompt_continuation="",
        bottom_toolbar=toolbar,
        mouse_support=True,
        clipboard=clip,
    )


def read_user_input() -> str:
    global _session
    if PTK:
        try:
            if _session is None:
                _session = _make_session()
            return _session.prompt("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            return "exit"
    else:
        try:
            return input("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            return "exit"


# =============================================================
#  Transcript logging
# =============================================================

_TRANSCRIPT_DIR = Path(__file__).parent / "transcripts"
_TRANSCRIPT_DIR.mkdir(exist_ok=True)


def _open_transcript() -> Path:
    fp = _TRANSCRIPT_DIR / f"srd46_chat_{dt.datetime.now():%Y%m%d_%H%M%S}.txt"
    fp.write_text(
        "--- SRD-46 Chat Transcript -------------------\n"
        f"Model : {MODEL}\n"
        f"User  : {API_USER}\n"
        f"Time  : {dt.datetime.now():%Y-%m-%d %H:%M:%S}\n"
        "----------------------------------------------\n\n",
        encoding="utf-8",
    )
    return fp


def _append_transcript(fp: Path, role: str, text: str):
    with fp.open("a", encoding="utf-8") as f:
        f.write(f"== [{role}] ==\n{text.strip()}\n\n")

