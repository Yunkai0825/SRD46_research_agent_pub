"""
Question builder for subagent delegation.
==========================================
Injects ``[Purpose:]``, ``[Tasks:]``, and ``[Context:]`` markers into
a question string before dispatching it to a subagent.
"""
from __future__ import annotations


def build_full_question(
    question: str,
    purpose: str = "",
    tasks: str = "",
    context: str = "",
) -> str:
    """Build an enriched question with structured markers.

    Parameters
    ----------
    question : str
        The core question text.
    purpose : str
        High-level intent — prepended as ``[Purpose: ...]``.
    tasks : str
        Specific tasks — appended as ``[Tasks: ...]``.
    context : str
        Prior context — appended as ``[Context: ...]``.

    Returns
    -------
    str
        The enriched question with markers.
    """
    full = question
    if purpose:
        full = f"[Purpose: {purpose}]\n{full}"
    if tasks:
        full += f"\n\n[Tasks: {tasks}]"
    if context:
        full += f"\n\n[Context: {context}]"
    return full
