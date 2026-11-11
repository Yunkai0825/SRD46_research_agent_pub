"""Serve common CDN assets from local npm packages, for rendering without internet.

Covers: Chart.js from cdnjs/jsdelivr/unpkg, and Google Fonts css2 requests for any
family installed as @fontsource/<family-slug> (e.g. @fontsource/ibm-plex-sans).
Anything else that can't be served is aborted quickly instead of hanging.
"""
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs


def _slug(family):
    return re.sub(r"[^a-z0-9]+", "-", family.lower()).strip("-")


def _font_css(node_modules, query):
    css = []
    for fam in parse_qs(query).get("family", []):
        name, _, spec = fam.partition(":")
        name = name.replace("+", " ")
        pkg = node_modules / "@fontsource" / _slug(name)
        if not pkg.exists():
            continue
        weights, italics = set(), set()
        if spec:
            axes, _, vals = spec.partition("@")
            axes = axes.split(",")
            for tup in vals.split(";"):
                parts = tup.split(",")
                d = dict(zip(axes, parts))
                w = d.get("wght", "400").split("..")[0]
                (italics if d.get("ital") == "1" else weights).add(w)
        if not weights and not italics:
            weights = {"400"}
        for w in sorted(weights):
            f = pkg / f"{w}.css"
            if f.exists():
                css.append(f.read_text())
        for w in sorted(italics):
            f = pkg / f"{w}-italic.css"
            if f.exists():
                css.append(f.read_text())
        # rewrite relative font urls to a routable URL
        css = [c.replace("url(./files/", f"url(https://offline.fonts/{_slug(name)}/files/") for c in css]
    return "\n".join(css)


async def install_routes(ctx, root):
    nm = Path(root) / "node_modules"

    async def handler(route):
        url = route.request.url
        u = urlparse(url)
        try:
            if u.hostname == "fonts.googleapis.com" and u.path.startswith("/css"):
                return await route.fulfill(status=200, content_type="text/css", body=_font_css(nm, u.query))
            if u.hostname == "offline.fonts":
                _, slug, _, fname = u.path.split("/", 3)
                f = nm / "@fontsource" / slug / "files" / fname
                if f.exists():
                    return await route.fulfill(status=200, content_type="font/woff2", body=f.read_bytes())
            if re.search(r"chart\.js|Chart\.js", url) and u.path.endswith(".js"):
                f = nm / "chart.js" / "dist" / ("chart.umd.js")
                if f.exists():
                    return await route.fulfill(status=200, content_type="application/javascript", body=f.read_bytes())
            if u.scheme in ("http", "https"):
                return await route.abort()
        except Exception:
            return await route.abort()
        return await route.continue_()

    await ctx.route("**/*", handler)
