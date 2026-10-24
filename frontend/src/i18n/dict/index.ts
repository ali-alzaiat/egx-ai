import { ADMIN_COPY } from "./admin";
import { COMPANIES_COPY } from "./companies";
import { HUB_COPY } from "./hub";
import { HUB_RESEARCH_COPY } from "./hubResearch";
import { MARKETS_COPY } from "./markets";
import { SHELL_COPY } from "./shell";
import { STANCE_COPY } from "./stance";
import { TRACKING_COPY } from "./tracking";
import type { CopyEntry, Lang } from "./types";

export type { CopyEntry, Lang } from "./types";

/**
 * Single source of truth for all UI copy, EN and AR, merged from per-area
 * modules so each page lane owns one file. Every key MUST carry both
 * languages and keys must be unique across modules (asserted in i18n.test.ts).
 * Arabic is real translated copy and renders with Western digits.
 */
export const SHORT_COPY = {
  ...SHELL_COPY,
  ...STANCE_COPY,
  ...MARKETS_COPY,
  ...COMPANIES_COPY,
  ...HUB_COPY,
  ...HUB_RESEARCH_COPY,
  ...TRACKING_COPY,
  ...ADMIN_COPY,
} as const;

/** The per-area modules, exposed for the uniqueness test. */
export const COPY_MODULES: Record<string, Record<string, CopyEntry>> = {
  shell: SHELL_COPY,
  stance: STANCE_COPY,
  markets: MARKETS_COPY,
  companies: COMPANIES_COPY,
  hub: HUB_COPY,
  hubResearch: HUB_RESEARCH_COPY,
  tracking: TRACKING_COPY,
  admin: ADMIN_COPY,
};

export type CopyKey = keyof typeof SHORT_COPY;

/** Values for `{name}` placeholders inside a copy string. */
export type CopyParams = Readonly<Record<string, string | number>>;

export function t(key: CopyKey, lang: Lang, params?: CopyParams): string {
  const text: string = SHORT_COPY[key][lang];
  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (match, name: string) => {
    const value = params[name];
    return value === undefined ? match : String(value);
  });
}
