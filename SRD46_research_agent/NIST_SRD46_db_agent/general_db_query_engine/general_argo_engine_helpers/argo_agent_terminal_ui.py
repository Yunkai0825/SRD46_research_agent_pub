"""
ArgoAgentTerminalUI — reusable interactive CLI base class.
==========================================================
Provides a generic REPL loop for any Argo-based agent.  Subclasses
override hooks to customise the banner, result display, and
pre/post-processing.

Supports multi-round continuation: between rounds the UI preserves
agent memory, working memory, session directory, and system prompt so
that each follow-up question sees the full conversation history.

Usage (subclass)::

    class AnalysisTerminalUI(ArgoAgentTerminalUI):
        agent_name = "ThermoML Analysis Agent"

        def run_agent(self, question: str):
            return orchestrator.run(question)

        def display_result(self, result) -> None:
            print(f"\\nAgent: {result.answer}\\n")

    if __name__ == "__main__":
        AnalysisTerminalUI().main()
"""

from __future__ import annotations

import logging
import re as _re
import sys
from pathlib import Path
from typing import Any

# ── Continuation-prompt context cleaning ──────────────────────

_SECTION_HEADER_RE = _re.compile(r'^## .+$', _re.MULTILINE)


def strip_context_for_continuation(final_context: str) -> str:
    """Strip *System Prompt* and *Working Memory* sections from final_context.

    The raw ``final_context`` produced by the ReAct loop has the form::

        ## System Prompt
        {system_prompt}

        ## Working Memory
        {working_memory}

        ## User
        {turn_1}

        ## Assistant
        {turn_2}
        …

        ## LLM Response
        {response}

    For continuation we want everything AFTER the preamble sections so
    that the next round can re-inject a fresh system prompt and fresh
    working memory while keeping the full conversation history intact.

    Returns the cleaned text starting from the first ``## User`` or
    ``## Assistant`` section.  If no conversation headers are found the
    input is returned as-is.
    """
    if not final_context:
        return ""
    for m in _SECTION_HEADER_RE.finditer(final_context):
        header = m.group(0).strip()
        if header.startswith("## User") or header.startswith("## Assistant"):
            return final_context[m.start():].strip()
    return final_context


class ArgoAgentTerminalUI:
    """Base interactive terminal UI for Argo-powered agents.

    Override points
    ---------------
    - ``agent_name``       — shown in the banner.
    - ``quit_commands``    — set of strings that exit the loop.
    - ``run_agent()``      — called with the user question; returns a result.
    - ``display_result()`` — formats and prints the result.
    - ``on_before_run()``  — hook before ``run_agent`` (e.g. setup logging).
    - ``on_after_run()``   — hook after ``display_result`` (e.g. close session).
    - ``configure_logging()`` — override to set custom log config.

    Continuation state
    ------------------
    ``_round``, ``_session_dir``, ``_prev_memory``, ``_prev_working_memory``
    are maintained automatically.  Subclasses that support continuation
    should override ``extract_continuation_state()`` and
    ``build_run_kwargs()`` to thread these values into their orchestrator.
    """

    agent_name: str = "Argo Agent"
    quit_commands: set[str] = {"quit", "exit", "q"}

    # ── Continuation state (across rounds) ───────────────────

    _round: int = 0
    _session_dir: str | None = None
    _cleaned_context: str = ""
    _prev_working_memory: Any = None

    # ── Logging ─────────────────────────────────────────────

    log_format: str = "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s"
    log_datefmt: str = "%H:%M:%S"
    log_level: int = logging.INFO
    suppressed_loggers: list[str] = ["urllib3", "requests"]

    def configure_logging(self) -> None:
        """Set up logging. Override for custom configuration."""
        logging.basicConfig(
            level=self.log_level,
            format=self.log_format,
            datefmt=self.log_datefmt,
        )
        for name in self.suppressed_loggers:
            logging.getLogger(name).setLevel(logging.WARNING)

    # ── Path setup ──────────────────────────────────────────

    def ensure_sys_paths(self) -> None:
        """Add necessary directories to ``sys.path``.

        Override to inject agent-specific paths.  The default
        implementation is a no-op.
        """

    # ── Banner ──────────────────────────────────────────────

    def print_banner(self) -> None:
        """Print the startup banner."""
        print(f"\n{'=' * 60}")
        print(f"  {self.agent_name} — Interactive Mode")
        print("=" * 60)
        print("Type your question, or 'quit' to exit.\n")

    # ── Agent execution hooks ───────────────────────────────

    def run_agent(self, question: str) -> Any:
        """Execute the agent on *question* and return the result.

        **Must be overridden** by subclasses.
        """
        raise NotImplementedError("Subclass must implement run_agent()")

    def display_result(self, result: Any) -> None:
        """Format and print the agent result.

        Default implementation prints ``result.answer`` if available,
        otherwise ``str(result)``.
        """
        answer = getattr(result, "answer", None) or str(result)
        print(f"\nAgent: {answer}\n")

    def on_before_run(self, question: str) -> None:
        """Hook called before ``run_agent()``.  Default is no-op."""

    def on_after_run(self, question: str, result: Any) -> None:
        """Hook called after ``display_result()``.  Default is no-op."""

    # ── Continuation helpers ─────────────────────────────────

    def extract_continuation_state(self, result: Any) -> None:
        """Pull cleaned context / working memory / session_dir from *result*.

        Called after every successful ``run_agent()``.  The UI owns
        context stripping: we take ``result.final_context`` and strip
        system-prompt / working-memory preamble sections so the next
        round receives only the conversation turns.
        """
        self._session_dir = getattr(result, "session_dir", self._session_dir)
        self._cleaned_context = strip_context_for_continuation(
            getattr(result, "final_context", ""),
        )
        self._prev_working_memory = getattr(result, "working_memory", None)

    def build_run_kwargs(self) -> dict[str, Any]:
        """Return extra kwargs for ``run_agent`` on continuation rounds.

        Subclasses can use this to pass ``round_number``, ``session_dir``,
        ``prev_context``, ``prev_working_memory`` into their orchestrator.
        Returns an empty dict on the first round.
        """
        if self._round <= 1:
            return {}
        return {
            "round_number": self._round,
            "session_dir": self._session_dir,
            "prev_context": self._cleaned_context,
            "prev_working_memory": self._prev_working_memory,
        }

    # ── Main loop ───────────────────────────────────────────

    def main(self) -> None:
        """Interactive REPL loop with multi-round continuation."""
        self.configure_logging()
        self.ensure_sys_paths()
        self.print_banner()

        while True:
            try:
                prompt_prefix = f"[R{self._round + 1}] " if self._round else ""
                question = input(f"{prompt_prefix}You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if not question or question.lower() in self.quit_commands:
                print("Goodbye!")
                break

            self._round += 1

            self.on_before_run(question)
            result = self.run_agent(question)
            self.display_result(result)
            self.extract_continuation_state(result)
            self.on_after_run(question, result)
