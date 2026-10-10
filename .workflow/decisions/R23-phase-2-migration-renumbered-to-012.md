# R23 — Phase 2 migration renumbered to 012

**From:** Mostafa (tech-lead) · 2026-10-10
**Trigger:** R22 R6 names the Phase 2 migration `011_industry`; live chain is linear 001–011 with head 011 (`011_data_quality.py`, `revision = "011"`, `down_revision = "010"`). Same forced-renumber class as R10.

**Ruling:** the migration is `012_industry.py`, `revision = "012"`, `down_revision = "011"`. All other R22 lines stand. Router carries the 012 number into the staff-backend brief.
