"""Record the EGX AI demo tour with Playwright (headless Chromium, 1280x800).

One page load, then in-app navigation only (no white flashes). A warm-up pass visits every
screen first so nothing is still loading on camera. Captions are not drawn on the page: their
times go to out/timeline.json and post.py burns them into a strip below the app, along with
speeding up the assistant's thinking time. The tour avoids screens that show statement amounts,
which come from vendor files.
"""

import asyncio
import json
import re
import sys
import time
from pathlib import Path

from playwright.async_api import Locator, Page, async_playwright

BASE = "http://localhost:5173"
OUT = Path(__file__).parent / "out"
W, H = 1280, 800
MODEL = "gemini-3.5-flash-lite"

INIT = r"""
(() => {
  if (!sessionStorage.getItem('demo-init')) {
    localStorage.setItem('egx-lang', 'en');
    localStorage.setItem('egx-assistant-model', '%MODEL%');
    sessionStorage.setItem('demo-init', '1');
  }
  const ensure = () => {
    if (!document.body || document.getElementById('demo-cursor')) return;
    const c = document.createElement('div');
    c.id = 'demo-cursor';
    c.style.cssText = 'position:fixed;z-index:2147483647;width:18px;height:18px;margin:-9px 0 0 -9px;' +
      'border-radius:50%;background:rgba(255,196,0,.55);border:2px solid #fff;box-shadow:0 0 6px rgba(0,0,0,.5);' +
      'pointer-events:none;left:-40px;top:-40px;transition:transform .12s';
    document.body.appendChild(c);
  };
  document.addEventListener('mousemove', (e) => {
    ensure();
    const c = document.getElementById('demo-cursor');
    c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px';
  }, true);
  document.addEventListener('mousedown', () => { const c = document.getElementById('demo-cursor'); if (c) c.style.transform = 'scale(.6)'; }, true);
  document.addEventListener('mouseup', () => { const c = document.getElementById('demo-cursor'); if (c) c.style.transform = ''; }, true);
})();
""".replace("%MODEL%", MODEL)

CARD_JS = """([title, sub, note]) => {
  const d = document.createElement('div');
  d.id = 'demo-card';
  d.style.cssText = 'position:fixed;inset:0;z-index:2147483646;display:flex;align-items:center;justify-content:center;' +
    'background:linear-gradient(135deg,#0b0f19,#16233f);color:#fff;font-family:system-ui,Segoe UI,sans-serif;text-align:center';
  d.innerHTML = '<div><div style="font-size:64px;font-weight:700;letter-spacing:-1px"></div>' +
    '<div style="font-size:26px;margin-top:14px;opacity:.9"></div><div style="font-size:18px;margin-top:28px;opacity:.6"></div></div>';
  const parts = d.firstChild.children;
  parts[0].textContent = title; parts[1].textContent = sub; parts[2].textContent = note;
  document.body.appendChild(d);
}"""

# Nothing on screen is still loading: no busy tables, loading lines or skeleton bars.
SETTLED_JS = """() => !document.querySelector('[aria-busy="true"], p.loading, [data-slot="skeleton"]')"""

WARM_PATHS = [
    "/", "/recommendations", "/recommendations?egx33=1", "/companies/COMI", "/companies/COMI/price",
    "/companies/COMI/shariah", "/companies/COMI/financials/quality",
]


class Tour:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.t0 = time.monotonic()
        self.waits: list[tuple[float, float]] = []
        self.caps: list[tuple[float, str]] = []
        self.marks: dict[str, float] = {}
        self.log: list[str] = []

    def now(self) -> float:
        return time.monotonic() - self.t0

    def cap(self, text: str) -> None:
        self.caps.append((self.now(), text))

    async def pause(self, s: float) -> None:
        await self.page.wait_for_timeout(int(s * 1000))

    async def settle(self, timeout: float = 60) -> None:
        # A click starts loading on the next render: check too early and the page still looks settled.
        start = self.now()
        await self.pause(0.6)
        await self.page.wait_for_function(SETTLED_JS, timeout=int(timeout * 1000))
        if self.now() - start > 2.0:
            self.waits.append((start + 0.3, self.now()))
        await self.pause(0.4)

    async def move_to(self, locator: Locator, steps: int = 25) -> None:
        await locator.scroll_into_view_if_needed()
        box = await locator.bounding_box()
        if box:
            await self.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=steps)

    async def click(self, locator: Locator) -> None:
        await self.move_to(locator)
        await self.pause(0.3)
        await locator.click()

    async def scroll(self, dy: int, seconds: float = 1.5) -> None:
        n = 20
        for _ in range(n):
            await self.page.mouse.wheel(0, dy / n)
            await self.page.wait_for_timeout(int(seconds * 1000 / n))

    async def card(self, title: str, sub: str, note: str) -> None:
        await self.page.evaluate(CARD_JS, [title, sub, note])

    async def uncard(self) -> None:
        await self.page.evaluate("() => document.getElementById('demo-card')?.remove()")

    async def ask(self, question: str, done_text: str, sent_cap: str | None = None) -> str:
        box = self.page.get_by_role("textbox").last
        await self.click(box)
        await box.press_sequentially(question, delay=45)
        await self.pause(0.5)
        start = self.now()
        await box.press("Enter")
        if sent_cap:
            self.cap(sent_cap)
        try:
            await self.page.get_by_text(done_text, exact=False).last.wait_for(timeout=120000)
        except Exception:
            await self.page.screenshot(path=str(OUT / "fail.png"))
            (OUT / "fail.txt").write_text(await self.panel().inner_text(), encoding="utf-8")
            raise
        self.waits.append((start + 1.5, self.now()))
        await self.pause(0.5)
        return await self.panel().inner_text()

    def panel(self) -> Locator:
        return self.page.locator("aside, [role=dialog]").last

    async def scroll_panel_to_end(self, seconds: float = 2.5) -> None:
        box = await self.panel().bounding_box()
        if box:
            await self.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] * 0.45, steps=15)
            n = 20
            for _ in range(n):
                await self.page.mouse.wheel(0, 60)
                await self.page.wait_for_timeout(int(seconds * 1000 / n))

    async def model_ready(self) -> None:
        await self.page.wait_for_function(
            "m => [...document.querySelectorAll('select')].some(s => s.value === m)", arg=MODEL, timeout=30000
        )


async def warm_up(browser) -> None:  # type: ignore[no-untyped-def]
    ctx = await browser.new_context(viewport={"width": W, "height": H})
    await ctx.add_init_script(INIT)
    page = await ctx.new_page()
    for path in WARM_PATHS:
        await page.goto(BASE + path)
        await page.wait_for_function(SETTLED_JS, timeout=120000)
        await page.wait_for_timeout(800)
    await ctx.close()


async def main() -> None:
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.webm"):
        old.unlink()
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        await warm_up(browser)
        ctx = await browser.new_context(
            viewport={"width": W, "height": H}, record_video_dir=str(OUT), record_video_size={"width": W, "height": H},
            locale="en-US", color_scheme="light",
        )
        await ctx.add_init_script(INIT)
        page = await ctx.new_page()
        t = Tour(page)

        await page.goto(BASE + "/")
        await page.wait_for_function(SETTLED_JS, timeout=60000)
        await t.card("EGX AI", "A research tool for Egyptian Exchange stocks", "Research aid, not investment advice")
        await page.mouse.move(W - 24, H - 24)  # the cursor stays clear of the title
        await t.pause(0.3)
        t.marks["start"] = t.now()
        await t.pause(4)
        await t.uncard()

        # 1. Market overview
        t.cap("Market overview: latest prices, model stances and Shariah status across EGX")
        await t.pause(4)
        await t.scroll(520, 2.5)
        t.cap("Momentum leaders, ranked across the whole market")
        await t.pause(3)
        await t.scroll(-520, 1.2)

        # 2. Recommendations and the EGX33 filter
        await t.click(page.get_by_role("link", name="Recommendations", exact=True).first)
        await t.settle()
        t.cap("Recommendations: model stances for the 50 most-traded stocks, not advice")
        await t.pause(4)
        await t.click(page.get_by_text("EGX33 Shariah members only", exact=False).first)
        await t.settle()
        t.cap("Filter to official EGX33 Shariah members in one click")
        await t.pause(4)
        await t.click(page.get_by_text("EGX33 Shariah members only", exact=False).first)
        await t.settle()

        # 3. Company hub and chart
        t.cap("Each company has its own hub: prices first, then signals, valuation and Shariah")
        await t.click(page.locator('a[href="/companies/COMI/price"]').first)
        await t.settle()
        await t.click(page.get_by_role("link", name="Overview", exact=True).first)
        await t.settle()
        await t.pause(3)
        await t.scroll(260, 1.5)
        t.marks["gif_start"] = t.now()
        t.cap("Price chart: any period, as a line or as candles")
        await t.click(page.get_by_role("radio", name="1Y", exact=True).first)
        await t.pause(1.2)
        await t.click(page.get_by_role("radio", name="Candles", exact=True).first)
        await t.pause(1.5)
        box = await page.locator("canvas").first.bounding_box()
        if box:
            y = box["y"] + box["height"] * 0.5
            await page.mouse.move(box["x"] + 40, y, steps=10)
            await page.mouse.move(box["x"] + box["width"] - 60, y, steps=70)
        await t.click(page.get_by_role("button", name="Patterns", exact=True).first)
        t.cap("Chart patterns, with how that shape played out before: history, not a forecast")
        await t.settle()
        await page.get_by_text("Loading Chart patterns", exact=False).first.wait_for(state="hidden", timeout=60000)
        await t.scroll(240, 1.2)
        await t.pause(4.5)
        t.marks["gif_end"] = t.now()

        # 4. Stance
        await page.evaluate("window.scrollTo(0,0)")
        t.cap("Price & signals: a rule-based stance with its confidence, reasons and limits")
        await t.click(page.get_by_role("link", name="Price & signals", exact=True).first)
        await t.settle()
        await page.evaluate("window.scrollTo(0,0)")
        await t.pause(2.5)
        await t.move_to(page.get_by_text("Why", exact=True).first)
        await t.pause(3)

        # 5. Shariah (top of the tab only: verdicts, no statement ratios)
        await page.evaluate("window.scrollTo(0,0)")
        await t.click(page.get_by_role("link", name="Shariah", exact=True).first)
        await t.settle()
        t.cap("Shariah: our own screen beside official EGX33 membership, never merged")
        await t.pause(5)

        # 6. Data cross-checks
        # Straight to the Data quality sub-tab: the Financials tab opens on the statements, which show
        # vendor amounts. The cursor goes to the Financials tab and the router navigates in-app.
        t.cap("Cross-checks test our own data: filing backing, a second source, accounting identities")
        await t.move_to(page.get_by_role("link", name="Financials", exact=True).first)
        await t.pause(0.3)
        await page.evaluate(
            "p => { history.pushState(null, '', p); dispatchEvent(new PopStateEvent('popstate')); }",
            "/companies/COMI/financials/quality",
        )
        await t.settle()
        await page.get_by_role("heading", name="Cross-checks").first.scroll_into_view_if_needed()
        await t.pause(3.5)
        await t.click(page.get_by_role("button", name="Run checks now").first)
        await t.settle()
        t.cap("…plus price sanity against the EGX daily limit, and data freshness")
        await t.scroll(600, 3)
        await t.pause(2)
        await page.evaluate("window.scrollTo(0,0)")

        # 7. Assistant (English)
        await t.click(page.get_by_role("link", name="Price & signals", exact=True).first)
        await t.settle()
        t.cap("The AI assistant answers from the app's own data, with the model you choose")
        await t.click(page.get_by_role("button", name="Ask the assistant").first)
        await t.model_ready()
        await t.pause(2.5)
        q = "How has COMI's share price performed against its sector? Price returns only, please."
        t.log.append(await t.ask(q, "Sources", "It calls read-only tools, then checks every figure in its answer"))
        t.cap("Every figure is checked; news is searched only when the model and key allow it")
        await t.pause(3)
        await t.scroll_panel_to_end()
        await t.pause(3)
        await t.click(page.get_by_role("button", name="Close assistant").first)

        # 8. Dark mode and Arabic, from the sidebar switches
        t.cap("Full Arabic with a right-to-left layout, and dark mode")
        await t.click(page.get_by_role("radio", name="Dark", exact=True).first)
        await t.pause(0.8)
        await t.click(page.get_by_role("radio", name="عربي", exact=True).first)
        await t.settle()
        await page.evaluate("window.scrollTo(0,0)")
        await t.pause(4)
        await t.click(page.get_by_role("button", name="اسأل المساعد").first)
        await t.model_ready()
        new_chat = page.get_by_role("button", name="محادثة جديدة")
        if await new_chat.count():
            await t.click(new_chat.first)
        await t.pause(0.8)
        t.cap("Asked in Arabic, it reads the data cross-checks and answers in Arabic")
        t.log.append(await t.ask("هل بيانات COMI في التطبيق صحيحة؟", "المصادر"))
        await t.pause(2.5)
        await t.scroll_panel_to_end(3)
        await t.pause(3)

        # 9. End
        t.cap("")
        await page.mouse.move(W - 24, H - 24, steps=10)
        await t.card("EGX AI", "github.com/ali-alzaiat/egx-ai", "Deterministic figures · checked AI answers · English and Arabic")
        await t.pause(4)
        t.marks["end"] = t.now()
        await t.pause(0.5)

        (OUT / "timeline.json").write_text(
            json.dumps({"waits": t.waits, "caps": t.caps, "marks": t.marks}, ensure_ascii=False), encoding="utf-8"
        )
        (OUT / "answers.txt").write_text("\n\n=====\n\n".join(t.log), encoding="utf-8")
        await ctx.close()
        await browser.close()
    raw = [p for p in OUT.glob("*.webm") if p.name != "raw.webm"]
    if raw:
        raw[0].replace(OUT / "raw.webm")
    # The tour must never show statement amounts (vendor data).
    if re.search(r"revenue|net income|bn EGP|إيرادات|صافي الربح", "\n".join(t.log), re.I):
        print("WARNING: an assistant answer mentions statement amounts; re-record", file=sys.stderr)
    if re.search(r"Couldn't verify the figures|تعذّر التحقق من الأرقام", "\n".join(t.log)):
        print("WARNING: an assistant answer failed the figure check; re-record", file=sys.stderr)
    print("done", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
