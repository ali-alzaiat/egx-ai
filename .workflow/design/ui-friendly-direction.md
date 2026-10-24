# Friendly retail look: three variants (ux-expert: Salma, 2026-10-24)

Source: owner decision R45 U1 ("Friendly retail app"). This file **replaces spec `ui-redesign-2026-10.md` §2.1 to §2.4 and the visual parts of §3** for whichever variant the owner picks. Structure (sidebar plus drawer, 7-tab hub, admin, stance and Shariah wording in §5, cards on phone and sortable tables on desktop) is unchanged. Nothing here is built until the owner chooses.

Visual proof: `.workflow/design/friendly-variants-2026-10.html` (all three variants, English and Arabic RTL, light and dark, same sample data labelled as samples).

## 0. Decision needed (ASK USER)

| | A Cobalt Cards | B Warm Paper | C Ink and Pills |
|---|---|---|---|
| Look | Cool white cards on pale blue-grey, soft shadow, cobalt accent | Cream canvas, hairline-bordered cards, no shadow, petrol accent | White/black, tinted fills with no borders, pill badges, each table row is its own tile |
| Fonts (Latin + Arabic) | Plus Jakarta Sans + Cairo | Figtree + Noto Kufi Arabic | Manrope + Readex Pro |
| Radius sm / md / lg | 10 / 16 / 24 | 12 / 20 / 28 | 12 / 20 / 28, pill badges |
| Table row (today 32) | 56, divider lines | 64, divider lines | 60 tile + 8 gap |
| Rows visible per 640 px | about 11 | about 10 | about 9 |
| Body / figure size | 16 / 36 | 16 / 34 | 16 / 44 |
| Elevation | soft shadow (hairline in dark) | none | none |
| Closest to | A mainstream fintech app | none of the named apps, calmest | Robinhood |
| Main risk | Least distinctive | Lowest density after C, most padding | Ink accent is quiet: active nav and "Passes our screen" rely on the word, not hue; tile rows need `border-spacing` table CSS |

**Recommendation: A.** It is the closest to a mainstream retail-investing app, keeps the most rows on screen of the three (56 px rows), and its cobalt accent is clearly separate from gain green, loss red and warn amber, so the Shariah and navigation states (which must never use gain or loss colours) stay obvious. It is also the cheapest re-skin: the same table markup, only token values change. Choose B if you want the calmest, least generic look and accept fewer rows per screen. Choose C if you want the Robinhood feel and accept a quieter accent.

ASK USER: which variant (A, B or C)? Any change you want to it (for example row height or radius) is a token edit afterwards.

## 1. Research (short, and what it did and did not support)

I could not inspect Thndr, Robinhood or Revolut screens directly (no authenticated access; search results gave descriptions, not screenshots), so the variants come from design judgement and these two facts:

- Thndr says its users are mostly first-time investors under 30 and uses mobile-first design ([thndr.app/about](https://thndr.app/blogpost/about-us/), [App Store listing](https://apps.apple.com/us/app/thndr-%D8%AB%D8%A7%D9%86%D8%AF%D8%B1/id1494883259)). This supports 16 px body text, plain-word labels and 44 px or larger touch targets in all variants.
- Robinhood's rebrand work is described as black, white and neutrals with a single accent ([Porto Rocha case study](https://www.portorocha.com/robinhood)). Secondary sources claim pill-shaped controls; I treated that as unverified. This is the basis for variant C only.
- Revolut and the exact Thndr colours were not verified and are not cited.

## 2. Fonts (verified 2026-10-24)

The Google Fonts CSS API (`css2?family=...`) returns an `/* arabic */` unicode-range subset for Cairo, Noto Kufi Arabic and Readex Pro, and all three loaded with the weights below in a browser (`document.fonts`). Plus Jakarta Sans, Figtree and Manrope are Latin-only, so Arabic text uses the Arabic partner of the pair (the `html[lang="ar"]` override puts it first).

| Variant | Link for `index.html` (replaces spec §2.1; keep `IBM Plex Mono` only for methodology IDs) |
|---|---|
| A | `https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Cairo:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400&display=swap` |
| B | `https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&family=Noto+Kufi+Arabic:wght@400;500;600&family=IBM+Plex+Mono:wght@400&display=swap` |
| C | `https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&family=Readex+Pro:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400&display=swap` |

Weights used: A 400/500/600 UI and 700 for h1, figures, headings. B 400/500/600 only (headings 600; Noto Kufi has no 700 in the link). C 400/500/600 UI and 700 for headings and figures. This relaxes spec §2.6's "400, 500, 600 only" for A and C. Keep it in `<link>`, never a CSS `@import`.

## 3. Contrast (WCAG 2.x, computed, text pairs AA 4.5:1, control edges 3:1)

Every text pair in every theme passes. Lowest values per variant (light / dark):

| Pair | A | B | C |
|---|---|---|---|
| `--text-3` on `--surface-2` | 5.06 / 5.37 | 5.44 / 5.60 | 5.55 / 4.89 |
| `--text-3` on `--accent-bg` | 5.01 / 5.17 | 5.49 / 4.98 | 5.60 / 4.70 |
| `--gain` on `--gain-bg` | 4.74 / 7.50 | 5.07 / 7.40 | 4.86 / 8.61 |
| `--loss` on `--loss-bg` | 4.85 / 7.06 | 5.07 / 6.75 | 4.86 / 6.51 |
| `--warn` on `--warn-bg` | 5.66 / 8.12 | 5.56 / 7.83 | 5.56 / 8.12 |
| `--accent` on `--accent-bg` | 5.78 / 7.06 | 6.16 / 6.96 | 15.99 / 13.83 |
| `--accent-ink` on `--accent` | 6.78 / 8.96 | 7.19 / 9.36 | 18.85 / 18.18 |
| `--neutral` on `--surface-2` | 5.40 / 7.08 | 5.90 / 6.17 | 5.55 / 6.64 |
| `--border-strong` on `--bg` / `--surface` (≥3) | 3.38 / 3.66 and 4.24 / 3.88 | 3.56 / 3.81 and 3.80 / 3.52 | 3.60 / 3.31 and 4.04 / 3.65 |
| `--text` on `--bg` | 16.5 / 16.5 | 16.2 / 15.9 | 19.7 / 18.2 |

Not relying on colour alone (kept from the spec): the change cell always has a sign (+ or U+2212) and a triangle; the stance badge always has its shape (triangle up, bar, triangle down) and its word; Shariah verdicts are words and never use gain or loss colours. In C, `--surface` against `--bg` is a tint with no border (1.09:1), which is acceptable only because cards are not controls; every input and button uses `--border-strong` (≥3:1) or a filled accent, so the 3:1 rule for controls holds. Chart series tokens and z-layers are unchanged from `tokens.css`.

## 4. New tokens (everything else keeps the name in `tokens.css`)

| New | Why |
|---|---|
| `--radius-lg`, `--radius-pill` | Hero card, bottom sheet, pill badges and avatars |
| `--shadow-card` and `--card-border` | Card elevation: A uses a shadow in light and a hairline in dark; B always a hairline; C neither (tint only). One token pair lets one component serve all three |
| `--badge-radius`, `--badge-h`, `--badge-pad` | Badge shape differs per variant |
| `--card-pad`, `--card-gap` | Card inner padding and the gap between cards (phone list, stat tiles) |
| `--space-16` | Large section spacing |

`--radius-sm` and `--radius-md` keep their names but mean "controls and inputs" and "cards, table frame, popovers, drawer". All legacy aliases at the bottom of `tokens.css` stay until each page migrates.

Arabic: every variant uses the same pattern as today: Arabic font first, `--tracking-heading: 0`, and line heights +4 px over Latin (Cairo, Noto Kufi and Readex Pro all have taller ascenders and marks than their Latin partners). Font sizes are not changed.

## 5. Variant A: Cobalt Cards (recommended)

Drop-in replacement for §2.2 to §2.4. Same names as `tokens.css`, new ones listed in section 4.

```css
/* light + shared (replaces spec 2.2) */
:root {
  color-scheme: light;
  --bg: #f4f6fa; --surface: #ffffff; --surface-2: #eaeef5;
  --border: #dde2ec; --border-strong: #7d8699;
  --text: #0f1729; --text-2: #3d4660; --text-3: #5a6480;
  --accent: #1f4fd1; --accent-bg: #e6edfd; --accent-ink: #ffffff;
  --gain: #0b7a43; --gain-bg: #e3f4ea;
  --loss: #c42b33; --loss-bg: #fdeaec;
  --warn: #8a5300; --warn-bg: #fdf1dc;
  --neutral: #55607a;
  --scrim: rgba(15, 23, 41, 0.4);
  --shadow-pop: 0 8px 28px rgba(15, 23, 41, 0.16);
  --shadow-card: 0 1px 2px rgba(15, 23, 41, 0.06), 0 6px 16px rgba(15, 23, 41, 0.06); --card-border: transparent;
  --focus: var(--accent);
  --font-ui: "Plus Jakarta Sans", "Cairo", system-ui, sans-serif;
  --font-code: "IBM Plex Mono", ui-monospace, monospace; /* methodology versions/IDs only; add to the Google Fonts link */
  --fs-micro: 12px; --lh-micro: 16px;
  --fs-meta: 13px; --lh-meta: 18px;
  --fs-table: 15px; --lh-table: 22px;
  --fs-ui: 16px; --lh-ui: 24px;
  --fs-read: 17px; --lh-read: 26px;
  --fs-h3: 18px; --lh-h3: 26px;
  --fs-h2: 22px; --lh-h2: 30px;
  --fs-h1: 28px; --lh-h1: 36px;
  --fs-figure: 36px; --lh-figure: 40px;
  --tracking-heading: -0.02em;
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px; --space-5: 20px;
  --space-6: 24px; --space-8: 32px; --space-10: 40px; --space-12: 48px; --space-16: 64px;
  --gutter: 32px;
  --radius-sm: 10px; /* controls, inputs */
  --radius-md: 16px; /* cards, table frame, popovers, drawer */
  --radius-lg: 24px; /* hero card, bottom sheet, phone frame */
  --radius-pill: 999px;
  --badge-radius: 8px; --badge-h: 24px; --badge-pad: 0 10px;
  --control-h: 44px; --row-h: 56px; --row-h-compact: 48px;
  --card-pad: 20px; --card-gap: 16px;
  --sidebar-w: 248px; --topbar-h: 56px; --content-max: 1280px;
  --dur: 150ms; --ease: ease-out;
}

/* dark (replaces spec 2.3) */
:root[data-theme="dark"] { /* repeat this block inside @media (prefers-color-scheme: dark) for :root:not([data-theme="light"]), as tokens.css does today */
  color-scheme: dark;
  --bg: #0b0f19; --surface: #131928; --surface-2: #1b2335;
  --border: #27304a; --border-strong: #6b7694;
  --text: #eaeef8; --text-2: #b6bfd6; --text-3: #8c97b3;
  --accent: #8fb0ff; --accent-bg: #172547; --accent-ink: #0b0f19;
  --gain: #4ccb86; --gain-bg: #11291d;
  --loss: #ff8a82; --loss-bg: #331a1c;
  --warn: #e8b05a; --warn-bg: #2b2112;
  --neutral: #a5aec6;
  --scrim: rgba(0, 0, 0, 0.6);
  --shadow-pop: 0 8px 28px rgba(0, 0, 0, 0.55);
  --shadow-card: none; --card-border: var(--border);
}

/* Arabic (replaces spec 2.4): line-heights +4px, sizes unchanged */
html[lang="ar"] {
  --font-ui: "Cairo", "Plus Jakarta Sans", system-ui, sans-serif;
  --lh-micro: 20px;
  --lh-meta: 22px;
  --lh-table: 26px;
  --lh-ui: 28px;
  --lh-read: 30px;
  --lh-h3: 30px;
  --lh-h2: 34px;
  --lh-h1: 40px;
  --lh-figure: 44px;
  --tracking-heading: 0;
}
```

**Fixed table values for A.** Cards on `--surface` over `--bg`, radius 16, `--card-pad` 20. Row dividers 1 px `--border`, no zebra, hover row `--surface-2`. Badge: 8 px radius, 24 px high, 10 px inline padding, 13 px 600. Page gutter 32. Sidebar 248, top bar 56.

## 6. Variant B: Warm Paper

```css
/* light + shared (replaces spec 2.2) */
:root {
  color-scheme: light;
  --bg: #faf7f2; --surface: #ffffff; --surface-2: #f1ece3;
  --border: #e6dfd2; --border-strong: #8a8272;
  --text: #1d1a16; --text-2: #4a443b; --text-3: #655e53;
  --accent: #0b5f78; --accent-bg: #e2f0f4; --accent-ink: #ffffff;
  --gain: #12743f; --gain-bg: #e6f2e8;
  --loss: #b8322a; --loss-bg: #fbe9e5;
  --warn: #8a5300; --warn-bg: #fbefd9;
  --neutral: #5f594e;
  --scrim: rgba(29, 26, 22, 0.4);
  --shadow-pop: 0 8px 24px rgba(29, 26, 22, 0.14);
  --shadow-card: none; --card-border: var(--border);
  --focus: var(--accent);
  --font-ui: "Figtree", "Noto Kufi Arabic", system-ui, sans-serif;
  --font-code: "IBM Plex Mono", ui-monospace, monospace; /* methodology versions/IDs only; add to the Google Fonts link */
  --fs-micro: 12px; --lh-micro: 16px;
  --fs-meta: 13px; --lh-meta: 18px;
  --fs-table: 15px; --lh-table: 22px;
  --fs-ui: 16px; --lh-ui: 24px;
  --fs-read: 17px; --lh-read: 26px;
  --fs-h3: 18px; --lh-h3: 26px;
  --fs-h2: 22px; --lh-h2: 30px;
  --fs-h1: 30px; --lh-h1: 38px;
  --fs-figure: 34px; --lh-figure: 40px;
  --tracking-heading: -0.015em;
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px; --space-5: 20px;
  --space-6: 24px; --space-8: 32px; --space-10: 40px; --space-12: 48px; --space-16: 64px;
  --gutter: 40px;
  --radius-sm: 12px; /* controls, inputs */
  --radius-md: 20px; /* cards, table frame, popovers, drawer */
  --radius-lg: 28px; /* hero card, bottom sheet, phone frame */
  --radius-pill: 999px;
  --badge-radius: 999px; --badge-h: 26px; --badge-pad: 0 12px;
  --control-h: 44px; --row-h: 64px; --row-h-compact: 52px;
  --card-pad: 28px; --card-gap: 24px;
  --sidebar-w: 256px; --topbar-h: 60px; --content-max: 1280px;
  --dur: 150ms; --ease: ease-out;
}

/* dark (replaces spec 2.3) */
:root[data-theme="dark"] { /* repeat this block inside @media (prefers-color-scheme: dark) for :root:not([data-theme="light"]), as tokens.css does today */
  color-scheme: dark;
  --bg: #14120f; --surface: #1d1a16; --surface-2: #27231e;
  --border: #373229; --border-strong: #77705f;
  --text: #f1ece3; --text-2: #c3bcae; --text-3: #a29a8b;
  --accent: #6fc3dc; --accent-bg: #12303b; --accent-ink: #14120f;
  --gain: #55c885; --gain-bg: #14281b;
  --loss: #f28b7e; --loss-bg: #34191a;
  --warn: #e8b05a; --warn-bg: #2e2412;
  --neutral: #aaa293;
  --scrim: rgba(0, 0, 0, 0.6);
  --shadow-pop: 0 8px 24px rgba(0, 0, 0, 0.55);
  --shadow-card: none; --card-border: var(--border);
}

/* Arabic (replaces spec 2.4): line-heights +4px, sizes unchanged */
html[lang="ar"] {
  --font-ui: "Noto Kufi Arabic", "Figtree", system-ui, sans-serif;
  --lh-micro: 20px;
  --lh-meta: 22px;
  --lh-table: 26px;
  --lh-ui: 28px;
  --lh-read: 30px;
  --lh-h3: 30px;
  --lh-h2: 34px;
  --lh-h1: 42px;
  --lh-figure: 44px;
  --tracking-heading: 0;
}
```

**Fixed table values for B.** Cards on `--surface` over a cream `--bg`, 1 px `--border`, no shadow, radius 20, `--card-pad` 28. Row dividers 1 px `--border`. Badge: pill, 26 px high, 12 px inline padding. Page gutter 40. Sidebar 256, top bar 60. Heading weight 600, not 700.

## 7. Variant C: Ink and Pills

```css
/* light + shared (replaces spec 2.2) */
:root {
  color-scheme: light;
  --bg: #ffffff; --surface: #f5f5f6; --surface-2: #ebebed;
  --border: #e3e3e6; --border-strong: #868690;
  --text: #0b0b0d; --text-2: #3b3b42; --text-3: #5c5c66;
  --accent: #111114; --accent-bg: #ececef; --accent-ink: #ffffff;
  --gain: #00793a; --gain-bg: #e1f5e9;
  --loss: #c81f2a; --loss-bg: #fde8ea;
  --warn: #8a5300; --warn-bg: #fbefd9;
  --neutral: #5c5c66;
  --scrim: rgba(11, 11, 13, 0.4);
  --shadow-pop: 0 8px 28px rgba(11, 11, 13, 0.18);
  --shadow-card: none; --card-border: transparent;
  --focus: var(--accent);
  --font-ui: "Manrope", "Readex Pro", system-ui, sans-serif;
  --font-code: "IBM Plex Mono", ui-monospace, monospace; /* methodology versions/IDs only; add to the Google Fonts link */
  --fs-micro: 12px; --lh-micro: 16px;
  --fs-meta: 13px; --lh-meta: 18px;
  --fs-table: 15px; --lh-table: 22px;
  --fs-ui: 16px; --lh-ui: 24px;
  --fs-read: 17px; --lh-read: 26px;
  --fs-h3: 20px; --lh-h3: 28px;
  --fs-h2: 24px; --lh-h2: 32px;
  --fs-h1: 32px; --lh-h1: 40px;
  --fs-figure: 44px; --lh-figure: 48px;
  --tracking-heading: -0.02em;
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px; --space-5: 20px;
  --space-6: 24px; --space-8: 32px; --space-10: 40px; --space-12: 48px; --space-16: 64px;
  --gutter: 32px;
  --radius-sm: 12px; /* controls, inputs */
  --radius-md: 20px; /* cards, table frame, popovers, drawer */
  --radius-lg: 28px; /* hero card, bottom sheet, phone frame */
  --radius-pill: 999px;
  --badge-radius: 999px; --badge-h: 28px; --badge-pad: 0 12px;
  --control-h: 48px; --row-h: 60px; --row-h-compact: 52px;
  --card-pad: 24px; --card-gap: 12px;
  --sidebar-w: 248px; --topbar-h: 56px; --content-max: 1280px;
  --dur: 150ms; --ease: ease-out;
}

/* dark (replaces spec 2.3) */
:root[data-theme="dark"] { /* repeat this block inside @media (prefers-color-scheme: dark) for :root:not([data-theme="light"]), as tokens.css does today */
  color-scheme: dark;
  --bg: #0a0a0b; --surface: #17171a; --surface-2: #232327;
  --border: #2e2e33; --border-strong: #70707a;
  --text: #f5f5f7; --text-2: #bcbcc4; --text-3: #8f8f99;
  --accent: #f5f5f7; --accent-bg: #26262b; --accent-ink: #0a0a0b;
  --gain: #3ddc84; --gain-bg: #0f2a1b;
  --loss: #ff7b73; --loss-bg: #321819;
  --warn: #e8b05a; --warn-bg: #2b2112;
  --neutral: #a8a8b2;
  --scrim: rgba(0, 0, 0, 0.6);
  --shadow-pop: 0 8px 28px rgba(0, 0, 0, 0.6);
  --shadow-card: none; --card-border: transparent;
}

/* Arabic (replaces spec 2.4): line-heights +4px, sizes unchanged */
html[lang="ar"] {
  --font-ui: "Readex Pro", "Manrope", system-ui, sans-serif;
  --lh-micro: 20px;
  --lh-meta: 22px;
  --lh-table: 26px;
  --lh-ui: 28px;
  --lh-read: 30px;
  --lh-h3: 32px;
  --lh-h2: 36px;
  --lh-h1: 44px;
  --lh-figure: 52px;
  --tracking-heading: 0;
}
```

**Fixed table values for C.** The page is `--bg` white (near-black in dark), cards and rows are `--surface` tints with no border and no shadow. Table: `border-collapse: separate; border-spacing: 0 8px`, each row's first and last cell take `--radius-md`, no divider lines, hover row `--surface-2`. Optional 36 px ticker monogram circle in the stock cell (`--surface-2` fill, 12 px 700 text); it is a scanning aid on phone, drop it if you want less decoration. Badge: pill, 28 px high, 12 px padding. Active nav item is `--accent-bg` with `--text`, since the accent is ink. Page gutter 32.

## 8. What changes in §3 components (applies to all three; variant differences in the last column)

| Spec § | Today | Friendly version | Variant notes |
|---|---|---|---|
| §2.6 base type | 14 px body, sentence case, weights 400/500/600 | 16 px body (`--fs-ui`), 15 px table (`--fs-table`), 13 px meta (nothing under 12). Negative letter-spacing on Latin headings only. Weight 700 for h1, figures and hub price in A and C | B stays at 600 |
| Touch and focus | 32 px controls, 40 px on phone | `--control-h` 44 px (48 in C) everywhere, including desktop. 2 px focus ring with 2 px offset, never removed | none |
| §3.1 AppShell | 224 px sidebar, 48 px bar, 4 px radius items | Sidebar and bar widths per variant, nav items `--control-h` high with `--radius-sm`, active item `--accent-bg` + `--accent` text + 600. Drawer: `--radius-lg` on the free corners, `--shadow-pop`, `--scrim` | C active item uses `--text` on `--accent-bg` |
| §3.2 PageHeader | h1 24/32 | h1 per variant (28, 30, 32), 32 px below | none |
| §3.3 Combobox | 32 px | `--control-h`, `--radius-sm`, popover `--radius-md` + `--shadow-pop`, options 44 px high | none |
| §3.4 DataTable | 32 px rows, one-line stock cell, 1 px frame, no shadow, header band `--surface-2` | Rows `--row-h` (56/64/60). Stock cell may stack ticker over name again (rows are tall enough; the one-line rule existed for the 66 px problem). Header has no fill, 13 px `--text-3` 500. Sticky header and first column stay, sorting, `aria-sort` and URL state unchanged. Compact toggle uses `--row-h-compact` (48/52/52). Frame, shadow and dividers per variant | A: card with shadow, divider lines. B: hairline card, divider lines. C: no frame, row tiles with 8 px gaps |
| §3.4 Phone cards | Unboxed rows with 1 px dividers | Each row is a boxed card: `--surface`, `--radius-md`, 16 px padding, `--card-gap` between cards, whole card is the link, min 44 px tap. Same 4 fields (stock + price/change, badges, two label/value pairs). Phone card shows percent change only, sign and triangle kept | A: shadow. B: hairline. C: tint, no border |
| §3.5 StatStrip | No cards, dividers | Stat tiles allowed: `--surface`, `--radius-md`, `--card-pad`, label 13 px `--text-3` over value; 2 columns on phone. Still no hover lift and no icons | tile border/shadow per variant |
| §3.6 Missing | "—" in `--text-3` | Unchanged | none |
| §3.7 Badges | 4 px radius, 20 px, 12 px text, "no pills" | `--badge-h`, `--badge-radius`, `--badge-pad`, 13 px 600. Word always present; stance shape icon grows from 8 to 10 px. Still no uppercase, no emoji, no check marks | A: 8 px radius. B and C: pills |
| §3.8 Notice | 1 px border, 6 px radius | `--radius-md`, `--card-pad`, 20 px icon, one style, no colour stripe | C: tint fill instead of border (warn keeps `--warn-bg`) |
| §3.9 States | One sentence, inside the widget | Same copy and rules, more air: 32 px padding. Buttons are `--control-h`, filled accent for the single primary action | none |
| Hub header (§4.4.1) | Dense header strip | A hero card: ticker 28-32 px, name, price at `--fs-figure`, change with triangle, then stance badge + "Confidence n/100" + Shariah badge, then the as-of line. Nothing new is added; the same facts are larger | C figure 44 px |
| Charts (§4.4.2) | Series tokens | Unchanged. Chart card gets `--card-pad` and `--radius-md` | none |

**Cost of friendliness, plainly:** rows are 56 to 68 px tall versus 32 today, so a screen shows about 9 to 11 rows instead of 20. That is the intended trade; the compact toggle (48 to 52 px) and the sortable header are how a power user recovers density. Phone layout is already cards and is not affected much.

## 9. Not changed

Stance wording (§5.1), Shariah wording and colour rule (§5.2: Shariah never uses gain or loss colours), number formatting rules (§2.6 table, Western digits, U+2212), RTL rules (§6), motion (colour and opacity only, no transforms), routes and hub tabs, FE-1 shell structure. The re-skin lands in `styles/tokens.css`, `styles/ui.css` and `components/ui/*` as R45 says.

ASK USER: which variant (A, B or C)?
