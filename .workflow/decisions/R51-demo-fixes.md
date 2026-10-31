# R51 Fixes found by reviewing the demo video

Owner request (2026-10-31): "the video is full of bugs fix them". A frame-by-frame review of
`docs/media/egx-ai-demo.mp4` found these app bugs (recording glitches are fixed in `scripts/demo`):

1. SAIB's name stored as "SociÃ©tÃ©…": the universe fetch decoded a page with no declared charset as Latin-1.
2. Recommendations showed "0 stocks" and stance counts of 0 while the EGX33-filtered list was still loading.
3. Stance reasons and limitations stayed English on the Arabic page (the backend sends finished English sentences).
4. The assistant panel covered the right 420 px of the page, hiding what the user asks about.
5. Assistant answers showed raw backticks and internal codes (`company_performance`, `warn`, `cross_source`).

Found in the re-recorded video:

6. The Arabic answer was blocked as unverified: the figure check read the day of "31 أكتوبر" (the tools'
   ISO `as_of` date, written with a month name) as a figure. Dates with an English or Arabic month name are
   now ignored like numeric dates.
7. Opening the patterns panel narrowed the price chart and pushed the latest months off its right edge; the
   chart now keeps the same dates in view on resize.
8. With the assistant panel beside the page, the company header squeezed four tiles into ~560 px and clipped
   the Shariah tile; the header grid now follows its own width (container query): four across from 720 px,
   2x2 below.

| # | Decision | Owner's choice |
|---|---|---|
| C1 | Translating stance reasons and limitations | **Codes + params**: the backend adds a code and parameters to each reason part and limitation; the frontend writes the sentence from its EN/AR copy. English `text` stays as the fallback. Additive API change. |
| C2 | Assistant panel on wide screens | **Push content aside** at 1280 px and wider; an overlay below that. |
| C3 | Demo video captions | **Strip below the app**: 1280x880 video, captions burned into a dark strip under the 800 px app area. |
