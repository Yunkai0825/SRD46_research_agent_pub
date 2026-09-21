"""Render full HTML pages (published artifacts, HTML reports) to a full-page PNG.

    python render_page.py report.html [more ...] [--out DIR] [--width 1280] [--offline-assets DIR]

Pages often load Google Fonts or Chart.js from a CDN. Without internet, pass
--offline-assets pointing at a folder with node_modules from:
    npm install chart.js@4 @fontsource/<family> ...
and those requests are answered from local files (see offline_assets.py).
"""
import argparse, asyncio, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from browser import _launch_kwargs


async def _render(jobs, width, scale, offline_dir):
    from playwright.async_api import async_playwright
    out = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(**_launch_kwargs())
        ctx = await browser.new_context(viewport={"width": width, "height": 900}, device_scale_factor=scale)
        if offline_dir:
            from offline_assets import install_routes
            await install_routes(ctx, Path(offline_dir))
        page = await ctx.new_page()
        for src, png in jobs:
            png = Path(png)
            png.parent.mkdir(parents=True, exist_ok=True)
            await page.set_viewport_size({"width": width, "height": 900})
            await page.goto(Path(src).resolve().as_uri())
            try:
                await page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                pass
            await page.evaluate("document.fonts ? document.fonts.ready.then(() => true) : true")
            await page.wait_for_timeout(1500)  # let charts finish animating
            h = await page.evaluate("Math.max(document.documentElement.scrollHeight, document.body ? document.body.scrollHeight : 0)")
            await page.set_viewport_size({"width": width, "height": min(max(h, 600), 16000)})
            await page.wait_for_timeout(300)
            await page.screenshot(path=str(png), full_page=True)
            dims = await page.evaluate("[document.documentElement.scrollWidth, document.documentElement.scrollHeight]")
            out.append((png, (round(dims[0] * scale), round(dims[1] * scale))))
        await browser.close()
    return out


def render(jobs, width=1280, scale=1.5, offline_dir=None):
    """jobs: [(html_path, out_png)]"""
    return asyncio.run(_render(jobs, width, scale, offline_dir))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--out")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--scale", type=float, default=1.5)
    ap.add_argument("--offline-assets")
    a = ap.parse_args()
    jobs = [(i, (Path(a.out) if a.out else Path(i).parent) / (Path(i).stem + ".png")) for i in a.inputs]
    for png, size in render(jobs, a.width, a.scale, a.offline_assets):
        print(f"{png}  {size[0]}x{size[1]}")


if __name__ == "__main__":
    main()
