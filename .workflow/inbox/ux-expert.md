# Inbox: ux-expert

From: router · 2026-10-24
Task: the user changed the visual direction to **"Friendly retail app"** (rounded cards, larger type, more whitespace; Thndr / Robinhood / Revolut-stocks feel) — see `.workflow/decisions/R45-owner-review-r43-ui.md` U1. Structure stays (sidebar + drawer, 7-tab hub, admin, stance wording, cards on phone / sortable tables on desktop). Only the look changes.

Produce 3 concrete variants of the friendly look. Each: palette (light + dark, WCAG AA for text, gain/loss not the only signal), Latin + Arabic font pair from Google Fonts with real Arabic support (verify the Arabic subset exists), type scale, radius, spacing, shadow/elevation, table-row and card treatment, badge style. Keep it not-AI-slop: no gradients/glow, no emoji, no generic purple. Short research only (look at 2–4 real retail investing apps; cite only what you use).

Deliverables:
1. `.workflow/design/friendly-variants-2026-10.html` — one self-contained static page (inline CSS, Google Fonts link only, no JS frameworks) showing the 3 variants side by side or stacked, each rendering the same samples: company header (ticker, name, price, change, stance badge, Shariah badge), 4 rows of the Recommendations table, a phone-width stock card, in EN and AR (RTL). Use realistic sample values (COMI, ETEL, ABUK, SWDY), labelled as samples.
2. `.workflow/design/ui-friendly-direction.md` — per variant the token values as a drop-in replacement for spec §2.2–2.4 (same token names as `frontend/src/styles/tokens.css`, adding new ones only if needed), plus what changes in §3 components. Mark your recommendation and why.

Do not edit frontend code. End with `ASK USER: which variant?` (options + recommendation in the deliverable). Handback ≤150 words.
