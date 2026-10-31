"""Record the EGX AI demo tour with Playwright (headless Chromium, 1280x800).

Writes the raw .webm to out/ and a timeline.json of the slow waits (assistant answers) so the
post-processing step can speed them up. Avoids screens that show raw statement amounts.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from playwright.async_api import Page, async_playwright

BASE = "http://localhost:5173"
OUT = Path(__file__).parent / "out"
W, H = 1280, 800

INIT = r"""
(() => {
  if (!sessionStorage.getItem('demo-init')) {
    localStorage.setItem('egx-lang', 'en');
    localStorage.setItem('egx-assistant-model', 'gemini-3.5-flash-lite');
    sessionStorage.setItem('demo-init', '1');
  }
  const ensure = () => {
    if (!document.body) return;
    if (!document.getElementById('demo-cursor')) {
      const c = document.createElement('div');
      c.id = 'demo-cursor';
      c.style.cssText = 'position:fixed;z-index:2147483647;width:18px;height:18px;margin:-9px 0 0 -9px;' +
        'border-radius:50%;background:rgba(255,196,0,.55);border:2px solid #fff;box-shadow:0 0 6px rgba(0,0,0,.5);' +
        'pointer-events:none;left:-40px;top:-40px;transition:transform .12s';
      document.body.appendChild(c);
    }
  };
  document.addEventListener('mousemove', (e) => {
    ensure();
    const c = document.getElementById('demo-cursor');
    c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px';
  }, true);
  document.addEventListener('mousedown', () => { const c = document.getElementById('demo-cursor'); if (c) c.style.transform = 'scale(.6)'; }, true);
  document.addEventListener('mouseup', () => { const c = document.getElementById('demo-cursor'); if (c) c.style.transform = ''; }, true);
  window.__cap = (text) => {
    ensure();
    let el = document.getElementById('demo-caption');
    if (!el) {
      el = document.createElement('div');
      el.id = 'demo-caption';
      el.dir = 'ltr';
      el.style.cssText = 'position:fixed;z-index:2147483646;bottom:28px;' +
        'max-width:780px;padding:12px 22px;border-radius:12px;background:rgba(10,14,24,.88);color:#fff;' +
        'font:500 21px/1.35 system-ui,Segoe UI,sans-serif;text-align:center;box-shadow:0 6px 24px rgba(0,0,0,.35);' +
        'pointer-events:none;transition:opacity .25s';
      document.body.appendChild(el);
    }
    const rtl = document.documentElement.dir === 'rtl';
    el.style.left = rtl ? 'auto' : '36px'; el.style.right = rtl ? '36px' : 'auto';
    el.textContent = text; el.style.opacity = text ? '1' : '0';
  };
})();
"""

CARD = """<!doctype html><html><body style="margin:0;height:100vh;display:flex;align-items:center;
justify-content:center;background:linear-gradient(135deg,#0b0f19,#16233f);color:#fff;
font-family:system-ui,Segoe UI,sans-serif;text-align:center"><div>
<div style="font-size:64px;font-weight:700;letter-spacing:-1px">{title}</div>
<div style="font-size:26px;margin-top:14px;opacity:.9">{sub}</div>
<div style="font-size:18px;margin-top:28px;opacity:.6">{note}</div></div></body></html>"""


class Tour:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.t0 = time.monotonic()
        self.waits: list[tuple[float, float]] = []
        self.log: list[str] = []
        self.marks: dict[str, float] = {}

    def now(self) -> float:
        return time.monotonic() - self.t0

    async def cap(self, text: str) -> None:
        await self.page.evaluate("t => window.__cap && window.__cap(t)", text)

    async def pause(self, s: float) -> None:
        await self.page.wait_for_timeout(int(s * 1000))

    async def move_to(self, locator, steps: int = 25) -> None:
        box = await locator.bounding_box()
        if box:
            await self.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=steps)

    async def click(self, locator) -> None:
        await self.move_to(locator)
        await self.pause(0.3)
        await locator.click()

    async def scroll(self, dy: int, seconds: float = 1.5) -> None:
        n = 20
        for _ in range(n):
            await self.page.mouse.wheel(0, dy / n)
            await self.page.wait_for_timeout(int(seconds * 1000 / n))

    async def goto(self, path: str, ready: str) -> None:
        await self.page.goto(BASE + path)
        await self.page.get_by_text(ready, exact=False).first.wait_for(timeout=30000)
        await self.pause(0.6)

    async def card(self, title: str, sub: str, note: str, seconds: float) -> None:
        await self.page.set_content(CARD.format(title=title, sub=sub, note=note))
        await self.pause(seconds)

    async def ask(self, question: str, done_text: str) -> str:
        box = self.page.get_by_role("textbox").last
        await self.click(box)
        await box.press_sequentially(question, delay=45)
        await self.pause(0.5)
        start = self.now()
        await box.press("Enter")
        await self.page.get_by_text(done_text, exact=False).last.wait_for(timeout=120000)
        self.waits.append((start + 1.5, self.now()))
        await self.pause(0.5)
        panel = self.page.locator("aside, [role=dialog]").last
        return await panel.inner_text()


async def main() -> None:
    OUT.mkdir(exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        ctx = await browser.new_context(
            viewport={"width": W, "height": H}, record_video_dir=str(OUT), record_video_size={"width": W, "height": H},
            locale="en-US", color_scheme="light",
        )
        await ctx.add_init_script(INIT)
        page = await ctx.new_page()
        t = Tour(page)
        await page.mouse.move(W / 2, H / 2)

        # 0. Title
        await t.card("EGX AI", "A research tool for Egyptian Exchange stocks",
                     "Research aid, not investment advice", 4)

        # 1. Market overview
        await t.goto("/", "Momentum score")
        await t.cap("Market overview: latest prices, model stances and Shariah status across EGX")
        await t.pause(3.5)
        await t.scroll(520, 2.5)
        await t.cap("Momentum leaders, ranked across the whole market")
        await t.pause(3)
        await t.scroll(-520, 1.2)

        # 1b. Recommendations
        await t.click(page.get_by_role("link", name="Recommendations", exact=True).first)
        await page.get_by_text("Leans buy", exact=False).first.wait_for()
        await t.cap("Model stances for the 50 most-traded stocks: research calculations, not advice")
        await t.pause(3.5)
        await t.click(page.get_by_text("EGX33 Shariah members only", exact=False).first)
        await t.cap("Filter to official EGX33 Shariah members in one click")
        await t.pause(3.5)
        await t.click(page.get_by_text("EGX33 Shariah members only", exact=False).first)
        await t.pause(1)

        # 2. Company hub, price chart, stance
        card = page.get_by_text("Commercial International Bank", exact=False).first
        await t.move_to(card)
        await t.cap("Open any company from the lists")
        await t.pause(1)
        await t.goto("/companies/COMI", "At a glance")
        await t.cap("Every company has its own hub, starting with prices and an at-a-glance summary")
        await t.pause(2.5)
        canvas = page.locator("canvas").first
        await t.scroll(260, 1.5)
        t.marks["gif_start"] = t.now()
        await t.cap("Price chart: any period, as a line or as candles")
        await t.click(page.get_by_role("radio", name="1Y", exact=True).first)
        await t.pause(1.2)
        await t.click(page.get_by_role("radio", name="Candles", exact=True).first)
        await t.pause(1.5)
        box = await canvas.bounding_box()
        if box:
            y = box["y"] + box["height"] * 0.5
            await page.mouse.move(box["x"] + 40, y, steps=10)
            await page.mouse.move(box["x"] + box["width"] - 60, y, steps=70)
        await t.cap("Chart patterns, shown with how that shape has played out before: history, not a forecast")
        await t.click(page.get_by_role("button", name="Patterns", exact=True).first)
        start = t.now()
        await page.get_by_text("Loading Chart patterns", exact=False).first.wait_for(state="hidden", timeout=60000)
        if t.now() - start > 2.5:
            t.waits.append((start + 1.0, t.now()))
        await t.pause(5)
        t.marks["gif_end"] = t.now()

        await t.click(page.get_by_role("link", name="Price & signals", exact=True).first)
        await page.get_by_text("Reference levels", exact=False).first.wait_for()
        await page.evaluate("window.scrollTo(0,0)")
        await t.cap("Price & signals: a rule-based stance with its confidence, reasons and limits")
        await t.pause(3)
        await t.move_to(page.get_by_text("Why", exact=True).first)
        await t.pause(3)

        # 3. Shariah (top of the tab only: verdicts, no statement ratios)
        await page.evaluate("window.scrollTo(0,0)")
        await t.click(page.get_by_role("link", name="Shariah", exact=True).first)
        await page.get_by_text("EGX33 Shariah index", exact=False).first.wait_for()
        await t.cap("Shariah: our own screen beside official EGX33 membership, never merged")
        await t.pause(5)

        # 4. Data cross-checks
        await t.goto("/companies/COMI/financials/quality", "Cross-checks")
        heading = page.get_by_role("heading", name="Cross-checks").first
        await heading.scroll_into_view_if_needed()
        await t.cap("Cross-checks test our own data: filing backing, a second source, accounting identities")
        await t.pause(3.5)
        await t.click(page.get_by_role("button", name="Run checks now").first)
        await t.pause(1.5)
        await t.cap("…plus price sanity against the EGX daily limit, and freshness")
        await t.scroll(600, 3)
        await t.pause(2)
        await page.evaluate("window.scrollTo(0,0)")

        # 5. Assistant (English)
        await t.goto("/companies/COMI/price", "Reference levels")
        await t.click(page.get_by_role("button", name="Ask the assistant").first)
        await t.cap("The AI assistant answers from the app's own data, with the model you choose")
        await t.pause(2)
        answer_en = await t.ask("How has COMI's share price performed against its sector? Price returns only, please.",
                                "Figures checked against our data")
        t.log.append(answer_en)
        await t.cap("Every figure in the answer is checked against the tools' data")
        await t.pause(3)
        await page.locator("aside, [role=dialog]").last.hover()
        await t.scroll(500, 3)
        await t.cap("News is searched only when the model and your key allow it, and says so when not")
        await t.pause(3.5)

        # 6. Arabic, right to left, dark mode
        await page.evaluate("localStorage.setItem('egx-lang','ar')")
        await page.emulate_media(color_scheme="dark")
        await t.goto("/companies/COMI/price", "COMI")
        await t.cap("Full Arabic with a right-to-left layout, and dark mode")
        await t.pause(4)
        await t.click(page.get_by_role("button", name="اسأل المساعد").first)
        await t.pause(1)
        answer_ar = await t.ask("هل بيانات COMI في التطبيق صحيحة؟", "أرقام روجعت على بياناتنا")
        t.log.append(answer_ar)
        await t.cap("Asked in Arabic, it reads the data cross-checks and answers in Arabic")
        await t.pause(5)

        # 7. End
        await t.card("EGX AI", "github.com/ali-alzaiat/egx-ai",
                     "Deterministic figures · checked AI answers · English and Arabic", 4)

        (OUT / "timeline.json").write_text(json.dumps({"waits": t.waits, "marks": t.marks, "end": t.now()}), encoding="utf-8")
        (OUT / "answers.txt").write_text("\n\n=====\n\n".join(t.log), encoding="utf-8")
        await ctx.close()
        await browser.close()
    print("done", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
