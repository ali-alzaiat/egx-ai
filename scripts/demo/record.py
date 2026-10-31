"""Record the EGX AI demo story with Playwright (headless Chromium) for the Remotion composition.

The page lays out as 1920x1080 but renders at CSS zoom 2 in a 3840x2160 viewport, captured as a 3840x2160
video, so the composition can zoom 2x and stay sharp (Playwright's recorder ignores device scale factors). One page load, then in-app navigation only. A warm-up pass visits every
screen first so little is still loading on camera.

Writes remotion/public/rec/raw.mp4 (from Playwright's raw.webm) and remotion/public/timeline.json:
  beats  [{id, start, end}]  the story beats (ids from story.json); each lasts at least its narration
  waits  [[from, to]]        loading or thinking time the composition speeds up to WAIT_SHOWN seconds
  focus  [[t, box | null]]   where the camera zooms from time t (box = [x, y, w, h] in video px), null = full page
All times are seconds from the start of the video. The tour never shows statement amounts (vendor data).

Usage: python record.py   (run narrate.py first; DEMO_BASE overrides the app address)
"""

import asyncio
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import imageio_ffmpeg
from playwright.async_api import Locator, Page, async_playwright

HERE = Path(__file__).parent
PUBLIC = HERE / "remotion" / "public"
BASE = os.environ.get("DEMO_BASE", "http://localhost:5173")
Z = 2  # CSS zoom: the page lays out as 1920x1080
W, H = 1920 * Z, 1080 * Z  # viewport and video, in px
MODEL = "gemini-3.5-flash-lite"
WAIT_SHOWN = 1.0  # seconds a sped-up wait lasts in the video (the composition reads it from timeline.json)
BEAT_TAIL = 0.8  # silence after each beat's narration

INIT = r"""
(() => {
  if (!sessionStorage.getItem('demo-init')) {
    localStorage.setItem('egx-lang', 'en');
    localStorage.setItem('egx-assistant-model', '%MODEL%');
    sessionStorage.setItem('demo-init', '1');
  }
  addEventListener('DOMContentLoaded', () => {
    const s = document.createElement('style');
    // html.demo-blur hides the Shariah page's ratio values and purification amounts (vendor data).
    s.textContent = 'html{zoom:%Z%} html.demo-blur .rs-section ~ .rs-section{filter:blur(9px)}';
    document.head.appendChild(s);
  });
  // Mouse coordinates are viewport px; lengths inside the zoomed page are CSS px.
  const Z = %Z%;
  // A drawn arrow cursor and click ripple: headless Chromium shows no pointer.
  const ARROW = '<svg width="26" height="26" viewBox="0 0 26 26"><path d="M3 2 L3 21 L8.5 16 L12 24 L15.5 22.5 L12 15 L19 15 Z" ' +
    'fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
  const ensure = () => {
    if (!document.body || document.getElementById('demo-cursor')) return;
    const c = document.createElement('div');
    c.id = 'demo-cursor';
    c.innerHTML = ARROW;
    c.style.cssText = 'position:fixed;z-index:2147483647;pointer-events:none;left:-60px;top:-60px;' +
      'margin:-3px 0 0 -3px;filter:drop-shadow(0 1px 2px rgba(0,0,0,.35));transition:transform .1s';
    document.body.appendChild(c);
  };
  document.addEventListener('mousemove', (e) => {
    ensure();
    const c = document.getElementById('demo-cursor');
    c.style.left = e.clientX / Z + 'px'; c.style.top = e.clientY / Z + 'px';
  }, true);
  document.addEventListener('mousedown', (e) => {
    const c = document.getElementById('demo-cursor');
    if (c) c.style.transform = 'scale(.85)';
    const r = document.createElement('div');
    r.style.cssText = 'position:fixed;z-index:2147483646;pointer-events:none;border-radius:50%;' +
      'border:3px solid rgba(37,99,235,.9);width:16px;height:16px;margin:-8px 0 0 -8px;' +
      `left:${e.clientX / Z}px;top:${e.clientY / Z}px;transition:transform .45s ease-out,opacity .45s ease-out`;
    document.body.appendChild(r);
    requestAnimationFrame(() => { r.style.transform = 'scale(3.2)'; r.style.opacity = '0'; });
    setTimeout(() => r.remove(), 500);
  }, true);
  document.addEventListener('mouseup', () => { const c = document.getElementById('demo-cursor'); if (c) c.style.transform = ''; }, true);
})();
""".replace("%MODEL%", MODEL).replace("%Z%", str(Z))

# Nothing on screen is still loading: no busy tables, loading lines or skeleton bars.
SETTLED_JS = """() => !document.querySelector('[aria-busy="true"], p.loading, [data-slot="skeleton"]')"""

# The box of the card around an element (the nearest bordered or shadowed block), in viewport px.
CARD_JS = """(e) => {
  let n = e;
  while (n && n !== document.body) {
    const s = getComputedStyle(n);
    if ((parseFloat(s.borderTopWidth) > 0 || s.boxShadow !== 'none') && n.getBoundingClientRect().width > 480) break;
    n = n.parentElement;
  }
  const r = (n && n !== document.body ? n : e).getBoundingClientRect();
  return [r.x, r.y, r.width, r.height];
}"""

WARM_PATHS = [
    "/", "/companies/COMI", "/companies/COMI/price", "/companies/COMI/shariah", "/companies/COMI/financials/quality",
]


Box = list[float]


def union(*boxes: Box) -> Box:
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[0] + b[2] for b in boxes)
    y1 = max(b[1] + b[3] for b in boxes)
    return [x0, y0, x1 - x0, y1 - y0]


class Tour:
    def __init__(self, page: Page, narration: dict[str, float]) -> None:
        self.page = page
        self.narration = narration
        self.t0 = time.monotonic()
        self.waits: list[tuple[float, float]] = []
        self.focus_log: list[tuple[float, Box | None]] = []
        self.beats: list[dict[str, object]] = []
        self.log: list[str] = []

    def now(self) -> float:
        return time.monotonic() - self.t0

    async def pause(self, s: float) -> None:
        await self.page.wait_for_timeout(int(s * 1000))

    # ---- beats: each lasts at least its narration (sped-up waits count as WAIT_SHOWN) ----
    async def beat(self, beat_id: str | None) -> None:
        if self.beats:
            last = self.beats[-1]
            start = float(last["start"])  # type: ignore[arg-type]
            hidden = sum(max(0.0, min(b, self.now()) - max(a, start) - WAIT_SHOWN) for a, b in self.waits if b > start)
            shown = self.now() - start - hidden
            need = self.narration[str(last["id"])] + BEAT_TAIL
            if shown < need:
                await self.pause(need - shown)
            last["end"] = self.now()
        if beat_id:
            self.beats.append({"id": beat_id, "start": self.now(), "end": None})

    # ---- camera ----
    async def box(self, locator: Locator, card: bool = False) -> Box:
        if card:
            return [float(v) for v in await locator.evaluate(CARD_JS)]
        b = await locator.bounding_box()
        if not b:
            raise RuntimeError(f"no box for {locator}")
        return [b["x"], b["y"], b["width"], b["height"]]

    def focus(self, box: Box | None, pad: float = 24 * Z) -> None:
        if box:
            box = [box[0] - pad, box[1] - pad, box[2] + 2 * pad, box[3] + 2 * pad]
        self.focus_log.append((self.now(), box))

    # ---- actions ----
    async def settle(self, timeout: float = 60, since: float | None = None) -> None:
        # A click starts loading on the next render: check too early and the page still looks settled.
        start = self.now() if since is None else since
        await self.pause(0.6)
        await self.page.wait_for_function(SETTLED_JS, timeout=int(timeout * 1000))
        if self.now() - start > 2.0:
            self.waits.append((start + 0.3, self.now()))
        await self.pause(0.3)

    async def move_to(self, locator: Locator, steps: int = 30) -> None:
        await locator.scroll_into_view_if_needed()
        b = await locator.bounding_box()
        if b:
            await self.page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, steps=steps)

    async def click(self, locator: Locator) -> None:
        await self.move_to(locator)
        await self.pause(0.25)
        await locator.click()

    async def scroll_to(self, y: int, seconds: float = 1.2) -> None:
        start = await self.page.evaluate("scrollY")
        n = 24
        for i in range(1, n + 1):
            k = i / n
            eased = k * k * (3 - 2 * k)
            await self.page.evaluate(f"scrollTo(0, {start + (y - start) * eased})")
            await self.page.wait_for_timeout(int(seconds * 1000 / n))

    async def scroll_into_view(self, locator: Locator, top: int = 120) -> None:
        """Scroll so the element sits `top` CSS px below the top of the window."""
        b = await locator.bounding_box()
        if b:
            await self.scroll_to(int(await self.page.evaluate("scrollY") + b["y"] - top * Z))

    def panel(self) -> Locator:
        return self.page.get_by_role("dialog").last

    async def panel_focus(self) -> None:
        b = await self.box(self.panel())
        self.focus([b[0], 70 * Z, b[2], 620 * Z], pad=8 * Z)

    async def ask(self, question: str, done_text: str) -> str:
        box = self.page.get_by_role("textbox").last
        p = await self.box(self.panel())
        self.focus([p[0], p[1] + p[3] - 420 * Z, p[2], 420 * Z], pad=8 * Z)  # the question box while typing
        await self.click(box)
        await box.press_sequentially(question, delay=25)
        await self.pause(0.4)
        start = self.now()
        await box.press("Enter")
        await self.panel_focus()  # then the conversation, from the top
        try:
            await self.page.get_by_text(done_text, exact=False).last.wait_for(timeout=120000)
        except Exception:
            await self.page.screenshot(path=str(PUBLIC / "fail.png"))
            (PUBLIC / "fail.txt").write_text(await self.panel().inner_text(), encoding="utf-8")
            raise
        self.waits.append((start + 1.2, self.now()))
        await self.pause(0.4)
        return await self.panel().inner_text()

    async def scroll_panel(self, seconds: float = 2.5) -> None:
        b = await self.panel().bounding_box()
        if b:
            await self.page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] * 0.4, steps=15)
            n = 24
            for _ in range(n):
                await self.page.mouse.wheel(0, 50 * Z)
                await self.page.wait_for_timeout(int(seconds * 1000 / n))

    async def model_ready(self) -> None:
        await self.page.wait_for_function(
            "m => [...document.querySelectorAll('select')].some(s => s.value === m)", arg=MODEL, timeout=30000
        )

    async def goto_in_app(self, path: str) -> None:
        await self.page.evaluate("p => { history.pushState(null, '', p); dispatchEvent(new PopStateEvent('popstate')); }", path)


async def warm_up(browser) -> None:  # type: ignore[no-untyped-def]
    ctx = await browser.new_context(viewport={"width": W, "height": H})
    await ctx.add_init_script(INIT)
    page = await ctx.new_page()
    for path in WARM_PATHS:
        await page.goto(BASE + path)
        await page.wait_for_function(SETTLED_JS, timeout=120000)
        await page.wait_for_timeout(800)
    await ctx.close()


async def tour(t: Tour) -> None:
    page = t.page
    tab = lambda name: page.get_by_role("link", name=name, exact=True).first  # noqa: E731

    # Market: the dashboard's most-traded list, then one company.
    await t.beat("market")
    await t.pause(1.2)
    t.focus(await t.box(page.locator("table").first, card=True))
    await t.pause(2.2)
    comi = page.locator('a[href^="/companies/COMI"]').first
    await t.move_to(comi)
    await t.pause(1.4)
    await comi.click()
    t.focus(None)
    await t.settle()

    # Chart: candles over a year, then the patterns panel.
    await t.beat("chart")
    await t.click(tab("Overview"))
    await t.settle()
    canvas = page.locator("canvas").first
    await t.scroll_into_view(page.get_by_role("radio", name="1Y", exact=True).first, top=200)
    t.focus(await t.box(canvas, card=True))
    await t.click(page.get_by_role("radio", name="1Y", exact=True).first)
    await t.pause(0.5)
    await t.click(page.get_by_role("radio", name="Candles", exact=True).first)
    await t.pause(0.6)
    b = await t.box(canvas)
    await page.mouse.move(b[0] + 40 * Z, b[1] + b[3] * 0.5, steps=8)
    await page.mouse.move(b[0] + b[2] - 60 * Z, b[1] + b[3] * 0.5, steps=30)
    await t.click(page.get_by_role("button", name="Patterns", exact=True).first)
    start = t.now()
    await page.get_by_text("Loading Chart patterns", exact=False).first.wait_for(state="hidden", timeout=60000)
    await t.settle(since=start)  # the patterns load counts as a wait too
    chart = await t.box(canvas, card=True)
    t.focus([chart[0], chart[1], chart[2], min(chart[3], 560 * Z)])  # the chart, not the long patterns list
    await t.pause(1.0)

    # Stance: the rule-based stance, its reasons and limits.
    await t.beat("stance")
    t.focus(None)
    await t.scroll_to(0, 0.8)
    await t.click(tab("Price & signals"))
    await t.settle()
    await t.scroll_to(0, 0.3)
    stance_card = await t.box(page.get_by_role("button", name="Explain this").first, card=True)
    t.focus(stance_card)
    await t.pause(2.5)
    limits = await t.box(page.get_by_text("Limitations", exact=True).first)
    t.focus(union(stance_card, [stance_card[0], limits[1], stance_card[2], 110 * Z]))  # the card down to the limits
    await t.move_to(page.get_by_text("Why", exact=True).first)
    await t.pause(1.5)

    # Shariah: our screen beside official EGX33 membership.
    await t.beat("shariah")
    t.focus(None)
    await page.evaluate("document.documentElement.classList.add('demo-blur')")
    await t.click(tab("Shariah"))
    await t.settle()
    ours = await t.box(page.get_by_text("Our screening", exact=True).first, card=True)
    egx33 = await t.box(page.get_by_text("EGX33 Shariah index", exact=True).first, card=True)
    t.focus(union(ours, egx33))
    await t.pause(1.0)

    # Data checks: straight to the Data quality sub-tab (the Financials tab opens on statements, which
    # show vendor amounts). The cursor goes to the Financials tab and the router navigates in-app.
    await t.beat("checks")
    t.focus(None)
    await t.move_to(tab("Financials"))
    await t.pause(0.3)
    await t.goto_in_app("/companies/COMI/financials/quality")
    await page.evaluate("document.documentElement.classList.remove('demo-blur')")
    await t.settle()
    heading = page.get_by_role("heading", name="Cross-checks").first
    await t.scroll_into_view(heading, top=90)
    cross = await t.box(heading, card=True)
    t.focus([cross[0], cross[1], cross[2], min(cross[3], 520 * Z)])
    await t.click(page.get_by_role("button", name="Run checks now").first)
    await t.settle()
    await t.pause(0.4)
    t.focus(None)
    await t.scroll_into_view(page.get_by_text("Price sanity", exact=True).first, top=160)
    sanity = await t.box(page.get_by_text("Price sanity", exact=True).first)
    fresh = await t.box(page.get_by_text("Freshness", exact=True).first)
    t.focus([cross[0], sanity[1] - 16 * Z, cross[2], fresh[1] - sanity[1] + 200 * Z])
    await t.pause(1.0)

    # Assistant (English).
    await t.beat("assistant")
    t.focus(None)
    await t.scroll_to(0, 0.6)
    await t.click(tab("Price & signals"))
    await t.settle()
    await t.click(page.get_by_role("button", name="Ask the assistant").first)
    await t.model_ready()
    q = "How has COMI's share price performed against its sector? Price returns only, please."
    t.log.append(await t.ask(q, "Sources"))
    await t.pause(0.8)
    await t.scroll_panel(2.0)
    await t.pause(0.5)
    t.focus(None)
    await t.click(page.get_by_role("button", name="Close assistant").first)

    # Arabic, right to left, in dark mode; the assistant answers in Arabic.
    await t.beat("arabic")
    dark = page.get_by_role("radio", name="Dark", exact=True).first
    await t.scroll_into_view(dark, top=700)  # the theme and language switches sit at the page's foot
    await t.click(dark)
    await t.pause(0.6)
    await t.click(page.get_by_role("radio", name="عربي", exact=True).first)
    await t.settle()
    await t.scroll_to(0, 0.7)
    await t.pause(0.6)
    await t.click(page.get_by_role("button", name="اسأل المساعد").first)
    await t.model_ready()
    new_chat = page.get_by_role("button", name="محادثة جديدة")
    if await new_chat.count():
        await t.click(new_chat.first)
    t.log.append(await t.ask("هل بيانات COMI في التطبيق صحيحة؟", "المصادر"))
    await t.pause(0.8)
    await t.scroll_panel(2.5)
    await t.pause(0.6)
    await t.beat(None)


async def main() -> None:
    narration = {k: float(v["seconds"]) for k, v in json.loads((PUBLIC / "narration.json").read_text(encoding="utf-8")).items()}
    rec = PUBLIC / "rec"
    rec.mkdir(parents=True, exist_ok=True)
    for old in rec.glob("*.webm"):
        old.unlink()
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        await warm_up(browser)
        ctx = await browser.new_context(
            viewport={"width": W, "height": H}, record_video_dir=str(rec), record_video_size={"width": W, "height": H},
            locale="en-US", color_scheme="light",
        )
        await ctx.add_init_script(INIT)
        page = await ctx.new_page()
        t = Tour(page, narration)
        await page.goto(BASE + "/")
        await page.wait_for_function(SETTLED_JS, timeout=60000)
        await page.mouse.move(W * 0.6, H * 0.55)
        await t.pause(0.5)
        await tour(t)
        await t.pause(0.5)
        timeline = {
            "size": [W, H], "waitShown": WAIT_SHOWN, "beats": t.beats, "waits": t.waits, "focus": t.focus_log,
        }
        (PUBLIC / "timeline.json").write_text(json.dumps(timeline, indent=1), encoding="utf-8")
        (PUBLIC / "answers.txt").write_text("\n\n=====\n\n".join(t.log), encoding="utf-8")
        await ctx.close()
        await browser.close()
    raw = [p for p in rec.glob("*.webm") if p.name != "raw.webm"]
    if raw:
        raw[0].replace(rec / "raw.webm")
    # Playwright's WebM has no seek index; Remotion needs a seekable file (a keyframe every second).
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-y", "-i", "raw.webm", "-c:v", "libx264", "-preset", "fast",
         "-crf", "16", "-g", "25", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "raw.mp4"],
        check=True, cwd=rec,
    )
    joined = "\n".join(t.log)
    # The tour must never show statement amounts (vendor data).
    if re.search(r"revenue|net income|bn EGP|إيرادات|صافي الربح", joined, re.I):
        print("WARNING: an assistant answer mentions statement amounts; re-record", file=sys.stderr)
    if re.search(r"Couldn't verify the figures|تعذّر التحقق من الأرقام", joined):
        print("WARNING: an assistant answer failed the figure check; re-record", file=sys.stderr)
    print("done", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
