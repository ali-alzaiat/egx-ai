# Inbox: pm

From: router · 2026-10-24
Task R44 (decide, don't build): using `.workflow/research/r43-sector-and-valuation-sources.md` and the open items D-6/D-8/D-9 in `.workflow/design/r43-computed-company-data.md`, decide:
(a) D-9 sector loading: sources in priority order (sector-index pages → name match reviewed), how EGX sectors map to Shariah screening categories (exclusion list: conventional banks, insurance, alcohol, tobacco, gambling, etc.; Islamic banks per existing carve-out), handling of mixed sectors like "Food, Beverages and Tobacco" (company-level override list, never sector-wide fail), what stays UNKNOWN.
(b) D-8 valuation assumptions v1: which sourced values become the `valuation_assumptions` record (risk-free, ERP/CRP, terminal growth anchor), currency consistency (EGP nominal), which models stay INSUFFICIENT for lack of sourced multiples, and the methodology version label.
(c) D-6: DPS = dividends paid ÷ shares outstanding, and interest income alone for purification — accept or reject.
Keep it to one page with acceptance criteria. Write to `.workflow/decisions/R44-sectors-and-valuation-assumptions.md`; handback ≤150 words per `.workflow/AGENT_RULES.md`. End NEXT: staff-backend | BLOCKED | DONE.
