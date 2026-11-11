"""Render claude.ai inline charts (chart_display_v0 data) to PNG, styled like the chat UI.

Input: the chart JSON the chat tool received ({style, title, x_axis, y_axis, series}),
as saved in an export's artifacts/chart_*.json or pulled from a chat tree.

    python render_chart.py chart_1.json [more.json ...] [--out DIR] [--theme light|dark] [--width 720] [--keep-html]

Needs: pip install playwright && python -m playwright install chromium
"""
import argparse, html, json, math, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from claude_theme import TOKENS, SERIES, FONT_SANS
from browser import screenshot_elements


def _tick_increment(start, stop, count):
    step = (stop - start) / max(count, 1)
    power = math.floor(math.log10(step)) if step > 0 else 0
    error = step / (10 ** power)
    factor = 10 if error >= math.sqrt(50) else 5 if error >= math.sqrt(10) else 2 if error >= math.sqrt(2) else 1
    return factor * 10 ** power


def nice_ticks(lo, hi, count=7):
    if hi == lo:
        hi = lo + 1
    inc = _tick_increment(lo, hi, count)
    first = math.ceil(lo / inc - 1e-9)
    last = math.floor(hi / inc + 1e-9)
    return [round(i * inc, 10) for i in range(first, last + 1)], inc


def nice_domain(lo, hi, count=7):
    if hi == lo:
        lo, hi = lo - 1, hi + 1
    for _ in range(5):
        inc = _tick_increment(lo, hi, count)
        nlo, nhi = math.floor(lo / inc) * inc, math.ceil(hi / inc) * inc
        if (nlo, nhi) == (lo, hi):
            break
        lo, hi = nlo, nhi
    return lo, hi


def fmt(v, inc=None):
    if inc is not None and inc < 1:
        d = max(0, -math.floor(math.log10(inc) + 1e-9))
        return f"{v:.{d}f}"
    return f"{int(round(v))}" if abs(v - round(v)) < 1e-9 else f"{v:g}"


def text_w(s, px=12):
    return sum(px * (0.35 if ch in ".,:;|il1 " else 0.62) for ch in str(s))


def build_card(spec, theme="light", width=720):
    t = TOKENS[theme]
    colors = SERIES[theme]
    style = (spec.get("style") or "line").lower()
    xa, ya = spec.get("x_axis") or {}, spec.get("y_axis") or {}
    series = spec.get("series") or []
    points_mode = any("points" in s for s in series)

    # ----- data -> numeric arrays
    cats = [str(c) for c in (xa.get("data") or [])]
    data = []
    for s in series:
        if "points" in s:
            pts = []
            for p in s["points"]:
                x, y = (p.get("x"), p.get("y")) if isinstance(p, dict) else (p[0], p[1])
                pts.append((float(x), None if y is None else float(y)))
        else:
            vals = s.get("values") or []
            if not cats:
                cats = [str(i + 1) for i in range(len(vals))]
            pts = [(i, None if v is None else float(v)) for i, v in enumerate(vals)]
        data.append((s.get("name", ""), pts))

    ys = [y for _, pts in data for _, y in pts if y is not None]
    ylo = ya.get("min") if ya.get("min") is not None else (min(ys) if ys else 0)
    yhi = ya.get("max") if ya.get("max") is not None else (max(ys) if ys else 1)
    if ya.get("min") is None or ya.get("max") is None:
        nlo, nhi = nice_domain(ylo, yhi)
        ylo = ylo if ya.get("min") is not None else nlo
        yhi = yhi if ya.get("max") is not None else nhi
    if style == "bar" and ylo > 0 and ya.get("min") is None:
        ylo = 0
    yticks, yinc = nice_ticks(ylo, yhi)

    if points_mode:
        xs = [x for _, pts in data for x, _ in pts]
        xlo = xa.get("min") if xa.get("min") is not None else min(xs)
        xhi = xa.get("max") if xa.get("max") is not None else max(xs)
        if xa.get("min") is None or xa.get("max") is None:
            nlo, nhi = nice_domain(xlo, xhi)
            xlo = xlo if xa.get("min") is not None else nlo
            xhi = xhi if xa.get("max") is not None else nhi
        xticks, xinc = nice_ticks(xlo, xhi)

    # ----- geometry
    plot_w = width - 32
    ml = max(text_w(fmt(v, yinc)) for v in yticks) + 10
    mr, mt, mb = 10, 8, 26
    H = 240
    iw, ih = plot_w - ml - mr, H - mt - mb

    def sy(y):
        return mt + ih - (y - ylo) / (yhi - ylo) * ih

    if points_mode:
        def sx(x):
            return ml + (x - xlo) / (xhi - xlo) * iw
    else:
        n = max(len(cats), 1)
        if style == "bar":
            band = iw / n
            def sx(i):
                return ml + band * (i + 0.5)
        else:
            def sx(i):
                return ml + (iw * i / (n - 1) if n > 1 else iw / 2)

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{plot_w}" height="{H}" viewBox="0 0 {plot_w} {H}" style="display:block;overflow:visible">',
           f'<defs><clipPath id="c"><rect x="{ml - 6}" y="{mt - 6}" width="{iw + 12}" height="{ih + 12}"/></clipPath></defs>']
    for v in yticks:
        y = sy(v)
        is_base = abs(v - ylo) < 1e-9
        svg.append(f'<line x1="{ml}" x2="{ml + iw}" y1="{y:.2f}" y2="{y:.2f}" stroke="{t["baseline"] if is_base else t["grid"]}" stroke-width="1"/>')
        svg.append(f'<text x="{ml - 8}" y="{y:.2f}" dy="0.32em" text-anchor="end" font-size="12" fill="{t["text-muted"]}">{html.escape(fmt(v, yinc))}</text>')
    if not any(abs(v - ylo) < 1e-9 for v in yticks):
        svg.append(f'<line x1="{ml}" x2="{ml + iw}" y1="{sy(ylo):.2f}" y2="{sy(ylo):.2f}" stroke="{t["baseline"]}" stroke-width="1"/>')

    if points_mode:
        for v in xticks:
            svg.append(f'<text x="{sx(v):.2f}" y="{mt + ih + 18}" text-anchor="middle" font-size="12" fill="{t["text-muted"]}">{html.escape(fmt(v, xinc))}</text>')
    else:
        n = len(cats)
        k = max(1, math.ceil(n / 6))
        idx = list(range(0, n, k))
        if n and idx[-1] != n - 1:
            idx.append(n - 1)
        for i in idx:
            anchor = "start" if (i == 0 and style != "bar") else "end" if (i == n - 1 and style != "bar") else "middle"
            x = sx(i) - (6 if anchor == "start" else -6 if anchor == "end" else 0)
            svg.append(f'<text x="{x:.2f}" y="{mt + ih + 18}" text-anchor="{anchor}" font-size="12" fill="{t["text-muted"]}">{html.escape(cats[i])}</text>')

    nser = len(data)
    many = max((len(p) for _, p in data), default=0) > 60
    for si, (name, pts) in enumerate(data):
        c = colors[si % len(colors)]
        if style == "bar" and not points_mode:
            band = iw / max(len(cats), 1)
            bw = min(24, band * 0.8 / max(nser, 1))
            for x, y in pts:
                if y is None:
                    continue
                x0 = sx(x) - bw * nser / 2 + si * bw
                y0, y1 = sy(max(y, ylo)), sy(ylo)
                svg.append(f'<rect x="{x0 + 1:.2f}" y="{min(y0, y1):.2f}" width="{bw - 2:.2f}" height="{abs(y1 - y0):.2f}" rx="2" fill="{c}"/>')
            continue
        segs, cur = [], []
        for x, y in pts:
            if y is None:
                if cur:
                    segs.append(cur)
                cur = []
            else:
                cur.append((sx(x), sy(y)))
        if cur:
            segs.append(cur)
        for seg in segs:
            d = "M" + "L".join(f"{a:.2f},{b:.2f}" for a, b in seg)
            if style == "area":
                area = d + f"L{seg[-1][0]:.2f},{sy(ylo):.2f}L{seg[0][0]:.2f},{sy(ylo):.2f}Z"
                svg.append(f'<path d="{area}" fill="{c}" fill-opacity="0.10" stroke="none" clip-path="url(#c)"/>')
            if style != "scatter":
                svg.append(f'<path d="{d}" fill="none" stroke="{c}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" clip-path="url(#c)"/>')
            if style == "scatter" or not many:
                for a, b in seg:
                    svg.append(f'<circle cx="{a:.2f}" cy="{b:.2f}" r="4" fill="{c}" stroke="{t["surface-2"]}" stroke-width="2"/>')
    svg.append("</svg>")

    legend = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:6px;margin-right:16px">'
        f'<span style="display:inline-block;width:12px;height:{12 if style in ("bar", "scatter") else 2}px;border-radius:{6 if style == "scatter" else 1}px;background:{colors[i % len(colors)]}"></span>'
        f'<span style="font-size:12px;color:{t["text-secondary"]}">{html.escape(nm)}</span></span>'
        for i, (nm, _) in enumerate(data))
    sub = " by ".join(x for x in (ya.get("title"), xa.get("title")) if x)
    return (f'<div class="card" style="box-sizing:border-box;width:{width}px;padding:16px;background:{t["surface-2"]};'
            f'border:1px solid {t["border"]};border-radius:12px;font-family:{FONT_SANS};color:{t["text-primary"]}">'
            f'<div style="font-size:14px;font-weight:500;line-height:20px">{html.escape(spec.get("title") or "")}</div>'
            f'<div style="font-size:12px;line-height:18px;color:{t["text-secondary"]};margin-bottom:12px">{html.escape(sub)}</div>'
            + "".join(svg) +
            (f'<div style="margin-top:12px;line-height:18px">{legend}</div>' if nser > 1 or spec.get("series") else "") +
            "</div>")


def chart_page(spec, theme="light", width=720):
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(spec.get("title") or "chart")}</title></head>'
            f'<body style="margin:0;padding:16px;background:{TOKENS[theme]["page"]}">{build_card(spec, theme, width)}</body></html>')


def render(jobs, theme="light", width=720, keep_html=False):
    """jobs: list of (spec_dict, out_png_path). Returns list of (out_png, (w, h))."""
    pages = []
    for spec, out_png in jobs:
        out_png = Path(out_png)
        out_png.parent.mkdir(parents=True, exist_ok=True)
        page = out_png.with_suffix(".render.html")
        page.write_text(chart_page(spec, theme, width), encoding="utf-8")
        pages.append((page, out_png))
    sizes = screenshot_elements([(p, ".card", png) for p, png in pages], viewport_width=width + 32)
    if not keep_html:
        for p, _ in pages:
            p.unlink(missing_ok=True)
    return sizes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--out", default=None, help="output folder (default: next to each input)")
    ap.add_argument("--theme", default="light", choices=["light", "dark"])
    ap.add_argument("--width", type=int, default=720)
    ap.add_argument("--keep-html", action="store_true")
    a = ap.parse_args()
    jobs = []
    for inp in a.inputs:
        p = Path(inp)
        spec = json.loads(p.read_text(encoding="utf-8"))
        out = (Path(a.out) if a.out else p.parent) / (p.stem + ".png")
        jobs.append((spec, out))
    for png, size in render(jobs, a.theme, a.width, a.keep_html):
        print(f"{png}  {size[0]}x{size[1]}")


if __name__ == "__main__":
    main()
