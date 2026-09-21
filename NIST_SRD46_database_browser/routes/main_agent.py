"""Main-agent stub route.

Placeholder landing page for the future top-level (L0) orchestrator that
will eventually drive both the query and analysis sub-agents. For now it
just introduces the agent section and links to the two working sub-agents.

Blueprint: ``/agent/main/``
"""

from __future__ import annotations

from flask import Blueprint, render_template

main_agent_bp = Blueprint("main_agent", __name__, url_prefix="/agent/main")


@main_agent_bp.route("/")
def main_agent_page():
    return render_template("main_agent.html")
