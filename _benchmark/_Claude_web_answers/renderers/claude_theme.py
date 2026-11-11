"""Design tokens that claude.ai uses for inline charts and visualize widgets.

Values come from the visualize read_me that claude.ai sends to the model (CSS
variables, color ramps, chart palette) and from a DOM snapshot of a rendered
chart card. The real UI font (Anthropic Sans) isn't bundled; a system sans
stack is used instead, so text metrics differ slightly.
"""

FONT_SANS = '"Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, "Helvetica Neue", Arial, "Liberation Sans", "DejaVu Sans", sans-serif'
FONT_SERIF = 'Georgia, "Times New Roman", serif'
FONT_MONO = 'ui-monospace, "SFMono-Regular", Consolas, "Liberation Mono", monospace'

TOKENS = {
    "light": {
        "page": "#fcfcfb", "surface-0": "#fcfcfb", "surface-1": "#fcfcfb", "surface-2": "#ffffff",
        "text-primary": "#0b0b0b", "text-secondary": "#52514e", "text-muted": "#898781",
        "border": "rgba(11,11,11,0.10)", "border-strong": "rgba(11,11,11,0.20)", "border-stronger": "rgba(11,11,11,0.32)",
        "grid": "#e1e0d9", "baseline": "#c3c2b7",
        "text-accent": "#185FA5", "text-danger": "#A32D2D", "text-success": "#3B6D11", "text-warning": "#854F0B",
        "bg-accent": "#E6F1FB", "bg-danger": "#FCEBEB", "bg-success": "#EAF3DE", "bg-warning": "#FAEEDA",
        "border-accent": "#378ADD", "border-danger": "#E24B4A", "border-success": "#639922", "border-warning": "#BA7517",
    },
    "dark": {
        "page": "#151515", "surface-0": "#151515", "surface-1": "#1a1a19", "surface-2": "#1f1f1e",
        "text-primary": "#f0efec", "text-secondary": "#c3c2b7", "text-muted": "#898781",
        "border": "rgba(255,255,255,0.10)", "border-strong": "rgba(255,255,255,0.20)", "border-stronger": "rgba(255,255,255,0.32)",
        "grid": "#2c2c2a", "baseline": "#383835",
        "text-accent": "#85B7EB", "text-danger": "#F09595", "text-success": "#97C459", "text-warning": "#EF9F27",
        "bg-accent": "#0C447C", "bg-danger": "#791F1F", "bg-success": "#27500A", "bg-warning": "#633806",
        "border-accent": "#378ADD", "border-danger": "#E24B4A", "border-success": "#639922", "border-warning": "#BA7517",
    },
}

# Categorical chart palette ("Cove"), slot order is fixed.
SERIES = {
    "light": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
    "dark": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
}

# Color ramps for c-{ramp} classes: stops 50, 100, 200, 400, 600, 800, 900
RAMPS = {
    "purple": ["#EEEDFE", "#CECBF6", "#AFA9EC", "#7F77DD", "#534AB7", "#3C3489", "#26215C"],
    "teal": ["#E1F5EE", "#9FE1CB", "#5DCAA5", "#1D9E75", "#0F6E56", "#085041", "#04342C"],
    "coral": ["#FAECE7", "#F5C4B3", "#F0997B", "#D85A30", "#993C1D", "#712B13", "#4A1B0C"],
    "pink": ["#FBEAF0", "#F4C0D1", "#ED93B1", "#D4537E", "#993556", "#72243E", "#4B1528"],
    "gray": ["#F1EFE8", "#D3D1C7", "#B4B2A9", "#888780", "#5F5E5A", "#444441", "#2C2C2A"],
    "blue": ["#E6F1FB", "#B5D4F4", "#85B7EB", "#378ADD", "#185FA5", "#0C447C", "#042C53"],
    "green": ["#EAF3DE", "#C0DD97", "#97C459", "#639922", "#3B6D11", "#27500A", "#173404"],
    "amber": ["#FAEEDA", "#FAC775", "#EF9F27", "#BA7517", "#854F0B", "#633806", "#412402"],
    "red": ["#FCEBEB", "#F7C1C1", "#F09595", "#E24B4A", "#A32D2D", "#791F1F", "#501313"],
}
S50, S100, S200, S400, S600, S800, S900 = range(7)


def root_css(theme):
    t = TOKENS[theme]
    lines = [f"--{k}:{v};" for k, v in t.items() if k not in ("page", "grid", "baseline")]
    lines += [f"--font-sans:{FONT_SANS};", f"--font-voice:{FONT_SERIF};", f"--font-mono:{FONT_MONO};", "--radius:8px;",
              "--pad-sm:8px;--pad-md:12px;--pad-lg:16px;--pad-xl:24px;--gap-xs:4px;--gap-sm:8px;--gap-md:12px;--gap-lg:16px;--gap-xl:24px;",
              "--p:var(--text-primary);--s:var(--text-secondary);--t:var(--text-muted);--bg2:var(--surface-2);--b:var(--border);"]
    for i, c in enumerate(SERIES[theme], 1):
        lines.append(f"--series-{i}:{c};")
    return ":root{" + "".join(lines) + "}"


def widget_css(theme):
    """CSS the visualize widget host provides: tokens, base HTML styles and pre-built SVG classes."""
    dark = theme == "dark"
    css = [root_css(theme),
           f"html,body{{margin:0;background:{TOKENS[theme]['page']};color:var(--text-primary);font-family:var(--font-sans);font-size:16px;line-height:1.7;}}",
           "h1{font-size:22px;font-weight:500;margin:0 0 8px}h2{font-size:18px;font-weight:500;margin:0 0 8px}h3{font-size:16px;font-weight:500;margin:0 0 8px}",
           ".sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);border:0}",
           "button{font:inherit;font-size:14px;color:var(--text-primary);background:transparent;border:0.5px solid var(--border-strong);border-radius:var(--radius);padding:6px 12px;}",
           "input,select,textarea{font:inherit;font-size:14px;color:var(--text-primary);background:var(--surface-2);border:0.5px solid var(--border-strong);border-radius:var(--radius);}",
           "svg text{font-family:var(--font-sans)}",
           "svg .t{font-size:14px;font-weight:400;fill:var(--text-primary)}",
           "svg .ts{font-size:12px;font-weight:400;fill:var(--text-secondary)}",
           "svg .th{font-size:14px;font-weight:500;fill:var(--text-primary)}",
           "svg .box{fill:var(--surface-1);stroke:var(--border-strong)}",
           "svg .node{cursor:pointer}",
           "svg .arr{stroke:var(--text-secondary);stroke-width:1.5;fill:none}",
           "svg .leader{stroke:var(--text-muted);stroke-width:0.5;stroke-dasharray:3 3;fill:none}"]
    for name, st in RAMPS.items():
        fill, stroke, title, sub = (st[S800], st[S200], st[S100], st[S200]) if dark else (st[S50], st[S600], st[S800], st[S600])
        shapes = ", ".join([f"svg .c-{name} > {s}" for s in ("rect", "circle", "ellipse", "polygon")] + [f"svg {s}.c-{name}" for s in ("rect", "circle", "ellipse")])
        css.append(f"{shapes}{{fill:{fill};stroke:{stroke}}}")
        css.append(f"svg .c-{name} > .t, svg .c-{name} > .th{{fill:{title}}} svg .c-{name} > .ts{{fill:{sub}}}")
    return "\n".join(css)
