# R48: UI libraries (owner rulings 2026-10-30)

The owner asked for lightweight-charts for charts and shadcn/ui for UI components, on a new branch based on `security-hardening` (R47 included).

| # | Ruling |
|---|---|
| U1 | **Tailwind v4, mapped to our tokens.** shadcn/ui needs Tailwind; its theme variables point at the existing tokens in `src/styles/tokens.css`, so the look, dark mode and RTL stay. Radix direction follows the UI language. |
| U2 | **Shared components move to shadcn**: Button, Input, Select, segmented filters (ToggleGroup), Tabs, Table, Popover / Tooltip, Badge, Skeleton, Dialog. Page layouts keep their CSS. |
| U3 | **Price chart rebuilt on lightweight-charts, plus candlesticks**: same ranges; a Line / Candles toggle from stored OHLC; the volatility range on real future dates (the separate 1M/3M/6M axis goes away); pattern shapes and confirm levels as overlays; side panels unchanged; zoom and pan. The chart keeps left-to-right time in Arabic. |

## Follow-up UX rulings (owner, 2026-10-30)

| # | Ruling |
|---|---|
| U4 | **Forecast pads history**: with Forecast on, the visible history is at least as long as the cone horizon, so short ranges (Week, Month) stay readable. |
| U5 | **Ctrl/Cmd + wheel zooms the chart**; a plain wheel scrolls the page. Drag, pinch and arrow keys still pan and zoom. |
| U6 | **Info (i) is a popover on every screen size** (collision-aware); the phone bottom sheet is retired. |
| U7 | **Native `<select>` stays** (styled); route-link tab strips stay links. Radix Select, Tabs, Tooltip and Dialog are not adopted for now. |
| U8 | **Chart grows with overlays; pattern lines trimmed**: while Patterns or Forecast is drawn the plot is 360px tall (280px on phones), and each pattern line is cut to the price band of the shape's own key points (a fitted boundary no longer runs far past the shape). |
