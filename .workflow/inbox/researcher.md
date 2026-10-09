# Inbox: researcher

From: router (user directive) · 2026-10-09
Task: Whole-app UX research. The user dislikes the app's current UX and wants it
enhanced based on how comparable apps do it.

Focus: best-in-class UX for retail-facing stock / investment-research / screener apps.
Study a spread, e.g. Simply Wall St, TradingView, Koyfin, Finviz, Yahoo Finance,
Stock Analysis, Wisesheets, and Shariah-screening apps (Zoya, Musaffa, Islamicly).
Cover:
- Information architecture and navigation (what belongs in the top nav vs a company
  page; how a "screener" is framed).
- Dashboard and company-page layout (hero, key stats, tabs vs scroll, progressive
  disclosure).
- Data-heavy tables/screeners: density, sorting, filtering, column choice, mobile.
- States: empty, loading, error, missing data — what good apps do.
- Colour, typography and chart discipline; dark mode.
- How confidence / data-quality / coverage is communicated honestly.
- Onboarding: how a first-timer finds their first answer.

Every claim cited with a URL. Mark anything you cannot verify as `no data`. Prefer
patterns a small React app can realistically copy.

Deliverable: `.workflow/research/app-wide-ux-patterns.md`
End with exactly one contract string: NEXT: ux-expert, BLOCKED: <question>, or DONE.
