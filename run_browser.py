#!/usr/bin/env python3
"""Launch only the standalone SRD-46 browser and its native agents."""
from __future__ import annotations
import argparse
import importlib
from pathlib import Path
import sys
import threading
import webbrowser

ROOT = Path(__file__).absolute().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def serve(app, host, port, *, open_browser=True):
    from werkzeug.serving import make_server
    browser_host = {'0.0.0.0': '127.0.0.1', '::': '::1'}.get(host, host)
    if ':' in browser_host:
        browser_host = '[' + browser_host + ']'
    with make_server(host, port, app, threaded=True) as server:
        url = f'http://{browser_host}:{server.server_port}'
        print(f'SRD-46 browser: {url}', flush=True)
        opener = threading.Timer(0.25, webbrowser.open_new_tab, args=(url,)) if open_browser else None
        if opener:
            opener.daemon = True
            opener.start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            if opener:
                opener.cancel()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings', type=Path)
    parser.add_argument('--api-user')
    parser.add_argument('--provider', choices=['argo', 'anthropic', 'openai'])
    parser.add_argument('--model', help='Explicitly use this model for all agent roles')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5046)
    parser.add_argument('--no-open', action='store_true', help='Start the server without opening a browser tab')
    parser.add_argument('--check', action='store_true', help='Offline startup/route smoke without starting a server')
    args = parser.parse_args(argv)
    from output_settings.runtime import configure, restore_data
    configure(args.settings, api_user=args.api_user, provider=args.provider,
              model=args.model, require_credentials=False)
    restore_data()
    browser = importlib.import_module('NIST_SRD46_database_browser.app')
    if args.check:
        client = browser.app.test_client()
        for endpoint in ('/', '/agent/analysis/', '/agent/', '/analysis/', '/analysis/matrix/'):
            response = client.get(endpoint)
            if response.status_code != 200:
                raise RuntimeError(f'{endpoint}: HTTP {response.status_code}')
            print(endpoint + ': OK')
        return 0
    serve(browser.app, args.host, args.port, open_browser=not args.no_open)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
