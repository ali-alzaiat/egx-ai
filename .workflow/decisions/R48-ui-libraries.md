# R48: UI libraries (owner rulings 2026-10-30)

The owner asked for lightweight-charts for charts and shadcn/ui for UI components, on a new branch based on `security-hardening` (R47 included).

| # | Ruling |
|---|---|
| U1 | **Tailwind v4, mapped to our tokens.** shadcn/ui needs Tailwind; its theme variables point at the existing tokens in `src/styles/tokens.css`, so the look, dark mode and RTL stay. Radix direction follows the UI language. |
| U2 | **Shared components move to shadcn**: Button, Input, Select, segmented filters (ToggleGroup), Tabs, Table, Popover / Tooltip, Badge, Skeleton, Dialog. Page layouts keep their CSS. |
| U3 | **Price chart rebuilt on lightweight-charts, plus candlesticks**: same ranges; a Line / Candles toggle from stored OHLC; the volatility range on real future dates (the separate 1M/3M/6M axis goes away); pattern shapes and confirm levels as overlays; side panels unchanged; zoom and pan. The chart keeps left-to-right time in Arabic. |
