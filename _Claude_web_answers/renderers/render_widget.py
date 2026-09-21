"""Render claude.ai "visualize" widgets (show_widget code) to PNG, using the chat's theme tokens.

Widget code is an SVG or HTML fragment that relies on CSS variables and classes the
chat host provides (--text-primary, --surface-1, class="t|ts|th", c-blue, ...). This
wraps the fragment in a page that defines them, at the chat's 680 px widget width.

    python render_widget.py widget_1_x.html [more ...] [--out DIR] [--theme light|dark] [--keep-html]

Input files can be the raw fragment or an exported widget_*.html (a bare <html> wrapper is unwrapped).
Writes <name>.png and, with --keep-html, <name>_standalone.html.
"""
import argparse, html, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from claude_theme import widget_css
from browser import screenshot_elements

WIDGET_WIDTH = 680
HEAD_EXTRA = ('<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3/dist/tabler-icons.min.css">')


def unwrap(code):
    m = re.search(r"<body[^>]*>(.*)</body>", code, re.S | re.I)
    return m.group(1).strip() if m else code


def widget_page(code, title="widget", theme="light"):
    code = unwrap(code)
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>{HEAD_EXTRA}'
            f'<style>{widget_css(theme)}\n#widget{{width:{WIDGET_WIDTH}px;padding:8px 0;}}</style></head>'
            f'<body><div id="widget">{code}</div></body></html>')


def render(jobs, theme="light", keep_html=False):
    """jobs: [(widget_code, title, out_png)]"""
    pages = []
    for code, title, out_png in jobs:
        out_png = Path(out_png)
        out_png.parent.mkdir(parents=True, exist_ok=True)
        page = out_png.with_name(out_png.stem + "_standalone.html")
        page.write_text(widget_page(code, title, theme), encoding="utf-8")
        pages.append((page, out_png))
    sizes = screenshot_elements([(p, "#widget", png) for p, png in pages], viewport_width=WIDGET_WIDTH + 40, wait_ms=800)
    if not keep_html:
        for p, _ in pages:
            p.unlink(missing_ok=True)
    return sizes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--out")
    ap.add_argument("--theme", default="light", choices=["light", "dark"])
    ap.add_argument("--keep-html", action="store_true")
    a = ap.parse_args()
    jobs = []
    for inp in a.inputs:
        p = Path(inp)
        jobs.append((p.read_text(encoding="utf-8"), p.stem, (Path(a.out) if a.out else p.parent) / (p.stem + ".png")))
    for png, size in render(jobs, a.theme, a.keep_html):
        print(f"{png}  {size[0]}x{size[1]}")


if __name__ == "__main__":
    main()
