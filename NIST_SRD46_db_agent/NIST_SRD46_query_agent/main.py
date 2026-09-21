#!/usr/bin/env python
"""
SRD-46 MCP Server – entry point.

Usage
-----
    python main.py              # stdio transport (default, for MCP clients)
    python main.py --sse        # SSE transport  (for web/HTTP clients)
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).absolute().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def main():
    from NIST_SRD46_db_agent.NIST_SRD46_query_agent.server import mcp          # deferred import keeps module-level fast

    transport = "sse" if "--sse" in sys.argv else "stdio"
    print(f"Starting SRD-46 MCP server (transport={transport}) …")
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
