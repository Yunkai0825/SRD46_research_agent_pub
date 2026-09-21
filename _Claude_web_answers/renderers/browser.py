"""Small Playwright helpers shared by the renderers."""
import asyncio
from pathlib import Path


def _launch_kwargs():
    import os
    exe = os.environ.get("RENDER_CHROMIUM")  # optional: path to a Chromium/Chrome/Edge executable
    return {"executable_path": exe} if exe else {}


async def _shots(jobs, viewport_width, scale, full_page_wait_ms):
    from playwright.async_api import async_playwright
    out = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(**_launch_kwargs())
        ctx = await browser.new_context(viewport={"width": viewport_width, "height": 900}, device_scale_factor=scale)
        page = await ctx.new_page()
        for html_path, selector, png in jobs:
            await page.goto(Path(html_path).resolve().as_uri())
            try:
                await page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                pass
            await page.evaluate("document.fonts ? document.fonts.ready.then(() => true) : true")
            await page.wait_for_timeout(full_page_wait_ms)
            if selector:
                el = await page.query_selector(selector)
                await el.screenshot(path=str(png))
                box = await el.bounding_box()
                out.append((png, (round(box["width"] * scale), round(box["height"] * scale))))
            else:
                await page.screenshot(path=str(png), full_page=True)
                dims = await page.evaluate("[document.documentElement.scrollWidth, document.documentElement.scrollHeight]")
                out.append((png, (dims[0] * scale, dims[1] * scale)))
        await browser.close()
    return out


def screenshot_elements(jobs, viewport_width=760, scale=2, wait_ms=300):
    """jobs: [(html_path, css_selector_or_None, png_path)]"""
    return asyncio.run(_shots(jobs, viewport_width, scale, wait_ms))
